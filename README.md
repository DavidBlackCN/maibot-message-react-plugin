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

### v2.1.1
- **修复**：移除 Manifest 中 SDK 不支持的 `http_request` 能力声明
- **修复**：移除对 MaiBot 宿主内部 `TaskConfig` / `LLMOrchestrator` 的直接导入和内部属性操作
- **修复**：不再读取宿主 `model_config.toml`，避免绕过插件 SDK 文件访问边界
- **调整**：`llm_task` 统一通过 SDK 公共接口 `ctx.llm.generate(..., model=...)` 传递

### v2.1.0
- **新增**：普通群聊消息旁路主动贴表情，使用 `EventHandler.ON_MESSAGE` 且不拦截正常回复流程
- **新增**：`[proactive]` 配置区，可控制主动贴表情开关、概率、关键词加权概率、冷却时间和自消息跳过
- **修复**：`llm_task` 同时支持 MaiBot task 名（如 `replyer`、`planner`、`utils`、`tool_use`）和具体模型标识名
- **修复**：适配 SDK 2.x `ctx.llm.generate()` 的 `response` 返回字段，兼容旧 `content` 字段
- **修复**：限制 LLM 只能返回可用的反应表情 ID，避免向 Napcat 发送未知表情
- **调整**：Manifest 按当前严格校验补充 `display` 和问题反馈链接，并移除未使用的 `send_message` 能力声明

### v2.0.1
- **修复**：修正消息结构解析，适配 MaiBot SDK 2.x 实际字段名（`message_info`、`group_info`、`session_id` 等）
- **修复**：群聊判断改用 `group_id` 直接检测，不再依赖 `chat_type`
- **修复**：消息查询 API 改用 `ctx.message.get_recent`
- **修复**：时间戳类型转换兼容字符串格式
- **修复**：`capabilities` 改为精确方法级授权（`llm.generate`、`message.get_recent`）
- **新增**：`llm_task` 配置支持直接填模型标识名
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
config_version = "2.1.1"

[napcat]
host = "napcat"
port = 9999
token = ""
llm_task = "planner"

[proactive]
enabled = true
chance = 0.35
keyword_chance = 0.75
cooldown_seconds = 180
min_text_length = 2
skip_self_messages = true
```

`llm_task` 默认使用 `planner`。也可留空使用系统默认模型，填写其他 MaiBot 模型任务名（如 `replyer`、`utils`、`tool_use`），或填写当前 SDK/宿主支持通过 `model` 参数指定的模型标识。

`[proactive]` 控制普通聊天中是否主动贴表情。该逻辑不发送文字回复，不会阻塞麦麦正常聊天，只是在群聊消息进入流程时低频尝试通过 Napcat 添加反应表情。

## 致谢

感谢 [Ghost_chu](https://github.com/Ghost-chu) 开发的原版插件，感谢 [putaojuju](https://github.com/putaojuju) 的修改版插件，本插件基于此更新。

## 许可证

本项目采用 MIT 许可证，继承自原项目。
