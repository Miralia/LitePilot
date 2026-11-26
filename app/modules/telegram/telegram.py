import asyncio
import json
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urljoin, quote

from app.modules.telegram.compat import ensure_urllib3_header_param_compat

# Must run before importing pyTelegramBotAPI.
ensure_urllib3_header_param_compat()

from telebot import TeleBot, apihelper  # noqa: E402
from telebot.types import (  # noqa: E402
    BotCommand,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegramify_markdown import standardize, telegramify  # noqa: E402
try:
    from telegramify_markdown import entities_to_markdownv2  # noqa: E402
except ImportError:
    entities_to_markdownv2 = None
try:
    from telegramify_markdown.content import ContentTypes, File, Photo, Text  # noqa: E402
except ImportError:
    from telegramify_markdown.type import ContentTypes, File, Photo, Text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.metainfo import MetaInfo  # noqa: E402
from app.helper.image import ImageHelper  # noqa: E402
from app.helper.thread import ThreadHelper  # noqa: E402
from app.log import logger  # noqa: E402
from app.utils.common import retry  # noqa: E402
from app.utils.http import RequestUtils  # noqa: E402
from app.utils.string import StringUtils  # noqa: E402


TELEGRAM_PARSE_MODE_MARKDOWN = "MarkdownV2"


class RetryException(Exception):
    """
    Telegram 消息发送重试异常。
    """

    pass


class Telegram:
    """
    Telegram 消息客户端，负责发送、接收和转发 Telegram 消息。
    """

    _ds_url = (
        f"http://127.0.0.1:{settings.PORT}/api/v1/message?token={settings.API_TOKEN}"
    )
    _bot: TeleBot = None
    _callback_handlers: Dict[str, Callable] = {}  # 存储回调处理器
    _user_chat_mapping: Dict[
        str, str
    ] = {}  # userid -> chat_id mapping for reply targeting
    _bot_username: Optional[str] = None  # Bot username for mention detection
    _typing_tasks: Dict[str, threading.Thread] = {}  # chat_id -> typing任务
    _typing_stop_flags: Dict[str, threading.Event] = {}  # chat_id -> 停止信号
    _typing_lock = threading.RLock()
    _typing_interval_seconds = 5
    _typing_initial_delay_seconds = 1
    _typing_max_duration_seconds = 10 * 60
    _typing_command_max_duration_seconds = 30
    _typing_callback_max_duration_seconds = 60

    def __init__(
            self,
            TELEGRAM_TOKEN: Optional[str] = None,
            TELEGRAM_CHAT_ID: Optional[str] = None,
            **kwargs,
    ):
        """
        初始化参数
        """
        # 即使配置不完整也保留基础属性，便于测试和未启用实例安全调用发送方法。
        self._telegram_token = TELEGRAM_TOKEN
        self._telegram_chat_id = TELEGRAM_CHAT_ID
        self._polling_thread = None
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            logger.error("Telegram配置不完整！")
            return
        # 初始化机器人
        if self._telegram_token and self._telegram_chat_id:
            # telegram bot api 地址，格式：https://api.telegram.org
            api_url = kwargs.get("API_URL")
            if api_url:
                # 如果提供了自定义API地址，使用它
                apihelper.API_URL = urljoin(api_url, "/bot{0}/{1}")
                apihelper.FILE_URL = urljoin(api_url, "/file/bot{0}/{1}")
                # 使用自定义地址时，不设置代理
                apihelper.proxy = None
            else:
                # 使用默认Telegram API地址
                apihelper.API_URL = "https://api.telegram.org/bot{0}/{1}"
                apihelper.FILE_URL = "https://api.telegram.org/file/bot{0}/{1}"
                # 设置代理
                apihelper.proxy = settings.PROXY
            # bot
            _bot = TeleBot(self._telegram_token, parse_mode=TELEGRAM_PARSE_MODE_MARKDOWN)
            # 记录句柄
            self._bot = _bot
            # 获取并存储bot用户名用于@检测
            try:
                bot_info = _bot.get_me()
                self._bot_username = bot_info.username
                logger.info(f"Telegram bot用户名: @{self._bot_username}")
            except Exception as e:
                logger.error(f"获取bot信息失败: {e}")
                self._bot_username = None

            # 标记渠道来源
            if kwargs.get("name"):
                # URL encode the source name to handle special characters
                encoded_name = quote(kwargs.get("name"), safe="")
                self._ds_url = f"{self._ds_url}&source={encoded_name}"

            @_bot.message_handler(commands=["start", "help"])
            def send_welcome(message):
                _bot.reply_to(
                    message,
                    "欢迎使用 LitePilot。可用命令：/downloading、/transfer、/redo、/clear_cache、/version",
                )

            @_bot.message_handler(content_types=[
                "text", "photo", "video", "document", "animation",
                "audio", "voice", "sticker", "video_note",
            ], func=lambda message: True)
            def echo_all(message):
                # Update user-chat mapping when receiving messages
                self._update_user_chat_mapping(message.from_user.id, message.chat.id)

                # Check if we should process this message
                if self._should_process_message(message):
                    payload = self._serialize_update_payload(message)
                    if not payload:
                        logger.warning("Telegram消息序列化失败，跳过转发")
                        return
                    response = RequestUtils(timeout=15).post_res(
                        self._ds_url, json=payload
                    )
                    if not response or response.status_code >= 400:
                        logger.warning("Telegram消息转发失败")

            @_bot.callback_query_handler(func=lambda call: True)
            def callback_query(call):
                """
                处理按钮点击回调
                """
                chat_id = None
                try:
                    # Update user-chat mapping for callbacks too
                    chat_id = call.message.chat.id
                    self._update_user_chat_mapping(
                        call.from_user.id, chat_id
                    )

                    # 解析回调数据
                    callback_data = call.data
                    user_id = str(call.from_user.id)

                    logger.info(f"收到按钮回调：{callback_data}，用户：{user_id}")

                    # 发送回调数据给主程序处理
                    callback_json = {
                        "callback_query": {
                            "id": call.id,
                            "from": call.from_user.to_dict(),
                            "message": {
                                "message_id": call.message.message_id,
                                "chat": {
                                    "id": chat_id,
                                },
                            },
                            "data": callback_data,
                        }
                    }

                    # 先确认回调，避免用户看到loading状态
                    _bot.answer_callback_query(call.id)

                    # 发送给主程序处理
                    response = RequestUtils(timeout=15).post_res(
                        self._ds_url, json=callback_json
                    )
                    if not response or response.status_code >= 400:
                        logger.warning("Telegram按钮回调转发失败")

                except Exception as err:
                    logger.error(f"处理按钮回调失败：{str(err)}")
                    _bot.answer_callback_query(call.id, "处理失败，请重试")

            def run_polling():
                """
                定义线程函数来运行 infinity_polling
                """
                try:
                    _bot.infinity_polling(long_polling_timeout=30, logger_level=None)
                except Exception as err:
                    logger.error(f"Telegram消息接收服务异常：{str(err)}")

            # 启动线程来运行 infinity_polling
            self._polling_thread = threading.Thread(target=run_polling, daemon=True)
            self._polling_thread.start()
            logger.info("Telegram消息接收服务启动")

    @property
    def bot(self):
        """
        获取Telegram Bot实例
        :return: TeleBot实例或None
        """
        return self._bot

    @property
    def bot_username(self) -> Optional[str]:
        """
        获取Bot用户名
        :return: Bot用户名或None
        """
        return self._bot_username

    def download_file(self, file_id: str) -> Optional[bytes]:
        """
        下载Telegram文件
        :param file_id: 文件ID
        :return: 文件字节数据
        """
        if not self._bot:
            return None
        try:
            file_info = self._bot.get_file(file_id)
            file_url = apihelper.FILE_URL.format(
                self._telegram_token, file_info.file_path
            )
            resp = RequestUtils(
                proxies=apihelper.proxy, timeout=30
            ).get_res(file_url)
            if resp and resp.content:
                logger.info(
                    "Telegram文件下载成功: file_id=%s, file_path=%s, content_bytes=%s",
                    file_id,
                    file_info.file_path,
                    len(resp.content),
                )
                return resp.content
            logger.warning(
                "Telegram文件下载失败: file_id=%s, file_path=%s, file_url=%s, proxy_enabled=%s",
                file_id,
                getattr(file_info, "file_path", None),
                file_url,
                bool(apihelper.proxy),
            )
        except Exception as e:
            logger.error(f"下载Telegram文件失败: {e}")
        return None

    @staticmethod
    def _telegramify_item_text(item: Text) -> str:
        """将 telegramify 文本片段转换为 Telegram MarkdownV2 字符串。"""
        if entities_to_markdownv2:
            return entities_to_markdownv2(item.text, item.entities)
        return standardize(item.text)

    @staticmethod
    def _telegramify_item_caption(item: Text | File | Photo) -> str:
        """将 telegramify 文本或媒体片段转换为 Telegram MarkdownV2 caption。"""
        if isinstance(item, Text):
            return Telegram._telegramify_item_text(item)
        if entities_to_markdownv2:
            return entities_to_markdownv2(item.caption_text, item.caption_entities)
        return standardize(item.caption_text)

    @staticmethod
    def _format_title(title: Optional[str]) -> Optional[str]:
        """生成 Telegram MarkdownV2 标题文本。"""
        if not title:
            return None
        return f"**{standardize(title).removesuffix(chr(10))}**"

    @staticmethod
    def _format_text(text: Optional[str]) -> Optional[str]:
        """
        转义 Telegram MarkdownV2 正文。

        MarkdownV2 把 ``. - ( ) ! # + = | { }`` 等视为保留字符，正文里
        未经转义的文本会破坏格式甚至导致消息被拒。三反引号代码块是例外：
        其内容按原样展示，只需保证围栏本身合法，因此先切出代码块再分别
        处理其余片段。
        """
        if not text:
            return text

        parts: List[str] = []
        buffer: List[str] = []
        in_code = False
        for line in str(text).split("\n"):
            if line.strip() == "```":
                if in_code:
                    buffer.append(line)
                    parts.append("\n".join(buffer))
                    buffer = []
                    in_code = False
                else:
                    # 代码块前保留换行，避免与前一段文字粘连
                    if buffer:
                        parts.append(standardize("\n".join(buffer)) + "\n")
                        buffer = []
                    buffer.append(line)
                    in_code = True
                continue
            buffer.append(line)
        if buffer:
            tail = "\n".join(buffer)
            parts.append(tail if in_code else standardize(tail))
        return "".join(parts)

    @staticmethod
    def _format_detail_link(link: str) -> str:
        """生成 Telegram MarkdownV2 查看详情链接。"""
        return f"[查看详情]({link})"

    @staticmethod
    def _prepare_text(text: Optional[str]) -> Optional[str]:
        """生成 Telegram MarkdownV2 可发送文本。"""
        if not text:
            return None
        return standardize(text)

    @staticmethod
    def _serialize_update_payload(message: Any) -> Optional[dict]:
        """
        将 Telegram Message 对象稳定序列化为 dict，避免 requests 的 json 参数再次包一层字符串。
        """
        try:
            if hasattr(message, "to_dict"):
                payload = message.to_dict()
            else:
                payload = getattr(message, "json", None) or message
            if isinstance(payload, str):
                payload = json.loads(payload)
            return payload if isinstance(payload, dict) else None
        except Exception as e:
            logger.error(f"序列化Telegram消息失败: {e}")
            return None

    def _update_user_chat_mapping(self, userid: int, chat_id: int) -> None:
        """
        更新用户与聊天的映射关系
        :param userid: 用户ID
        :param chat_id: 聊天ID
        """
        if userid and chat_id:
            self._user_chat_mapping[str(userid)] = str(chat_id)

    def _get_user_chat_id(self, userid: str) -> Optional[str]:
        """
        获取用户对应的聊天ID
        :param userid: 用户ID
        :return: 聊天ID或None
        """
        return self._user_chat_mapping.get(str(userid)) if userid else None

    def _should_process_message(self, message) -> bool:
        """
        判断是否应该处理这条消息
        :param message: Telegram消息对象
        :return: 是否处理
        """
        # 私聊消息总是处理
        if message.chat.type == "private":
            logger.debug(f"处理私聊消息：用户 {message.from_user.id}")
            return True

        # 消息内容：文本消息用 text，媒体消息的说明文字用 caption
        message_text = message.text or message.caption or ""

        # 群聊中的命令消息总是处理（以/开头）
        if message_text.startswith("/"):
            logger.debug(f"处理群聊命令消息：{message_text[:20]}...")
            return True

        # 群聊中检查是否@了机器人
        if message.chat.type in ["group", "supergroup"]:
            if not self._bot_username:
                # 如果没有获取到bot用户名，为了安全起见处理所有消息
                logger.debug("未获取到bot用户名，处理所有群聊消息")
                return True

            # 检查消息文本或说明文字中是否包含@bot_username
            if f"@{self._bot_username}" in message_text:
                logger.debug(f"检测到@{self._bot_username}，处理群聊消息")
                return True

            # 检查消息实体（文本消息用 entities，媒体消息用 caption_entities）
            entities = (message.entities if message.text is not None else message.caption_entities) or []
            for entity in entities:
                if entity.type == "mention":
                    # Telegram offset/length 基于 UTF-16 代码单元，需用字节编码处理含 emoji 的消息
                    mention_text = message_text.encode('utf-16-le')[
                        entity.offset * 2: (entity.offset + entity.length) * 2
                    ].decode('utf-16-le')
                    if mention_text == f"@{self._bot_username}":
                        logger.debug(
                            f"通过实体检测到@{self._bot_username}，处理群聊消息"
                        )
                        return True

            # 群聊中没有@机器人，不处理
            logger.debug(
                f"群聊消息未@机器人，跳过处理：{message_text[:30] if message_text else 'No text'}..."
            )
            return False

        # 其他类型的聊天默认处理
        logger.debug(f"处理其他类型聊天消息：{message.chat.type}")
        return True

    def get_state(self) -> bool:
        """
        获取状态
        """
        return self._bot is not None

    def _start_typing_task(
            self,
            chat_id: Union[str, int],
            max_duration_seconds: Optional[float] = None,
            initial_delay_seconds: Optional[float] = None,
    ) -> None:
        """
        启动持续发送正在输入状态的任务
        """
        chat_id_str = str(chat_id)
        # 如果已有任务在运行，先停止
        self._stop_typing_task(chat_id_str)

        # 使用独立 Event 避免同一 chat 新旧 typing 线程互相误改停止标记。
        stop_event = threading.Event()
        max_duration = max_duration_seconds or self._typing_max_duration_seconds
        initial_delay = (
            self._typing_initial_delay_seconds
            if initial_delay_seconds is None
            else max(initial_delay_seconds, 0)
        )

        def typing_worker():
            """延迟首发并定期发送 typing 状态的后台线程。"""
            started_at = time.monotonic()
            try:
                # Telegram 没有撤销 typing 的接口，短响应先等待一小段时间，
                # 避免回复已经发出后客户端仍残留几秒“正在输入”。
                if initial_delay and stop_event.wait(initial_delay):
                    return
                while not stop_event.is_set():
                    if time.monotonic() - started_at >= max_duration:
                        logger.warning(
                            "Telegram typing状态超过最大续期，自动停止: chat_id=%s",
                            chat_id_str,
                        )
                        break
                    try:
                        if self._bot:
                            self._bot.send_chat_action(chat_id, "typing")
                    except Exception as e:
                        logger.debug(f"发送typing状态失败: {e}")
                    # Telegram 客户端约 5-6 秒后会隐藏 typing，需要周期性续发。
                    stop_event.wait(self._typing_interval_seconds)
            finally:
                with self._typing_lock:
                    current = self._typing_tasks.get(chat_id_str)
                    if current is threading.current_thread():
                        self._typing_tasks.pop(chat_id_str, None)
                        self._typing_stop_flags.pop(chat_id_str, None)

        thread = threading.Thread(target=typing_worker, daemon=True)
        with self._typing_lock:
            self._typing_stop_flags[chat_id_str] = stop_event
            self._typing_tasks[chat_id_str] = thread
        thread.start()

    def _stop_typing_task(self, chat_id: Union[str, int]) -> None:
        """
        停止正在输入状态的任务
        """
        chat_id_str = str(chat_id)
        with self._typing_lock:
            stop_event = self._typing_stop_flags.pop(chat_id_str, None)
            task = self._typing_tasks.pop(chat_id_str, None)
        if stop_event:
            stop_event.set()
        if task and task.is_alive() and task is not threading.current_thread():
            task.join(timeout=1)

    def start_typing(
            self,
            chat_id: Optional[Union[str, int]] = None,
            userid: Optional[Union[str, int]] = None,
    ) -> bool:
        """
        外部链路主动启动 typing 状态。
        """
        if chat_id:
            target_chat_id = chat_id
        elif userid:
            target_chat_id = self._get_user_chat_id(str(userid)) or str(userid)
        else:
            target_chat_id = None
        target_chat_id = target_chat_id or (str(userid) if userid else None)
        if not target_chat_id:
            return False
        self._start_typing_task(target_chat_id)
        return True

    def stop_typing(
            self,
            chat_id: Optional[Union[str, int]] = None,
            userid: Optional[Union[str, int]] = None,
    ) -> bool:
        """
        外部链路主动停止 typing 状态。
        """
        if chat_id:
            target_chat_id = chat_id
        elif userid:
            target_chat_id = self._get_user_chat_id(str(userid)) or str(userid)
        else:
            target_chat_id = None
        target_chat_id = target_chat_id or (str(userid) if userid else None)
        if not target_chat_id:
            return False
        self._stop_typing_task(target_chat_id)
        return True

    def send_msg(
            self,
            title: str,
            text: Optional[str] = None,
            image: Optional[str] = None,
            userid: Optional[str] = None,
            link: Optional[str] = None,
            buttons: Optional[List[List[dict]]] = None,
    ) -> Optional[dict]:
        """
        发送Telegram消息
        :param title: 消息标题
        :param text: 消息内容
        :param image: 消息图片地址
        :param userid: 用户ID，如有则只发消息给该用户
        :param link: 跳转链接
        :param buttons: 按钮列表，格式：[[{"text": "按钮文本", "callback_data": "回调数据"}]]
        :return: 包含 message_id, chat_id, success 的字典
        """
        if not self._telegram_token or not self._telegram_chat_id:
            return None

        chat_id = self._determine_target_chat_id(userid)
        if not title and not text:
            logger.warning("标题和内容不能同时为空")
            return {"success": False}

        try:
            bold_title = self._format_title(title)
            # 正文同样需要转义：MarkdownV2 把 . - ( ) 等视为保留字符，
            # 未转义会导致整条消息被 Telegram 拒收或格式错乱；
            # text 里预设的 ``` 代码块需要保留，由 _format_text 处理
            formatted_text = self._format_text(text)
            if bold_title and formatted_text:
                caption = f"{bold_title}\n{formatted_text}"
            elif bold_title:
                caption = bold_title
            elif formatted_text:
                caption = formatted_text
            else:
                caption = ""

            if link:
                caption = f"{caption}\n{self._format_detail_link(link)}"

            reply_markup = self._create_inline_keyboard(buttons) if buttons else None
            sent = self.__send_request(
                userid=chat_id,
                image=image,
                caption=caption,
                reply_markup=reply_markup,
            )
            if sent and hasattr(sent, "message_id"):
                return {
                    "success": True,
                    "message_id": sent.message_id,
                    "chat_id": sent.chat.id if hasattr(sent, "chat") else chat_id,
                }
            if sent:
                return {"success": True}
            return {"success": False}

        except Exception as msg_e:
            logger.error(f"发送消息失败：{msg_e}")
            return {"success": False}

    def _determine_target_chat_id(self, userid: Optional[str] = None) -> str:
        """
        确定目标聊天ID，使用用户映射确保回复到正确的聊天
        :param userid: 用户ID
        :return: 目标聊天ID
        """
        if userid:
            mapped_chat_id = self._get_user_chat_id(userid)
            if mapped_chat_id:
                return mapped_chat_id
            # 如果映射中没有，回退到使用userid作为聊天ID (私聊场景)
            return userid
        return self._telegram_chat_id

    @staticmethod
    def _create_inline_keyboard(buttons: List[List[Dict]]) -> InlineKeyboardMarkup:
        """
        创建内联键盘
        :param buttons: 按钮配置，格式：[[{"text": "按钮文本", "callback_data": "回调数据", "url": "链接"}]]
        :return: InlineKeyboardMarkup对象
        """
        keyboard = []
        for row in buttons:
            button_row = []
            for button in row:
                if "url" in button:
                    # URL按钮
                    btn = InlineKeyboardButton(text=button["text"], url=button["url"])
                else:
                    # 回调按钮
                    btn = InlineKeyboardButton(
                        text=button["text"], callback_data=button["callback_data"]
                    )
                button_row.append(btn)
            keyboard.append(button_row)
        return InlineKeyboardMarkup(keyboard)

    def answer_callback_query(
            self,
            callback_query_id: int,
            text: Optional[str] = None,
            show_alert: bool = False,
    ) -> Optional[bool]:
        """
        回应回调查询
        """
        if not self._bot:
            return None

        try:
            self._bot.answer_callback_query(
                callback_query_id, text=text, show_alert=show_alert
            )
            return True
        except Exception as e:
            logger.error(f"回应回调查询失败：{str(e)}")
            return False

    def __send_request(
            self,
            userid: Optional[str] = None,
            image="",
            caption="",
            reply_markup: Optional[InlineKeyboardMarkup] = None,
    ):
        """
        向Telegram发送报文，返回发送的消息对象
        :param reply_markup: 内联键盘
        :return: 发送成功返回消息对象，失败返回None
        """
        kwargs = {
            "chat_id": userid or self._telegram_chat_id,
            "parse_mode": TELEGRAM_PARSE_MODE_MARKDOWN,
            "reply_markup": reply_markup,
        }
        image = self.__process_image(image)

        try:
            # 图片消息的标题长度限制为1024，文本消息为4096
            caption_limit = 1024 if image else 4096
            if len(caption) < caption_limit:
                return self.__send_short_message(image, caption, **kwargs)
            sent_idx = set()
            return self.__send_long_message(image, caption, sent_idx, **kwargs)
        except Exception as e:
            logger.error(f"发送Telegram消息失败: {e}")
            return None

    @staticmethod
    def __process_image(image_url: Optional[str]) -> Optional[bytes]:
        """
        处理图片URL，获取图片内容
        """
        if not image_url:
            return None
        image = ImageHelper().fetch_image(image_url)
        if not image:
            logger.warning(f"图片获取失败: {image_url}，仅发送文本消息")
        return image

    @retry(RetryException, logger=logger)
    def __send_short_message(self, image: Optional[bytes], caption: str, **kwargs):
        """
        发送短消息
        """
        try:
            if image:
                return self._bot.send_photo(
                    photo=image,
                    caption=self._prepare_text(caption),
                    **kwargs,
                )
            return self._bot.send_message(
                text=self._prepare_text(caption),
                **kwargs
            )
        except Exception:
            raise RetryException(f"发送{'图片' if image else '文本'}消息失败")

    @retry(RetryException, logger=logger)
    def __send_long_message(
            self, image: Optional[bytes], caption: str, sent_idx: set, **kwargs
    ):
        """
        发送长消息
        """

        reply_markup = kwargs.pop("reply_markup", None)

        boxs: list[Text | File | Photo] = (
            ThreadHelper()
            .submit(lambda x: asyncio.run(telegramify(x)), caption)
            .result()
        )

        ret = None
        for i, item in enumerate(boxs):
            if i in sent_idx:
                # 跳过已发送消息
                continue

            try:
                current_reply_markup = reply_markup if i == 0 else None

                if item.content_type == ContentTypes.TEXT and (i != 0 or not image):
                    ret = self._bot.send_message(
                        **kwargs,
                        text=self._telegramify_item_text(item),
                        reply_markup=current_reply_markup,
                    )

                elif item.content_type == ContentTypes.PHOTO or (image and i == 0):
                    ret = self._bot.send_photo(
                        **kwargs,
                        photo=(
                            getattr(item, "file_name", ""),
                            getattr(item, "file_data", image),
                        ),
                        caption=self._telegramify_item_caption(item),
                        reply_markup=current_reply_markup,
                    )

                elif item.content_type == ContentTypes.FILE:
                    ret = self._bot.send_document(
                        **kwargs,
                        document=(item.file_name, item.file_data),
                        caption=self._telegramify_item_caption(item),
                        reply_markup=current_reply_markup,
                    )

                sent_idx.add(i)

            except Exception as e:
                try:
                    raise RetryException(f"消息 [{i + 1}/{len(boxs)}] 发送失败") from e
                except NameError:
                    raise

        return ret

    def register_commands(self, commands: Dict[str, dict]):
        """
        注册菜单命令
        """
        if not self._bot:
            return
        # 设置bot命令
        if commands:
            self._bot.delete_my_commands()
            self._bot.set_my_commands(
                commands=[
                    BotCommand(cmd[1:], str(desc.get("description")))
                    for cmd, desc in commands.items()
                ]
            )

    def delete_commands(self):
        """
        清理菜单命令
        """
        if not self._bot:
            return
        # 清理菜单命令
        self._bot.delete_my_commands()

    def stop(self) -> None:
        """
        停止Telegram消息接收服务
        """
        # 停止所有typing任务
        for chat_id in list(self._typing_tasks.keys()):
            self._stop_typing_task(chat_id)
        if not self._bot:
            return

        self._bot.stop_bot()
        if self._polling_thread:
            self._polling_thread.join()
        self._polling_thread = None
        self._bot = None
        logger.info("Telegram消息接收服务已停止")
