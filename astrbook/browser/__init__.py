"""帖子浏览器模块

多轮上下文 Bot 浏览帖子功能，采用双 AI 协作架构：
- Dispatcher AI: 分析帖子列表，选择要浏览的帖子
- Reader AI: 深度阅读帖子，决定互动动作
"""

from .browser import ThreadBrowser
from .dispatcher import DispatcherAI
from .reader import ReaderSession
from .executor import ActionExecutor
from .prompts import register_prompts

__all__ = [
    "ThreadBrowser",
    "DispatcherAI",
    "ReaderSession",
    "ActionExecutor",
    "register_prompts",
]
