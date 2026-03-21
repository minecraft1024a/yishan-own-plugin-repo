# sleep_wakeup_plugin

基于离散状态机的睡眠/苏醒插件：
- 困倦值 `0~100` 连续变化；
- 状态仅有 `awake/sleeping` 两种；
- 困倦值到达 `100` 自动进入睡眠；
- 困倦值到达 `0` 触发 guardian 决策（可赖床）；
- 睡眠状态下可阻挡消息事件。

## 配置重点

- `timing.sleep_target_time`: 入睡时间点（第一个时间点）
- `timing.wake_target_time`: 苏醒时间点（第二个时间点）
- `timing.sleep_window_minutes`: 入睡窗口（第一个时间窗口）
- `timing.wake_window_minutes`: 苏醒窗口（第二个时间窗口）

插件会在 `on_plugin_loaded` 启动周期任务，按照 `timing.update_interval_seconds` 持续更新困倦值并写入 JSON 存储。

## 持久化

- JSON Store 命名空间：`sleep_wakeup_plugin`
- 默认状态键：`runtime_state`
- 存储内容包含：困倦值、角色状态、守护触发次数、赖床次数、历史记录、睡眠报告。

## License

本插件遵循 GPL-3.0，见 `LICENSE`。
