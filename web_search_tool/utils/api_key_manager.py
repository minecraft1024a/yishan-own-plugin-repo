"""
API密钥管理器，提供轮询机制
"""

import itertools

from src.kernel.logger import get_logger

logger = get_logger("api_key_manager")


class APIKeyManager:
    """
    API密钥管理器，支持轮询机制
    只管理 API key，客户端创建由调用方自行处理
    """

    def __init__(self, api_keys: list[str], service_name: str = "Unknown"):
        """
        初始化API密钥管理器

        Args:
            api_keys: API密钥列表
            service_name: 服务名称，用于日志记录
        """
        self.service_name = service_name
        self.api_keys: list[str] = []
        self.key_cycle: itertools.cycle | None = None

        if api_keys:
            # 过滤有效的API密钥，排除None、空字符串、"None"字符串等
            valid_keys = [
                key.strip() for key in api_keys
                if isinstance(key, str) and key.strip() and key.strip().lower() not in ("none", "null", "")
            ]

            if valid_keys:
                self.api_keys = valid_keys
                self.key_cycle = itertools.cycle(self.api_keys)
                logger.info(f"✅ {service_name} 成功加载 {len(valid_keys)} 个 API 密钥")
            else:
                logger.warning(f"⚠️  {service_name} API Keys 配置无效（包含None或空值），{service_name} 功能将不可用")
        else:
            logger.warning(f"⚠️  {service_name} API Keys 未配置，{service_name} 功能将不可用")

    def is_available(self) -> bool:
        """检查是否有可用的API密钥"""
        return bool(self.api_keys and self.key_cycle)

    def get_next_key(self) -> str | None:
        """获取下一个API密钥（轮询）"""
        if not self.is_available():
            return None

        assert self.key_cycle is not None
        return next(self.key_cycle)

    def get_key_count(self) -> int:
        """获取可用API密钥数量"""
        return len(self.api_keys)
    
    def get_all_keys(self) -> list[str]:
        """获取所有API密钥"""
        return self.api_keys.copy()


def create_api_key_manager_from_config(
    config_keys: list[str] | str | None, service_name: str
) -> APIKeyManager:
    """
    从配置创建API密钥管理器的便捷函数

    Args:
        config_keys: 从配置读取的API密钥（可以是单个密钥字符串或密钥列表）
        service_name: 服务名称

    Returns:
        API密钥管理器实例
    """
    # 统一处理为列表
    if isinstance(config_keys, str):
        api_keys = [config_keys] if config_keys.strip() else []
    elif isinstance(config_keys, list):
        api_keys = config_keys
    else:
        api_keys = []
    
    return APIKeyManager(api_keys, service_name)
