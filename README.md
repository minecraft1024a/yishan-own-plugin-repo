# MoFox 插件集合

这是一个 [Neo-MoFox](https://github.com/yourusername/Neo-MoFox) 机器人的插件集合仓库，包含多个功能丰富、实用的社区插件。

## 📦 插件列表

### 1. AI 表情包选择器 (ai_emoji_sender)
智能表情包选择插件，让 AI 根据聊天场景自动选择最合适的表情包发送。

**主要特性：**
- 🎯 智能分析聊天场景
- 🎲 随机抽取候选表情包
- 🔄 依赖 MediaManager VLM 识别
- 💬 支持场景提示

[详细文档](./ai_emoji_sender/README.md)

### 2. AstrBot 论坛集成 (astrbook)
将 MoFox 机器人与 AstrBot 论坛平台深度集成。

**主要特性：**
- ✅ 自动回复论坛通知
- ✅ 定时发布优质内容
- ✅ LLM 智能分类
- ✅ 社交互动功能

[详细文档](./astrbook/README.md)

### 3. 消息处理插件 (message_process_plugin)
增强型消息处理能力。

[详细文档](./message_process_plugin/README.md)

### 4. 网页搜索工具 (web_search_tool)
为机器人提供网页搜索能力。

[详细文档](./web_search_tool/README.md)

## 🚀 快速开始

### 环境要求

- Python >= 3.11
- Neo-MoFox >= 1.0.0
- uv (推荐) 或 pip

### 安装插件

1. **克隆仓库**
```bash
git clone https://github.com/yourusername/my_plugin.git
cd my_plugin
```

2. **复制插件到 MoFox**
```bash
# 将需要的插件文件夹复制到 MoFox 的 plugins 目录
cp -r ai_emoji_sender /path/to/Neo-MoFox/plugins/
cp -r astrbook /path/to/Neo-MoFox/plugins/
```

3. **配置插件**
```bash
# 编辑对应插件的配置文件
# 配置文件位于: Neo-MoFox/config/plugins/<plugin_name>/config.toml
```

4. **重启 MoFox**
```bash
cd /path/to/Neo-MoFox
uv run main.py
```

## 📖 开发指南

如果你想开发自己的 MoFox 插件，请参考：

- [Neo-MoFox 官方文档](https://github.com/yourusername/Neo-MoFox/tree/main/docs)
- [插件开发教程](https://github.com/yourusername/mofox-plugin-toolkit)

## 📄 许可证

本仓库中的所有插件均采用 **GNU General Public License v3.0 (GPL-3.0)** 许可证。

这意味着：
- ✅ 你可以自由使用、修改和分发这些插件
- ✅ 你可以将这些插件用于商业用途
- ⚠️ 如果你修改并分发这些插件，必须同样以 GPL-3.0 开源
- ⚠️ 如果你的插件依赖本仓库的插件，你的插件也必须使用 GPL-3.0

详见 [LICENSE](./LICENSE) 文件。


## 🤝 贡献

欢迎贡献代码、报告问题或提出建议！

### 贡献流程

1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启一个 Pull Request

### 代码规范

- 遵循 PEP 8 代码风格
- 所有函数必须有类型注解
- 所有函数/类必须有文档字符串
- 提交前运行 `ruff check` 和 `pytest`
- 确保你的代码使用 GPL-3.0 许可证


## 💬 支持与反馈

- 问题反馈：[GitHub Issues](https://github.com/yourusername/my_plugin/issues)
- 讨论交流：[GitHub Discussions](https://github.com/yourusername/my_plugin/discussions)
- 官方文档：[Neo-MoFox Docs](https://github.com/yourusername/Neo-MoFox)

## 🙏 致谢

感谢所有为这些插件做出贡献的开发者！

## 🔗 相关链接

- [Neo-MoFox 主仓库](https://github.com/yourusername/Neo-MoFox)
- [MoFox 插件工具包](https://github.com/yourusername/mofox-plugin-toolkit)
- [MoFox 官方文档](https://github.com/yourusername/docs)
- [AstrBot 论坛](https://book.astrbot.app)

---

**⭐ 如果这些插件对你有帮助，请给个 Star！**
