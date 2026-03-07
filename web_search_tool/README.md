# Web Search Tool Plugin

网络搜索工具插件，为 Neo-MoFox 提供强大的网络搜索功能。

## 功能特性

### 🔍 多搜索引擎支持

| 引擎名称 | 类型 | 需要 API 密钥 | 特点 |
|---------|------|--------------|------|
| **DuckDuckGo** | 免费 | ❌ | 注重隐私，无需配置即可使用 |
| **Bing** | 免费 | ❌ | 微软搜索，结果准确 |
| **Exa** | API | ✅ | AI 驱动，语义搜索 |
| **Tavily** | API | ✅ | 为 AI 优化的搜索引擎 |
| **Metaso** | API | ✅ | 中文搜索优化 |
| **Serper** | API | ✅ | Google 搜索 API |
| **SearXNG** | 自托管 | ❌ | 元搜索引擎，需要自行部署 |

### 🛠️ 两种组件类型

#### 1. Tool 组件 - `web_search`
供 LLM 直接调用的工具，用于：
- 实时获取最新信息
- 验证事实和数据
- 查找具体内容
- 自动决策何时使用搜索

#### 2. Service 组件 - `web_search`
供其他插件调用的服务接口，提供：
- 程序化搜索功能
- 多种搜索策略
- 引擎状态检查
- 灵活的参数控制

### 📋 搜索策略

- **single** - 单引擎搜索（默认）
- **parallel** - 并行搜索多引擎，聚合结果
- **fallback** - 回退策略，失败时尝试下一个

## 安装配置

### 1. 启用插件

在插件配置目录中编辑 `web_search_tool/config.toml`：

```toml
[plugin]
enabled = true
version = "1.0.0"

[components]
enable_web_search_tool = true      # 启用 Tool 组件（供 LLM 调用）
enable_web_search_service = true   # 启用 Service 组件（供插件调用）
```

### 2. 配置搜索引擎

#### 使用免费引擎（无需配置）

默认启用 DuckDuckGo，无需额外配置：

```toml
[search]
default_engine = "ddg"
enabled_engines = ["ddg", "bing"]
search_strategy = "single"
max_results = 10
```

#### 配置 API 密钥

如需使用高级搜索引擎，需配置 API 密钥：

```toml
[api_keys]
exa_api_key = "your_exa_api_key_here"
tavily_api_key = "your_tavily_api_key_here"
metaso_api_key = "your_metaso_api_key_here"
serper_api_key = "your_serper_api_key_here"
```

获取 API 密钥：
- **Exa**: https://exa.ai/
- **Tavily**: https://tavily.com/
- **Metaso**: https://metaso.cn/
- **Serper**: https://serper.dev/

### 3. 配置代理（可选）

```toml
[proxy]
enable_proxy = true
http_proxy = "http://proxy.example.com:8080"
https_proxy = "http://proxy.example.com:8080"
socks5_proxy = "socks5://proxy.example.com:1080"
```

### 4. 配置 SearXNG（可选）

如果使用自托管的 SearXNG：

```toml
[searxng]
base_url = "http://localhost:8080"
```

## 使用方法

### Tool 组件使用

Tool 组件会自动注册到 LLM 可用工具列表，LLM 会在需要时自动调用：

```python
# LLM 会在需要时自动调用，无需手动干预
# 用户: "2024年诺贝尔物理学奖得主是谁？"
# LLM: [自动调用 web_search tool]
```

Tool Schema（自动生成）：
```json
{
  "type": "function",
  "function": {
    "name": "web_search",
    "description": "联网搜索工具...",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "要搜索的关键词或问题"
        },
        "num_results": {
          "type": "integer",
          "description": "期望返回的搜索结果数量"
        },
        "time_range": {
          "type": "string",
          "description": "搜索时间范围：'any', 'week', 'month'"
        }
      },
      "required": ["query"]
    }
  }
}
```

### Service 组件使用

在其他插件中调用搜索服务：

```python
from src.core.managers import get_service_manager

# 获取服务
service_manager = get_service_manager()
search_service = service_manager.get_service("web_search_tool:service:web_search")

# 基本搜索
results = await search_service.search("Python 3.12 新特性")
print(results["content"])

# 指定引擎
results = await search_service.search(
    query="AI 最新进展",
    num_results=10,
    engine="ddg"
)

# 使用并行策略
results = await search_service.search(
    query="量子计算突破",
    strategy="parallel"
)

# 检查可用引擎
available = await search_service.get_available_engines()
print(f"可用引擎: {available}")

# 检查引擎状态
status = await search_service.check_engine_status("ddg")
print(status)
```

更多使用示例请查看 `services/USAGE_EXAMPLES.py`。

## API 参考

### SearchService

#### `search(query, num_results=5, time_range="any", engine=None, strategy=None)`

执行网络搜索。

**参数：**
- `query` (str): 搜索查询
- `num_results` (int): 返回结果数量
- `time_range` (str): 时间范围 ('any', 'week', 'month')
- `engine` (str | None): 指定引擎
- `strategy` (str | None): 搜索策略

**返回：**
```python
{
    "type": "web_search_result",
    "content": "格式化的搜索结果",
    "query": "原始查询",
    "num_results": 5,
    "engine_used": "ddg"  # 仅 single/fallback 策略
}
```

#### `get_available_engines()`

获取所有可用的搜索引擎列表。

**返回：** `list[str]`

#### `check_engine_status(engine_name)`

检查指定搜索引擎的状态。

**返回：**
```python
{
    "engine": "ddg",
    "exists": True,
    "available": True,
    "type": "DDGSearchEngine"
}
```

## 高级配置

### 搜索策略对比

| 策略 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **single** | 快速，省资源 | 单一来源 | 一般查询 |
| **parallel** | 结果丰富，去重 | 慢，消耗 API 配额 | 重要查询 |
| **fallback** | 可靠性高 | 可能较慢 | 稳定性优先 |

### 性能优化建议

1. **缓存利用**：搜索结果会自动缓存，避免重复查询
2. **结果数量**：建议设置 5-10 条，避免过多
3. **引擎选择**：
   - 日常使用：DuckDuckGo/Bing（免费）
   - 高质量结果：Exa/Tavily（需付费）
   - 中文优化：Metaso

## 故障排除

### 常见问题

**Q: 搜索总是失败？**
- 检查网络连接
- 确认引擎配置正确
- 查看日志了解具体错误

**Q: API 引擎不可用？**
- 检查 API 密钥是否正确配置
- 确认 API 配额未用完
- 验证 API 密钥权限

**Q: 代理无法使用？**
- 确认代理地址格式正确
- 测试代理连接是否正常
- 检查代理是否支持 HTTPS

**Q: SearXNG 连接失败？**
- 确认 SearXNG 服务正在运行
- 检查 base_url 配置
- 验证网络可达性

## 开发指南

### 添加新搜索引擎

1. 在 `engines/` 目录创建新引擎文件
2. 继承 `BaseSearchEngine` 基类
3. 实现 `search()` 和 `is_available()` 方法
4. 在配置中添加相关设置
5. 在 `WebSearchConfig` 中注册

示例：
```python
from .base import BaseSearchEngine

class MySearchEngine(BaseSearchEngine):
    def __init__(self, config):
        super().__init__(config)
        # 初始化
    
    async def search(self, query, num_results, time_range):
        # 实现搜索逻辑
        pass
    
    def is_available(self):
        # 检查可用性
        return True
```

## 更新日志

### 1.0.0 (2026-02-15)
- ✨ 初始版本发布
- 🔍 支持 7 种搜索引擎
- 🛠️ 提供 Tool 和 Service 两种组件
- 📋 支持 3 种搜索策略
- 🔧 完善的配置系统
- 📖 详细的文档和示例

## 许可证

GPL-V3

## 贡献

欢迎提交 Issue 和 Pull Request！

## 相关链接

- [Neo-MoFox 官网](https://github.com/MoFox-Studio/Neo-MoFox)
- [插件开发文档](https://docs.mofox-sama.com/docs/development/)
