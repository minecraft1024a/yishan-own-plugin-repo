"""日程表系统插件

AI 驱动的智能日程管理系统。
"""

from typing import Optional

from src.core.components.base.plugin import BasePlugin
from src.core.components.loader import register_plugin
from src.core.components.base.config import BaseConfig
from src.kernel.logger import get_logger

from .config import ScheduleConfig
from .database import get_schedule_database
from .managers import initialize_schedule_manager, initialize_plan_manager
from .services.schedule_service import ScheduleService
from .services.plan_service import PlanService
from .event_handlers.schedule_init_handler import ScheduleInitHandler
from .tools.add_plan_tool import AddPlanTool
from .tools.update_schedule_item_tool import UpdateScheduleItemTool
from .tools.get_current_activity_tool import GetCurrentActivityTool
from .tools.get_today_schedule_tool import GetTodayScheduleTool
from .tools.get_monthly_plans_tool import GetMonthlyPlansTool

logger = get_logger("schedule_system", display="日程系统")

@register_plugin
class ScheduleSystemPlugin(BasePlugin):
    """日程表系统插件

    提供完整的日程表和月度计划管理能力。

    功能：
    - AI 自动生成每日日程
    - 月度计划管理
    - 用户偏好学习
    - 完整的 CRUD 接口
    """

    plugin_name: str = "schedule_system"
    plugin_description: str = "AI 驱动的日程表与月度计划管理系统"
    plugin_version: str = "2.0.0"

    configs: list[type[BaseConfig]] = [ScheduleConfig]
    dependent_components: list[str] = []  # 可选依赖其他插件

    def __init__(self, config: Optional[ScheduleConfig] = None):
        super().__init__(config)
        self.config: ScheduleConfig = config or ScheduleConfig()

        # 初始化组件（延迟到 on_plugin_loaded）
        self._schedule_service: Optional[ScheduleService] = None
        self._plan_service: Optional[PlanService] = None
        self._init_handler: Optional[ScheduleInitHandler] = None

    def get_components(self) -> list[type]:
        """返回插件包含的所有组件

        Returns:
            组件类列表
        """
        components = [
            ScheduleService,
            PlanService,
            ScheduleInitHandler,
            UpdateScheduleItemTool,  # 更新日程项工具
            GetCurrentActivityTool,  # 获取当前活动工具
            GetTodayScheduleTool,  # 获取今日日程工具
        ]
        if self.config.plan.enabled:
            components.extend([AddPlanTool,GetMonthlyPlansTool])
        return components

    async def on_plugin_loaded(self) -> None:
        """插件加载时初始化

        执行：
        1. 初始化数据库
        2. 创建服务实例
        3. 创建事件处理器实例
        """
        logger.info(f"日程系统插件加载中: version={self.plugin_version}")

        try:
            # 1. 初始化数据库
            db = get_schedule_database()
            await db.initialize()
            logger.info("数据库初始化成功")

            # 2. 初始化管理器单例
            initialize_schedule_manager(self, db)
            initialize_plan_manager(self, db)
            self._schedule_service = ScheduleService(self)
            self._plan_service = PlanService(self) if self.config.plan.enabled else None
            self._init_handler = ScheduleInitHandler(self)
            logger.info("管理器单例初始化成功")

            logger.info("日程系统插件加载成功")

        except Exception as e:
            logger.error(f"日程系统插件加载失败: {e}", exc_info=True)
            raise

    async def on_plugin_unloaded(self) -> None:
        """插件卸载时清理资源

        执行：
        1. 清理定时任务
        2. 关闭数据库连接
        3. 清理服务实例
        """
        logger.info("日程系统插件卸载中")

        try:
            # 清理定时任务
            if self._init_handler:
                await self._init_handler.cleanup()

            # 关闭数据库连接
            await get_schedule_database().close()

            # 清理服务实例
            self._schedule_service = None
            self._plan_service = None
            self._init_handler = None

            logger.info("日程系统插件卸载完成")

        except Exception as e:
            logger.error(f"日程系统插件卸载失败: {e}", exc_info=True)

    # ==================== 属性访问器 ====================

    @property
    def schedule_service(self) -> Optional[ScheduleService]:
        """获取日程服务实例"""
        return self._schedule_service

    @property
    def plan_service(self) -> Optional[PlanService]:
        """获取计划服务实例"""
        return self._plan_service
