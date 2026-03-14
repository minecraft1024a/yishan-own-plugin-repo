"""趋势分析工具

使用服务端热度算法分析论坛当前的热门话题和趋势
"""

from typing import Annotated, TYPE_CHECKING
from collections import Counter

from src.core.components.base.tool import BaseTool
from src.kernel.logger import get_logger

if TYPE_CHECKING:
    from ..plugin import AstrBotPlugin

logger = get_logger("astrbot.trend_analyzer_tool", display="趋势分析")


class TrendAnalyzerTool(BaseTool):
    """趋势分析tool
    
    使用服务端热度算法（带时间衰减）分析论坛热门话题
    热度公式: score = (views * 0.1 + replies * 2 + likes * 1.5) / (age_hours + 2) ^ 1.5
    """
    
    tool_name = "trend_analyzer"
    tool_description = (
        "分析 AstrBook 论坛的热门趋势。使用服务端热度算法，"
        "综合考虑浏览量、回复数、点赞数和时间衰减，返回当前最热门的帖子"
    )
    
    async def execute(
        self,
        days: Annotated[int, "统计天数（1-30天内发布的帖子）"] = 7,
        limit: Annotated[int, "返回热门帖子数量（1-10）"] = 5,
    ) -> tuple[bool, dict]:
        """执行趋势分析
        
        Args:
            days: 统计天数，默认 7 天（限制 1-30）
            limit: 返回数量，默认 5 个（限制 1-10）
            
        Returns:
            (成功标志, 结果字典)
        """
        try:
            # 获取 API 服务
            from src.core.managers import get_service_manager
            
            service_manager = get_service_manager()
            service_sig = f"{self.plugin.plugin_name}:service:astrbot_api"
            api_service = service_manager.get_service(service_sig)
            
            if not api_service:
                return False, {"error": f"无法获取 AstrBot API 服务: {service_sig}"}
            
            # 调用 trending API
            logger.info(f"获取热门趋势：统计 {days} 天内的 {limit} 个热门帖子")
            trending_threads = await api_service.get_trending(days=days, limit=limit)
            
            if not trending_threads:
                return True, {
                    "message": f"最近 {days} 天内暂无热门帖子",
                    "hot_threads": [],
                    "category_stats": {},
                    "hot_keywords": [],
                    "suggestions": ["论坛活动较少，可以发布新内容吸引用户"]
                }
            
            # 提取热门帖子信息
            hot_threads = []
            categories = []
            all_keywords = []
            
            for thread in trending_threads:
                thread_info = {
                    "id": thread.get("id"),
                    "title": thread.get("title", ""),
                    "category": thread.get("category", ""),
                    "author": thread.get("author", {}).get("username", "未知"),
                    "views": thread.get("views", 0),
                    "replies": thread.get("replies", 0),
                    "likes": thread.get("likes", 0),
                    "created_at": thread.get("created_at", ""),
                }
                hot_threads.append(thread_info)
                
                # 统计分类
                category = thread.get("category", "")
                if category:
                    categories.append(category)
                
                # 提取标题关键词（简单分词）
                title = thread.get("title", "")
                words = title.replace("，", " ").replace("。", " ").replace("！", " ").replace("？", " ").split()
                all_keywords.extend([w for w in words if len(w) > 1])
            
            # 统计分类分布
            category_counter = Counter(categories)
            category_stats = dict(category_counter.most_common())
            
            # 统计高频关键词
            keyword_counter = Counter(all_keywords)
            hot_keywords = [kw for kw, count in keyword_counter.most_common(10)]
            
            # 生成建议
            suggestions = []
            
            # 基于分类的建议
            if category_stats:
                top_category = max(category_stats.items(), key=lambda x: x[1])[0]
                suggestions.append(f"'{top_category}' 分类最热门，发帖时可以考虑此分类")
            
            # 基于关键词的建议
            if hot_keywords:
                top_keywords = hot_keywords[:5]
                suggestions.append(f"热门关键词：{', '.join(top_keywords)}")
            
            # 基于互动数据的建议
            avg_replies = sum(t["replies"] for t in hot_threads) / len(hot_threads) if hot_threads else 0
            if avg_replies > 10:
                suggestions.append("热门帖子互动活跃，发布高质量内容更容易获得关注")
            
            return True, {
                "message": f"成功获取最近 {days} 天内的 {len(hot_threads)} 个热门帖子",
                "hot_threads": hot_threads,
                "category_stats": category_stats,
                "hot_keywords": hot_keywords,
                "suggestions": suggestions
            }
            
        except Exception as e:
            logger.error(f"分析趋势失败: {e}", exc_info=True)
            return False, {"error": f"分析趋势失败: {str(e)}"}
