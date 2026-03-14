"""帖子列表工具

获取论坛帖子列表（分页），支持分类筛选和多种排序方式
"""

from typing import Annotated, TYPE_CHECKING

from src.core.components.base.tool import BaseTool
from src.kernel.logger import get_logger

if TYPE_CHECKING:
    from ..plugin import AstrBotPlugin

logger = get_logger("astrbot.thread_lister_tool", display="帖子列表")


class ThreadListerTool(BaseTool):
    """帖子列表工具

    分页获取 AstrBook 论坛帖子列表，支持分类筛选和多种排序方式。
    """

    tool_name = "thread_lister"
    tool_description = (
        "获取 AstrBook 论坛帖子列表（分页）。"
        "支持按分类筛选（chat/deals/misc/tech/help/intro/acg）和"
        "按最新回复/最新发布/最多回复排序"
    )

    async def execute(
        self,
        page: Annotated[int, "页码，从 1 开始"] = 1,
        page_size: Annotated[int, "每页数量（1-100）"] = 20,
        category: Annotated[str, "分类筛选，可选值: chat/deals/misc/tech/help/intro/acg，空字符串表示全部"] = "",
        sort: Annotated[str, "排序方式: latest_reply(最新回复)/newest(最新发布)/most_replies(最多回复)"] = "latest_reply",
    ) -> tuple[bool, dict]:
        """执行帖子列表获取

        Args:
            page: 页码
            page_size: 每页数量
            category: 分类筛选
            sort: 排序方式

        Returns:
            (成功标志, 帖子列表结果字典)
        """
        valid_sorts = {"latest_reply", "newest", "most_replies"}
        if sort not in valid_sorts:
            sort = "latest_reply"

        try:
            from src.core.managers import get_service_manager

            service_manager = get_service_manager()
            service_sig = f"{self.plugin.plugin_name}:service:astrbot_api"
            api_service = service_manager.get_service(service_sig)

            if not api_service:
                return False, {"error": f"无法获取 AstrBot API 服务: {service_sig}"}

            logger.info(f"获取帖子列表: page={page} page_size={page_size} category={category!r} sort={sort}")

            result = await api_service.get_threads(
                category=category if category else None,
                page=page,
                per_page=max(1, min(page_size, 100)),
                sort=sort,
                format="json",
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
                    "has_replied": thread.get("has_replied", False),
                })

            return True, {
                "total": total,
                "page": page,
                "page_size": page_size,
                "sort": sort,
                "category": category or "全部",
                "threads": threads,
                "message": f"获取帖子列表成功，共 {total} 条，第 {page} 页，本页 {len(threads)} 条",
            }

        except Exception as e:
            logger.error(f"获取帖子列表失败: {e}", exc_info=True)
            return False, {"error": f"获取帖子列表失败: {e}"}
