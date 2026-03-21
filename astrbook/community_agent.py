"""AstrBook 社区活动管理 Agent

统一管理论坛的发帖、看帖、互动等社区活动
使用 LLM 多轮对话进行自主决策

Prompt 使用系统模板管理，支持动态内容注入和渲染策略
"""

from typing import TYPE_CHECKING

from src.core.components.base.agent import BaseAgent
from src.core.components.types import ChatType
from src.kernel.llm import LLMUsable, LLMContextManager, LLMRequest, LLMPayload, ROLE, Text
from src.kernel.logger import get_logger
from src.core.config import get_model_config

# Prompt 系统
from src.core.prompt import (
    PromptTemplate,
    get_prompt_manager,
    get_system_reminder_store,
    SystemReminderBucket,
    optional
)

# 直接 import Tool 类，不使用字符串签名
from .tools import (
    FinishTaskTool,
    HistoryManagerTool,
    PostCreatorTool,
    ThreadReaderTool,
    ThreadListerTool,
    ThreadSearcherTool,
    InteractionTool,
)

if TYPE_CHECKING:
    from .plugin import AstrBotPlugin

logger = get_logger("astrbot.agent", display="社区Agent")


class AstrBookCommunityAgent(BaseAgent):
    """社区活动管理 Agent
    
    负责管理 AstrBook 论坛的所有社区活动，包括：
    - 发布新帖子
    - 浏览和阅读帖子
    - 回复、点赞、关注等互动
    - 分析论坛趋势
    
    Agent 通过多轮 LLM 对话自主决策，直到调用 finish_task 工具结束
    """
    
    agent_name = "astrbook_community_manager"
    agent_description = (
        "管理 AstrBook 论坛的社区活动，包括发帖、看帖、回复、点赞等。"
        "Agent 会根据当前配额、论坛状态自主决定执行何种活动。"
    )
    
    chat_type = ChatType.ALL
    
    # ✅ 直接使用类引用，不用字符串签名
    usables: list[type[LLMUsable]] = [
        HistoryManagerTool,
        ThreadListerTool,
        ThreadSearcherTool,
        PostCreatorTool,
        ThreadReaderTool,
        InteractionTool,
        FinishTaskTool,
    ]
    
    # Prompt 模板名称
    PROMPT_TEMPLATE_NAME = "astrbook_agent_system"
    REMINDER_BUCKET = SystemReminderBucket.ACTOR
    
    def __init__(self, stream_id: str, plugin: "AstrBotPlugin"):
        super().__init__(stream_id, plugin)
        self.config = plugin.config.agent  # type: ignore[union-attr]
        self._finished = False
        self._register_prompt_template()
    
    def _register_prompt_template(self) -> None:
        """注册 Agent 系统提示词模板
        
        使用 PromptTemplate 管理系统提示词，支持占位符和渲染策略
        """
        prompt_manager = get_prompt_manager()
        
        # 检查是否已注册
        if prompt_manager.get_template(self.PROMPT_TEMPLATE_NAME):
            return
        
        # 创建模板
        template = PromptTemplate(
            name=self.PROMPT_TEMPLATE_NAME,
            template="""# 你的身份

你是 {bot_nickname}，{bot_identity}
你负责管理 AstrBook 休闲论坛的社区活动，包括发布帖子和浏览回复其他人的内容。

## 工作目标

1. **保持活跃**：定期在论坛发帖和互动，营造活跃氛围
2. **质量优先**：发布有价值的内容，避免灌水
3. **自然互动**：像真实用户一样参与讨论，不要机械化
4. **配额管理**：遵守每日行为配额，避免过度活跃

## 可用工具

你可以调用以下工具来完成任务：

1. **history_manager**: 查询今日配额使用情况和剩余配额
2. **trend_analyzer**: 分析当前论坛的话题趋势和热门内容
3. **thread_lister**: 获取帖子列表（分页），支持分类筛选和排序
4. **thread_searcher**: 根据关键词搜索帖子标题和正文
5. **post_creator**: 生成并发布新帖子（可指定话题和分类）
6. **thread_reader**: 深度阅读单个帖子并决定互动方式
7. **interaction**: 执行回复/点赞/关注等互动动作
8. **finish_task**: 结束本次任务（完成工作后必须调用）

## 决策流程建议

### 第一步：了解当前状态
- 调用 **history_manager** 查看today配额

### 第二步：分析论坛趋势
- 调用 **trend_analyzer** 了解热门话题

### 第三步：选择活动类型

**选项A - 发帖**（如果配额允许）：
1. 根据趋势选择话题
2. 调用 **post_creator** 发布帖子

**选项B - 看帖互动**：
1. 调用 **thread_lister** 获取帖子列表，或用 **thread_searcher** 搜索特定话题
2. 对每个帖子调用 **thread_reader** 阅读
3. 根据阅读结果调用 **interaction** 互动

### 第四步：结束任务
- 完成一轮活动后，调用 **finish_task** 结束

## 行为规范

1. **自然性**：模仿真实用户，避免过于规律
2. **多样性**：发帖主题和互动方式要多样化
3. **节制性**：不要过度发帖或回复
4. **相关性**：回复内容要与帖子主题相关
5. **友好性**：保持礼貌和友好的语气

## 重要提醒

- 每次任务只需完成一个主要活动（发帖 OR 看帖）
- 达到配额上限时必须停止
- 完成工作后必须调用 finish_task
- API 已自动过滤你回复过帖子（has_replied），无需担心重复

现在开始你的工作吧！
""",
            policies={
                "bot.nickname": optional("MoFox"),
                "bot.identity": optional("智能助手"),
            }
        )
        
        # 注册到管理器
        prompt_manager.register_template(template)
        logger.debug(f"已注册 Prompt 模板: {self.PROMPT_TEMPLATE_NAME}")
    
    async def execute(self) -> tuple[bool, str]:
        """Agent 主入口
        
        执行社区活动任务，通过多轮 LLM 对话自主决策
        
        Returns:
            (成功标志, 结果描述)
        """
        try:
            logger.info("🤖 AstrBook Agent 开始执行社区活动任务")
            
            # 创建上下文管理器
            context_manager = LLMContextManager(
                max_payloads=self.config.max_decision_rounds * 2
            )
            payloads: list[LLMPayload] = []
            
            # 构建系统提示词（使用模板）
            system_prompt = await self._build_system_prompt()
            payloads = context_manager.add_payload(payloads, LLMPayload(ROLE.SYSTEM, Text(system_prompt)))
            
            # 更新 SystemReminder 存储当前状态
            await self._update_state_reminder()
            
            # 获取当前状态并注入
            initial_state = get_system_reminder_store().get(self.REMINDER_BUCKET)
            if initial_state:
                payloads = context_manager.add_payload(
                    payloads,
                    LLMPayload(ROLE.USER, Text(f"## 当前状态\n{initial_state}"))
                )
            
            # 决策循环
            for round_num in range(self.config.max_decision_rounds):
                logger.info(f"决策轮次 {round_num + 1}/{self.config.max_decision_rounds}")
                
                # 调用 LLM
                model_config = get_model_config()
                model_set = model_config.get_task(self.config.llm_model)
                
                llm_request = LLMRequest(
                    model_set=model_set,
                    request_name="agent_decision",
                    context_manager=context_manager,
                    payloads=list(payloads),
                )
                
                # 添加工具 schema
                llm_request.add_payload(LLMPayload(ROLE.TOOL, self.get_local_usables()))  # type: ignore[arg-type]
                
                response = await llm_request.send(stream=False)
                await response  # 收集完整响应，填充 response.message 和 response.call_list
                
                logger.debug(f"LLM 响应: {str(response.message)[:300]}...")
                
                # 检查是否有工具调用
                tool_calls = response.call_list or []
                
                if not tool_calls:
                    logger.warning("LLM 未返回工具调用，尝试解析文本")
                    # 添加助手回复到上下文
                    assistant_text = response.message or ""
                    payloads = context_manager.add_payload(
                        payloads,
                        LLMPayload(ROLE.ASSISTANT, Text(assistant_text))
                    )
                    
                    # 提示 LLM 使用工具
                    payloads = context_manager.add_payload(
                        payloads,
                        LLMPayload(ROLE.USER, Text("请调用合适的工具来完成任务。"))
                    )
                    continue
                
                # 执行工具调用
                all_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call.name
                    tool_args = tool_call.args if isinstance(tool_call.args, dict) else {}
                    
                    logger.info(f"调用工具: {tool_name} 参数: {tool_args}")
                    
                    try:
                        success, result = await self.execute_local_usable(
                            usable_name=tool_name,
                            **tool_args
                        )
                        
                        all_results.append({
                            "tool": tool_name,
                            "success": success,
                            "result": result
                        })
                        
                        # 检查是否是 finish_task
                        if tool_name in ["finish_task", "tool-finish_task"] and success:
                            if isinstance(result, dict) and result.get("finished"):
                                self._finished = True
                                reason = result.get("reason", "未知原因")
                                logger.info(f"✅ Agent 任务完成: {reason}")
                                return True, f"任务完成: {reason}"
                        
                    except Exception as e:
                        logger.error(f"工具调用失败 ({tool_name}): {e}", exc_info=True)
                        all_results.append({
                            "tool": tool_name,
                            "success": False,
                            "result": f"工具调用失败: {e}"
                        })
                
                # 将工具结果添加到上下文
                results_text = "\n".join([
                    f"- {r['tool']}: {'成功' if r['success'] else '失败'} - {r['result']}"
                    for r in all_results
                ])
                payloads = context_manager.add_payload(
                    payloads,
                    LLMPayload(ROLE.USER, Text(f"## 工具执行结果\n{results_text}"))
                )
                
                # 如果已完成，退出
                if self._finished:
                    break
            
            # 达到最大轮数
            if not self._finished:
                logger.warning(f"达到最大决策轮数 {self.config.max_decision_rounds}，强制结束")
                return True, f"达到最大决策轮数 {self.config.max_decision_rounds}"
            
            return True, "任务完成"
            
        except Exception as e:
            logger.error(f"Agent 执行失败: {e}", exc_info=True)
            return False, f"Agent 执行失败: {e}"
    
    async def _build_system_prompt(self) -> str:
        """构建系统提示词
        
        使用 PromptTemplate 渲染，支持动态替换 bot 信息
        """
        from src.core.config import get_core_config
        
        # 获取 bot 人格配置
        core_config = get_core_config()
        personality = core_config.personality
        
        # 从管理器获取模板
        prompt_manager = get_prompt_manager()
        template = prompt_manager.get_template(self.PROMPT_TEMPLATE_NAME)
        
        if not template:
            logger.warning(f"模板 {self.PROMPT_TEMPLATE_NAME} 未找到，使用默认提示词")
            return "你是 AstrBook 社区管理 Agent，负责论坛活动。"
        
        # 设置占位符并构建（使用扁平键）
        prompt = await (
            template
            .set("bot_nickname", personality.nickname)
            .set("bot_identity", personality.identity)
            .build()
        )
        
        return prompt
    
    async def _update_state_reminder(self) -> None:
        """更新 SystemReminder 中的当前状态
        
        将配额、趋势等动态信息存储到 SystemReminderStore
        供后续 LLM 请求读取
        """
        try:
            from .state_manager import get_state_manager
            
            store = get_system_reminder_store()
            
            # 获取配额摘要（使用单例）
            state_manager = get_state_manager()
            quota_summary = await state_manager.get_quota_summary()
            store.set(
                bucket=self.REMINDER_BUCKET,
                name="quota_status",
                content=quota_summary
            )
            
            logger.debug("已更新 SystemReminder 状态")
            
        except Exception as e:
            logger.error(f"更新状态提醒失败: {e}")