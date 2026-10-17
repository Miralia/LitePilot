from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from app.chain import ChainBase
from app.chain.transfer import TransferChain
from app.core.config import settings
from app.log import logger
from app.schemas import CommingMessage, Notification
from app.schemas.message import ChannelCapabilityManager
from app.schemas.types import EventType, MessageChannel


class MessageChain(ChainBase):
    """
    外来消息处理链

    本分支只保留三类交互：斜杠命令执行、整理失败通知的重试回调、插件消息回调。
    智能体对话、订阅/技能交互、未识别资源的搜索下载交互已随对应能力一并删除。
    """

    @dataclass
    class _ProcessingStatus:
        """渠道侧“消息正在处理”状态的规范化结构。"""

        channel: MessageChannel
        source: str
        userid: Optional[Union[str, int]] = None
        message_id: Optional[Union[str, int]] = None
        chat_id: Optional[Union[str, int]] = None
        metadata: Optional[Dict[str, Any]] = None

        def to_dict(self) -> Dict[str, Any]:
            """转换为模块接口可安全传递的普通字典。"""
            return {
                "channel": self.channel.value,
                "source": self.source,
                "userid": self.userid,
                "message_id": self.message_id,
                "chat_id": self.chat_id,
                "metadata": self.metadata or {},
            }

    def process(self, body: Any, form: Any, args: Any) -> None:
        """
        调用模块识别消息内容
        """
        # 消息来源
        source = args.get("source")
        # 获取消息内容
        info = self.message_parser(source=source, body=body, form=form, args=args)
        if not info:
            logger.info("消息链路未识别到有效消息: source=%s", source)
            return
        # 更新消息来源
        source = info.source
        # 渠道
        channel = info.channel
        # 用户ID
        userid = info.userid
        # 用户名（当渠道未提供公开用户名时，回退为 userid 的字符串，避免后续类型校验异常）
        username = (
            str(info.username) if info.username not in (None, "") else str(userid)
        )
        if userid is None or userid == "":
            logger.debug(f"未识别到用户ID：{body}{form}{args}")
            return

        # 消息内容（本分支只处理文本，图片/语音/附件随智能体一并删除）
        text = str(info.text).strip() if info.text else ""
        if not text:
            logger.debug(f"未识别到消息内容：：{body}{form}{args}")
            return

        # 处理消息
        self.handle_message(
            channel=channel,
            source=source,
            userid=userid,
            username=username,
            text=text,
            original_message_id=info.message_id,
            original_chat_id=info.chat_id,
            reply_to_message_id=info.reply_to_message_id,
        )

    def handle_message(
            self,
            channel: MessageChannel,
            source: str,
            userid: Union[str, int],
            username: str,
            text: Optional[str],
            original_message_id: Optional[Union[str, int]] = None,
            original_chat_id: Optional[str] = None,
            reply_to_message_id: Optional[Union[str, int]] = None,
    ) -> None:
        """
        识别消息内容，执行操作
        """
        processing_status = None
        processing_finish_deferred = False
        try:
            if not text.startswith("CALLBACK:"):
                self._record_user_message(
                    channel=channel,
                    source=source,
                    userid=userid,
                    username=username,
                    text=text,
                )
                processing_status = self._mark_message_processing_started(
                    channel=channel,
                    source=source,
                    userid=userid,
                    original_message_id=original_message_id,
                    original_chat_id=original_chat_id,
                    text=text,
                )

            processing_finish_deferred = self._handle_message_core(
                channel=channel,
                source=source,
                userid=userid,
                username=username,
                text=text,
                original_message_id=original_message_id,
                original_chat_id=original_chat_id,
                reply_to_message_id=reply_to_message_id,
                processing_status=processing_status,
            ) is True
        finally:
            if not processing_finish_deferred:
                self._mark_message_processing_finished(
                    channel=channel,
                    source=source,
                    userid=userid,
                    status=processing_status,
                    original_message_id=original_message_id,
                    original_chat_id=original_chat_id,
                )

    def _handle_message_core(
            self,
            channel: MessageChannel,
            source: str,
            userid: Union[str, int],
            username: str,
            text: Optional[str],
            original_message_id: Optional[Union[str, int]] = None,
            original_chat_id: Optional[str] = None,
            processing_status: Optional[_ProcessingStatus] = None,
            reply_to_message_id: Optional[Union[str, int]] = None,
    ) -> bool:
        """执行实际消息路由，便于统一包裹处理中状态。"""

        if text.startswith("CALLBACK:"):
            if ChannelCapabilityManager.supports_callbacks(channel):
                return self._handle_callback(
                    text=text,
                    channel=channel,
                    source=source,
                    userid=userid,
                    username=username,
                    original_message_id=original_message_id,
                    original_chat_id=original_chat_id,
                    processing_status=processing_status,
                )
            logger.warning(
                "渠道 %s 不支持回调，但收到了回调消息：%s",
                channel.value,
                text,
            )
            return False

        # 斜杠命令交给命令链处理
        if text.startswith("/"):
            self.eventmanager.send_event(
                EventType.CommandExcute,
                {
                    "cmd": text,
                    "user": userid,
                    "channel": channel,
                    "source": source,
                    "processing_status": processing_status.to_dict()
                    if processing_status
                    else None,
                },
            )
            return bool(processing_status)

        # 其余文本广播给关注用户消息的模块与插件
        self.eventmanager.send_event(
            EventType.UserMessage,
            {
                "text": text,
                "userid": userid,
                "channel": channel,
                "source": source,
                "chat_id": original_chat_id,
                "reply_to_message_id": reply_to_message_id,
            },
        )
        return False

    def _mark_message_processing_started(
            self,
            channel: MessageChannel,
            source: str,
            userid: Union[str, int],
            original_message_id: Optional[Union[str, int]],
            original_chat_id: Optional[Union[str, int]],
            text: str,
    ) -> Optional[_ProcessingStatus]:
        """为支持的渠道标记“消息正在处理”。"""
        status = self.start_message_processing_status(
            channel=channel,
            source=source,
            userid=userid,
            message_id=original_message_id,
            chat_id=original_chat_id,
            text=text,
        )
        if not status:
            return None

        metadata = status.get("metadata")
        return self._ProcessingStatus(
            channel=channel,
            source=source,
            userid=status.get("userid", userid),
            message_id=status.get("message_id", original_message_id),
            chat_id=status.get("chat_id", original_chat_id),
            metadata=metadata if isinstance(metadata, dict) else {},
        )

    def _mark_message_processing_finished(
            self,
            channel: MessageChannel,
            source: str,
            userid: Union[str, int],
            status: Optional[_ProcessingStatus] = None,
            original_message_id: Optional[Union[str, int]] = None,
            original_chat_id: Optional[Union[str, int]] = None,
    ) -> None:
        """
        结束渠道侧“消息正在处理”状态。
        不同渠道的表现可能是 reaction、typing 等，消息链只负责调用通用模块接口。
        """
        if not status:
            return
        self.finish_message_processing_status(
            status=status.to_dict(),
            channel=channel,
            source=source,
            userid=userid,
            message_id=status.message_id or original_message_id,
            chat_id=status.chat_id or original_chat_id,
        )

    def _handle_callback(
            self,
            text: str,
            channel: MessageChannel,
            source: str,
            userid: Union[str, int],
            username: str,
            original_message_id: Optional[Union[str, int]] = None,
            original_chat_id: Optional[str] = None,
            processing_status: Optional[_ProcessingStatus] = None,
    ) -> bool:
        """
        处理按钮回调
        """

        # 提取回调数据
        callback_data = text[9:]  # 去掉 "CALLBACK:" 前缀
        logger.info(f"处理按钮回调：{callback_data}")

        if self._handle_transfer_callback(
                callback_data=callback_data,
                channel=channel,
                source=source,
                userid=userid,
                username=username,
        ):
            return False

        # 插件消息的事件回调 [PLUGIN]插件ID|内容
        if callback_data.startswith("[PLUGIN]"):
            # 提取插件ID和内容
            plugin_id, content = callback_data.split("|", 1)
            # 广播给插件处理
            self.eventmanager.send_event(
                EventType.MessageAction,
                {
                    "plugin_id": plugin_id.replace("[PLUGIN]", ""),
                    "text": content,
                    "userid": userid,
                    "channel": channel,
                    "source": source,
                    "original_message_id": original_message_id,
                    "original_chat_id": original_chat_id,
                },
            )
            return False

        logger.error(f"回调数据格式错误：{callback_data}")
        self.post_message(
            Notification(
                channel=channel,
                source=source,
                userid=userid,
                username=username,
                title="回调数据格式错误，请检查！",
                save_history=False,
            )
        )
        return False

    @staticmethod
    def _parse_transfer_callback(
            callback_data: str,
    ) -> Optional[tuple[str, int]]:
        """
        解析整理失败通知按钮回调。
        """
        prefix = "transfer_retry_"
        if callback_data.startswith(prefix):
            history_id = callback_data.replace(prefix, "", 1)
            if history_id.isdigit():
                return "retry", int(history_id)
        return None

    def _handle_transfer_callback(
            self,
            callback_data: str,
            channel: MessageChannel,
            source: str,
            userid: Union[str, int],
            username: str,
    ) -> bool:
        """
        处理整理失败通知中的重试类按钮。
        """
        callback = self._parse_transfer_callback(callback_data)
        if not callback:
            return False

        action, history_id = callback
        if action == "retry":
            self._retry_transfer_history(
                history_id=history_id,
                channel=channel,
                source=source,
                userid=userid,
                username=username,
            )
        return True

    def _retry_transfer_history(
            self,
            history_id: int,
            channel: MessageChannel,
            source: str,
            userid: Union[str, int],
            username: str,
    ) -> None:
        """
        立即重新整理一条失败的整理记录。
        """
        self.post_message(
            Notification(
                channel=channel,
                source=source,
                userid=userid,
                username=username,
                title=f"开始重新整理记录 #{history_id} ...",
                save_history=False,
            )
        )

        state, errmsg = TransferChain().redo_transfer_history(history_id)
        if state:
            self.post_message(
                Notification(
                    channel=channel,
                    source=source,
                    userid=userid,
                    username=username,
                    title=f"整理记录 #{history_id} 已重新整理",
                    link=settings.MP_DOMAIN("#/history"),
                    save_history=False,
                )
            )
            return

        self.post_message(
            Notification(
                channel=channel,
                source=source,
                userid=userid,
                username=username,
                title="重新整理失败",
                text=errmsg,
                link=settings.MP_DOMAIN("#/history"),
                save_history=False,
            )
        )

    def _record_user_message(
            self,
            channel: MessageChannel,
            source: str,
            userid: Union[str, int],
            username: str,
            text: str,
    ) -> None:
        """
        保存一条用户消息到消息历史与数据库。
        """
        self.messagehelper.put(
            CommingMessage(
                userid=userid,
                username=username,
                channel=channel,
                source=source,
                text=text,
            ),
            role="user",
        )
        self.messageoper.add(
            channel=channel,
            source=source,
            userid=username or userid,
            text=text,
            action=0,
        )
