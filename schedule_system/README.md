# 日程表系统插件 (schedule_system)

AI 驱动的智能日程管理系统，为 Neo-MoFox 机器人提供完整的日程表和月度计划管理能力。

## ✨ 特性

- 🤖 **AI 智能生成** - 基于 LLM 自动生成合理的每日日程
- 📅 **月度计划管理** - 制定和跟踪月度目标
- 🧠 **偏好学习** - 分析用户习惯，优化日程安排
- 🔄 **自动降级** - LLM 失败时使用模板/历史数据
- ⏰ **定时任务** - 每日自动生成明日日程
- 🛠️ **完整 CRUD** - 手动管理日程和计划
- 📊 **统计分析** - 跟踪完成率和偏好分析

## 📦 安装

1. 将插件文件夹复制到 MoFox 的 `plugins/` 目录：
```bash
cp -r schedule_system /path/to/Neo-MoFox/plugins/
```

2. 配置插件（编辑 `config/plugins/schedule_system/config.toml`）

3. 重启 MoFox

## 🚀 使用方法

### Service API 调用

```python
from src.app.plugin_system.api import service_api

# 获取日程表服务
schedule_service = service_api.get_service("schedule_system:service:schedule")

# 获取今日日程
today_schedule = await schedule_service.get_schedule("2026-03-14")

# 添加日程项
item_id = await schedule_service.add_schedule_item(
    date="2026-03-14",
    time_range="14:00-15:00",
    activity="会议",
    priority=4
)

# 获取当前活动
current = await schedule_service.get_current_activity()
```

### 配置说明

```toml
[schedule]
enabled = true
generation_model = "schedule_generator"
max_retries = 3
retry_delay = 5

[plan]
enabled = true
max_plans_per_month = 15
completion_threshold = 3

[features]
enable_learning = true
enable_statistics = true
```

## 📖 API 文档

### ScheduleService

- `get_schedule(date: str)` - 获取指定日期的日程
- `get_current_activity()` - 获取当前正在进行的活动
- `add_schedule_item(...)` - 添加日程项
- `update_schedule_item(item_id, **updates)` - 更新日程项
- `delete_schedule_item(item_id)` - 删除日程项
- `regenerate_schedule(date)` - 重新生成日程

### PlanService

- `get_active_plans(month: str)` - 获取活跃计划
- `add_plan(...)` - 添加月度计划
- `complete_plan(plan_id)` - 完成计划
- `cancel_plan(plan_id)` - 取消计划
- `update_plan(plan_id, **updates)` - 更新计划

## 🏗️ 架构说明

```
schedule_system/
├── plugin.py              # 插件入口
├── config.py             # 配置系统
├── models.py             # 数据库模型
├── database.py           # 数据库访问层（封装所有数据库操作）
├── services/             # Service 层
│   ├── schedule_service.py
│   └── plan_service.py
├── managers/             # 业务逻辑层
│   ├── schedule_manager.py
│   └── plan_manager.py
├── generators/           # LLM 生成器
│   ├── schedule_generator.py
│   └── plan_generator.py
└── event_handlers/       # 事件处理
    └── schedule_init_handler.py
```

### 数据库架构

插件使用 **独立的 SQLite 数据库**（`data/schedule_system/schedule.db`），通过 `PluginDatabase` 管理：

- 与主程序数据库完全隔离
- 使用标准的 `CRUDBase`/`QueryBuilder`/`AggregateQuery` 接口
- 所有数据库操作封装在 `database.py` 中
- 自动创建表和管理连接

## 🔧 开发指南

### 运行测试

```bash
# 在 Neo-MoFox 根目录
pytest test/plugins/schedule_system/
```

### 代码风格

- 遵循 PEP 8
- 所有函数必须有类型注解
- 所有公开 API 必须有文档字符串
- 使用 `ruff check` 检查代码

## 📄 许可证

本插件采用 GPL-3.0 许可证。详见 [LICENSE](./LICENSE) 文件。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 🔗 相关链接

- [Neo-MoFox 主仓库](https://github.com/MoFox-Studio/Neo-MoFox)
- [插件开发文档](https://github.com/MoFox-Studio/docs)
- [问题反馈](https://github.com/MoFox-Studio/my_plugin/issues)

---

**版本**: 2.0.0  
**作者**: MoFox Team  
**更新日期**: 2026-03-14
