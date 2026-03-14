# UpdateScheduleItemTool 使用说明

## 概述

`UpdateScheduleItemTool` 是一个允许 LLM 更新已有日程项的工具组件。通过这个工具，LLM 可以在对话中根据用户的需求修改日程的活动描述或优先级，但**不能修改时间、日期等其他属性**。

## 工具签名

- **组件类型**: `tool`
- **工具名称**: `update_schedule_item`
- **完整签名**: `schedule_system:tool:update_schedule_item`

## 参数说明

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `item_id` | int | 是 | - | 要更新的日程项 ID |
| `activity` | str \| None | 否 | None | 新的活动描述，1-200 个字符 |
| `priority` | int \| None | 否 | None | 新的优先级，1-5，5 最高，3 中等，1 最低 |

**注意**: 必须至少提供 `activity` 或 `priority` 中的一个参数。

## LLM 调用示例

### 场景 1: 只更新活动描述

```python
# 用户说："把下午的会议改成线上会议"
# LLM 调用：
{
    "tool": "update_schedule_item",
    "arguments": {
        "item_id": 123,
        "activity": "团队会议（线上）"
    }
}
```

### 场景 2: 只更新优先级

```python
# 用户说："把那个会议标记为高优先级"
# LLM 调用：
{
    "tool": "update_schedule_item",
    "arguments": {
        "item_id": 123,
        "priority": 5
    }
}
```

### 场景 3: 同时更新描述和优先级

```python
# 用户说："把下午的会议改成紧急会议，标为最高优先级"
# LLM 调用：
{
    "tool": "update_schedule_item",
    "arguments": {
        "item_id": 123,
        "activity": "紧急团队会议",
        "priority": 5
    }
}
```

## 返回值

### 成功时

```python
(True, {
    "item_id": 123,
    "updated_fields": {
        "activity": "团队会议（线上）",
        "priority": 5
    },
    "status": "已更新"
})
```

### 失败时

```python
# 参数错误
(False, "活动描述必须在 1-200 个字符之间")
(False, "优先级必须在 1-5 之间")
(False, "必须至少提供 activity 或 priority 中的一个参数")

# 找不到日程项
(False, "更新日程项失败: 可能找不到 ID=123 的日程项")

# 其他错误
(False, "更新日程项失败: 数据库连接失败")
```

## 程序化调用示例

```python
from src.app.plugin_system.api import component_api

# 获取工具实例
tool = component_api.get_component("schedule_system:tool:update_schedule_item")

if tool:
    # 更新活动描述
    success, result = await tool.execute(
        item_id=123,
        activity="团队会议（改为明天）"
    )
    
    # 更新优先级
    success, result = await tool.execute(
        item_id=123,
        priority=5
    )
    
    # 同时更新
    success, result = await tool.execute(
        item_id=123,
        activity="紧急会议",
        priority=5
    )
```

## 限制说明

### ✅ 可以更新的字段

- `activity`: 活动描述（1-200 字符）
- `priority`: 优先级（1-5）

### ❌ 不能更新的字段

- `time_range`: 时间范围（如需修改时间，请删除后重新添加）
- `date`: 日期（如需修改日期，请删除后重新添加）
- `tags`: 标签（如需修改标签，请删除后重新添加）
- `is_completed`: 完成状态（应通过其他方式标记完成）

## 与其他组件的集成

### ScheduleService

`UpdateScheduleItemTool` 内部调用 `ScheduleService.update_schedule_item()` 方法，但只传递允许的字段（`activity` 和 `priority`）。

### 数据库

更新会修改 `schedule_items` 表中对应记录的：
- `activity` 字段
- `priority` 字段
- `updated_at` 字段（自动更新）

## 典型使用流程

### 流程 1: 修改活动描述

```
用户: "把下午的会议改成线上会议"
  ↓
LLM: 查询当前日程 → 找到对应项 ID
  ↓
LLM: 调用 update_schedule_item(item_id=123, activity="团队会议（线上）")
  ↓
系统: 更新数据库 → 返回成功
  ↓
LLM: "好的，已将下午的会议更新为线上会议"
```

### 流程 2: 提升优先级

```
用户: "这个会议很重要，标记为高优先级"
  ↓
LLM: 识别日程项 ID
  ↓
LLM: 调用 update_schedule_item(item_id=123, priority=5)
  ↓
系统: 更新优先级 → 返回成功
  ↓
LLM: "好的，已将该会议标记为最高优先级"
```

## 最佳实践

1. **明确 ID**: 在更新前确保知道正确的 `item_id`
2. **简洁描述**: 活动描述应简洁明了，不超过 200 字符
3. **合理优先级**: 避免所有事项都是最高优先级
4. **验证结果**: 检查返回值确认更新成功
5. **错误处理**: 如果 ID 不存在，提示用户确认或查询最新日程

## 常见问题

### Q: 为什么只能更新文字和优先级？

A: 这是设计上的限制，因为：
- 时间修改可能导致日程冲突
- 日期修改可能影响整体规划
- 标签系统需要更复杂的验证
- 如需修改这些字段，建议删除后重新创建

### Q: 如何获取 item_id？

A: 可以通过以下方式：
```python
# 获取今天的日程
schedule = await schedule_service.get_schedule("2026-03-14")
for item in schedule:
    print(f"ID: {item['id']}, 活动: {item['activity']}")
```

### Q: 更新失败怎么办？

A: 检查以下几点：
- 确认 `item_id` 是否存在
- 验证参数格式是否正确
- 检查服务是否正常运行
- 查看日志获取详细错误信息

### Q: 可以同时更新多个日程项吗？

A: 不可以，每次调用只能更新一个日程项。如需批量更新，需要多次调用。

## 日志

工具会在以下情况记录日志：

```python
# 成功更新
logger.info(f"LLM 更新日程项成功: id={item_id}, updates={updates}")

# 参数错误
logger.warning(f"活动描述必须在 1-200 个字符之间")
logger.warning(f"优先级必须在 1-5 之间")

# 更新失败
logger.warning(f"更新日程项失败: 可能找不到 ID={item_id} 的日程项")

# 其他错误
logger.error(f"更新日程项失败: {error}", exc_info=True)
```

查看日志文件：`logs/schedule_system_*.log`

## 配合使用的其他工具

- `add_monthly_plan`: 添加月度计划
- `get_schedule` (Service API): 查询日程
- `delete_schedule_item` (Service API): 删除日程项

## 示例对话

```
用户: 我下午的会议能改成线上吗？

AI: [查询今天的日程]
    好的，我看到你下午 14:00-15:00 有个团队会议。
    [调用 update_schedule_item(item_id=123, activity="团队会议（线上）")]
    已经帮你改成线上会议了。

用户: 这个会议很重要，标记一下

AI: [调用 update_schedule_item(item_id=123, priority=5)]
    好的，已将该会议标记为最高优先级。
```

## 未来改进

可能的增强方向：

- [ ] 支持批量更新多个日程项
- [ ] 支持更多字段的安全更新
- [ ] 添加更新历史记录
- [ ] 支持条件更新（例如：只有未完成的才能更新）
- [ ] 添加更新前的确认机制
