# 日程表系统 - 快速开始

## 安装

1. 将插件复制到 MoFox 的 `plugins/` 目录：
```bash
cp -r schedule_system /path/to/Neo-MoFox/plugins/
```

2. 重启 MoFox：
```bash
cd /path/to/Neo-MoFox
uv run main.py
```

## 配置说明

### 基础配置

```toml
[schedule]
enabled = true                      # 是否启用日程表
generation_model = "schedule_generator"  # 模型任务名
generation_time = "23:00"           # 每日生成时间
max_retries = 3                     # 最大重试次数

[plan]
enabled = true                      # 是否启用月度计划
max_plans_per_month = 15           # 每月最大计划数
completion_threshold = 3            # 自动完成阈值
```

### 自定义指南

在 `config.toml` 中添加自定义生成指南：

```toml
[schedule]
custom_guidelines = """
生成日程时请注意：
1. 我是夜猫子，晚上更有精神
2. 工作时间：14:00-22:00
3. 每天至少安排 2 小时学习时间
"""

[plan]
custom_guidelines = """
月度计划偏好：
1. 技术学习优先
2. 每周至少运动 3 次
3. 工作与生活平衡
```

## 使用方法

### 调用 Service API

其他插件可以通过 Service API 调用：

```python
from src.app.plugin_system.api import service_api

# 获取日程服务
schedule_service = service_api.get_service("schedule_system:service:schedule")

# 获取今日日程
today_schedule = await schedule_service.get_schedule("2026-03-14")
for item in today_schedule:
    print(f"{item['time_range']}: {item['activity']}")

# 获取当前活动
current = await schedule_service.get_current_activity()
if current:
    print(f"正在进行: {current['activity']}")

# 添加日程项
item_id = await schedule_service.add_schedule_item(
    date="2026-03-14",
    time_range="16:00-17:00",
    activity="团队会议",
    priority=5,
    tags=["工作", "重要"]
)

# 重新生成日程
await schedule_service.regenerate_schedule("2026-03-15")
```

### 月度计划管理

```python
# 获取计划服务
plan_service = service_api.get_service("schedule_system:service:plan")

# 查看本月计划
plans = await plan_service.get_active_plans("2026-03")
for plan in plans:
    print(f"- {plan['plan_text']} (优先级: {plan['priority']})")

# 添加计划
plan_id = await plan_service.add_plan(
    month="2026-03",
    plan_text="完成插件系统重构",
    priority=5,
    deadline="2026-03-31",
    tags=["开发", "重要"]
)

# 标记完成
await plan_service.complete_plan(plan_id)
```

## 定时任务

插件会自动注册以下定时任务：

1. **每日日程生成**
   - 时间：每天晚上 11:00（可配置）
   - 功能：生成明日日程
   - 任务名：`schedule_system:daily_schedule_generation`

2. **月度计划生成**
   - 时间：每月 1 日凌晨 00:00
   - 功能：生成/确认本月计划
   - 任务名：`schedule_system:monthly_plan_generation`

手动触发：

```python
from src.kernel.scheduler import get_unified_scheduler

scheduler = get_unified_scheduler()

# 手动触发日程生成
await scheduler.trigger_schedule("schedule_system:daily_schedule_generation")

# 手动触发计划生成
await scheduler.trigger_schedule("schedule_system:monthly_plan_generation")
```

## 降级机制

当 LLM 生成失败时，插件会自动使用降级机制：

1. **指数退避重试**
   - 第 1 次重试：延迟 5 秒
   - 第 2 次重试：延迟 10 秒
   - 第 3 次重试：延迟 20 秒

2. **降级策略**
   - 所有重试失败后，创建空日程表
   - 标记为 `generated_by="fallback"`
   - 记录错误信息到 `generation_error` 字段

## 日志查看

日志文件位于 MoFox 的 `logs/` 目录：

```bash
# 查看日程系统日志
grep "日程系统" logs/app_*.jsonl

# 查看生成日志
grep "日程生成" logs/app_*.jsonl

# 查看错误日志
grep "ERROR" logs/app_*.jsonl | grep "schedule_system"
```

## 常见问题

### Q: 提示模型未配置？

确保在 `config/model.toml` 中添加了任务配置：

```toml
[tasks.schedule_generator]
provider = "openai"
model = "gpt-4"
```

### Q: 生成失败怎么办？

1. 检查 LLM API 配置是否正确
2. 查看日志获取详细错误信息
3. 插件会自动使用降级机制，不会完全失败

### Q: 如何修改生成时间？

编辑 `config/plugins/schedule_system/config.toml`：

```toml
[schedule]
generation_time = "22:00"  # 改为晚上 10 点
```

### Q: 如何禁用某个功能？

```toml
[schedule]
enabled = false  # 禁用日程表

[plan]
enabled = false  # 禁用月度计划
```

## 数据库

插件使用**独立的 SQLite 数据库**（`data/schedule_system/schedule.db`）：

- 与 MoFox 主数据库完全隔离
- 自动创建和管理表结构
- 使用 `PluginDatabase` 提供的标准接口

### 数据库表

- `schedule_schedules`: 日程表
- `schedule_items`: 日程项
- `schedule_monthly_plans`: 月度计划
- `schedule_activity_statistics`: 活动统计（预留）

### 查询示例

```bash
# 使用 SQLite 命令行工具
sqlite3 data/schedule_system/schedule.db

# 查看所有日程
SELECT * FROM schedule_schedules ORDER BY date DESC LIMIT 10;

# 查看今日日程项
SELECT * FROM schedule_items 
WHERE schedule_id = (SELECT id FROM schedule_schedules WHERE date = '2026-03-14');

# 查看本月计划
SELECT * FROM schedule_monthly_plans 
WHERE target_month = '2026-03' AND status = 'active';
```

### 数据库位置

**重要**：插件使用独立数据库，不在主数据库（`data/MaiBot.db`）中：

- 插件数据库：`data/schedule_system/schedule.db`
- 主程序数据库：`data/MaiBot.db`（不相关）

## 卸载

1. 从 `plugins/` 目录删除插件文件夹
2. 重启 MoFox
3. （可选）删除插件数据库：
```bash
rm -rf data/schedule_system/
```

---

**更多文档**: 查看 [README.md](README.md) 和移植方案文档。
