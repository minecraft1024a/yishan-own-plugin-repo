"""日程生成器

使用 LLM 生成每日日程。
"""

import asyncio
import json
from typing import TYPE_CHECKING, Any, Optional

from src.kernel.llm import LLMPayload, LLMRequest, ROLE, Text
from src.kernel.logger import get_logger
from src.core.config import get_core_config
from src.core.prompt import get_prompt_manager, optional
from src.app.plugin_system.api.llm_api import get_model_set_by_task

from ..database import get_schedule_database
from ..utils.time_utils import get_weekday_name

if TYPE_CHECKING:
    from plugins.schedule_system.plugin import ScheduleSystemPlugin

logger = get_logger("schedule_system.schedule_generator", display="日程生成器")


# 日程生成提示词模板
SCHEDULE_GENERATION_PROMPT = """你是一个专业的日程规划助手。

# 关于你
你的名字是 {nickname}。
{persona_section}

# 你的任务
请为以下日期生成一份合理的24小时日程安排。

**日期信息**:
- 日期: {date}
- 星期: {weekday}

{monthly_plans_section}

**生成要求**:
1. 必须覆盖完整的24小时（00:00-24:00）
2. 时间段连续，无空隙或重叠
3. 考虑合理的作息时间
4. 工作日和休息日的安排应有所区别
5. 结合月度计划，合理安排相关活动

{custom_guidelines_section}

**输出格式** (严格的 JSON 数组):
[
  {{"time_range": "07:00-08:00", "activity": "晨练", "priority": 3}},
  {{"time_range": "08:00-09:00", "activity": "早餐", "priority": 4}}
]

请直接返回 JSON 数组，不要添加任何解释文字。priority 为 1-5 的整数。
"""


class ScheduleGenerator:
    """日程生成器

    使用 LLM 生成合理的每日日程安排。
    """

    def __init__(self,plugin : "ScheduleSystemPlugin"):
        """初始化生成器

        Args:
            plugin: plugin 实例
        """
        self.config = plugin.config
        self._register_prompt_template()

    def _register_prompt_template(self) -> None:
        """注册 prompt 模板到全局管理器"""
        # 获取 bot 人设配置
        core_config = get_core_config()
        personality = core_config.personality

        # 注册模板
        get_prompt_manager().get_or_create(
            name="schedule_system_generation_prompt",
            template=SCHEDULE_GENERATION_PROMPT,
            policies={
                "nickname": optional(personality.nickname),
                "persona_section": self._build_persona_policy(personality),
                "monthly_plans_section": optional(""),  # 运行时动态设置
                "custom_guidelines_section": optional(""),  # 运行时动态设置
                "date": optional(""),  # 运行时动态设置
                "weekday": optional(""),  # 运行时动态设置
            },
        )
        logger.debug("日程生成 prompt 模板已注册")

    def _build_persona_policy(self, personality: Any) -> Any:
        """构建人设策略

        Args:
            personality: 人设配置对象

        Returns:
            渲染策略
        """
        parts = []

        if personality.personality_core:
            parts.append(f"核心人格：{personality.personality_core}")

        if personality.personality_side:
            parts.append(f"性格侧面：{personality.personality_side}")

        if personality.identity:
            parts.append(f"身份特征：{personality.identity}")

        persona_text = "\n".join(parts) if parts else ""
        return optional(persona_text)

    async def generate(self, date: str) -> bool:
        """生成指定日期的日程

        Args:
            date: 日期字符串 (YYYY-MM-DD)

        Returns:
            是否成功
        """
        max_retries = self.config.schedule.max_retries
        retry_delay = self.config.schedule.retry_delay

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(
                    f"开始生成日程: date={date}, attempt={attempt}/{max_retries}"
                )

                # 调用 LLM 生成
                schedule_data = await self._generate_with_llm(date)

                if schedule_data:
                    # 保存到数据库
                    await self._save_schedule(date, schedule_data, "llm")
                    logger.info(f"日程生成成功: date={date}")
                    # 格式化并显示日程
                    self._display_schedule(date, schedule_data)
                    return True
                else:
                    logger.warning(f"LLM 生成失败: date={date}, attempt={attempt}")

            except Exception as e:
                logger.error(
                    f"日程生成失败: date={date}, attempt={attempt}, error={e}",
                    exc_info=True,
                )

            # 重试延迟（指数退避）
            if attempt < max_retries:
                delay = retry_delay * (2 ** (attempt - 1))
                logger.info(f"等待 {delay} 秒后重试...")
                await asyncio.sleep(delay)

        # 所有重试均失败，等待下次触发
        logger.warning(f"日程生成失败（已重试 {max_retries} 次），将等待下次自动生成: date={date}")
        return False

    async def _generate_with_llm(self, date: str) -> Optional[list[dict[str, Any]]]:
        """使用 LLM 生成日程

        Args:
            date: 日期字符串

        Returns:
            日程项列表，失败返回 None
        """
        try:
            # 获取模型配置
            model_set = get_model_set_by_task(
                self.config.schedule.generation_model
            )

            # 构建提示词
            prompt = await self._build_prompt(date)

            # 构建系统提示（包含 bot 人设）
            core_config = get_core_config()
            personality = core_config.personality

            system_prompt_parts = ["你是一个专业的日程规划助手。"]

            if personality.nickname:
                system_prompt_parts.append(f"你的名字是 {personality.nickname}。")

            if personality.personality_core:
                system_prompt_parts.append(f"{personality.personality_core}")

            system_prompt = "\n".join(system_prompt_parts)

            # 创建请求
            request = LLMRequest(
                model_set=model_set, request_name="schedule_generation"
            )
            request.add_payload(
                LLMPayload(ROLE.SYSTEM, Text(system_prompt))
            )
            request.add_payload(LLMPayload(ROLE.USER, Text(prompt)))

            # 发送请求
            response = await request.send(stream=False)
            await response  # 等待完成

            result_text = response.message

            # 解析响应
            schedule_data = self._parse_llm_response(result_text)
            return schedule_data

        except Exception as e:
            logger.error(f"LLM 生成失败: {e}", exc_info=True)
            return None

    async def _build_prompt(self, date: str) -> str:
        """构建生成提示词

        Args:
            date: 日期字符串

        Returns:
            提示词文本
        """
        weekday = get_weekday_name(date, "zh")

        # 获取月度计划（如果启用）
        monthly_plans_text = ""
        if self.config.plan.enabled:
            from ..utils.time_utils import parse_date

            month = parse_date(date).strftime("%Y-%m")
            # 通过服务管理器获取 plan_service
            try:
                from src.core.managers import get_service_manager
                plan_service = get_service_manager().get_service("schedule_system:service:plan")
                if plan_service:
                    plans = await plan_service.get_active_plans(month)
                    if plans:
                        plans_list = "\n".join(
                            [f"{i+1}. {p['plan_text']}" for i, p in enumerate(plans)]
                        )
                        monthly_plans_text = f"**本月的目标计划**（请在日程中适当体现）:\n{plans_list}"
            except Exception as e:
                logger.warning(f"获取月度计划失败: {e}")

        # 自定义指南
        custom_guidelines_text = ""
        if self.config.schedule.custom_guidelines:
            custom_guidelines_text = f"**用户自定义要求**:\n{self.config.schedule.custom_guidelines}"

        # 获取并渲染模板
        template = get_prompt_manager().get_template("schedule_system_generation_prompt")

        # 设置动态值
        prompt = await (
            template.set("date", date)
            .set("weekday", weekday)
            .set("monthly_plans_section", monthly_plans_text)
            .set("custom_guidelines_section", custom_guidelines_text)
            .build()
        )

        return prompt.strip()

    def _parse_llm_response(
        self, response_text: str
    ) -> Optional[list[dict[str, Any]]]:
        """解析 LLM 响应

        Args:
            response_text: LLM 返回的文本

        Returns:
            解析后的日程项列表，失败返回 None
        """
        try:
            # 清理响应（移除 markdown 代码块标记）
            response_text = response_text.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])

            # 解析 JSON
            schedule_data = json.loads(response_text)

            if not isinstance(schedule_data, list):
                logger.error("响应格式错误: 不是数组")
                return None

            # 验证每个项
            validated_data = []
            for item in schedule_data:
                if not isinstance(item, dict):
                    continue

                if "time_range" not in item or "activity" not in item:
                    continue

                validated_item = {
                    "time_range": item["time_range"],
                    "activity": item["activity"],
                    "priority": item.get("priority", 3),
                    "tags": item.get("tags", []),
                }
                validated_data.append(validated_item)

            if not validated_data:
                logger.error("没有有效的日程项")
                return None

            logger.debug(f"解析到 {len(validated_data)} 个日程项")
            return validated_data

        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            return None
        except Exception as e:
            logger.error(f"响应解析失败: {e}", exc_info=True)
            return None

    async def _save_schedule(
        self, date: str, schedule_data: list[dict[str, Any]], generated_by: str
    ) -> bool:
        """保存日程到数据库

        Args:
            date: 日期
            schedule_data: 日程项列表
            generated_by: 生成方式 (llm/template/fallback)

        Returns:
            是否成功
        """
        try:
            # 创建日程表
            schedule_record = {
                "date": date,
                "version": 1,
                "is_active": True,
                "generated_by": generated_by,
            }
            db = get_schedule_database()
            schedule = await db.create_schedule(schedule_record)

            # 创建日程项
            for item_data in schedule_data:
                item_record = {
                    "schedule_id": schedule.id,
                    "time_range": item_data["time_range"],
                    "activity": item_data["activity"],
                    "priority": item_data.get("priority", 3),
                    "tags": item_data.get("tags", []),
                    "is_completed": False,
                    "is_auto_generated": True,
                }
                await db.create_schedule_item(item_record)

            logger.info(f"日程保存成功: date={date}, items={len(schedule_data)}")

            # 更新月度计划使用次数（如果引用了计划）
            if self.config.plan.enabled:
                await self._update_plan_usage(date)

            return True

        except Exception as e:
            logger.error(f"保存日程失败: {e}", exc_info=True)
            return False

    async def _update_plan_usage(self, date: str) -> None:
        """更新月度计划使用次数

        Args:
            date: 使用日期
        """
        try:
            from ..utils.time_utils import parse_date

            month = parse_date(date).strftime("%Y-%m")

            # 通过服务管理器获取 plan_service
            from src.core.managers import get_service_manager
            plan_service = get_service_manager().get_service("schedule_system:service:plan")
            if not plan_service:
                return

            plans = await plan_service.get_active_plans(month)

            # 这里简化处理：假设所有活跃计划都被引用了
            # 实际应该检查日程内容是否真的包含计划相关活动
            for plan in plans:
                await plan_service.manager.increment_usage(plan["id"], date)

        except Exception as e:
            logger.warning(f"更新计划使用次数失败: {e}")

    def _display_schedule(self, date: str, schedule_data: list[dict[str, Any]]) -> None:
        """格式化并显示日程

        Args:
            date: 日期字符串 (YYYY-MM-DD)
            schedule_data: 日程项列表
        """
        weekday = get_weekday_name(date, "zh")
        priority_labels = {1: "★", 2: "★★", 3: "★★★", 4: "★★★★", 5: "★★★★★"}

        lines = [
            f"\n{'=' * 40}",
            f"  📅 {date}（{weekday}）日程安排",
            f"{'=' * 40}",
        ]

        for item in schedule_data:
            time_range = item.get("time_range", "")
            activity = item.get("activity", "")
            priority = item.get("priority", 3)
            stars = priority_labels.get(priority, "★★★")
            tags = item.get("tags", [])
            tag_str = f"  [{', '.join(tags)}]" if tags else ""
            lines.append(f"  {time_range:<14} {activity}{tag_str}  {stars}")

        lines.append(f"{'=' * 40}")
        lines.append(f"  共 {len(schedule_data)} 个时间段")
        lines.append(f"{'=' * 40}\n")

        logger.info("\n".join(lines))
