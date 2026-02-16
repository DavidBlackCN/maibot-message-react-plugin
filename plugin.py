import json
from typing import List, Tuple, Type

from src.chat.knowledge.utils.json_fix import fix_broken_generated_json
from src.chat.utils.utils import translate_timestamp_to_human_readable
from src.common.data_models.message_data_model import MessageAndActionModel
from src.common.logger import get_logger
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    BaseAction,
    ComponentInfo,
    ActionActivationType,
    ConfigField
)
from src.plugin_system.apis import message_api, llm_api
from src.plugin_system.apis.database_api import store_action_info

logger = get_logger("msg_react")
available_react_emojis = {76: "点赞", 307: "喵喵", 285: "摸鱼",
                          66: "爱心", 147: "棒棒糖", 424: "狂按按钮",
                          49: "抱抱", 38: "木槌敲头", 277: "狗头",
                          265: "辣眼睛", 390: "头秃", 63: "玫瑰",
                          212: "托腮", 5: "大哭", 9: "委屈",
                          350: "贴贴", 175: "卖萌", 344: "大怨种",
                          187: "鬼魂", 144: "礼花", 146: "爆筋",
                          311: "打call", 59: "便便", 46: "猪头",
                          37: "骷髅头", 13: "呲牙", 124: "OK",
                          233: "笑哭", 20: "偷笑", 293: "敲脑瓜"}

class MessageReactAction(BaseAction):


    """处理消息反应的 Action"""
    action_name = "msg_react"
    action_description = "向指定群聊消息添加反应表情，表情会显示在对应消息的下面"
    parallel_action = True
    activation_type = ActionActivationType.ALWAYS

    action_parameters = {
        "target_message_id": "要贴表情的消息ID（可选，不填则默认对触发消息贴表情）"
    }

    action_require = [
        "需要或想要对消息添加反应表情时",
        "表达情绪时可以选择使用",
        "当你想要和某人友好互动时可选择调用",
        "当你想要提醒某人时可选择调用",
        "提示：贴反应表情的Action不视为回复消息。无论什么时候，若与reply同时出现在选择中，应优先选择reply的action",
    ]

    associated_types = ["text", "emoji", "image", "reply", "voice"]

    llm_judge_prompt = """
    判定是否需要使用反应动作的条件：
    1. 用户明确要求为其消息添加反应表情
    2. 你需要或者想要对消息添加反应表情以表达情绪
    3. 你想要和某人友好互动，但又不想发送消息破坏聊天节奏
    3. 不要发送太多反应表情，如果你已经发送过多个反应表情则回答"否"

    请回答"是"或"否"。
    """

    async def execute(self) -> Tuple[bool, str]:
        """执行消息反应动作"""
        if not self.is_group:
            return False, "消息反应仅支持群聊"

        target_message_id = self.action_data.get("target_message_id")
        target_message = None

        if target_message_id:
            recent_messages = message_api.get_recent_messages(chat_id=self.chat_id, limit=20)
            for msg in recent_messages:
                if msg.message_id == target_message_id:
                    target_message = msg
                    break
            if not target_message:
                logger.warning(f"未在最近消息中找到目标消息ID: {target_message_id}，回退到触发消息")
                target_message = self.action_message
        else:
            target_message = self.action_message

        if not target_message:
            return False, "没有可用的目标消息"

        target_msg_id = target_message.message_id
        target_user_name = target_message.user_info.user_nickname
        target_content = target_message.processed_plain_text or ""
        if target_content:
            target_content = target_content.replace("\n", " ").replace("\r", " ")[:100]

        available_emojis_prompt = ", ".join(
            [f"{emoji_id}:{emoji_name}" for emoji_id, emoji_name in available_react_emojis.items()])

        recent_messages = message_api.get_recent_messages(chat_id=self.chat_id, limit=10)
        messages_text = ""
        if recent_messages:
            list_message = []
            for msg in recent_messages:
                maam = MessageAndActionModel.from_DatabaseMessages(msg)
                user_name = maam.user_nickname
                content = maam.processed_plain_text.replace("\n", " ").replace("\r", " ")[:50] if maam.processed_plain_text else ""
                msg_id = msg.message_id
                timestamp = translate_timestamp_to_human_readable(maam.time, mode="relative")
                marker = " [目标消息]" if msg_id == target_msg_id else ""
                list_message.append(f"{msg_id},{timestamp},{user_name}:{content}{marker}")
            messages_text = "\n".join(list_message)

        prompt = f"""你是一个正在进行聊天的网友，需要为目标消息选择一个最合适的反应表情。

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

        logger.debug(f"生成的LLM Prompt: {prompt}")

        models = llm_api.get_available_models()
        chat_model_config = models.get("tool_use")
        if not chat_model_config:
            logger.error("未找到'tool_use'模型配置，无法调用LLM")
            return False, "未找到'tool_use'模型配置"

        success, chosen_react_emoji_json_str, _, _ = await llm_api.generate_with_model(
            prompt, model_config=chat_model_config, request_type="text"
        )
        logger.debug(f"LLM返回: {chosen_react_emoji_json_str}")

        if not success:
            logger.error(f"LLM调用失败: {chosen_react_emoji_json_str}")
            return False, f"LLM调用失败: {chosen_react_emoji_json_str}"

        try:
            fixedResp = fix_broken_generated_json(chosen_react_emoji_json_str)
            json_resp = json.loads(fixedResp)
            emoji_id_raw = json_resp.get("emoji_id")
            if not emoji_id_raw:
                return False, "LLM未返回emoji_id"
            chosen_react_emoji_id = str(emoji_id_raw).strip().replace('"', "").replace("'", "")
            chosen_react_emoji_name = available_react_emojis.get(int(chosen_react_emoji_id), "未知表情")
        except Exception as e:
            logger.error(f"解析LLM响应失败: {e}")
            return False, f"解析LLM响应失败: {e}"

        logger.info(f"准备贴表情: 消息ID={target_msg_id}, 表情={chosen_react_emoji_id}:{chosen_react_emoji_name}")

        await self.send_msg_react(
            self.chat_id,
            target_msg_id,
            chosen_react_emoji_id,
            self.get_config("napcat.host", "napcat"),
            self.get_config("napcat.port", 9999),
            self.get_config("napcat.token", None)
        )

        await store_action_info(
            self.chat_stream,
            True,
            f"[反应表情：贴在 {target_user_name} 的消息上，表情={chosen_react_emoji_name}]",
            True,
            self.thinking_id,
            self.action_data,
            self.action_name
        )

        return True, f"反应表情：贴在 {target_user_name} 的消息上，表情={chosen_react_emoji_name}"

    async def send_msg_react(self, chat_id, message_id, chosen_react_emoji, napcat_host, napcat_port, napcat_token) -> Tuple[bool, str]:
        import http.client
        conn = http.client.HTTPConnection(napcat_host, napcat_port)
        payload = {"message_id": message_id, "emoji_id": chosen_react_emoji, "set": True}
        payload = json.dumps(payload)
        headers = {"Content-Type": "application/json"}
        if napcat_token:
            headers["Authorization"] = napcat_token
        logger.debug(f"发送消息反应: chat_id={chat_id}, message_id={message_id}, emoji_id={chosen_react_emoji}")
        try:
            conn.request("POST", "/set_msg_emoji_like", payload, headers)
            res = conn.getresponse()
            data = res.read()
            result = data.decode("utf-8")
            logger.debug(f"贴表情响应: {result}")
            try:
                data_json = json.loads(result)
                return data_json.get("status") == "ok", data_json.get("message", result)
            except Exception as e:
                error_info = {
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
                return False, f"贴表情失败 {error_info}"
        except Exception as e:
            error_info = {
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
            logger.error(f"贴表情异常: {error_info}")
            return False, f"贴表情失败 {error_info}"


@register_plugin
class MessageReactPlugin(BasePlugin):
    """消息反应插件 - 为群聊消息添加表情反应"""

    plugin_name: str = "maiplug_message_react"
    enable_plugin: bool = True
    dependencies: List[str] = []
    python_dependencies: List[str] = []
    config_file_name: str = "config.toml"

    config_section_descriptions = {"plugin": "插件基本信息"}

    config_schema: dict = {
        "plugin": {
            "name": ConfigField(type=str, default="maiplug_message_react", description="插件名称"),
            "version": ConfigField(type=str, default="1.1.0", description="插件版本"),
            "enabled": ConfigField(type=bool, default=True, description="是否启用插件"),
        },
        "napcat": {
            "host": ConfigField(type=str, default="napcat", description="Napcat服务地址"),
            "port": ConfigField(type=int, default=9999, description="Napcat服务端口"),
            "token": ConfigField(type=str, default="", description="Napcat服务认证Token"),
        }
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        return [(MessageReactAction.get_action_info(), MessageReactAction)]
