# AddPlanTool 使用说明

## 概述

`AddPlanTool` 是一个允许 LLM 直接添加月度计划的工具组件。通过这个工具，LLM 可以在对话中根据用户的需求自动创建月度计划，无需人工干预。

## 变更说明

### 移除的功能

以下自动生成相关的功能已被移除：

1. **PlanGenerator** - 月度计划自动生成器（位于 `generators/plan_generator.py`）
2. **PlanService.ensure_plans_for_month()** - 确保月份有计划并自动生成的方法
3. **PlanManager.ensure_plans_for_month()** - 管理器中的相应方法
4. **定时任务** - 每月自动生成计划的定时任务已从事件处理器中移除

### 新增功能

- **AddPlanTool** - LLM 可调用的工具组件，允许在对话中添加月度计划

## 工具签名

- **组件类型**: `tool`
- **工具名称**: `add_monthly_plan`
- **完整签名**: `schedule_system:tool:add_monthly_plan`

## 参数说明

| 参数名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `month` | str | 是 | - | 目标月份，格式为 YYYY-MM，例如 "2026-03" |
| `plan_text` | str | 是 | - | 计划内容描述，1-500 个字符 |
| `priority` | int | 否 | 3 | 优先级，1-5，5 最高，3 中等，1 最低 |
| `deadline` | str \| None | 否 | None | 可选的截止日期，格式为 YYYY-MM-DD |
| `tags` | list[str] \| None | 否 | None | 可选的标签列表，例如 ["学习", "工作"] |

## LLM 调用示例

LLM 可以在对话中自然地调用此工具：

```python
# 用户说："我这个月要每周运动3次"
# LLM 调用：
{
    "tool": "add_monthly_plan",
    "arguments": {
        "month": "2026-03",
        "plan_text": "每周运动3次",
        "priority": 4,
        "tags": ["健康", "运动"]
    }
}
```

```python
# 用户说："提醒我在3月31日前完成项目文档"
# LLM 调用：
{
    "tool": "add_monthly_plan",
    "arguments": {
        "month": "2026-03",
        "plan_text": "完成项目文档",
        "priority": 5,
        "deadline": "2026-03-31",
        "tags": ["工作", "文档"]
    }
}
```

## 返回值

### 成功时

```python
(True, {
    "plan_id": 123,
    "month": "2026-03",
    "plan_text": "每周运动3次",
    "priority": 4,
    "status": "已添加"
})
```

### 失败时

```python
# 参数验证错误
(False, "添加计划失败（参数错误）: 月份验证失败: 月份格式错误")

# 其他错误
(False, "添加计划失败: 数据库连接失败")
```

## 程序化调用示例

虽然此工具主要供 LLM 调用，但也可以在代码中直接使用：

```python
from src.app.plugin_system.api import component_api

# 获取工具实例
tool = component_api.get_component("schedule_system:tool:add_monthly_plan")

if tool:
    # 调用工具
    success, result = await tool.execute(
        month="2026-03",
        plan_text="每周阅读2本书",
        priority=4,
        tags=["学习", "阅读"]
    )
    
    if success:
        print(f"计划已添加: {result}")
    else:
        print(f"添加失败: {result}")
```

## 与其他组件的集成

### PlanService

`AddPlanTool` 内部调用 `PlanService.add_plan()` 方法，因此：

- 所有参数验证逻辑保持不变
- 数据库操作完全一致
- 日志记录统一管理

### 数据库

添加的计划会直接保存到 `monthly_plans` 表中，包含以下字段：

- `id`: 自动生成的唯一标识
- `target_month`: 目标月份
- `plan_text`: 计划内容
- `priority`: 优先级 (1-5)
- `status`: 状态（默认为 "active"）
- `usage_count`: 使用次数（初始为 0）
- `tags`: 标签列表
- `deadline`: 截止日期（可选）
- `created_at` / `updated_at`: 时间戳

## 配置

工具的行为受插件配置影响：

```toml
# config/plugins/schedule_system.toml
[plan]
enabled = true  # 必须启用才能使用此工具
completion_threshold = 5  # 计划自动完成阈值
```

## 权限控制

此工具尊重插件的权限设置。如果需要限制谁可以通过 LLM 添加计划，可以在插件配置中设置：

```python
# 在插件类中设置
dependent_components = ["permission_system:service:permission"]
```

## 最佳实践

1. **明确月份**: 始终使用 YYYY-MM 格式的月份
2. **合理优先级**: 使用 1-5 的优先级，避免所有计划都是最高优先级
3. **有意义的标签**: 使用标签来组织和分类计划
4. **设置截止日期**: 对于有明确时间要求的计划，建议设置 deadline
5. **简洁描述**: plan_text 应该简洁明了，避免过于冗长

## 常见问题

### Q: 工具调用失败怎么办？

A: 检查以下几点：
- 插件是否正确加载
- `PlanService` 是否初始化成功
- 参数格式是否正确
- 查看日志中的详细错误信息

### Q: LLM 何时会调用此工具？

A: 当用户在对话中表达以下意图时：
- 设定目标或计划
- 提到要做某事
- 请求添加待办事项
- 讨论未来的安排

### Q: 如何确认计划已成功添加？

A: 可以通过以下方式确认：
- 查看工具返回的 `plan_id`
- 调用 `PlanService.get_active_plans(month)` 查询
- 检查数据库中的 `monthly_plans` 表

## 日志

工具会在以下情况记录日志：

```python
# 成功添加
logger.info(f"LLM 添加月度计划成功: id={plan_id}, month={month}")

# 参数错误
logger.warning(f"添加计划失败（参数错误）: {error}")

# 其他错误
logger.error(f"添加计划失败: {error}", exc_info=True)
```

查看日志文件：`logs/schedule_system_*.log`

## 迁移指南

如果你之前依赖自动生成功能，现在需要：

1. **手动添加计划**: 通过对话告诉 LLM 你的月度计划
2. **批量导入**: 准备一个计划列表，通过 API 批量添加
3. **定期回顾**: 每月初手动回顾和添加新月份的计划

示例：

```python
# 批量添加计划
plans = [
    {"month": "2026-03", "plan_text": "每周运动3次", "priority": 4},
    {"month": "2026-03", "plan_text": "完成项目文档", "priority": 5},
    {"month": "2026-03", "plan_text": "学习新技术", "priority": 3},
]

for plan_data in plans:
    await tool.execute(**plan_data)
```

## 未来改进

可能的增强方向：

- [ ] 添加批量导入工具
- [ ] 支持从模板创建计划
- [ ] 集成 MCP (Model Context Protocol) 支持
- [ ] 添加计划冲突检测
- [ ] 支持周期性计划
