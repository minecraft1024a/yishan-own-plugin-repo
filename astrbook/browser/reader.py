"""浏览 AI 会话模块

负责深度阅读单个帖子，多轮对话决定互动动作
"""

import json
import re
from typing import TYPE_CHECKING

from src.core.prompt import get_prompt_manager
from src.core.config import get_core_config, get_model_config
from src.kernel.llm import LLMRequest, LLMPayload, ROLE, Text, LLMContextManager
from src.kernel.logger import get_logger

if TYPE_CHECKING:
    from src.core.components.base.plugin import BasePlugin
    from .executor import ActionExecutor

logger = get_logger("astrbot.reader", display="浏览AI")


class ReaderSession:
    """浏览 AI 会话

    满上下文多轮对话：
    - 深度阅读帖子内容
    - 翻页浏览评论
    - 决定互动动作（回复、点赞、关注等）
    """

    def __init__(
        self,
        plugin: "BasePlugin",
        service,
        executor: "ActionExecutor",
        thread_detail: dict,
        config,
    ):
        self.plugin = plugin
        self.service = service
        self.executor = executor
        self.thread_detail = thread_detail
        self.config = config

        # 加载人设
        core_config = get_core_config()
        self.personality = core_config.personality

        # 会话状态
        self.reply_count = 0  # 本帖回复次数
        self.current_reply_page = 1  # 当前回复页码
        self.finished = False

        # 上下文管理
        self.context_manager = LLMContextManager(
            max_payloads=config.max_context_payloads
        )
        self.payloads: list[LLMPayload] = []

        # 帖子信息
        self.thread = thread_detail.get("thread", {})
        self.thread_id = self.thread.get("id")

    async def run(self):
        """运行浏览会话"""
        # 1. 初始化会话 - 注入系统提示词和帖子内容
        self._init_session()

        # 2. 多轮对话循环
        max_rounds = 10  # 防止无限循环
        for _ in range(max_rounds):
            if self.finished:
                break

            # 检查回复数限制
            if self.reply_count >= self.config.max_replies_per_session:
                logger.info("已达回复数上限，结束浏览")
                break

            # 获取 AI 决策
            result = await self._get_ai_decision()

            if not result:
                logger.warning("AI 未返回有效决策，结束浏览")
                break

            # 执行动作
            await self._handle_action(result)

    def _init_session(self):
        """初始化会话"""
        manager = get_prompt_manager()

        # 系统提示词
        system_template = manager.get_template("astrbot_browser_reader_system")
        persona_description = (
            f"你是 {self.personality.nickname}，{self.personality.personality_core}\n"
            f"兴趣爱好: {getattr(self.personality, 'interests', '各种话题')}"
        )
        system_prompt = system_template.set(
            "persona_description", persona_description
        ).build()
        logger.info(system_prompt)
        self.payloads.append(LLMPayload(ROLE.SYSTEM, Text(system_prompt)))

        # 帖子内容
        content_prompt = self._build_thread_content_prompt()
        self.payloads.append(LLMPayload(ROLE.USER, Text(content_prompt)))

    def _build_thread_content_prompt(self) -> str:
        """构建帖子内容提示词"""
        manager = get_prompt_manager()
        template = manager.get_template("astrbot_browser_thread_content")

        thread = self.thread
        replies_data = self.thread_detail.get("replies", {})
        author = thread.get("author", {})
        is_mine = thread.get("is_mine", False)

        # 格式化回复列表
        replies_content = self._format_replies(replies_data.get("items", []))

        # 处理分类名称（可能为 None）
        category_display = thread.get("category_name") or thread.get("category", "未知")

        # 构建作者信息，如果是自己的帖子则添加标记
        author_display = str(author.get("nickname", "未知"))
        if is_mine:
            author_display += " [这是你自己发的帖子]"
        # 匹配模板占位符名称
        prompt = (
            template.set("title", str(thread.get("title", "无标题")))
            .set("category", str(category_display))
            .set("author", author_display)
            .set("author_id", str(author.get("id", "")))
            .set("created_at", str(thread.get("created_at", "")[:16].replace("T", " ")))
            .set("view_count", str(thread.get("view_count", 0)))
            .set("reply_count", str(thread.get("reply_count", 0)))
            .set("like_count", str(thread.get("like_count", 0)))
            .set("content", str(thread.get("content", "")))
            .set("replies", str(replies_content))
            .set("displayed_replies", str(len(replies_data.get("items", []))))
            .set("total_replies", str(replies_data.get("total", 0)))
            .build()
        )
        logger.info(prompt)
        return prompt

    def _format_replies(self, replies: list) -> str:
        """格式化回复列表"""
        if not replies:
            return "（暂无回复）"

        lines = []
        for reply in replies:
            floor_num = reply.get("floor_num", "?")
            author = reply.get("author", {}).get("nickname", "未知")
            content = reply.get("content", "")
            like_count = reply.get("like_count", 0)
            reply_id = reply.get("id")
            sub_count = reply.get("sub_reply_count", 0)

            lines.append(
                f"【{floor_num}楼】#{reply_id} {author} (👍{like_count})"
                + (f" [有{sub_count}条楼中楼]" if sub_count > 0 else "")
            )
            lines.append(f"  {content[:200]}")
            lines.append("")

        return "\n".join(lines)

    async def _get_ai_decision(self) -> dict | None:
        """获取 AI 决策"""
        model_config = get_model_config()
        model_set = model_config.get_task(self.config.reader_model)

        # 创建请求
        llm_request = LLMRequest(
            model_set,
            request_name="astrbot_reader",
            context_manager=self.context_manager,
        )

        # 添加所有 payload
        for payload in self.payloads:
            llm_request.add_payload(payload)

        # 发送请求
        response = await llm_request.send(stream=False, auto_append_response=False)
        response_text = await response

        logger.info(f"浏览 AI 响应: {response_text[:200]}...")

        # 添加 AI 响应到上下文
        self.payloads.append(LLMPayload(ROLE.ASSISTANT, Text(response_text)))

        # 解析 JSON
        return self._parse_json(response_text)

    async def _handle_action(self, result: dict):
        """处理 AI 动作"""
        action = result.get("action")

        if action == "READ_MORE":
            await self._handle_read_more(result)

        elif action == "REPLY_THREAD":
            await self._handle_reply_thread(result)

        elif action == "REPLY_FLOOR":
            await self._handle_reply_floor(result)

        elif action == "LIKE":
            await self._handle_like(result)

        elif action == "FOLLOW":
            await self._handle_follow(result)

        elif action == "FINISH_READING":
            self._handle_finish(result)

        elif action == "MULTI_ACTION":
            await self._handle_multi_action(result)

        else:
            logger.warning(f"未知动作类型: {action}")
            self.finished = True

    async def _handle_read_more(self, result: dict):
        """处理翻页阅读"""
        target = result.get("target", "replies")
        page = result.get("page", self.current_reply_page + 1)

        if target == "replies":
            # 获取更多回复
            thread_detail = await self.service.get_thread_detail(
                self.thread_id, page=page
            )

            if thread_detail:
                self.current_reply_page = page
                replies_data = thread_detail.get("replies", {})
                replies_content = self._format_replies(replies_data.get("items", []))

                # 反馈给 AI
                feedback = f"## 回复（第 {page} 页）\n\n{replies_content}"
                self.payloads.append(LLMPayload(ROLE.USER, Text(feedback)))

        elif target == "sub_replies":
            reply_id = result.get("reply_id")
            if reply_id:
                sub_replies = await self.service.get_sub_replies(reply_id, page=page)
                if sub_replies:
                    content = self._format_sub_replies(sub_replies.get("items", []))
                    feedback = f"## 楼中楼（#{reply_id}）\n\n{content}"
                    self.payloads.append(LLMPayload(ROLE.USER, Text(feedback)))

    def _format_sub_replies(self, sub_replies: list) -> str:
        """格式化楼中楼"""
        if not sub_replies:
            return "（暂无楼中楼）"

        lines = []
        for sr in sub_replies:
            author = sr.get("author", {}).get("nickname", "未知")
            content = sr.get("content", "")
            sr_id = sr.get("id")
            reply_to = sr.get("reply_to")

            if reply_to:
                lines.append(
                    f"  ↳ #{sr_id} {author} @{reply_to.get('nickname', '?')}: {content[:100]}"
                )
            else:
                lines.append(f"  ↳ #{sr_id} {author}: {content[:100]}")

        return "\n".join(lines)

    async def _handle_reply_thread(self, result: dict):
        """处理回复帖子"""
        if not self.config.enable_reply:
            self._add_feedback("回复功能已禁用")
            return

        content = result.get("content")
        if not content:
            return

        success, detail = await self.executor.reply_thread(self.thread_id, content)

        if success:
            self.reply_count += 1
            self._add_feedback(f"✅ 回复成功：{content[:50]}...")
        else:
            self._add_feedback(f"❌ 回复失败：{detail}")

    async def _handle_reply_floor(self, result: dict):
        """处理回复楼层"""
        if not self.config.enable_reply:
            self._add_feedback("回复功能已禁用")
            return

        reply_id = result.get("reply_id")
        content = result.get("content")
        reply_to_id = result.get("reply_to_id")

        if not reply_id or not content:
            return

        # 传入 thread_id 以便查找主楼层 ID
        success, detail = await self.executor.reply_floor(
            reply_id, content, reply_to_id, thread_id=self.thread_id
        )

        if success:
            self.reply_count += 1
            self._add_feedback("✅ 楼中楼回复成功")
        else:
            self._add_feedback(f"❌ 楼中楼回复失败：{detail}")

    async def _handle_like(self, result: dict):
        """处理点赞"""
        if not self.config.enable_like:
            self._add_feedback("点赞功能已禁用")
            return

        target_type = result.get("target_type")

        if not target_type:
            return

        # 点赞帖子时自动使用当前帖子ID，不需要AI提供
        if target_type == "thread":
            target_id = self.thread_id
        else:
            # 点赞回复时需要AI提供回复ID
            target_id = result.get("target_id")
            if not target_id:
                self._add_feedback("❌ 点赞回复需要提供 target_id")
                return

        success, detail = await self.executor.like(target_type, target_id)

        if success:
            self._add_feedback(f"✅ 已点赞 {target_type} #{target_id}")
        else:
            self._add_feedback(f"❌ 点赞失败：{detail}")

    async def _handle_follow(self, result: dict):
        """处理关注"""
        if not self.config.enable_follow:
            self._add_feedback("关注功能已禁用")
            return

        user_id = result.get("user_id")
        username = result.get("username", "")

        if not user_id:
            return

        success, detail = await self.executor.follow(user_id)

        if success:
            self._add_feedback(f"✅ 已关注用户 {username}")
        else:
            self._add_feedback(f"❌ 关注失败：{detail}")

    def _handle_finish(self, result: dict):
        """处理完成阅读"""
        summary = result.get("summary", "")
        impression = result.get("impression", "neutral")

        logger.info(f"完成阅读帖子 #{self.thread_id}，印象: {impression}")
        if summary:
            logger.info(f"摘要: {summary}")

        self.finished = True

    async def _handle_multi_action(self, result: dict):
        """处理组合动作"""
        actions = result.get("actions", [])

        for action_item in actions:
            await self._handle_action(action_item)

            if self.finished:
                break

    def _add_feedback(self, message: str):
        """添加反馈消息到上下文"""
        feedback = f"**执行结果：** {message}"
        self.payloads.append(LLMPayload(ROLE.USER, Text(feedback)))

    def _parse_json(self, response: str) -> dict | None:
        """解析 JSON 响应"""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # 尝试提取 JSON 代码块
            json_match = re.search(r"```json\s*\n(.*?)\n```", response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

            # 尝试提取 {} 内容
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass

        logger.warning("无法解析 AI 响应为 JSON")
        return None
