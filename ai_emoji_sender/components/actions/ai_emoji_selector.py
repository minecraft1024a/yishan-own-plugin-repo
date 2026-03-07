"""AI 表情包选择器 Action

从数据库中随机抽取表情包描述，让 AI 根据聊天场景决定发送哪个表情包。
"""

import random
from typing import Annotated, cast

from src.app.plugin_system.api.log_api import get_logger
from src.app.plugin_system.api.llm_api import create_llm_request, get_model_set_by_task
from src.core.components.base import BaseAction
from src.core.components.types import ChatType
from src.kernel.llm import LLMContextManager, LLMPayload, ROLE, Text
from src.kernel.db.core.session import get_db_session
from src.core.models.sql_alchemy import Images
from ..configs.config import  Config
from sqlalchemy import select
import base64
from pathlib import Path

logger = get_logger("ai_emoji_selector")


class AIEmojiSelectorAction(BaseAction):
    """AI 表情包选择器动作
    
    功能流程：
    1. 从数据库中随机抽取最多 50 个表情包描述
    2. 将描述列表提供给 AI，让其根据当前聊天场景决定最合适的表情包
    3. 发送 AI 选中的表情包到聊天流
    
    适用场景：
    - 用户表达某种情绪时，AI 可以用合适的表情包回应
    - 聊天氛围需要活跃时，AI 可以主动发送有趣的表情包
    - 作为对话的情感补充，增强互动体验
    """

    action_name = "ai_emoji_sender"
    action_description = "从表情包库中智能选择并发送一个最符合当前场景的表情包。AI会从随机抽取的表情包中分析选择最合适的一个"
    primary_action = False  # 非主动作，可以配合其他动作使用
    chat_type = ChatType.ALL

    def __init__(self, *args, **kwargs):
        """初始化 Action 并加载配置"""
        super().__init__(*args, **kwargs)
        # 获取插件配置
        self.config = cast(Config,self.plugin.config)
        if not self.config:
            logger.warning("未找到插件配置，将使用默认值")

    async def execute(
        self,
        context_hint: Annotated[str, "当前聊天场景的描述，如'用户说了一个笑话'、'用户表示生气'、'氛围轻松愉快'等，帮助AI更好地选择表情包"] = ""
    ) -> tuple[bool, str]:
        """执行 AI 表情包选择并发送
        
        Args:
            context_hint: 场景提示（可选），帮助 AI 更好地选择表情包
            
        Returns:
            (成功与否, 结果详情)
        """
        try:
            # 获取配置的表情包数量
            emoji_count = self.config.selection.emoji_count
            
            # 1. 从数据库随机获取表情包描述
            emojis = await self._get_random_emojis(emoji_count)
            
            if not emojis:
                logger.warning("数据库中没有可用的表情包")
                return False, "数据库中没有可用的表情包"
            
            logger.info(f"获取到 {len(emojis)} 个表情包候选")
            
            # 2. 让 AI 选择最合适的表情包
            selected_emoji = await self._ai_select_emoji(emojis, context_hint)
            
            if not selected_emoji:
                logger.warning("AI 未能选择合适的表情包")
                return False, "AI 未能选择合适的表情包"
            
            logger.info(f"AI 选择了表情包：{selected_emoji['description'][:50]}")
            
            # 3. 发送表情包
            success = await self._send_emoji(selected_emoji)
            
            if success:
                return True, f"已发送表情包：{selected_emoji['description'][:50]}..."
            else:
                return False, "表情包发送失败"
                
        except Exception as e:
            logger.error(f"AI 表情包选择器执行失败: {e}", exc_info=True)
            return False, f"执行失败: {str(e)}"

    async def _get_random_emojis(self, limit: int = 50) -> list[dict]:
        """从数据库中随机获取表情包
        
        Args:
            limit: 最多获取的表情包数量
            
        Returns:
            表情包信息列表，每项包含：id, description, path, image_id
        """
        try:
            async with get_db_session() as session:
                # 查询所有类型为 emoji 且有描述的表情包
                stmt = select(Images).where(
                    Images.type == "emoji",
                    Images.description.isnot(None),
                    Images.description != ""
                )
                
                result = await session.execute(stmt)
                all_emojis = result.scalars().all()
                
                if not all_emojis:
                    logger.warning("数据库中没有表情包记录")
                    return []
                
                # 随机选择最多 limit 个
                selected_count = min(limit, len(all_emojis))
                selected_emojis = random.sample(list(all_emojis), selected_count)
                
                # 转换为字典格式并应用过滤规则
                emoji_list = []
                for emoji in selected_emojis:
                    # 应用过滤规则
                    if self.config and self.config.filter.require_description:
                        if not emoji.description or len(emoji.description) < self.config.filter.min_description_length:
                            continue
                    
                    # 检查排除关键词
                    if self.config and self.config.filter.exclude_keywords:
                        description = emoji.description or ""
                        if any(keyword in description for keyword in self.config.filter.exclude_keywords):
                            logger.debug(f"跳过包含排除关键词的表情包: {description[:30]}")
                            continue
                    
                    emoji_list.append({
                        "id": emoji.id,
                        "description": emoji.description or "无描述",
                        "path": emoji.path,
                        "image_id": emoji.image_id,
                    })
                
                logger.debug(f"从数据库中随机选择了 {len(emoji_list)} 个表情包")
                return emoji_list
                
        except Exception as e:
            logger.error(f"从数据库获取表情包失败: {e}", exc_info=True)
            return []

    async def _ai_select_emoji(
        self, 
        emojis: list[dict], 
        context_hint: str
    ) -> dict | None:
        """使用 AI 从候选表情包中选择最合适的一个
        
        Args:
            emojis: 候选表情包列表
            context_hint: 场景提示
            
        Returns:
            选中的表情包信息，失败返回 None
        """
        try:
            # 获取配置的模型任务类型
            model_task = self.config.selection.model_task
            
            # 获取 LLM 模型配置
            model_set = get_model_set_by_task(model_task)
            if not model_set:
                logger.warning(f"未配置 {model_task} LLM 模型，将随机选择表情包")
                if self.config and not self.config.selection.enable_random_fallback:
                    return None
                return random.choice(emojis)
            
            # 构建表情包列表提示词
            emoji_options = "\n".join([
                f"{i+1}. {emoji['description']}"
                for i, emoji in enumerate(emojis)
            ])
            
            # 构建提示词
            prompt = f"""你是一个表情包选择助手。请根据以下场景描述，从候选表情包中选择最合适的一个。

场景描述：{context_hint if context_hint else "用户需要一个表情包"}

候选表情包（共 {len(emojis)} 个）：
{emoji_options}

请仔细分析场景的情绪、氛围和语境，选择最符合当前场景的表情包。
只需要回复表情包的序号（1-{len(emojis)}），不要有其他内容。"""

            # 创建 LLM 请求
            context_manager = LLMContextManager(max_payloads=3)
            request = create_llm_request(
                model_set,
                "emoji_selection",
                context_manager=context_manager,
            )
            
            # 发送请求
            request.add_payload(LLMPayload(ROLE.USER, [Text(prompt)]))
            response = await request.send(stream=False)
            await response
            
            # 解析 AI 的选择
            selection_text = response.message.strip()
            if self.config and self.config.selection.log_selection_detail:
                logger.info(f"AI 原始响应: {selection_text}")
            else:
                logger.debug(f"AI 原始响应: {selection_text}")
            
            # 提取数字
            import re
            numbers = re.findall(r'\d+', selection_text)
            
            if numbers:
                selected_index = int(numbers[0]) - 1  # 转换为 0-based 索引
                
                if 0 <= selected_index < len(emojis):
                    logger.info(f"AI 选择了第 {selected_index + 1} 个表情包")
                    return emojis[selected_index]
                else:
                    logger.warning(f"AI 选择的序号超出范围: {selected_index + 1}")
                    if self.config and not self.config.selection.enable_random_fallback:
                        return None
                    return random.choice(emojis)
            else:
                logger.warning(f"无法从 AI 响应中提取序号: {selection_text}")
                if self.config and not self.config.selection.enable_random_fallback:
                    return None
                return random.choice(emojis)
                
        except Exception as e:
            logger.error(f"AI 选择表情包失败: {e}", exc_info=True)
            # 出错时根据配置决定是否随机选择
            if self.config and not self.config.selection.enable_random_fallback:
                return None
            return random.choice(emojis) if emojis else None

    async def _send_emoji(self, emoji: dict) -> bool:
        """发送表情包到聊天流
        
        Args:
            emoji: 表情包信息字典
            
        Returns:
            是否发送成功
        """
        try:
            # 读取图片文件
            file_path = Path(emoji['path'])
            
            # 如果路径不是绝对路径或不存在，尝试从 data/media_cache 查找
            if not file_path.is_absolute() or not file_path.exists():
                # 可能存储的是相对路径或哈希值，尝试在多个位置查找
                possible_paths = [
                    Path(emoji['path']),  # 原始路径
                    Path("data/media_cache/emojis") / Path(emoji['path']).name,
                    Path("data/media_cache/images") / Path(emoji['path']).name,
                    Path("data/media_cache/pending") / Path(emoji['path']).name,
                ]
                
                found = False
                for possible_path in possible_paths:
                    if possible_path.exists():
                        file_path = possible_path
                        found = True
                        logger.debug(f"找到表情包文件: {file_path}")
                        break
                
                if not found:
                    logger.warning(f"表情包文件不存在: {emoji['path']}")
                    return False
            
            # 读取文件为 base64
            with open(file_path, 'rb') as f:
                image_data = f.read()
                base64_data = base64.b64encode(image_data).decode('utf-8')
            
            # 使用无头 base64 数据发送
            # 只传递纯 base64 字符串，不带任何前缀
            base64_payload = base64_data
            
            # 使用 send_image 发送
            from src.app.plugin_system.api.send_api import send_image
            
            success = await send_image(
                image_data=base64_payload,
                stream_id=self.chat_stream.stream_id
            )
            
            if success:
                logger.info(f"表情包发送成功：{emoji['description'][:50]}")
            else:
                logger.warning(f"表情包发送失败：{emoji['description'][:50]}")
            
            return success
            
        except Exception as e:
            logger.error(f"发送表情包时出错: {e}", exc_info=True)
            return False
