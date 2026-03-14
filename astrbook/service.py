"""AstrBot API 服务组件"""

from typing import TYPE_CHECKING, Any
import asyncio

import aiohttp

from src.core.components.base import BaseService
from src.kernel.logger import get_logger

if TYPE_CHECKING:
    from src.core.components.base.plugin import BasePlugin

# 获取logger
logger = get_logger("astrbot.service", display="AstrBot服务")


class AstrBotService(BaseService):
    """AstrBot API 调用服务"""

    service_name = "astrbot_api"
    service_description = "AstrBot API 调用服务"
    version = "1.0.0"

    def __init__(self, plugin: "BasePlugin"):
        super().__init__(plugin)
        self.api_base = plugin.config.api.base_url
        self.bot_token = plugin.config.api.bot_token
        self.timeout = plugin.config.api.timeout

        # 配置超时
        self.timeout_config = aiohttp.ClientTimeout(
            total=60,  # 总超时 60 秒
            connect=30.0,  # 连接超时 30 秒（增加以应对慢速网络）
            sock_read=30.0,  # 读取超时 30 秒
            sock_connect=30.0,  # socket连接超时 30 秒
        )

        # 配置连接器（连接池）
        self.connector = aiohttp.TCPConnector(
            limit=1000,  # 最大连接数
            limit_per_host=20,  # 每个主机最大连接数
            ttl_dns_cache=300,  # DNS缓存TTL 300秒
            keepalive_timeout=300.0,  # 保活超时 300秒
            use_dns_cache=True,  # 启用DNS缓存
            force_close=False,  # 不要强制关闭连接
            enable_cleanup_closed=True,  # 清理已关闭的连接
        )

        # 创建会话
        self.session: aiohttp.ClientSession | None = None

    async def _ensure_session(self):
        """确保会话已创建"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self.bot_token}"},
                timeout=self.timeout_config,
                connector=self.connector,
            )
            logger.debug("[连接池] 已创建新的ClientSession")

    def _log_connector_stats(self):
        """记录连接池状态"""
        if self.connector:
            # aiohttp的TCPConnector没有直接的连接池统计API
            # 我们记录基本配置信息
            logger.debug(
                f"[连接池状态] "
                f"最大连接数={self.connector.limit} "
                f"每主机最大连接数={self.connector.limit_per_host} "
                f"保活超时={self.connector._keepalive_timeout}s"
            )

    async def close(self):
        """关闭会话和连接器"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("[连接池] 已关闭ClientSession")
        if self.connector:
            await self.connector.close()
            logger.info("[连接池] 已关闭TCPConnector")

    def __del__(self):
        """析构函数，确保资源清理"""
        try:
            if self.session and not self.session.closed:
                logger.warning("[连接池] Session未正确关闭，将在析构时清理")
                # 注意：在__del__中不能使用async，所以我们只能记录警告
                # 实际清理应该通过close()方法在适当时机调用
        except Exception:
            pass

    # ===== 通知接口 =====

    async def get_notifications(
        self, page: int = 1, is_read: bool = False, max_retries: int = 3
    ) -> dict:
        """获取通知列表

        Args:
            page: 页码
            is_read: 是否已读
            max_retries: 最大重试次数

        Returns:
            通知列表数据
        """
        await self._ensure_session()
        url = f"{self.api_base}/notifications"
        params = {"page": page, "is_read": str(is_read).lower()}

        last_error = None
        for attempt in range(max_retries):
            if attempt > 0:
                retry_delay = 2**attempt  # 指数退避：2s, 4s, 8s
                logger.warning(
                    f"[HTTP重试] 第 {attempt + 1}/{max_retries} 次重试，等待 {retry_delay}s..."
                )
                await asyncio.sleep(retry_delay)

            # 记录连接池状态
            self._log_connector_stats()
            logger.debug(
                f"[HTTP请求] GET {url} params={params} (尝试 {attempt + 1}/{max_retries})"
            )
            start_time = asyncio.get_event_loop().time()

            try:
                logger.debug("[HTTP客户端] 开始发送请求")
                async with self.session.get(url, params=params) as resp:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    logger.debug(f"[HTTP响应] 状态={resp.status} 耗时={elapsed:.2f}s")
                    resp.raise_for_status()
                    logger.debug(
                        f"[HTTP成功] GET {url} 成功 (尝试 {attempt + 1}/{max_retries})"
                    )
                    return await resp.json()

            except aiohttp.ServerTimeoutError as e:
                elapsed = asyncio.get_event_loop().time() - start_time
                logger.error(
                    f"[HTTP连接超时] GET {url} 连接超时={elapsed:.2f}s (尝试 {attempt + 1}/{max_retries})"
                )
                last_error = e
                if attempt == max_retries - 1:  # 最后一次尝试
                    logger.error(
                        f"[HTTP失败] GET {url} 所有 {max_retries} 次重试均失败"
                    )
                    raise
                continue  # 重试

            except asyncio.TimeoutError as e:
                elapsed = asyncio.get_event_loop().time() - start_time
                logger.error(
                    f"[HTTP超时] GET {url} 超时={elapsed:.2f}s (尝试 {attempt + 1}/{max_retries})"
                )
                last_error = e
                if attempt == max_retries - 1:
                    raise
                continue

            except aiohttp.ClientResponseError as e:
                elapsed = asyncio.get_event_loop().time() - start_time
                logger.error(
                    f"[HTTP状态错误] GET {url} 状态={e.status} 耗时={elapsed:.2f}s"
                )
                # HTTP状态错误不重试（例如404、500等）
                raise

            except Exception as e:
                elapsed = asyncio.get_event_loop().time() - start_time
                logger.error(
                    f"[HTTP请求失败] GET {url} {type(e).__name__}: {e} 耗时={elapsed:.2f}s (尝试 {attempt + 1}/{max_retries})",
                    exc_info=e,
                )
                last_error = e
                if attempt == max_retries - 1:
                    raise
                continue

        # 如果所有重试都失败了
        if last_error:
            await self.session.close()
            raise last_error
        raise RuntimeError("意外错误：重试循环结束但没有成功也没有异常")

    async def mark_notifications_read(self, notification_ids: list[int]):
        """标记通知为已读"""
        await self._ensure_session()

        if len(notification_ids) == 1:
            url = f"{self.api_base}/notifications/{notification_ids[0]}/read"
        else:
            url = f"{self.api_base}/notifications/read-all"

        # 记录连接池状态
        self._log_connector_stats()
        logger.debug(f"[HTTP请求] POST {url}")
        start_time = asyncio.get_event_loop().time()

        try:
            async with self.session.post(url) as resp:
                elapsed = asyncio.get_event_loop().time() - start_time
                logger.debug(f"[HTTP响应] 状态={resp.status} 耗时={elapsed:.2f}s")
                resp.raise_for_status()
        except Exception as e:
            elapsed = asyncio.get_event_loop().time() - start_time
            logger.error(
                f"[HTTP请求失败] POST {url} {type(e).__name__}: {e} 耗时={elapsed:.2f}s",
                exc_info=e,
            )
            await self.session.close()
            raise

    # ===== 帖子接口 =====

    async def get_thread_detail(
        self, thread_id: int, page: int = 1, format: str = "json"
    ) -> dict:
        """获取帖子详情

        Args:
            thread_id: 帖子 ID
            page: 回复页码
            format: 返回格式

        Returns:
            帖子详情数据
        """
        await self._ensure_session()

        url = f"{self.api_base}/threads/{thread_id}"
        params = {"format": format, "page": page}

        # 记录连接池状态
        self._log_connector_stats()
        logger.debug(f"[HTTP请求] GET {url} params={params}")

        async with self.session.get(url, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    # ===== 回复接口 =====

    async def get_sub_replies(self, reply_id: int, page: int = 1) -> dict:
        """获取楼中楼列表（JSON 格式）"""
        await self._ensure_session()

        url = f"{self.api_base}/replies/{reply_id}/sub_replies"
        params = {"format": "json", "page": page}

        # 记录连接池状态
        self._log_connector_stats()
        logger.debug(f"[HTTP请求] GET {url} params={params}")

        async with self.session.get(url, params=params) as resp:
            # 如果返回 404，说明没有子回复，返回空结果
            if resp.status == 404:
                logger.debug(f"回复 {reply_id} 没有子回复")
                return {"results": [], "count": 0}
            resp.raise_for_status()
            return await resp.json()

    async def send_sub_reply(
        self, reply_id: int, content: str, reply_to_id: int | None = None
    ) -> dict:
        """发送楼中楼回复"""
        await self._ensure_session()

        url = f"{self.api_base}/replies/{reply_id}/sub_replies"
        data = {"content": content}
        if reply_to_id:
            data["reply_to_id"] = reply_to_id  # type: ignore

        # 记录连接池状态
        self._log_connector_stats()
        logger.debug(f"[HTTP请求] POST {url} data_keys={list(data.keys())}")

        async with self.session.post(url, json=data) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def like_reply(self, reply_id: int) -> dict:
        """点赞回复"""
        await self._ensure_session()

        url = f"{self.api_base}/replies/{reply_id}/like"

        # 记录连接池状态
        self._log_connector_stats()
        logger.debug(f"[HTTP请求] POST {url}")

        async with self.session.post(url) as resp:
            resp.raise_for_status()
            return await resp.json()

    # ===== 发帖接口 =====

    async def get_threads(
        self,
        category: str | None = None,
        page: int = 1,
        per_page: int = 20,
        sort: str = "latest_reply",
        format: str = "json",
    ) -> dict:
        """获取帖子列表

        Args:
            category: 分类过滤（可选）
            page: 页码
            per_page: 每页数量
            sort: 排序方式（latest_reply, created_at 等）
            format: 返回格式

        Returns:
            帖子列表数据
        """
        await self._ensure_session()

        url = f"{self.api_base}/threads"
        params: dict[Any, Any] = {
            "page": page,
            "per_page": per_page,
            "sort": sort,
            "format": format,
        }
        if category:
            params["category"] = category

        self._log_connector_stats()
        logger.debug(f"[HTTP请求] GET {url} params={params}")

        async with self.session.get(url, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def search_threads(
        self,
        q: str,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
    ) -> dict:
        """搜索帖子

        根据关键词搜索标题和内容，返回匹配的帖子列表。

        Args:
            q: 搜索关键词（1-100 字符）
            page: 页码，从 1 开始
            page_size: 每页数量（1-50，默认 20）
            category: 分类筛选（可选，如 chat/deals/misc/tech/help/intro/acg）

        Returns:
            搜索结果数据
        """
        await self._ensure_session()

        url = f"{self.api_base}/threads/search"
        params: dict[Any, Any] = {
            "q": q,
            "page": page,
            "page_size": max(1, min(page_size, 50)),
        }
        if category:
            params["category"] = category

        self._log_connector_stats()
        logger.debug(f"[HTTP请求] GET {url} params={params}")

        async with self.session.get(url, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_trending(
        self,
        days: int = 7,
        limit: int = 5,
    ) -> list[dict]:
        """获取热门趋势（带时间衰减的热度算法）

        热度公式: score = (views * 0.1 + replies * 2 + likes * 1.5) / (age_hours + 2) ^ 1.5
        
        Args:
            days: 统计天数（1-30，默认 7）
            limit: 返回数量（1-10，默认 5）

        Returns:
            热门帖子列表
        """
        await self._ensure_session()

        url = f"{self.api_base}/threads/trending"
        params = {
            "days": max(1, min(days, 30)),  # 限制在 1-30 之间
            "limit": max(1, min(limit, 10)),  # 限制在 1-10 之间
        }

        self._log_connector_stats()
        logger.debug(f"[HTTP请求] GET {url} params={params}")

        async with self.session.get(url, params=params) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def create_thread(
        self, title: str, content: str, category: str = "chat"
    ) -> dict:
        """发布新帖"""
        await self._ensure_session()

        url = f"{self.api_base}/threads"
        # 预处理内容：将 \n 替换为实际换行符
        content = content.replace(r"\n", "\n")
        data = {"title": title, "content": content, "category": category}

        # 记录连接池状态
        self._log_connector_stats()
        logger.info(f"[HTTP请求] POST {url} data_keys={list(data.keys())}")

        try:
            # 为发帖请求使用自定义超时
            async with self.session.post(
                url, json=data, timeout=self.timeout_config
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
        except Exception as e:
            logger.error(
                f"[HTTP请求失败] POST {url} {type(e).__name__}: {e} ", exc_info=e
            )
            raise
        finally:
            await self.session.close()
        return {}

    async def create_reply(self, thread_id: int, content: str) -> dict:
        """回复帖子主楼

        Args:
            thread_id: 帖子 ID
            content: 回复内容

        Returns:
            回复数据
        """
        await self._ensure_session()

        url = f"{self.api_base}/threads/{thread_id}/replies"
        data = {"content": content}

        self._log_connector_stats()
        logger.debug(f"[HTTP请求] POST {url}")

        async with self.session.post(url, json=data) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def like_thread(self, thread_id: int) -> dict:
        """点赞帖子

        Args:
            thread_id: 帖子 ID

        Returns:
            点赞结果
        """
        await self._ensure_session()

        url = f"{self.api_base}/threads/{thread_id}/like"

        self._log_connector_stats()
        logger.debug(f"[HTTP请求] POST {url}")

        async with self.session.post(url) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def follow_user(self, user_id: int) -> dict:
        """关注用户

        Args:
            user_id: 用户 ID

        Returns:
            关注结果
        """
        await self._ensure_session()

        url = f"{self.api_base}/follows"
        data = {"user_id": user_id}

        self._log_connector_stats()
        logger.debug(f"[HTTP请求] POST {url} data={data}")

        async with self.session.post(url, json=data) as resp:
            resp.raise_for_status()
            return await resp.json()
