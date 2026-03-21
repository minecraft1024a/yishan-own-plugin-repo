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
from ..state_manager import get_state_manager

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
        self.state_manager = get_state_manager()
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
            prompt = await self._build_post_prompt(
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
    
    async def _build_post_prompt(
        self,
        recent_topics: str,
        search_results: str,
        topic_hint: str,
        category_hint: str
    ) -> str:
        """构建发帖提示词"""
        manager = get_prompt_manager()
        template = manager.get_or_create(
            name="astrbot_create_post",
            template="""# 你的身份
你叫 {bot_nickname}，{bot_identity}。

## 人格特征
{bot_personality}

## 表达风格
{bot_reply_style}

---

# 当前任务
你需要在 AstrBook 休闲论坛上发布一篇轻松的帖子。

## 发帖要求
这是一个**休闲论坛**，氛围轻松愉快，你可以：
1. **分享个人爱好**：音乐、游戏、动漫、美食、旅行、摄影等任何你感兴趣的事
2. **聊日常生活**：今天的心情、有趣的见闻、小确幸、吐槽日常
3. **发表随想感悟**：对某件事的看法、突然想到的有趣点子
4. **推荐好物**：最近喜欢的歌、书、电影、游戏、Up主等
5. **提问讨论**：关于兴趣爱好的问题，征集推荐

**不要太严肃**，不需要写得像学术论文或技术文档：
- 可以是轻松闲聊的语气
- 内容可以简短、随意，但要真诚
- 可以带点个性和情绪
- 重点是表达真实的想法和感受

## 可用的帖子分类
| 分类 Key | 分类名称 | 适合内容 |
|----------|----------|----------|
| chat | 闲聊 | 日常聊天、杂谈、心情分享 |
| tech | 技术 | 技术讨论、开发经验 |
| help | 求助 | 提问、寻求帮助、求推荐 |
| share | 分享 | 资源分享、经验分享、好物推荐 |
| deals | 优惠 | 优惠信息、活动分享 |
| intro | 自我介绍 | Bot 自我介绍 |
| acg | ACG | 二次元相关、动漫、游戏 |
| misc | 其他 | 杂项内容 |

## 当前时间
{current_time}

## 最近话题（可选参考）
{recent_topics}

## 网络搜索结果（可选参考）
{search_results}

---

# 发帖灵感参考
你可以从这些角度考虑：
- 最近在玩什么游戏/看什么番/听什么歌？
- 有什么想吐槽或分享的日常趣事？
- 对某个话题有什么独特看法？
- 想向大家提问或征集意见？
- 发现了什么有趣的东西想推荐？
- 今天心情如何，有什么感想？

---

# 输出要求
必须严格按照以下 JSON 格式输出：

```json
{{
  "title": "帖子标题（10-50字）",
  "content": "帖子内容（80-600字，自然随意即可）",
  "category": "分类名称（从上述可选分类中选择）",
  "reasoning": "为什么想发这个帖子（简短说明）"
}}
```

注意：
- 标题要自然、有趣，像朋友聊天
- 内容真诚放松，不要太正式或刻意
- 分类要准确匹配内容主题
- 保持符合你的人设和风格
- 可以表达个人情绪和想法
- 只输出 JSON，不要有其他文字
""",
        )
        
        current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")
        
        # 添加话题提示
        topic_section = ""
        if topic_hint:
            topic_section = f"\n## 话题提示\n{topic_hint}\n"
        
        if category_hint:
            topic_section += f"\n建议分类: {category_hint}\n"
        
        prompt_base = await (
            template.set("bot_nickname", self.personality.nickname)
            .set("bot_identity", self.personality.identity)
            .set("bot_personality", self.personality.personality_core)
            .set("bot_reply_style", self.personality.reply_style)
            .set("current_time", current_time)
            .set("recent_topics", recent_topics)
            .set("search_results", search_results)
            .build()
        )
        return prompt_base + topic_section
    
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
