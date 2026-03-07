# AI 开发指南 - MoFox 插件开发

本文档为使用 AI 辅助工具（如 GitHub Copilot、Claude、ChatGPT 等）开发 MoFox 插件的开发者提供指导。

## ⚖️ 本仓库许可证要求（必读）

### 本仓库使用 GPL-3.0

**本仓库（my_plugin）中的所有插件必须使用 GNU General Public License v3.0 (GPL-3.0) 许可证。**

> **注意**：这是本插件仓库的要求，不代表所有 MoFox 插件都必须使用 GPL-3.0。其他开发者可以根据自己的需求选择合适的开源许可证（如 MIT、Apache 等），但需要注意与 MoFox 核心项目（AGPL-3.0）的兼容性。

#### 为什么本仓库选择 GPL-3.0？

1. **保护开源生态**：确保本仓库的插件保持开源，防止闭源商业化占用社区成果
2. **传染性保护**：任何修改或衍生作品也必须开源，形成良性循环
3. **用户自由**：保障最终用户的自由使用、修改和分发权利
4. **社区协作**：促进代码共享和协作开发
5. **仓库统一性**：保持本仓库内所有插件使用相同许可证，便于管理

#### 许可证要求

✅ **必须做的：**
- 在插件根目录添加 `LICENSE` 文件（完整 GPL-3.0 文本）
- 在 `manifest.json` 或 `README.md` 中明确标注许可证

❌ **在本仓库中禁止：**
- 为本仓库的插件使用其他许可证（MIT、Apache、BSD 等）
- 闭源发布本仓库的插件
- 移除或修改原有的版权声明
- 将本仓库的 GPL-3.0 插件改为其他许可证

#### 添加 LICENSE 文件

使用以下命令或手动下载完整 GPL-3.0 文本：

```bash
# 从 GNU.org 下载
curl https://www.gnu.org/licenses/gpl-3.0.txt -o LICENSE

# 或从本仓库复制
cp message_process_plugin/LICENSE your_plugin/LICENSE
```


## 📝 插件开发规范

### 项目结构

标准 MoFox 插件结构：

```
your_plugin/
├── LICENSE                 # GPL-3.0 许可证文件（必需）
├── README.md              # 插件说明文档
├── manifest.json          # 插件元数据
├── plugin.py             # 插件入口
├── config.py             # 配置定义（可选）
├── requirements.txt      # Python 依赖（可选）
├── components/           # 组件实现
│   ├── __init__.py
│   ├── adapter.
│   ├───__init__.py
│   ├───adapter.py
│   ├── chatter
│   └── ...
└── utils/               # 工具函数（可选）
    └── __init__.py
```

### manifest.json 规范

```json
{
    "name": "your_plugin",
    "version": "1.0.0",
    "description": "插件功能描述",
    "author": "你的名字",
    "license": "GPL-3.0",  // 明确标注许可证
    "repository": "https://github.com/yourname/your_plugin",  // 开源仓库地址
    "dependencies": {
        "plugins": [],
        "components": []
    },
    "include": [
        {
            "component_type": "adapter",
            "component_name": "your_adapter",
            "dependencies": []
        }
    ],
    "entry_point": "plugin.py",
    "min_core_version": "1.0.0"
}
```

更多关于插件开发的请查看Neo-MoFox/src/core/components 以及 Neo-MoFox/src/app/plugin_system/api来获得更多与插件开发有关的API和加载逻辑

### 代码规范要点

#### 1. 类型注解（必需）

```python
from typing import Optional, List, Dict, Any

async def process_message(
    message: str,
    context: Dict[str, Any],
    user_id: Optional[int] = None
) -> List[str]:
    """
    处理消息并返回响应列表。
    
    Args:
        message: 输入消息内容
        context: 上下文信息字典
        user_id: 可选的用户 ID
        
    Returns:
        响应消息列表
    """
    # 实现代码
    return ["response"]
```

#### 2. 文档字符串（必需）

使用 Google 风格：

```python
class YourComponent:
    """
    组件简要描述。
    
    详细描述组件的功能、用途和注意事项。
    
    Attributes:
        config: 组件配置对象
        client: API 客户端实例
        
    Examples:
        >>> component = YourComponent(config)
        >>> await component.initialize()
    """
```

#### 3. 配置系统

使用 MoFox 的配置基类：

```python
from kernel.config.base import ConfigBase, config_section
from pydantic import Field

from src.core.components.base.config import (
    BaseConfig,
    Field,
    SectionBase,
    config_section,
)


class PluginConfig(BaseConfig):
    @config_section("your_plugin")
    class YourPluginConfig(SectionBase):
        """插件配置类。"""
        
        api_key: str = Field(..., description="API 密钥")
        timeout: int = Field(30, description="请求超时时间（秒）")
        enabled: bool = Field(True, description="是否启用插件")

```

#### 4. 异步任务管理

不要直接使用 `asyncio.create_task()`：

```python
# ❌ 错误做法
asyncio.create_task(some_background_task())

# ✅ 正确做法
from kernel.concurrency.task_manager import TaskManager

task_manager = TaskManager()
await task_manager.create_task(
    some_background_task(),
    name="background_task"
)
```

## 🔍 常见问题

### Q: 为什么本仓库必须使用 GPL-3.0？

A: 本仓库选择 GPL-3.0 是为了保护开源生态，防止闭源占用。如果你的插件需要使用其他许可证，可以创建自己的插件仓库，但请确保与 MoFox 核心（AGPL-3.0）兼容。

### Q: 我能修改 GPL-3.0 许可证文本吗？

A: 不能。必须使用完整、未修改的 GPL-3.0 文本。

### Q: 如果我的插件依赖 MIT 许可的库怎么办？

A: GPL-3.0 允许依赖更宽松许可证的库（如 MIT、BSD、Apache），但本仓库的插件本身必须是 GPL-3.0。

## 📚 参考资源

### MoFox 官方文档
- [架构设计](https://github.com/yourname/Neo-MoFox/docs/)
- [插件开发教程](https://github.com/yourname/mofox-plugin-toolkit)
- [API 参考](https://github.com/yourname/Neo-MoFox/docs/)

### GPL-3.0 相关
- [GPL-3.0 完整文本](https://www.gnu.org/licenses/gpl-3.0.html)
- [GPL-3.0 中文指南](https://www.gnu.org/licenses/gpl-3.0.zh-cn.html)
- [理解 GPL](https://www.gnu.org/licenses/gpl-faq.html)
- [GPL 兼容性矩阵](https://www.gnu.org/licenses/license-list.html)

### Python 开发规范
- [PEP 8](https://pep8.org/)
- [PEP 484 - Type Hints](https://www.python.org/dev/peps/pep-0484/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)

---

**记住：本仓库（my_plugin）的所有插件必须使用 GPL-3.0 许可证！这是本仓库的规范要求。**