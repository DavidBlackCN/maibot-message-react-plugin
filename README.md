# maibot-message-react-plugin - 麦麦贴表情

> [!NOTE]
> **原作者**: [Ghost_chu](https://github.com/Ghost-chu)  
> **原仓库**: [Ghost-chu/maiplug_message_react](https://github.com/Ghost-chu/maiplug_message_react)  
> **一开仓库**: [putaojuju/maiplug_message_react-remake](https://github.com/putaojuju/maiplug_message_react-remake)
>
> 本仓库为原插件的二开版，已迁移至 MaiBot 1.0.0 + maibot-plugin-sdk 2.x，使用DeepSeek V4 Pro迁移，自用。

麦麦插件，让麦麦学会怎么给消息贴表情吧
通过调用 Napcat API，让麦麦使用 LLM 决定为哪条消息贴哪个表情

<img width="832" height="427" alt="PixPin_2025-09-01_22-10-20" src="https://github.com/user-attachments/assets/e0a68cd3-718b-464b-b9e8-e7c1926421c3" />

## 兼容性

| 组件 | 最低版本 |
|------|----------|
| MaiBot | 1.0.0 |
| maibot-plugin-sdk | 2.5.1 |

## 更新日志

### v2.0.1
- **修复**：修正消息结构解析，适配 MaiBot SDK 2.x 实际字段名（`message_info`、`group_info`、`session_id` 等）
- **修复**：群聊判断改用 `group_id` 直接检测，不再依赖 `chat_type`
- **修复**：消息查询 API 改用 `ctx.message.get_recent`
- **修复**：时间戳类型转换兼容字符串格式
- **修复**：`capabilities` 改为精确方法级授权（`llm.generate`、`message.get_recent`）
- **新增**：`llm_task` 配置支持直接填模型标识名，通过 `LLMOrchestrator` 直连绕过 task 路由
- **新增**：启动时自动检测 Napcat HTTP 服务连通性
- **新增**：`plugin_type: "tool"` 清单字段

### v2.0.0
- **重大更新**：迁移至 MaiBot 1.0.0 + maibot-plugin-sdk 2.x
- 插件 ID 变更为 `com.putaojuju.msg-react`
- `BaseAction` → `@Tool`：LLM 通过工具描述自主判断调用时机
- 配置系统升级为 `PluginConfigBase` + `Field`（支持 WebUI 编辑和热重载）
- 生命周期方法迁移为 `on_load` / `on_unload` / `on_config_update`

### v1.1.0 (重制版)
- 修复了若干已知问题
- 优化了代码结构

## 安装与配置

1. 确认麦麦的模型配置中 `tool_use` 模型已正确配置。需要模型有一定智商和情商，推荐使用火山引擎的 `doubao-seed-1-6-25061` 模型。
2. 将插件文件夹放入 MaiBot 的 `plugins/` 目录下，重新启动以生成 `config.toml` 配置文件
3. 打开 Napcat WebUI 控制台，转到*网络配置*菜单，添加一个 HTTP 服务器，Host 填写 `0.0.0.0`，Port 可自行决定，其他选项保持默认。
4. 编辑生成的 `config.toml` 配置文件，配置 Napcat 服务地址、端口和认证 Token：
   - Docker 部署用户：Napcat 服务地址可直接使用 `napcat`
   - 本地部署用户：通常使用 `127.0.0.1`
5. 重新启动麦麦，在群里让麦麦给你贴个表情，能贴了就说明装好了

## 配置参考

```toml
[plugin]
enabled = true
config_version = "2.0.0"

[napcat]
host = "napcat"
port = 9999
token = ""
```

## 致谢

感谢 [Ghost_chu](https://github.com/Ghost-chu) 开发的原版插件，感谢 [putaojuju](https://github.com/putaojuju) 的修改版插件，本插件基于此更新。

## 许可证

本项目采用 MIT 许可证，继承自原项目。
