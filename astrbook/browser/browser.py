"""ThreadBrowser 主类

负责协调调度 AI 和浏览 AI 的工作流程
"""

import asyncio
from typing import TYPE_CHECKING

from src.kernel.concurrency import get_task_manager
from src.kernel.logger import get_logger

from .dispatcher import DispatcherAI
from .reader import ReaderSession
from .executor import ActionExecutor

if TYPE_CHECKING:
    from src.core.components.base.plugin import BasePlugin

logger = get_logger("astrbot.browser", display="帖子浏览器")


class ThreadBrowser:
    """帖子浏览器

    使用双 AI 协作架构：
    - Dispatcher AI: 轻量级，分析帖子列表，选择要浏览的帖子
    - Reader AI: 满上下文，深度阅读帖子，多轮对话决定互动
    """

    def __init__(self, plugin: "BasePlugin"):
        self.plugin = plugin
        self.config = plugin.config.browser
        self._task_info = None
        self._running = False

        # 运行时状态
        self.browsed_threads: set[int] = set()  # 已浏览的帖子 ID
        self.current_category: str = ""  # 当前浏览分类
        self.session_replies: int = 0  # 当前会话回复次数

        # 延迟初始化的组件
        self._service = None
        self._dispatcher = None
        self._executor = None

        logger.info("ThreadBrowser 初始化完成")

    def _ensure_components(self):
        """确保组件已初始化（延迟加载）"""
        if self._service is None:
            from src.core.managers import get_service_manager

            service_manager = get_service_manager()
            service_sig = f"{self.plugin.plugin_name}:service:astrbot_api"
            self._service = service_manager.get_service(service_sig)

            if not self._service:
                raise RuntimeError(f"无法获取 AstrBot API 服务: {service_sig}")

        if self._dispatcher is None:
            self._dispatcher = DispatcherAI(self.plugin)

        if self._executor is None:
            self._executor = ActionExecutor(self.plugin)

        logger.debug("组件延迟初始化完成")

    @property
    def service(self):
        self._ensure_components()
        return self._service

    @property
    def dispatcher(self):
        self._ensure_components()
        return self._dispatcher

    @property
    def executor(self):
        self._ensure_components()
        return self._executor

    async def start(self):
        """启动帖子浏览任务"""
        if not self.config.enabled:
            logger.info("帖子浏览功能未启用")
            return

        self._running = True

        # 设置初始分类
        if self.config.preferred_categories:
            self.current_category = self.config.preferred_categories[0]
        else:
            self.current_category = "chat"

        # 创建定时任务
        tm = get_task_manager()
        self._task_info = tm.create_task(
            self._browse_loop(),
            name="astrbot_thread_browser",
            daemon=True,
        )

        logger.info(f"帖子浏览任务已启动，间隔 {self.config.interval_minutes} 分钟")

    async def stop(self):
        """停止帖子浏览任务"""
        self._running = False

        if self._task_info:
            tm = get_task_manager()
            try:
                tm.cancel_task(self._task_info.task_id)
            except Exception:
                pass
            self._task_info = None

        logger.info("帖子浏览任务已停止")

    async def _browse_loop(self):
        """浏览主循环"""
        interval_seconds = self.config.interval_minutes * 60
        await asyncio.sleep(interval_seconds)

        while self._running:
            try:
                await self._do_browse_session()
            except Exception as e:
                logger.error(f"浏览会话出错: {e}", exc_info=True)

            # 等待下次执行

    async def _do_browse_session(self):
        """执行一次浏览会话"""
        logger.info(f"开始浏览会话，当前分类: {self.current_category}")

        # 重置会话状态
        self.session_replies = 0

        # 调度 AI 执行完整会话
        dispatcher_result = await self.dispatcher.run_session(
            initial_category=self.current_category,
            browsed_threads=self.browsed_threads,
        )

        # 更新当前分类
        if dispatcher_result.current_category:
            self.current_category = dispatcher_result.current_category

        # 浏览选中的帖子
        selected_threads = dispatcher_result.selected_threads

        if selected_threads:
            logger.info(f"开始浏览 {len(selected_threads)} 篇帖子")

            for item in selected_threads:
                thread_id = item.get("thread_id")
                if not thread_id:
                    continue

                # 浏览该帖子
                await self._browse_thread(thread_id)

                # 记录已浏览
                self.browsed_threads.add(thread_id)

                # 帖子间间隔
                await asyncio.sleep(self.config.browsing_interval)
        else:
            logger.info("本次会话未选中任何帖子")

        logger.info(f"浏览会话结束，原因: {dispatcher_result.finished_reason}")

    async def _browse_thread(self, thread_id: int):
        """浏览单个帖子"""
        logger.info(f"开始浏览帖子 #{thread_id}")

        try:
            # 获取帖子详情
            thread_detail = await self.service.get_thread_detail(thread_id)

            if not thread_detail:
                logger.warning(f"无法获取帖子详情: #{thread_id}")
                return

            # 创建浏览 AI 会话
            reader = ReaderSession(
                plugin=self.plugin,
                service=self.service,
                executor=self.executor,
                thread_detail=thread_detail,
                config=self.config,
            )

            # 执行多轮对话
            await reader.run()

            # 更新会话回复计数
            self.session_replies += reader.reply_count

            logger.info(f"完成浏览帖子 #{thread_id}")

        except Exception as e:
            logger.error(f"浏览帖子 #{thread_id} 出错: {e}", exc_info=True)

    def clear_browsed_history(self):
        """清空已浏览记录"""
        self.browsed_threads.clear()
        logger.info("已清空浏览历史")
