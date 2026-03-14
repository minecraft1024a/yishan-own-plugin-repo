"""AstrBot Chatter 组件"""

import json
import re
from typing import TYPE_CHECKING, AsyncGenerator

from src.core.components.base import BaseChatter
from src.core.components.base.chatter import ChatterResult, Failure, Stop, Success, Wait
from src.core.components.types import ChatType
from src.core.prompt import get_prompt_manager

if TYPE_CHECKING:
    from src.core.components.base.plugin import BasePlugin
    from src.core.models.message import Message

from src.kernel.logger import get_logger

logger = get_logger("astrbot_chatter")


class AstrBotChatter(BaseChatter):
    """AstrBot 论坛聊天器"""

    chatter_name = "astrbot_chatter"
    chatter_description = "AstrBot 论坛智能回复聊天器"
    associated_platforms = ["astrbot"]
    chat_type = ChatType.GROUP
    dependencies = ["astrbot:service:astrbot_api"]

    def __init__(self, stream_id: str, plugin: "BasePlugin"):
        super().__init__(stream_id, plugin)

        # 获取 Service
        from src.core.managers import get_service_manager

        service_manager = get_service_manager()
        service_sig = f"{plugin.plugin_name}:service:astrbot_api"
        self.service = service_manager.get_service(service_sig)

        if not self.service:
            raise RuntimeError(f"无法获取 AstrBot API 服务: {service_sig}")

        logger.info("成功获取 AstrBot API 服务")

        # 加载人设配置
        from src.core.config import get_core_config

        config = get_core_config()
        self.personality = config.personality

        # 初始化提示词模板
        self._init_prompts()

    async def execute(self) -> AsyncGenerator[ChatterResult, None]:
        """执行聊天器主逻辑"""
        # 获取未读消息(通知)
        unread_text, unread_messages = await self.fetch_unreads()

        if not unread_messages:
            yield Wait(time=None)
            return

        # 处理每条通知
        for idx, message in enumerate(unread_messages, 1):
            try:
                yield Wait(time=0)

                notif_type = message.extra.get("type")
                logger.debug(f"通知类型: {notif_type},message.extra:{message}")

                if notif_type in ["reply", "sub_reply"]:
                    logger.debug(
                        f"开始处理回复通知: thread_id={message.extra.get('thread_id')}, reply_id={message.extra.get('reply_id')}"
                    )
                    await self._handle_reply(message)
                    logger.info("回复通知处理完成")
                else:
                    logger.warning(f"跳过不支持的通知类型: {notif_type}")

                yield Success(message=f"已处理通知: {message.message_id}")

            except Exception as e:
                logger.error(f"处理通知失败: {e}", exc_info=True)
                yield Failure(error=str(e), exception=e)

        yield Stop(time=10)

    # ===============================================================================

    def _init_prompts(self):
        """初始化提示词模板"""
        manager = get_prompt_manager()

        manager.get_or_create(
            name="astrbot_reply",
            template="""# 你的身份
你叫 {bot_nickname}，{bot_identity}。

## 人格特征
{bot_personality}

## 表达风格
{bot_reply_style}

---

# 当前情境
你在 AstrBot 论坛上活跃，有人在帖子《{thread_title}》中回复了你。

## 帖子信息
- 标题: {thread_title}
- 分类: {category_name}
- 作者: {thread_author} {ownership_hint}

**帖子主楼内容：**
{thread_content}

---

## 讨论历史（供参考，了解讨论脉络）

{discussion_context}

---

## 📬 最新通知（触发本次回复的消息）

**来自用户：{from_user}**

{notification_content}

---

# 你的任务
1. **理解讨论脉络**：阅读帖子主题和讨论历史，了解话题背景
2. **分析最新消息**：重点理解最新通知中对方的意图和观点
3. **判断是否回复**：考虑消息是否与你相关、是否有实质内容、是否需要你的回应
4. **生成回复内容**：如果决定回复，以符合你人设的方式生成有价值的内容
5. **决定其他动作**：是否需要点赞、@提及等

# 输出要求
必须严格按照以下 JSON 格式输出：

```json
{{
  "should_reply": true,
  "reply_content": "你的回复内容（50-300字，如果不回复可为空）",
  "actions": {{
    "like": true,
    "mention": false
  }}
}}
```

注意：
- **should_reply**: true 表示要回复，false 表示不回复
- 不回复的情况：内容无关、纯灌水、简单表情、已充分讨论等
- 回复内容应在 50-300 字之间（不回复时可为空字符串）
- 保持符合你人设的语气和风格
- 只输出 JSON，不要有其他文字
""",
        )

    async def _handle_reply(self, message: "Message"):
        """处理回复通知"""
        from src.kernel.llm import LLMRequest, LLMPayload, ROLE, Text
        from src.core.config import get_model_config

        thread_id = message.extra.get("thread_id")
        reply_id = message.extra.get("reply_id")
        notif_type = message.extra.get("type")
        logger.info(
            f"开始处理,reply_id：{reply_id}，thread_id：{thread_id}，通知类型：{notif_type}"
        )

        if not thread_id or not reply_id:
            return

        # 1. 获取帖子详情
        thread_detail = await self.service.get_thread_detail(thread_id)

        # 2. 确定主楼层 ID
        main_floor_id = reply_id
        if notif_type == "sub_reply":
            # sub_reply 类型：reply_id 是楼中楼的 ID，需要找到所属的主楼层 ID
            main_floor_id = self._find_main_floor_id(thread_detail, reply_id)
            if not main_floor_id:
                logger.warning(f"无法找到楼中楼 {reply_id} 所属的主楼层 ID")
                return
            logger.info(f"楼中楼 {reply_id} 所属主楼层 ID: {main_floor_id}")

        # 3. 获取楼中楼列表
        sub_replies = await self.service.get_sub_replies(main_floor_id)

        # 4. 构建提示词（reply类型说明是回复bot自己的帖子）
        is_own_thread = notif_type == "reply"
        prompt = await self._build_reply_prompt(
            thread_detail, sub_replies, message, is_own_thread
        )

        # 4. 生成回复
        # 获取模型配置
        model_config = get_model_config()
        model_set = model_config.get_task(self.plugin.config.chatter.llm_model)

        # 创建 LLM 请求
        llm_request = LLMRequest(model_set, request_name="astrbot_reply")
        llm_request.add_payload(LLMPayload(ROLE.USER, Text(prompt)))

        # 发送请求
        response = await llm_request.send(stream=False)
        response_text = await response

        # 5. 解析并执行动作
        await self._execute_actions(response_text, message, main_floor_id)

    def _find_main_floor_id(self, thread_detail: dict, sub_reply_id: int) -> int | None:
        """从帖子详情中查找楼中楼所属的主楼层 ID

        Args:
            thread_detail: 帖子详情数据
            sub_reply_id: 楼中楼的 ID

        Returns:
            主楼层的 ID，如果找不到则返回 None
        """
        for reply in thread_detail.get("replies", {}).get("items", []):
            # 检查这个主楼层的楼中楼列表
            for sub_reply in reply.get("sub_replies", []):
                if sub_reply.get("id") == sub_reply_id:
                    return reply.get("id")

        return None

    async def _build_reply_prompt(
        self,
        thread_detail: dict,
        sub_replies: dict,
        message: "Message",
        is_own_thread: bool = False,
    ) -> str:
        """构建回复提示词"""
        manager = get_prompt_manager()
        template = manager.get_template("astrbot_reply")

        thread = thread_detail["thread"]

        # 获取当前触发通知的回复ID，避免在讨论历史中重复
        current_reply_id = message.extra.get("reply_id")

        # 格式化讨论上下文（更清晰的层级展示）
        discussion_lines = []
        for idx, reply in enumerate(thread_detail["replies"]["items"][:5], 1):
            floor_num = reply["floor_num"]
            author = reply["author"]["nickname"]
            content = reply["content"][:400]

            # 主楼层
            discussion_lines.append(f"【{floor_num}楼 - {author}】")
            discussion_lines.append(content)

            # 楼中楼回复（排除当前触发通知的消息）
            if reply.get("sub_replies"):
                for sub_idx, sub in enumerate(reply["sub_replies"][:5], 1):
                    # 跳过触发本次通知的回复
                    if str(sub.get("id")) == str(current_reply_id):
                        continue

                    sub_author = sub["author"]["nickname"]
                    sub_content = sub["content"][:400]
                    discussion_lines.append(f"\n    → {sub_author} 回复:")
                    discussion_lines.append(f"    {sub_content}")

            # 楼层分隔
            discussion_lines.append("")

        discussion_context = "\n".join(discussion_lines)

        # 构建提示词（加入人设信息）
        thread_author_info = "你自己" if is_own_thread else thread["author"]["nickname"]
        ownership_hint = "（这是你发的帖子）" if is_own_thread else ""

        template_builder = (
            template.set("bot_nickname", self.personality.nickname)
            .set("bot_identity", self.personality.identity)
            .set("bot_personality", self.personality.personality_core)
            .set("bot_reply_style", self.personality.reply_style)
            .set("thread_title", thread["title"])
            .set("category_name", thread["category_name"])
            .set("thread_author", thread_author_info)
            .set("ownership_hint", ownership_hint)
            .set("thread_content", thread["content"][:500])
            .set("discussion_context", discussion_context)
            .set(
                "from_user",
                message.extra.get("from_user", {}).get("nickname", "未知用户"),
            )
            .set(
                "notification_content", message.processed_plain_text or "（无文本内容）"
            )
        )
        prompt = await template_builder.build()
        logger.info(prompt)
        return prompt

    async def _execute_actions(
        self, llm_response: str, message: "Message", main_floor_id: int
    ):
        """执行动作

        Args:
            llm_response: LLM 的响应文本
            message: 触发通知的消息
            main_floor_id: 主楼层 ID（用于发送楼中楼回复）
        """
        reply_id = message.extra.get("reply_id")

        # 解析 JSON
        actions = self._parse_json_response(llm_response)
        logger.info(llm_response)
        if not actions:
            return

        # 检查是否决定回复
        should_reply = actions.get("should_reply", True)
        if not should_reply:
            logger.info(f"AI决定不回复此消息: {message.message_id}")
            # 即使不回复，也可以执行点赞等动作
            if actions.get("actions", {}).get("like"):
                await self.service.like_reply(reply_id)
            return

        # 发送回复
        if actions.get("reply_content"):
            content = actions["reply_content"]

            # 获取用户名并添加 @
            if actions.get("actions", {}).get("mention", False):
                username = message.extra.get("from_user", {}).get("nickname")
                if username:
                    content = f"@{username} {content}"

            # 使用楼中楼 ID 发送回复
            await self.service.send_sub_reply(reply_id=main_floor_id, content=content)
            logger.info(f"已回复消息: {message.message_id}")

        # 点赞
        if actions.get("actions", {}).get("like"):
            await self.service.like_reply(reply_id)

    def _parse_json_response(self, response: str) -> dict | None:
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

        return None
