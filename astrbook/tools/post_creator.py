"""发帖创建工具

复用 post_scheduler.py 的发帖逻辑，封装为 Tool
"""

import json
import re
from datetime import datetime
from typing import Annotated, TYPE_CHECKING

from src.core.components.base.tool import BaseTool
from src.core.prompt import get_prompt_manager
from src.core.config import get_core_config, get_model_config
from src.kernel.llm import LLMRequest, LLMPayload, ROLE, Text
from src.kernel.logger import get_logger

if TYPE_CHECKING:
    from ..plugin import AstrBotPlugin

logger = get_logger("astrbot.post_creator", display="发帖工具")


class PostCreatorTool(BaseTool):
    """发帖创建工具
    
    使用 LLM 生成并发布论坛帖子
    """
    
    tool_name = "post_creator"
    tool_description = (
        "生成并发布 AstrBook 论坛帖子。可指定话题提示、"
        "分类、是否调用搜索服务获取灵感"
    )
    
    def __init__(self, plugin: "AstrBotPlugin"):
        super().__init__(plugin)
        self.state_manager = plugin.state_manager
        core_config = get_core_config()
        self.personality = core_config.personality
    
    async def execute(
        self,
        topic_hint: Annotated[str, "话题提示，例如'分享周末活动'"] = "",
        category: Annotated[str, "指定发帖分类，如 chat/tech/share 等"] = "",
        use_search: Annotated[bool, "是否调用搜索服务获取网络参考信息"] = False
    ) -> tuple[bool, dict]:
        """执行发帖
        
        Args:
            topic_hint: 话题提示
            category: 指定分类
            use_search: 是否使用搜索
            
        Returns:
            (成功标志, 结果字典)
        """
        try:
            # 1. 检查配额
            if not await self.state_manager.can_post():
                state = await self.state_manager.get_today_stats()
                return False, {
                    "error": "已达到每日发帖上限",
                    "posts_today": state["post_count"],
                    "max_posts": self.plugin.config.agent.max_posts_per_day
                }
            
            # 2. 获取 API 服务
            from src.core.managers import get_service_manager
            
            service_manager = get_service_manager()
            service_sig = f"{self.plugin.plugin_name}:service:astrbot_api"
            api_service = service_manager.get_service(service_sig)
            
            if not api_service:
                return False, {"error": f"无法获取 AstrBot API 服务: {service_sig}"}
            
            # 3. 获取参考信息（可选）
            recent_topics = await self._get_recent_topics(api_service)
            search_results = ""
            if use_search:
                search_results = await self._get_search_insights()
            
            # 4. 构建提示词
            prompt = self._build_post_prompt(
                recent_topics=recent_topics,
                search_results=search_results,
                topic_hint=topic_hint,
                category_hint=category
            )
            
            # 5. 调用 LLM 生成帖子
            model_config = get_model_config()
            model_set = model_config.get_task(
                self.plugin.config.agent.post_llm_model
            )
            
            llm_request = LLMRequest(model_set, request_name="agent_create_post")
            llm_request.add_payload(LLMPayload(ROLE.USER, Text(prompt)))
            
            response = await llm_request.send(stream=False)
            response_text = await response
            
            logger.debug(f"LLM 响应: {response_text[:200]}...")
            
            # 6. 解析 JSON 响应
            post_data = self._parse_json_response(response_text)
            if not post_data:
                return False, {"error": "无法解析 LLM 响应为有效 JSON"}
            
            # 7. 验证数据
            if not all(k in post_data for k in ["title", "content", "category"]):
                return False, {"error": f"LLM 响应缺少必要字段: {post_data}"}
            
            # 8. 发布帖子
            result = await api_service.create_thread(
                title=post_data["title"],
                content=post_data["content"],
                category=post_data["category"]
            )
            
            # 9. 更新配额
            await self.state_manager.increment_count("post_count")
            
            logger.info(
                f"成功发布帖子: [{post_data['category']}] {post_data['title']} "
                f"(ID: {result.get('id', 'unknown')})"
            )
            
            return True, {
                "thread_id": result.get("id"),
                "title": post_data["title"],
                "content": post_data["content"],
                "category": post_data["category"],
                "reasoning": post_data.get("reasoning", "")
            }
            
        except Exception as e:
            logger.error(f"发布帖子失败: {e}", exc_info=True)
            return False, {"error": f"发布帖子失败: {e}"}
    
    async def _get_recent_topics(self, api_service) -> str:
        """获取最近话题列表"""
        try:
            result = await api_service.get_threads(
                category="",
                page=1,
                per_page=5,
                sort="latest_reply"
            )
            
            if not result or not result.get("items"):
                return "暂无最近话题参考"
            
            topics = []
            for item in result["items"][:5]:
                title = item.get("title", "无标题")
                category = item.get("category", "未知")
                topics.append(f"[{category}] {title}")
            
            return "\n".join(topics)
            
        except Exception as e:
            logger.warning(f"获取最近话题失败: {e}")
            return "暂无最近话题参考"
    
    async def _get_search_insights(self) -> str:
        """获取网络搜索结果"""
        try:
            from src.core.managers import get_service_manager
            
            service_manager = get_service_manager()
            search_service = service_manager.get_service(
                "web_search_tool:service:web_search"
            )
            
            if not search_service:
                logger.debug("搜索服务不可用")
                return "暂无网络搜索参考"
            
            # 根据时间生成查询词
            current_hour = datetime.now().hour
            if 6 <= current_hour < 12:
                query = "今日热点新闻"
            elif 12 <= current_hour < 18:
                query = "今日话题讨论"
            elif 18 <= current_hour < 22:
                query = "今日热搜"
            else:
                query = "今日趣闻"
            
            logger.info(f"正在搜索参考信息: {query}")
            
            result = await search_service.search(
                query=query,
                num_results=5,
                strategy="single"
            )
            
            if "error" in result:
                return "暂无网络搜索参考"
            
            content = result.get("content", "")
            return f"关于『{query}』的搜索结果：\n{content[:2000]}..." if content else "暂无网络搜索参考"
            
        except Exception as e:
            logger.warning(f"获取搜索结果失败: {e}")
            return "暂无网络搜索参考"
    
    def _build_post_prompt(
        self,
        recent_topics: str,
        search_results: str,
        topic_hint: str,
        category_hint: str
    ) -> str:
        """构建发帖提示词"""
        manager = get_prompt_manager()
        template = manager.get_template("astrbot_create_post")
        
        current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")
        
        # 添加话题提示
        topic_section = ""
        if topic_hint:
            topic_section = f"\n## 话题提示\n{topic_hint}\n"
        
        if category_hint:
            topic_section += f"\n建议分类: {category_hint}\n"
        
        return (
            template.set("bot_nickname", self.personality.nickname)
            .set("bot_identity", self.personality.identity)
            .set("bot_personality", self.personality.personality_core)
            .set("bot_reply_style", self.personality.reply_style)
            .set("current_time", current_time)
            .set("recent_topics", recent_topics)
            .set("search_results", search_results)
            .build()
        ) + topic_section
    
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
