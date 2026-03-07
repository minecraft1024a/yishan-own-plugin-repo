"""调度 AI 模块

负责分析帖子列表，选择要浏览的帖子
支持多轮对话，在内部处理翻页、切换分类等动作
"""

import json
import re
from typing import TYPE_CHECKING
from dataclasses import dataclass, field

from src.core.prompt import get_prompt_manager
from src.core.config import get_core_config, get_model_config
from src.kernel.llm import LLMRequest, LLMPayload, ROLE, Text
from src.kernel.logger import get_logger

if TYPE_CHECKING:
    from src.core.components.base.plugin import BasePlugin

logger = get_logger("astrbot.dispatcher", display="调度AI")


@dataclass
class DispatcherResult:
    """调度结果"""

    selected_threads: list[dict] = field(default_factory=list)  # 选中的帖子
    current_category: str = ""  # 最终分类
    finished_reason: str = ""  # 结束原因


class DispatcherAI:
    """调度 AI

    带上下文的多轮对话 AI：
    - 分析帖子列表
    - 评估兴趣度
    - 选择要浏览的帖子
    - 自主决定翻页、切换分类
    """

    def __init__(self, plugin: "BasePlugin"):
        self.plugin = plugin
        self.config = plugin.config.browser
        self._service = None

        # 加载人设
        core_config = get_core_config()
        self.personality = core_config.personality

        # 分类映射
        self.category_names = {
            "chat": "闲聊",
            "tech": "技术",
            "help": "求助",
            "share": "分享",
            "deals": "优惠",
            "intro": "自我介绍",
            "acg": "ACG",
            "misc": "其他",
        }

    @property
    def service(self):
        """延迟获取 API 服务"""
        if self._service is None:
            from src.core.managers import get_service_manager

            service_manager = get_service_manager()
            service_sig = f"{self.plugin.plugin_name}:service:astrbot_api"
            self._service = service_manager.get_service(service_sig)
            if not self._service:
                raise RuntimeError(f"无法获取 AstrBot API 服务: {service_sig}")
        return self._service

    async def run_session(
        self,
        initial_category: str,
        browsed_threads: set[int],
    ) -> DispatcherResult:
        """执行完整的调度会话

        Args:
            initial_category: 初始分类
            browsed_threads: 已浏览的帖子 ID 集合

        Returns:
            DispatcherResult 包含选中的帖子列表
        """
        result = DispatcherResult(current_category=initial_category)

        # 配置
        max_threads = self.config.max_threads_per_session
        max_rounds = getattr(self.config, "max_dispatcher_rounds", 10)

        # 上下文管理
        payloads: list[LLMPayload] = []

        # 添加系统提示词
        system_prompt = self._build_system_prompt()
        payloads.append(LLMPayload(ROLE.SYSTEM, Text(system_prompt)))

        # 会话状态
        current_category = initial_category
        current_page = 1

        # 调度循环
        for round_num in range(max_rounds):
            logger.debug(
                f"调度循环第 {round_num + 1} 轮，分类: {current_category}，页码: {current_page}"
            )

            # 1. 获取帖子列表
            thread_list = await self.service.get_threads(
                category=current_category,
                page=current_page,
                per_page=20,
                sort="latest_reply",
                format="json",
            )

            if not thread_list or not thread_list.get("items"):
                logger.info(
                    f"帖子列表为空（分类: {current_category}，页码: {current_page}）"
                )
                # 告诉 AI 列表为空
                user_msg = f"当前分类 {self.category_names.get(current_category, current_category)} 第 {current_page} 页没有帖子了。"
                payloads.append(LLMPayload(ROLE.USER, Text(user_msg)))
            else:
                # 2. 构建用户消息（帖子列表）
                user_msg = self._build_thread_list_message(
                    thread_list=thread_list,
                    browsed_threads=browsed_threads,
                    current_category=current_category,
                    current_page=current_page,
                    selected_count=len(result.selected_threads),
                    max_threads=max_threads,
                )
                payloads.append(LLMPayload(ROLE.USER, Text(user_msg)))

            # 3. 调用 LLM
            model_config = get_model_config()
            model_set = model_config.get_task(self.config.dispatcher_model)
            llm_request = LLMRequest(model_set, request_name="astrbot_dispatcher")
            for p in payloads:
                llm_request.add_payload(p)
            print(len(llm_request.payloads))
            response = await llm_request.send(stream=False)
            response_text = await response

            logger.debug(f"调度 AI 响应: {response_text[:300]}...")

            # 添加助手回复到上下文
            payloads.append(LLMPayload(ROLE.ASSISTANT, Text(response_text)))

            # 4. 解析响应
            ai_result = self._parse_json(response_text)
            if not ai_result:
                logger.warning("调度 AI 未返回有效 JSON")
                result.finished_reason = "AI 响应解析失败"
                break

            logger.info(f"调度 AI 决策: {ai_result}")

            # 5. 处理动作（支持多动作）
            actions = ai_result.get("actions", [ai_result])  # 兼容单动作和多动作

            should_break = False
            for action_data in actions:
                action = action_data.get("action")

                if action == "SELECT_THREADS":
                    new_selected = action_data.get("selected_threads", [])
                    # 按兴趣度排序
                    new_selected.sort(
                        key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(
                            x.get("interest_level", "low"), 2
                        )
                    )
                    result.selected_threads.extend(new_selected)
                    logger.info(
                        f"选中 {len(new_selected)} 篇，累计 {len(result.selected_threads)} 篇"
                    )

                    # 检查是否超过上限
                    if len(result.selected_threads) >= max_threads:
                        logger.info(f"已达到帖子上限 {max_threads}，强制结束调度")
                        result.finished_reason = f"已达到帖子上限 {max_threads}"
                        should_break = True
                        break

                elif action == "NEXT_PAGE":
                    current_page += 1
                    reason = action_data.get("reason", "")
                    logger.info(f"翻到下一页: {current_page}，原因: {reason}")

                elif action == "CHANGE_CATEGORY":
                    target = action_data.get("category")
                    if target and target in self.category_names:
                        current_category = target
                        current_page = 1
                        result.current_category = target
                        logger.info(f"切换分类到: {target}")
                    else:
                        logger.warning(f"无效的分类: {target}")

                elif action == "SKIP_ALL":
                    reason = action_data.get("reason", "未知原因")
                    logger.info(f"跳过当前页所有帖子: {reason}")
                    # 不 break，让 AI 继续决定下一步

                elif action == "FINISH":
                    reason = action_data.get("reason", "未知原因")
                    logger.info(f"AI 主动结束调度: {reason}")
                    result.finished_reason = reason
                    should_break = True
                    break

                else:
                    logger.warning(f"未知的调度动作: {action}")

            if should_break:
                break

        # 限制数量
        result.selected_threads = result.selected_threads[:max_threads]

        if not result.finished_reason:
            result.finished_reason = f"达到最大轮数 {max_rounds}"

        logger.info(f"调度会话结束，选中 {len(result.selected_threads)} 篇帖子")
        return result

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        # 构建人设描述
        persona_description = (
            f"你是 {self.personality.nickname}，{self.personality.personality_core}\n"
            f"兴趣爱好: {getattr(self.personality, 'interests', '各种话题')}"
        )

        # 优先分类
        preferred = self.config.preferred_categories
        preferred_text = (
            ", ".join(f"{k}({self.category_names.get(k, k)})" for k in preferred)
            if preferred
            else "无特别偏好"
        )

        manager = get_prompt_manager()
        template = manager.get_template("astrbot_browser_dispatcher_system")

        return (
            template.set("persona_description", persona_description)
            .set("preferred_categories", preferred_text)
            .set("max_threads", self.config.max_threads_per_session)
            .build()
        )

    def _build_thread_list_message(
        self,
        thread_list: dict,
        browsed_threads: set[int],
        current_category: str,
        current_page: int,
        selected_count: int,
        max_threads: int,
    ) -> str:
        """构建帖子列表用户消息"""
        # 格式化帖子列表
        items = thread_list.get("items", [])
        thread_lines = []
        filtered_count = 0  # 统计被过滤的帖子数

        for item in items:
            thread_id = item.get("id")
            has_replied = item.get("has_replied", False)

            # 过滤掉已经评论过的帖子
            if has_replied:
                filtered_count += 1
                logger.debug(
                    f"过滤已评论帖子: #{thread_id} {item.get('title', '无标题')}"
                )
                continue

            title = item.get("title", "无标题")
            author = item.get("author", {}).get("nickname", "未知")
            reply_count = item.get("reply_count", 0)
            like_count = item.get("like_count", 0)
            created_at = item.get("created_at", "")[:10]

            browsed_mark = " [已浏览]" if thread_id in browsed_threads else ""

            thread_lines.append(
                f"- #{thread_id} 《{title}》{browsed_mark}\n"
                f"  作者: {author} | 回复: {reply_count} | 点赞: {like_count} | 时间: {created_at}"
            )

        if filtered_count > 0:
            logger.info(f"已过滤 {filtered_count} 个已评论过的帖子")

        thread_list_text = "\n".join(thread_lines) if thread_lines else "（无帖子）"

        category_name = self.category_names.get(current_category, current_category)
        remaining = max_threads - selected_count

        return (
            f"## 当前位置\n"
            f"分类: {category_name} ({current_category}) | 第 {current_page} 页\n"
            f"已选: {selected_count}/{max_threads} 篇 | 还可选: {remaining} 篇\n\n"
            f"## 帖子列表\n{thread_list_text}\n\n"
            f"请选择你感兴趣的帖子，或执行其他动作。"
        )

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

        logger.warning(f"无法解析调度 AI 响应为 JSON: {response[:100]}...")
        return None
