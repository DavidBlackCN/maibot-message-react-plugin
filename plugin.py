"""MaiBot 消息贴表情插件 - 让麦麦学会对群聊消息贴表情。

通过 Napcat API，由 LLM 自动选择合适的表情对群聊消息做出反应。
兼容 MaiBot 1.0.0 + maibot-plugin-sdk 2.x。
"""

import json
import time
from typing import Any

import http.client

from maibot_sdk import Field, MaiBotPlugin, PluginConfigBase, Tool
from maibot_sdk.types import ToolParameterInfo, ToolParamType

# ============================================================
# 可用反应表情字典（ID → 名称）
# ============================================================
AVAILABLE_REACT_EMOJIS: dict[int, str] = {
    76: "点赞", 307: "喵喵", 285: "摸鱼",
    66: "爱心", 147: "棒棒糖", 424: "狂按按钮",
    49: "抱抱", 38: "木槌敲头", 277: "狗头",
    265: "辣眼睛", 390: "头秃", 63: "玫瑰",
    212: "托腮", 5: "大哭", 9: "委屈",
    350: "贴贴", 175: "卖萌", 344: "大怨种",
    187: "鬼魂", 144: "礼花", 146: "爆筋",
    311: "打call", 59: "便便", 46: "猪头",
    37: "骷髅头", 13: "呲牙", 124: "OK",
    233: "笑哭", 20: "偷笑", 293: "敲脑瓜",
}


# ============================================================
# 配置模型
# ============================================================
class PluginSectionConfig(PluginConfigBase):
    """插件基础配置。"""
    __ui_label__ = "插件"
    __ui_icon__ = "package"
    __ui_order__ = 0

    enabled: bool = Field(default=True, description="是否启用插件")
    config_version: str = Field(default="2.0.0", description="配置版本")


class NapcatConfig(PluginConfigBase):
    """Napcat 服务连接配置。"""
    __ui_label__ = "Napcat 服务"
    __ui_icon__ = "server"
    __ui_order__ = 1

    host: str = Field(default="napcat", description="Napcat 服务地址")
    port: int = Field(default=9999, description="Napcat 服务端口")
    token: str = Field(default="", description="Napcat 服务认证 Token")


class MessageReactConfig(PluginConfigBase):
    """插件顶层配置。"""
    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)
    napcat: NapcatConfig = Field(default_factory=NapcatConfig)


# ============================================================
# 工具函数
# ============================================================
def _fix_broken_json(raw: str) -> str:
    """修复 LLM 可能生成的格式有误的 JSON 字符串。"""
    if not raw:
        return raw
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start:end + 1]
    return raw


def _translate_timestamp_to_relative(ts: float) -> str:
    """将 Unix 时间戳转换为相对时间描述。"""
    if not ts:
        return "未知"
    now = time.time()
    diff = now - ts
    if diff < 60:
        return "刚刚"
    if diff < 3600:
        return f"{int(diff // 60)}分钟前"
    if diff < 86400:
        return f"{int(diff // 3600)}小时前"
    return f"{int(diff // 86400)}天前"


# ============================================================
# 插件类
# ============================================================
class MessageReactPlugin(MaiBotPlugin):
    """消息反应插件 - 为群聊消息添加表情反应。"""

    config_model = MessageReactConfig

    # --------------------------------------------------------
    # 生命周期
    # --------------------------------------------------------
    async def on_load(self) -> None:
        """插件加载时执行。"""
        self.ctx.logger.info("消息贴表情插件已加载")

    async def on_unload(self) -> None:
        """插件卸载时执行。"""
        self.ctx.logger.info("消息贴表情插件已卸载")

    async def on_config_update(
        self, scope: str, config_data: dict[str, Any], version: str
    ) -> None:
        """配置热重载时执行。"""
        if scope == "self":
            self.ctx.logger.info("插件配置已更新: version=%s", version)

    # --------------------------------------------------------
    # Tool: 贴表情 (替代旧版 MessageReactAction)
    # --------------------------------------------------------
    @Tool(
        "msg_react",
        brief_description="向指定群聊消息添加反应表情，表情会显示在对应消息的下面",
        detailed_description=(
            "向群聊中的某条消息添加反应表情（贴表情）。\n\n"
            "使用场景：\n"
            "- 需要或想要对消息添加反应表情来表达情绪时\n"
            "- 想要和某人友好互动但又不想发送消息破坏聊天节奏时\n"
            "- 想要提醒某人时\n\n"
            "注意事项：\n"
            "- 仅支持群聊场景\n"
            "- 不要频繁使用，避免短时间内对同一条消息发送过多表情\n"
            "- 贴表情不等同于回复消息，如需回复请优先使用回复功能\n\n"
            "参数说明：\n"
            "- target_message_id：string，可选。要贴表情的消息ID，不填则默认对触发消息贴表情"
        ),
        parameters=[
            ToolParameterInfo(
                name="target_message_id",
                param_type=ToolParamType.STRING,
                description="要贴表情的消息ID（可选，不填则默认对触发消息贴表情）",
                required=False,
            ),
        ],
    )
    async def handle_msg_react(
        self, target_message_id: str = "", **kwargs: Any
    ) -> dict[str, Any]:
        """执行消息贴表情。LLM 根据对话上下文决定是否调用此工具。"""
        # --- 从 kwargs 中提取 SDK 注入的上下文 ---
        message: dict[str, Any] = kwargs.get("message", {})
        stream_id: str = kwargs.get("stream_id", "")

        msg_base_info = message.get("message_base_info", {})
        chat_type = msg_base_info.get("chat_type", "")

        if chat_type != "group":
            return {"success": False, "content": "消息反应仅支持群聊"}

        # --- 确定目标消息 ---
        if target_message_id:
            target_msg_id = target_message_id
            # 尝试从最近消息中获取目标消息的发送者
            target_user_name, target_content = await self._get_target_message_info(
                target_msg_id, msg_base_info.get("chat_id", "") or stream_id
            )
        else:
            target_msg_id = msg_base_info.get("message_id", "")
            target_user_name = str(msg_base_info.get("user_nickname", "未知用户") or "未知用户")
            target_content = (message.get("plain_text", "") or "")[:100]

        if not target_msg_id:
            return {"success": False, "content": "没有可用的目标消息"}

        target_content = target_content.replace("\n", " ").replace("\r", " ")[:100]
        chat_id = msg_base_info.get("chat_id", "") or stream_id

        # --- 构建 prompt 让 LLM 选择表情 ---
        prompt = await self._build_emoji_selection_prompt(
            chat_id, target_msg_id, target_user_name, target_content
        )

        self.ctx.logger.debug("选表情 Prompt 长度: %d", len(prompt))

        # --- 调用 LLM 选择表情 ---
        chosen_react_emoji_id, chosen_react_emoji_name = await self._llm_select_emoji(prompt)
        if not chosen_react_emoji_id:
            return {"success": False, "content": f"LLM 选表情失败: {chosen_react_emoji_name}"}

        self.ctx.logger.info(
            "准备贴表情: 消息ID=%s, 表情=%s:%s",
            target_msg_id, chosen_react_emoji_id, chosen_react_emoji_name,
        )

        # --- 通过 Napcat API 发送表情反应 ---
        success, detail = await self._call_napcat_set_emoji(
            target_msg_id, chosen_react_emoji_id
        )

        if success:
            return {
                "success": True,
                "content": f"已对 {target_user_name} 的消息贴了 {chosen_react_emoji_name} 表情",
            }
        return {"success": False, "content": f"贴表情失败: {detail}"}

    # --------------------------------------------------------
    # 内部辅助方法
    # --------------------------------------------------------
    async def _get_target_message_info(
        self, target_msg_id: str, chat_id: str
    ) -> tuple[str, str]:
        """从最近消息中查找目标消息的发送者和内容。"""
        try:
            recent = await self.ctx.message.get_recent_messages(
                chat_id=chat_id, limit=20
            )
        except Exception as e:
            self.ctx.logger.warning("获取最近消息失败: %s", e)
            return "未知用户", ""

        if recent:
            for msg in recent:
                mb = msg.get("message_base_info", {})
                if mb.get("message_id") == target_msg_id:
                    name = str(mb.get("user_nickname", "未知用户") or "未知用户")
                    content = (msg.get("plain_text", "") or "")[:100]
                    return name, content

        return "未知用户", ""

    async def _build_emoji_selection_prompt(
        self,
        chat_id: str,
        target_msg_id: str,
        target_user_name: str,
        target_content: str,
    ) -> str:
        """构建让 LLM 选择表情的 prompt。"""
        # 构建表情列表
        available_emojis_prompt = ", ".join(
            f"{eid}:{ename}" for eid, ename in AVAILABLE_REACT_EMOJIS.items()
        )

        # 构建最近聊天记录
        messages_text = "（无法获取最近消息）"
        try:
            recent = await self.ctx.message.get_recent_messages(
                chat_id=chat_id, limit=10
            )
        except Exception as e:
            self.ctx.logger.warning("获取最近消息失败: %s", e)
            recent = None

        if recent:
            parts: list[str] = []
            for msg in recent:
                mb = msg.get("message_base_info", {})
                user_name = str(mb.get("user_nickname", "未知用户") or "未知用户")
                content = (msg.get("plain_text", "") or "").replace("\n", " ").replace("\r", " ")[:50]
                msg_id = mb.get("message_id", "")
                ts = _translate_timestamp_to_relative(mb.get("time", 0))
                marker = " [目标消息]" if msg_id == target_msg_id else ""
                parts.append(f"{msg_id},{ts},{user_name}:{content}{marker}")
            if parts:
                messages_text = "\n".join(parts)

        return f"""你是一个正在进行聊天的网友，需要为目标消息选择一个最合适的反应表情。

**目标消息**（标记为[目标消息]的那条）：
- 消息ID: {target_msg_id}
- 发送者: {target_user_name}
- 内容: {target_content}

**最近聊天记录**（格式：<id>,<time>,<user>:<content>）：
{messages_text}

**可用的反应表情**（ID:名称）：
{available_emojis_prompt}

请根据目标消息的内容和上下文，选择一个最合适的反应表情。
严格按JSON格式返回，不要添加任何解释：
{{
  "emoji_id": "选择的表情ID（数字）",
  "reason": "简短理由（10字以内）"
}}"""

    async def _llm_select_emoji(self, prompt: str) -> tuple[str, str]:
        """调用 LLM 选择表情，返回 (emoji_id, emoji_name)。失败时返回 ("", 错误消息)。"""
        try:
            llm_result = await self.ctx.llm.generate(prompt, request_type="text")
        except Exception as e:
            self.ctx.logger.error("LLM 调用异常: %s", e)
            return "", f"LLM 调用异常: {e}"

        if not llm_result:
            return "", "LLM 返回为空"

        # 尝试适配不同的返回格式
        if isinstance(llm_result, dict):
            if not llm_result.get("success", True):
                return "", llm_result.get("content", "LLM 返回失败")
            content = llm_result.get("content", "")
        else:
            content = str(llm_result)

        if not content:
            return "", "LLM 返回内容为空"

        # 解析 JSON 响应
        try:
            fixed = _fix_broken_json(content)
            data = json.loads(fixed)
            emoji_id_raw = data.get("emoji_id")
            if not emoji_id_raw:
                return "", "LLM 未返回 emoji_id"

            emoji_id = str(emoji_id_raw).strip().replace('"', "").replace("'", "")
            emoji_name = AVAILABLE_REACT_EMOJIS.get(int(emoji_id), "未知表情")
            return emoji_id, emoji_name
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            self.ctx.logger.error("解析 LLM 响应失败: %s, 原始响应: %s", e, content[:200])
            return "", f"解析 LLM 响应失败: {e}"

    async def _call_napcat_set_emoji(
        self, message_id: str, emoji_id: str
    ) -> tuple[bool, str]:
        """通过 Napcat HTTP API 发送消息反应表情。返回 (成功与否, 详情)。"""
        host = self.config.napcat.host
        port = self.config.napcat.port
        token = self.config.napcat.token

        conn = http.client.HTTPConnection(host, port, timeout=10)
        payload = json.dumps({
            "message_id": message_id,
            "emoji_id": emoji_id,
            "set": True,
        })
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = token

        self.ctx.logger.debug(
            "Napcat 请求: message_id=%s, emoji_id=%s", message_id, emoji_id
        )

        try:
            conn.request("POST", "/set_msg_emoji_like", payload, headers)
            res = conn.getresponse()
            data = res.read()
            result_text = data.decode("utf-8")
            self.ctx.logger.debug("Napcat 响应: %s", result_text)

            try:
                data_json = json.loads(result_text)
                ok = data_json.get("status") == "ok"
                return ok, data_json.get("message", result_text)
            except json.JSONDecodeError:
                return False, f"无法解析 Napcat 响应: {result_text}"
        except Exception as e:
            self.ctx.logger.error("贴表情 HTTP 异常: %s", e)
            return False, f"{type(e).__name__}: {e}"
        finally:
            conn.close()


# ============================================================
# 模块顶层工厂函数
# ============================================================
def create_plugin() -> MessageReactPlugin:
    """创建插件实例。"""
    return MessageReactPlugin()

