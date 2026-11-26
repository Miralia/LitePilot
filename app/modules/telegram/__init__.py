import json
import re
from typing import Dict, Optional, Union, List, Tuple, Any

from app.log import logger
from app.modules import _ModuleBase, _MessageBase
from app.modules.telegram.telegram import Telegram
from app.schemas import (
    MessageChannel,
    CommingMessage,
    Notification,
    NotificationConf,
)
from app.schemas.types import ModuleType


class TelegramModule(_ModuleBase, _MessageBase[Telegram]):
    """
    Telegram 通知模块，负责模块生命周期、消息解析和通知发送。
    """

    def init_module(self) -> None:
        """
        初始化模块
        """
        super().init_service(
            service_name=Telegram.__name__.lower(), service_type=Telegram
        )
        self._channel = MessageChannel.Telegram

    @staticmethod
    def get_name() -> str:
        """
        获取模块名称
        """
        return "Telegram"

    @staticmethod
    def get_type() -> ModuleType:
        """
        获取模块类型
        """
        return ModuleType.Notification

    @staticmethod
    def get_subtype() -> MessageChannel:
        """
        获取模块子类型
        """
        return MessageChannel.Telegram

    @staticmethod
    def get_priority() -> int:
        """
        获取模块优先级，数字越小优先级越高，只有同一接口下优先级才生效
        """
        return 0

    def stop(self) -> None:
        """停止模块"""
        for client in self.get_instances().values():
            try:
                client.stop()
            except Exception as err:
                logger.error(f"停止Telegram模块实例失败：{err}")

    def test(self) -> Optional[Tuple[bool, str]]:
        """
        测试模块连接性
        """
        if not self.get_instances():
            return None
        for name, client in self.get_instances().items():
            state = client.get_state()
            if not state:
                return False, f"Telegram {name} 未就绪"
        return True, ""

    def init_setting(self) -> Tuple[str, Union[str, bool]]:
        """
        获取模块初始化配置项。
        """
        pass

    @staticmethod
    def _get_admins(config: Optional[dict]) -> List[str]:
        """
        解析 Telegram 管理员配置，兼容逗号分隔和首尾空白。
        """
        return [
            admin.strip()
            for admin in str((config or {}).get("TELEGRAM_ADMINS") or "").split(",")
            if admin.strip()
        ]

    @classmethod
    def _should_reject_admin_command(
            cls,
            config: Optional[dict],
            *user_ids: Optional[Union[str, int]],
    ) -> bool:
        """
        判断 Telegram 命令或命令型按钮回调是否应因非管理员身份被拒绝。
        """
        admins = cls._get_admins(config)
        if not admins:
            return False
        candidates = [
            str(user_id).strip()
            for user_id in user_ids
            if user_id is not None and str(user_id).strip()
        ]
        return not any(candidate in admins for candidate in candidates)

    @staticmethod
    def _get_users(config: Optional[dict]) -> List[str]:
        """
        解析 Telegram 用户白名单，兼容逗号分隔和首尾空白。
        """
        return [
            user.strip()
            for user in str((config or {}).get("TELEGRAM_USERS") or "").split(",")
            if user.strip()
        ]

    @classmethod
    def _is_allowed_user(
            cls,
            config: Optional[dict],
            user_id: Optional[Union[str, int]],
    ) -> bool:
        """
        判断用户是否可使用机器人；管理员不受普通用户白名单遗漏影响。
        """
        users = cls._get_users(config)
        if not users:
            return True
        candidate = str(user_id).strip() if user_id is not None else ""
        return candidate in users or candidate in cls._get_admins(config)

    def message_parser(
        self, source: str, body: Any, form: Any, args: Any
    ) -> Optional[CommingMessage]:
        """
        解析消息内容，返回字典，注意以下约定值：
        userid: 用户ID
        username: 用户名
        text: 内容
        :param source: 消息来源
        :param body: 请求体
        :param form: 表单
        :param args: 参数
        :return: 渠道、消息体
        """
        """
            普通消息格式：
            {
                'update_id': ,
                'message': {
                    'message_id': ,
                    'from': {
                        'id': ,
                        'is_bot': False,
                        'first_name': '',
                        'username': '',
                        'language_code': 'zh-hans'
                    },
                    'chat': {
                        'id': ,
                        'first_name': '',
                        'username': '',
                        'type': 'private'
                    },
                    'date': ,
                    'text': ''
                }
            }

            按钮回调格式：
            {
                'callback_query': {
                    'id': '',
                    'from': {...},
                    'message': {...},
                    'data': 'callback_data'
                }
            }
        """
        # 获取服务配置
        client_config = self.get_config(source)
        if not client_config:
            return None
        client: Telegram = self.get_instance(client_config.name)
        try:
            message = json.loads(body)
            while isinstance(message, str):
                message = json.loads(message)
        except Exception as err:
            logger.debug(f"解析Telegram消息失败：{str(err)}")
            return None

        if not isinstance(message, dict):
            logger.debug(f"Telegram消息格式无效：{type(message)}")
            return None

        # 兼容某些转发链路使用 Telegram Update 外壳
        if "message" in message and isinstance(message.get("message"), dict):
            message = message.get("message")

        if message:
            # 处理按钮回调
            if "callback_query" in message:
                return self._handle_callback_query(message, client_config, client)

            # 处理普通消息
            return self._handle_text_message(message, client_config, client)

        return None

    def _handle_callback_query(
        self, message: dict, client_config: NotificationConf, client: Telegram
    ) -> Optional[CommingMessage]:
        """
        处理按钮回调查询
        """
        callback_query = message.get("callback_query", {})
        user_info = callback_query.get("from", {})
        callback_data = callback_query.get("data", "")
        user_id = user_info.get("id")
        user_name = user_info.get("username")

        if callback_data and user_id:
            if not self._is_allowed_user(client_config.config, user_id):
                if client:
                    client.answer_callback_query(
                        callback_query_id=callback_query.get("id"),
                        text="你不在用户白名单中，无法使用此机器人",
                        show_alert=True,
                    )
                return None

            if self._should_reject_admin_command(
                    client_config.config, user_id, user_name
            ):
                if client:
                    client.answer_callback_query(
                        callback_query_id=callback_query.get("id"),
                        text="只有管理员才有权限执行此操作",
                        show_alert=True,
                    )
                return None

            logger.info(
                f"收到来自 {client_config.name} 的Telegram按钮回调："
                f"userid={user_id}, username={user_name}, callback_data={callback_data}"
            )

            # 将callback_data作为特殊格式的text返回，以便主程序识别这是按钮回调
            callback_text = f"CALLBACK:{callback_data}"

            # 创建包含完整回调信息的CommingMessage
            return CommingMessage(
                channel=MessageChannel.Telegram,
                source=client_config.name,
                userid=user_id,
                username=user_name,
                text=callback_text,
                message_id=callback_query.get("message", {}).get("message_id"),
                chat_id=str(
                    callback_query.get("message", {}).get("chat", {}).get("id", "")
                ),
            )
        return None

    def _handle_text_message(
        self, msg: dict, client_config: NotificationConf, client: Telegram
    ) -> Optional[CommingMessage]:
        """
        处理普通文本消息
        """
        text = msg.get("text") or msg.get("caption")
        message_id = msg.get("message_id")
        user_id = msg.get("from", {}).get("id")
        user_name = msg.get("from", {}).get("username")
        chat_id = msg.get("chat", {}).get("id")

        # 将 text_link 实体中的 URL 嵌入到文本中
        if text:
            text = self._embed_entity_links(text, msg.get("entities") or msg.get("caption_entities"))

        # 将 reply_markup 中的 URL 按钮信息追加到文本中
        text = self._append_reply_markup_links(text, msg.get("reply_markup"))

        if user_id:
            if not text:
                logger.debug(
                    f"收到来自 {client_config.name} 的Telegram消息无文本"
                )
                return None

            logger.info(
                f"收到来自 {client_config.name} 的Telegram消息："
                f"userid={user_id}, username={user_name}, chat_id={chat_id}, text={text}"
            )

            cleaned_text = self._clean_bot_mention(
                text, client.bot_username if client else None
            )

            if not self._is_allowed_user(client_config.config, user_id):
                logger.info(f"用户{user_id}不在用户白名单中，无法使用此机器人")
                if client:
                    client.send_msg(
                        title="你不在用户白名单中，无法使用此机器人", userid=user_id
                    )
                return None

            if cleaned_text and cleaned_text.startswith("/"):
                if self._should_reject_admin_command(client_config.config, user_id, user_name):
                    if client:
                        client.send_msg(
                            title="只有管理员才有权限执行此命令", userid=user_id
                        )
                    return None

            return CommingMessage(
                channel=MessageChannel.Telegram,
                source=client_config.name,
                userid=user_id,
                username=user_name,
                text=cleaned_text,
                message_id=message_id,
                chat_id=str(chat_id) if chat_id else None,
            )
        return None

    @staticmethod
    def _embed_entity_links(text: str, entities: Optional[List[dict]]) -> str:
        """
        将 text_link 实体中的 URL 嵌入到文本中

        :param text: 原始文本
        :param entities: 消息实体列表
        :return: 嵌入链接后的文本
        """
        if not entities:
            return text
        text_link_entities = sorted(
            [e for e in entities if e.get("type") == "text_link" and e.get("url")],
            key=lambda e: e.get("offset", 0),
            reverse=True,
        )
        text_utf16 = text.encode("utf-16-le")
        for entity in text_link_entities:
            offset = entity.get("offset", 0)
            length = entity.get("length", 0)
            url = entity["url"]
            char_offset = len(text_utf16[:offset * 2].decode("utf-16-le"))
            char_length = len(text_utf16[offset * 2: (offset + length) * 2].decode("utf-16-le"))
            display_text = text[char_offset: char_offset + char_length]
            text = text[:char_offset] + f"{display_text}({url})" + text[char_offset + char_length:]
            text_utf16 = text.encode("utf-16-le")
        return text

    @staticmethod
    def _append_reply_markup_links(text: Optional[str], reply_markup: Optional[dict]) -> Optional[str]:
        """
        将 reply_markup 中的 URL 按钮信息追加到文本末尾

        :param text: 原始文本
        :param reply_markup: 消息的 reply_markup 字段
        :return: 追加按钮链接后的文本
        """
        if not reply_markup:
            return text
        inline_keyboard = reply_markup.get("inline_keyboard")
        if not inline_keyboard:
            return text
        button_lines = []
        for row in inline_keyboard:
            for button in row:
                btn_text = button.get("text", "")
                btn_url = button.get("url")
                if btn_url:
                    button_lines.append(f"{btn_text}({btn_url})")
        if not button_lines:
            return text
        buttons_text = "\n".join(button_lines)
        if text:
            return f"{text}\n{buttons_text}"
        return buttons_text

    @staticmethod
    def _clean_bot_mention(text: str, bot_username: Optional[str]) -> str:
        """
        清理消息中的@bot部分，确保文本处理一致性
        :param text: 原始消息文本
        :param bot_username: bot用户名
        :return: 清理后的文本
        """
        if not text or not bot_username:
            return text

        # Remove @bot_username from the beginning and any position in text
        cleaned = text
        mention_pattern = f"@{bot_username}"

        # Remove mention at the beginning with optional following space
        if cleaned.startswith(mention_pattern):
            cleaned = cleaned[len(mention_pattern):].lstrip()

        # Remove mention at any other position
        cleaned = cleaned.replace(mention_pattern, "").strip()

        # Clean up multiple spaces
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    def post_message(self, message: Notification, **kwargs) -> None:
        """
        发送消息
        :param message: 消息体
        :return: 成功或失败
        """
        for conf in self.get_configs().values():
            if not self.check_message(message, conf.name):
                continue
            targets = message.targets
            userid = message.userid
            if not userid and targets is not None:
                userid = targets.get("telegram_userid")
                if not userid:
                    logger.warning(f"用户没有指定 Telegram用户ID，消息无法发送")
                    return
            client: Telegram = self.get_instance(conf.name)
            if client:
                client.send_msg(
                    title=message.title,
                    text=message.text,
                    image=message.image,
                    userid=userid,
                    link=message.link,
                    buttons=message.buttons,
                )

    def mark_message_processing_started(
            self,
            channel: MessageChannel,
            source: str,
            userid: Optional[Union[str, int]] = None,
            message_id: Optional[Union[str, int]] = None,
            chat_id: Optional[Union[str, int]] = None,
            text: Optional[str] = None,
    ) -> Optional[dict]:
        """
        标记 Telegram 消息正在处理。
        Telegram typing 需要周期性续发，因此在模块接口中启动保活任务。
        """
        if channel != self._channel:
            return None
        client_config = self.get_config(source)
        if not client_config:
            return None
        client: Telegram = self.get_instance(client_config.name)
        if not client:
            return None
        started = client.start_typing(chat_id=chat_id, userid=userid)
        if not started:
            return None
        return {
            "channel": channel.value,
            "source": source,
            "userid": userid,
            "message_id": message_id,
            "chat_id": chat_id,
            "metadata": {"kind": "typing"},
        }

    def mark_message_processing_finished(
            self,
            channel: MessageChannel,
            source: str,
            userid: Optional[Union[str, int]] = None,
            message_id: Optional[Union[str, int]] = None,
            chat_id: Optional[Union[str, int]] = None,
            status: Optional[dict] = None,
    ) -> Optional[bool]:
        """
        结束 Telegram typing 状态。
        """
        if channel != self._channel:
            return None
        if status:
            chat_id = status.get("chat_id") or chat_id
            userid = status.get("userid") or userid
        client_config = self.get_config(source)
        if not client_config:
            return False
        client: Telegram = self.get_instance(client_config.name)
        if not client:
            return False
        return client.stop_typing(chat_id=chat_id, userid=userid)

    def register_commands(self, commands: Dict[str, dict]):
        """
        注册命令，实现这个函数接收系统可用的命令菜单
        :param commands: 命令字典
        """
        for client_config in self.get_configs().values():
            client = self.get_instance(client_config.name)
            if not client:
                continue

            client.register_commands(commands)
