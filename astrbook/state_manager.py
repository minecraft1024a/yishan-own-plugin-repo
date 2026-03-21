"""状态管理器 - 精简版

仅管理每日配额计数，利用 AstrBook API 的 has_replied 字段避免本地状态冗余
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from src.app.plugin_system.api import storage_api
from src.kernel.logger import get_logger

if TYPE_CHECKING:
    from .plugin import AstrBotPlugin

logger = get_logger("astrbot.state", display="状态管理")

_instance: StateManager | None = None


def init_state_manager(plugin: "AstrBotPlugin", store_name: str = "astrbot") -> "StateManager":
    """初始化状态管理器单例。

    应在插件加载时调用一次，后续通过 :func:`get_state_manager` 获取实例。

    Args:
        plugin: 所属插件实例
        store_name: 存储名称

    Returns:
        初始化完成的 StateManager 实例
    """
    global _instance
    _instance = StateManager(plugin, store_name)
    logger.debug("StateManager 已初始化")
    return _instance


def get_state_manager() -> "StateManager":
    """获取状态管理器单例。

    Returns:
        已初始化的 StateManager 实例

    Raises:
        RuntimeError: 若尚未调用 :func:`init_state_manager` 则抛出
    """
    if _instance is None:
        raise RuntimeError(
            "StateManager 尚未初始化，请先在插件加载时调用 init_state_manager()"
        )
    return _instance


class StateManager:
    """精简状态管理器
    
    只管理必需的每日配额计数：
    - post_count: 今日发帖数
    - reply_count: 今日回复数
    - like_count: 今日点赞数
    
    不再管理：
    - replied_threads（API 的 has_replied 已提供）
    - browsed_threads（Dispatcher 每次重新评估即可）
    """
    
    def __init__(self, plugin: "AstrBotPlugin", store_name: str = "astrbot"):
        self.plugin = plugin
        self.store_name = store_name
    
    async def load_state(self) -> dict:
        """加载状态数据
        
        Returns:
            状态字典，结构：
            {
                "date": "2026-03-14",
                "post_count": 2,
                "reply_count": 5,
                "like_count": 8
            }
        """
        try:
            data = await storage_api.load_json(self.store_name, "agent_quota")
            today = datetime.now().date().isoformat()
            
            # 检查日期，如果是新的一天则重置计数
            if not data or data.get("date") != today:
                logger.info(f"新的一天，重置配额计数（上次: {data.get('date') if data else '无'}）")
                new_state = {
                    "date": today,
                    "post_count": 0,
                    "reply_count": 0,
                    "like_count": 0
                }
                # 立即保存新状态，避免重复初始化
                await self.save_state(new_state)
                return new_state
            
            return data
            
        except Exception as e:
            logger.error(f"加载状态失败: {e}", exc_info=True)
            # 返回默认状态
            return {
                "date": datetime.now().date().isoformat(),
                "post_count": 0,
                "reply_count": 0,
                "like_count": 0
            }
    
    async def save_state(self, state: dict) -> None:
        """保存状态数据
        
        Args:
            state: 状态字典
        """
        try:
            await storage_api.save_json(self.store_name, "agent_quota", state)
            logger.debug(f"状态已保存: {state}")
        except Exception as e:
            logger.error(f"保存状态失败: {e}", exc_info=True)
    
    async def get_today_stats(self) -> dict:
        """获取今日统计
        
        Returns:
            包含今日各项计数的字典
        """
        return await self.load_state()
    
    async def increment_count(self, field: str) -> None:
        """增加指定字段的计数
        
        Args:
            field: 字段名（post_count / reply_count / like_count）
        """
        state = await self.load_state()
        
        if field not in state:
            logger.warning(f"未知的计数字段: {field}")
            return
        
        state[field] += 1
        await self.save_state(state)
        logger.info(f"{field} 增加到 {state[field]}")
    
    async def can_post(self) -> bool:
        """检查是否还能发帖
        
        Returns:
            是否未达到每日发帖上限
        """
        state = await self.load_state()
        max_posts = self.plugin.config.agent.max_posts_per_day
        return state["post_count"] < max_posts
    
    async def can_reply(self) -> bool:
        """检查是否还能回复
        
        Returns:
            是否未达到每日回复上限
        """
        state = await self.load_state()
        max_replies = self.plugin.config.agent.max_replies_per_day
        return state["reply_count"] < max_replies
    
    async def can_like(self) -> bool:
        """检查是否还能点赞
        
        Returns:
            是否未达到每日点赞上限
        """
        state = await self.load_state()
        max_likes = self.plugin.config.agent.max_likes_per_day
        return state["like_count"] < max_likes
    
    async def get_quota_summary(self) -> str:
        """获取配额摘要（人类可读格式）
        
        Returns:
            配额摘要字符串
        """
        state = await self.load_state()
        config = self.plugin.config.agent
        
        return (
            f"📊 今日配额使用情况 ({state['date']}):\n"
            f"- 发帖: {state['post_count']}/{config.max_posts_per_day}\n"
            f"- 回复: {state['reply_count']}/{config.max_replies_per_day}\n"
            f"- 点赞: {state['like_count']}/{config.max_likes_per_day}"
        )
