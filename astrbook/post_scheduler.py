"""AstrBot 定时发帖组件"""

import asyncio
import json
import re
from datetime import datetime
from typing import TYPE_CHECKING

from src.core.prompt import get_prompt_manager
from src.kernel.concurrency import get_task_manager
from src.kernel.logger import get_logger
from src.kernel.storage import json_store

if TYPE_CHECKING:
    from src.core.components.base.plugin import BasePlugin

logger = get_logger("post_scheduler")


class PostScheduler:
    """定时发帖调度器"""

    def __init__(self, plugin: "BasePlugin"):
        self.plugin = plugin
        self._task_info = None
        self._running = False
        self._posts_today = 0
        self._last_post_date = None
        self._storage_key = "astrbot_post_scheduler_state"

        # 加载人设配置
        from src.core.config import get_core_config

        config = get_core_config()
        self.personality = config.personality

        # 初始化提示词
        self._init_prompts()

    def _init_prompts(self):
        """初始化发帖提示词模板"""
        manager = get_prompt_manager()

        manager.get_or_create(
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

    async def start(self):
        """启动定时发帖任务"""
        self._running = True
        # 加载持久化的计数数据
        await self._load_state()

        # 使用系统任务管理器创建定时任务
        tm = get_task_manager()
        self._task_info = tm.create_task(
            self._schedule_loop(),
            name="astrbot_post_scheduler",
            daemon=True,
        )

        logger.info("定时发帖任务已启动")

    async def stop(self):
        """停止定时发帖任务"""
        self._running = False

        if self._task_info:
            tm = get_task_manager()
            try:
                tm.cancel_task(self._task_info.task_id)
            except Exception:
                pass
            self._task_info = None

        logger.info("定时发帖任务已停止")

    async def _schedule_loop(self):
        """定时任务循环"""
        schedule = self.plugin.config.poster.interval_minutes
        interval_seconds = schedule * 60

        logger.info(f"定时发帖间隔：{schedule} 分钟")

        while self._running:
            try:
                # 检查是否需要重置今日发帖计数
                current_date = datetime.now().date()
                if self._last_post_date != current_date:
                    self._posts_today = 0
                    self._last_post_date = current_date
                    # 保存重置后的状态
                    await self._save_state()

                # 检查今日发帖数量限制
                max_daily_posts = self.plugin.config.poster.max_daily_posts
                if self._posts_today >= max_daily_posts:
                    logger.info(f"今日发帖已达上限 ({max_daily_posts})，跳过本次发帖")
                else:
                    # 执行发帖
                    await self._create_post()
                    self._posts_today += 1
                    # 保存更新后的状态
                    await self._save_state()

            except Exception as e:
                logger.error(f"定时发帖出错: {e}", exc_info=True)

            # 等待下次执行
            await asyncio.sleep(interval_seconds)

    async def _create_post(self):
        """创建并发布帖子"""
        from src.core.managers import get_service_manager
        from src.kernel.llm import LLMRequest, LLMPayload, ROLE, Text
        from src.core.config import get_model_config

        # 获取 Service
        service_manager = get_service_manager()
        service_sig = f"{self.plugin.plugin_name}:service:astrbot_api"
        api_service = service_manager.get_service(service_sig)

        if not api_service:
            logger.error(f"无法获取 AstrBot API 服务: {service_sig}")
            return

        try:
            # 1. 获取最近话题（可选，用于参考）
            recent_topics = await self._get_recent_topics(api_service)

            # 2. 尝试获取网络搜索结果（可选，用于参考）
            search_results = await self._get_search_insights()

            # 3. 构建提示词
            prompt = self._build_post_prompt(recent_topics, search_results)

            # 4. 调用 LLM 生成帖子
            # 获取模型配置
            model_config = get_model_config()
            model_set = model_config.get_task(self.plugin.config.poster.llm_model)

            # 创建 LLM 请求
            llm_request = LLMRequest(model_set, request_name="astrbot_create_post")
            llm_request.add_payload(LLMPayload(ROLE.USER, Text(prompt)))

            # 发送请求
            response = await llm_request.send(stream=False)
            response_text = await response
            logger.info(response_text)
            # 5. 解析 JSON 响应
            post_data = self._parse_json_response(response_text)
            if not post_data:
                logger.error("无法解析 LLM 响应为有效的 JSON")
                return

            # 6. 验证数据
            if not all(k in post_data for k in ["title", "content", "category"]):
                logger.error("LLM 响应缺少必要字段")
                return

            # 7. 发布帖子
            result = await api_service.create_thread(
                title=post_data["title"],
                content=post_data["content"],
                category=post_data["category"],
            )

            logger.info(
                f"成功发布帖子: [{post_data['category']}] {post_data['title']} "
                f"(ID: {result.get('id', 'unknown')})"
            )

            if "reasoning" in post_data:
                logger.info(f"发帖理由: {post_data['reasoning']}")

        except Exception as e:
            logger.error(f"发布帖子失败: {e}", exc_info=True)

    async def _get_recent_topics(self, api_service) -> str:
        """获取最近的话题列表（用于参考）"""
        try:
            # 这里可以调用 API 获取最近帖子
            # 简化处理：返回空字符串或固定提示
            return "暂无最近话题参考"
        except Exception as e:
            logger.warning(f"获取最近话题失败: {e}")
            return "暂无最近话题参考"

    async def _get_search_insights(self) -> str:
        """尝试获取网络搜索结果作为发帖参考"""
        try:
            from src.core.managers import get_service_manager

            service_manager = get_service_manager()
            search_service = service_manager.get_service("web_search_tool:service:web_search")

            if not search_service:
                logger.debug("搜索服务不可用，跳过搜索")
                return "暂无网络搜索参考"

            # 根据时间和兴趣选择搜索关键词
            search_queries = self._generate_search_queries()
            if not search_queries:
                return "暂无网络搜索参考"

            # 执行搜索（选择一个查询）
            query = search_queries[0]
            logger.info(f"正在搜索参考信息: {query}")

            result = await search_service.search(
                query=query,
                num_results=8,  # 只获取少量结果作为参考
                strategy="single"
            )

            if "error" in result:
                logger.warning(f"搜索失败: {result['error']}")
                return "暂无网络搜索参考"

            # 格式化搜索结果
            content = result.get("content", "")
            if content:
                return f"关于『{query}』的搜索结果：\n{content[:3000]}..."  # 限制长度
            else:
                return "暂无网络搜索参考"

        except ImportError:
            logger.debug("搜索服务模块未安装，跳过搜索")
            return "暂无网络搜索参考"
        except Exception as e:
            logger.warning(f"获取搜索结果失败: {e}")
            return "暂无网络搜索参考"

    def _generate_search_queries(self) -> list[str]:
        """生成搜索查询关键词"""
        current_hour = datetime.now().hour
        queries = []

        # 根据时间段选择不同的话题
        if 6 <= current_hour < 12:
            queries = ["今日热点新闻", "早间资讯"]
        elif 12 <= current_hour < 18:
            queries = ["gpt5.3note", "gpt5.3note"]
        elif 18 <= current_hour < 22:
            queries = ["今日热搜", "有趣的话题"]
        else:
            queries = ["深夜话题", "今日趣闻"]

        return queries

    def _build_post_prompt(self, recent_topics: str, search_results: str = "") -> str:
        """构建发帖提示词"""
        manager = get_prompt_manager()
        template = manager.get_template("astrbot_create_post")

        current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M")

        prompt = (
            template.set("bot_nickname", self.personality.nickname)
            .set("bot_identity", self.personality.identity)
            .set("bot_personality", self.personality.personality_core)
            .set("bot_reply_style", self.personality.reply_style)
            .set("current_time", current_time)
            .set("recent_topics", recent_topics)
            .set("search_results", search_results or "暂无网络搜索参考")
            .build()
        )
        logger.info(prompt)
        return prompt

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

    async def _load_state(self):
        """从存储加载发帖状态"""
        try:
            state = await json_store.load(self._storage_key)
            if state:
                self._posts_today = state.get("posts_today", 0)
                last_date_str = state.get("last_post_date")
                if last_date_str:
                    self._last_post_date = datetime.strptime(
                        last_date_str, "%Y-%m-%d"
                    ).date()
                logger.info(
                    f"已加载发帖状态: 今日已发 {self._posts_today} 帖, "
                    f"最后发帖日期: {self._last_post_date}"
                )
        except Exception as e:
            logger.warning(f"加载发帖状态失败: {e}")

    async def _save_state(self):
        """保存发帖状态到存储"""
        try:
            state = {
                "posts_today": self._posts_today,
                "last_post_date": (
                    self._last_post_date.strftime("%Y-%m-%d")
                    if self._last_post_date
                    else None
                ),
            }
            await json_store.save(self._storage_key, state)
            logger.debug(f"已保存发帖状态: {state}")
        except Exception as e:
            logger.error(f"保存发帖状态失败: {e}")
