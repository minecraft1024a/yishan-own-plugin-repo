# AI 表情包选择器插件

## 功能简介

AI 表情包选择器插件提供智能表情包选择功能。当 AI 认为需要发送表情包时，会从表情包库中随机抽取最多 50 个候选项，然后由 AI 分析当前聊天场景，选择最合适的表情包发送。

## 主要特性

- 🎯 **智能选择**：AI 根据聊天场景自动分析并选择最合适的表情包
- 🎲 **随机候选**：每次从数据库随机抽取最多 50 个表情包作为候选
- 🔄 **自动识别**：依赖 MediaManager 的 VLM 识别功能，自动为表情包生成描述
- 💬 **场景感知**：支持传入场景提示，让 AI 做出更精准的选择

## 工作流程

1. **获取候选**：从数据库中随机抽取最多 50 个已识别的表情包
2. **AI 分析**：将表情包描述列表提供给 LLM，让其根据场景分析
3. **智能选择**：AI 返回最合适的表情包序号
4. **自动发送**：发送选中的表情包到聊天流

## 使用方式

### 在对话中触发

AI 可以在对话过程中主动调用此 action：

```
用户：今天心情真好！
AI：【调用 ai_emoji_selector action，context_hint="用户心情愉快"】
```

### Tool Calling 参数

```python
{
    "context_hint": "用户说了一个笑话"  # 可选，帮助 AI 更好地选择
}
```

## 依赖要求

- ✅ 数据库中需有已识别的表情包（type='emoji'，且有 description）
- ✅ 需要配置可用的 LLM 模型（task='chat'）
- ✅ MediaManager 的 VLM 功能需正常运行

## 配置说明

插件支持灵活的配置选项。配置文件位于：`config/plugins/ai_emoji_selector/config.toml`

### 表情包选择配置 [selection]

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `emoji_count` | int | 50 | 每次从数据库中随机抽取的表情包数量（范围：1-200，建议 20-100） |
| `model_task` | str | "utils" | 使用的 LLM 模型任务类型（需在 model.toml 中配置） |
| `enable_random_fallback` | bool | true | 当 AI 选择失败时，是否随机选择一个表情包作为备选 |
| `log_selection_detail` | bool | false | 是否记录详细的 AI 选择过程（用于调试） |

### 表情包过滤配置 [filter]

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `require_description` | bool | true | 是否要求表情包必须有描述才能被选择 |
| `min_description_length` | int | 2 | 表情包描述的最小长度（字符数） |
| `exclude_keywords` | list | [] | 排除包含这些关键词的表情包（如 ["广告", "二维码"]） |

### 配置示例

```toml
# config/plugins/ai_emoji_selector/config.toml

[selection]
emoji_count = 50
model_task = "utils"
enable_random_fallback = true
log_selection_detail = false

[filter]
require_description = true
min_description_length = 2
exclude_keywords = ["广告", "二维码", "推广"]
```

### 模型配置

在 `config/model.toml` 中配置对应的模型任务：

```toml
# 快速工具模型（用于表情包选择等轻量任务）
[[task_models]]
task = "utils"
provider = "openai"
model = "gpt-4o-mini"
max_tokens = 100
temperature = 0.3
```

## 依赖要求

### 场景 1：用户表达情绪

```
用户：哈哈哈笑死我了
AI：【调用 ai_emoji_selector，context_hint="用户大笑"】
→ AI 选择并发送"捧腹大笑"的表情包
```

### 场景 2：氛围活跃

```
用户：今天吃什么好呢？
AI：可以试试火锅哦~ 【调用 ai_emoji_selector，context_hint="推荐美食，氛围轻松"】
→ AI 选择并发送"馋嘴流口水"的表情包
```

### 场景 3：安慰用户

```
用户：唉，今天又加班了...
AI：辛苦了！【调用 ai_emoji_selector，context_hint="安慰用户疲惫"】
→ AI 选择并发送"抱抱安慰"的表情包
```

## 技术细节

### 数据库查询

插件从 `Images` 表查询满足以下条件的记录：
- `type = 'emoji'`
- `description IS NOT NULL AND description != ''`

### AI 提示词设计

```
你是一个表情包选择助手。请根据以下场景描述，从候选表情包中选择最合适的一个。

场景描述：{context_hint}

候选表情包（共 N 个）：
1. [表情包描述1]
2. [表情包描述2]
...

只需要回复表情包的序号（1-N），不要有其他内容。
```

### 容错机制

- 如果 LLM 不可用，自动降级为随机选择
- 如果 AI 返回格式错误，自动随机选择备用表情包
- 如果文件路径不存在，会在多个可能位置查找

## 版本信息

- **版本**：1.0.0
- **作者**：MoFox Team
- **最低核心版本**：1.0.0

## 注意事项

⚠️ **首次使用前**：确保表情包已通过 VLM 识别生成描述，否则数据库中可能没有可用的表情包。

⚠️ **性能考虑**：每次调用会进行数据库查询和 LLM 推理，建议避免频繁调用。

⚠️ **文件路径**：表情包文件默认存储在 `data/media_cache/emojis/` 目录。

本项目基于 GPL-v3.0 许可证开源,详见 [LICENSE](./LICENSE) 文件。