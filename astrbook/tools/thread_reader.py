"""帖子阅读工具

获取并格式化帖子内容，供 AI 阅读分析
"""

from typing import Annotated

from src.core.components.base.tool import BaseTool
from src.kernel.logger import get_logger

logger = get_logger("astrbot.thread_reader_tool", display="阅读工具")


class ThreadReaderTool(BaseTool):
    """帖子阅读工具
    
    获取并格式化帖子内容
    """
    
    tool_name = "thread_reader"
    tool_description = "获取指定帖子的详细内容（包括标题、正文、评论等）"
    
    async def execute(
        self,
        thread_id: Annotated[str, "要阅读的帖子 ID"],
        page: Annotated[int, "评论页码"] = 1
    ) -> tuple[bool, str]:
        """执行帖子阅读
        
        Args:
            thread_id: 帖子 ID
            page: 评论页码
            
        Returns:
            (成功标志, 格式化的帖子内容)
        """
        try:
            # 获取 API 服务
            from src.core.managers import get_service_manager
            
            service_manager = get_service_manager()
            service_sig = f"{self.plugin.plugin_name}:service:astrbot_api"
            api_service = service_manager.get_service(service_sig)
            
            if not api_service:
                return False, f"无法获取 AstrBot API 服务: {service_sig}"
            
            # 获取帖子详情
            thread_detail = await api_service.get_thread_detail(thread_id, page=page)
            
            if not thread_detail:
                return False, f"无法获取帖子 {thread_id} 的详情"
            
            # 构建格式化内容
            content = self._build_thread_content(thread_detail)
            
            return True, content
            
        except Exception as e:
            logger.error(f"阅读帖子失败 ({thread_id}): {e}", exc_info=True)
            return False, f"阅读帖子失败: {e}"
    
    def _build_thread_content(self, thread_detail: dict) -> str:
        """构建格式化的帖子内容
        
        Args:
            thread_detail: 帖子详情数据
            
        Returns:
            格式化的帖子内容字符串
        """
        thread = thread_detail.get("thread", {})
        replies_data = thread_detail.get("replies", {})
        author = thread.get("author", {})
        is_mine = thread.get("is_mine", False)
        
        # 格式化回复列表
        replies_content = self._format_replies(replies_data.get("items", []))
        
        # 处理分类名称
        category_display = thread.get("category_name") or thread.get("category", "未知")
        
        # 构建作者信息
        author_display = str(author.get("nickname", "未知"))
        if is_mine:
            author_display += " [这是你自己发的帖子]"
        
        # 构建完整内容
        lines = [
            "# 帖子详情",
            "",
            f"**标题**: {thread.get('title', '无标题')}",
            f"**分类**: {category_display}",
            f"**作者**: {author_display} (ID: {author.get('id', '')})",
            f"**发布时间**: {thread.get('created_at', '')[:16].replace('T', ' ')}",
            f"**浏览数**: {thread.get('view_count', 0)} | **回复数**: {thread.get('reply_count', 0)} | **点赞数**: {thread.get('like_count', 0)}",
            "",
            "## 正文内容",
            f"{thread.get('content', '')}",
            "",
            f"## 评论区 (显示 {len(replies_data.get('items', []))} / 共 {replies_data.get('total', 0)} 条)",
            f"{replies_content}",
        ]
        
        return "\n".join(lines)
    
    def _format_replies(self, replies: list) -> str:
        """格式化回复列表
        
        Args:
            replies: 回复列表
            
        Returns:
            格式化的回复内容
        """
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
