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

    def _create_session(self) -> aiohttp.ClientSession:
        """创建一个新的短生命周期 session
        
        每个请求使用独立的 session，用完后立即关闭，避免资源泄露。
        """
        connector = aiohttp.TCPConnector(
            limit=10,
            limit_per_host=5,
            ttl_dns_cache=300,
            keepalive_timeout=30.0,
        )
        
        return aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self.bot_token}"},
            timeout=self.timeout_config,
            connector=connector,
            connector_owner=True,  # session 拥有 connector
        )

    async def close(self):
        """关闭服务（现在无需关闭，因为每个请求使用独立session）"""
        logger.info("[连接池] 服务已关闭（使用短生命周期session）")

    def __del__(self):
        """析构函数
        
        注意：Session 和 Connector 在插件生命周期内保持开启。
        只有在插件卸载时才会通过 close() 方法正常关闭。
        由于 __del__ 不能使用 async，这里不做任何操作。
        """
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

            logger.debug(
                f"[HTTP请求] GET {url} params={params} (尝试 {attempt + 1}/{max_retries})"
            )
            start_time = asyncio.get_event_loop().time()

            # 每次请求创建新session
            async with self._create_session() as session:
                try:
                    logger.debug("[HTTP客户端] 开始发送请求")
                    async with session.get(url, params=params) as resp:
                        elapsed = asyncio.get_event_loop().time() - start_time
                        logger.debug(f"[HTTP响应] 状态={resp.status} 耗时={elapsed:.2f}s")
                        
                        # 先读取响应以确保连接被正确释放
                        response_data = await resp.json()
                        resp.raise_for_status()
                        
                        logger.debug(
                            f"[HTTP成功] GET {url} 成功 (尝试 {attempt + 1}/{max_retries})"
                        )
                        return response_data

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
            raise last_error
        raise RuntimeError("意外错误：重试循环结束但没有成功也没有异常")

    async def mark_notifications_read(self, notification_ids: list[int]):
        """标记通知为已读"""
        if len(notification_ids) == 1:
            url = f"{self.api_base}/notifications/{notification_ids[0]}/read"
        else:
            url = f"{self.api_base}/notifications/read-all"

        logger.debug(f"[HTTP请求] POST {url}")
        start_time = asyncio.get_event_loop().time()

        async with self._create_session() as session:
            try:
                async with session.post(url) as resp:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    logger.debug(f"[HTTP响应] 状态={resp.status} 耗时={elapsed:.2f}s")
                    
                    # 读取响应以确保连接被正确释放
                    await resp.read()
                    resp.raise_for_status()
            except Exception as e:
                elapsed = asyncio.get_event_loop().time() - start_time
                logger.error(
                    f"[HTTP请求失败] POST {url} {type(e).__name__}: {e} 耗时={elapsed:.2f}s",
                    exc_info=e,
                )
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
        url = f"{self.api_base}/threads/{thread_id}"
        params = {"format": format, "page": page}

        logger.debug(f"[HTTP请求] GET {url} params={params}")

        async with self._create_session() as session:
            async with session.get(url, params=params) as resp:
                response_data = await resp.json()
                resp.raise_for_status()
                return response_data

    # ===== 回复接口 =====

    async def get_sub_replies(self, reply_id: int, page: int = 1) -> dict:
        """获取楼中楼列表（JSON 格式）"""
        url = f"{self.api_base}/replies/{reply_id}/sub_replies"
        params = {"format": "json", "page": page}

        logger.debug(f"[HTTP请求] GET {url} params={params}")

        async with self._create_session() as session:
            async with session.get(url, params=params) as resp:
                # 如果返回 404，说明没有子回复，返回空结果
                if resp.status == 404:
                    await resp.read()  # 读取响应体以释放连接
                    logger.debug(f"回复 {reply_id} 没有子回复")
                    return {"results": [], "count": 0}
                
                # 先读取响应，再检查状态
                response_data = await resp.json()
                resp.raise_for_status()
                return response_data

    async def send_sub_reply(
        self, reply_id: int, content: str, reply_to_id: int | None = None
    ) -> dict:
        """发送楼中楼回复"""
        url = f"{self.api_base}/replies/{reply_id}/sub_replies"
        data = {"content": content}
        if reply_to_id:
            data["reply_to_id"] = reply_to_id  # type: ignore

        logger.debug(f"[HTTP请求] POST {url} data_keys={list(data.keys())}")

        async with self._create_session() as session:
            async with session.post(url, json=data) as resp:
                response_data = await resp.json()
                resp.raise_for_status()
                return response_data

    async def like_reply(self, reply_id: int) -> dict:
        """点赞回复"""
        url = f"{self.api_base}/replies/{reply_id}/like"

        logger.debug(f"[HTTP请求] POST {url}")

        async with self._create_session() as session:
            async with session.post(url) as resp:
                response_data = await resp.json()
                resp.raise_for_status()
                return response_data

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
        url = f"{self.api_base}/threads"
        params: dict[Any, Any] = {
            "page": page,
            "per_page": per_page,
            "sort": sort,
            "format": format,
        }
        if category:
            params["category"] = category

        logger.debug(f"[HTTP请求] GET {url} params={params}")

        async with self._create_session() as session:
            async with session.get(url, params=params) as resp:
                response_data = await resp.json()
                resp.raise_for_status()
                return response_data

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
        url = f"{self.api_base}/threads/search"
        params: dict[Any, Any] = {
            "q": q,
            "page": page,
            "page_size": max(1, min(page_size, 50)),
        }
        if category:
            params["category"] = category

        logger.debug(f"[HTTP请求] GET {url} params={params}")

        async with self._create_session() as session:
            async with session.get(url, params=params) as resp:
                response_data = await resp.json()
                resp.raise_for_status()
                return response_data


    async def create_thread(
        self, title: str, content: str, category: str = "chat"
    ) -> dict:
        """发布新帖"""
        url = f"{self.api_base}/threads"
        # 预处理内容：将 \n 替换为实际换行符
        content = content.replace(r"\n", "\n")
        data = {"title": title, "content": content, "category": category}

        logger.info(f"[HTTP请求] POST {url} data_keys={list(data.keys())}")

        async with self._create_session() as session:
            try:
                # 为发帖请求使用自定义超时
                async with session.post(
                    url, json=data, timeout=self.timeout_config
                ) as resp:
                    response_data = await resp.json()
                    resp.raise_for_status()
                    return response_data
            except Exception as e:
                logger.error(
                    f"[HTTP请求失败] POST {url} {type(e).__name__}: {e} ", exc_info=e
                )
                raise

    async def create_reply(self, thread_id: int, content: str) -> dict:
        """回复帖子主楼

        Args:
            thread_id: 帖子 ID
            content: 回复内容

        Returns:
            回复数据
        """
        url = f"{self.api_base}/threads/{thread_id}/replies"
        data = {"content": content}

        logger.debug(f"[HTTP请求] POST {url}")

        async with self._create_session() as session:
            async with session.post(url, json=data) as resp:
                response_data = await resp.json()
                resp.raise_for_status()
                return response_data

    async def like_thread(self, thread_id: int) -> dict:
        """点赞帖子

        Args:
            thread_id: 帖子 ID

        Returns:
            点赞结果
        """
        url = f"{self.api_base}/threads/{thread_id}/like"

        logger.debug(f"[HTTP请求] POST {url}")

        async with self._create_session() as session:
            async with session.post(url) as resp:
                response_data = await resp.json()
                resp.raise_for_status()
                return response_data

    async def follow_user(self, user_id: int) -> dict:
        """关注用户

        Args:
            user_id: 用户 ID

        Returns:
            关注结果
        """
        url = f"{self.api_base}/follows"
        data = {"user_id": user_id}

        logger.debug(f"[HTTP请求] POST {url} data={data}")

        async with self._create_session() as session:
            async with session.post(url, json=data) as resp:
                response_data = await resp.json()
                resp.raise_for_status()
                return response_data
