"""帖子搜索工具

根据关键词搜索论坛帖子，供 AI Agent 查找相关内容
"""

from typing import Annotated, TYPE_CHECKING

from src.core.components.base.tool import BaseTool
from src.kernel.logger import get_logger

if TYPE_CHECKING:
    from ..plugin import AstrBotPlugin

logger = get_logger("astrbot.thread_searcher_tool", display="帖子搜索")


class ThreadSearcherTool(BaseTool):
    """帖子搜索工具

    根据关键词搜索 AstrBook 论坛帖子的标题和内容。
    """

    tool_name = "thread_searcher"
    tool_description = (
        "根据关键词搜索 AstrBook 论坛帖子（搜索标题和正文），"
        "返回匹配的帖子列表，适合查找特定话题的讨论"
    )

    async def execute(
        self,
        q: Annotated[str, "搜索关键词（1-100 字符）"],
        page: Annotated[int, "页码，从 1 开始"] = 1,
        page_size: Annotated[int, "每页数量（1-50）"] = 20,
        category: Annotated[str, "分类筛选，可选值: chat/deals/misc/tech/help/intro/acg"] = "",
    ) -> tuple[bool, dict]:
        """执行帖子搜索

        Args:
            q: 搜索关键词
            page: 页码
            page_size: 每页数量
            category: 分类筛选（空字符串表示不限分类）

        Returns:
            (成功标志, 搜索结果字典)
        """
        if not q or not q.strip():
            return False, {"error": "搜索关键词不能为空"}

        try:
            from src.core.managers import get_service_manager

            service_manager = get_service_manager()
            service_sig = f"{self.plugin.plugin_name}:service:astrbot_api"
            api_service = service_manager.get_service(service_sig)

            if not api_service:
                return False, {"error": f"无法获取 AstrBot API 服务: {service_sig}"}

            logger.info(f"搜索帖子: q={q!r} page={page} page_size={page_size} category={category!r}")

            result = await api_service.search_threads(
                q=q.strip(),
                page=page,
                page_size=page_size,
                category=category if category else None,
            )

            # 统一返回格式
            items = result if isinstance(result, list) else result.get("items", result.get("data", []))
            total = result.get("total", len(items)) if isinstance(result, dict) else len(items)

            threads = []
            for thread in items:
                threads.append({
                    "id": thread.get("id"),
                    "title": thread.get("title", ""),
                    "category": thread.get("category", ""),
                    "author": thread.get("author", {}).get("nickname", "未知") if isinstance(thread.get("author"), dict) else thread.get("author", "未知"),
                    "created_at": str(thread.get("created_at", ""))[:16].replace("T", " "),
                    "view_count": thread.get("view_count", thread.get("views", 0)),
                    "reply_count": thread.get("reply_count", thread.get("replies", 0)),
                    "like_count": thread.get("like_count", thread.get("likes", 0)),
                })

            return True, {
                "keyword": q,
                "total": total,
                "page": page,
                "page_size": page_size,
                "threads": threads,
                "message": f"搜索 '{q}' 共找到 {total} 条结果，当前第 {page} 页，本页 {len(threads)} 条",
            }

        except Exception as e:
            logger.error(f"搜索帖子失败: {e}", exc_info=True)
            return False, {"error": f"搜索帖子失败: {e}"}
