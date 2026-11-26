from enum import Enum
from typing import Optional, Union, List

from pydantic import BaseModel

from app.schemas.types import ContentType, NotificationType, MessageChannel


class NotificationClearScope(str, Enum):
    """
    通知中心清理范围。
    """

    # 全部消息
    All = "all"
    # 系统消息
    System = "system"
    # 媒体消息
    Media = "media"


class NotificationClearBefore(BaseModel):
    """
    通知中心按范围记录的清理时间。
    """

    # 全部消息清理时间
    all: int = 0
    # 系统消息清理时间
    system: int = 0
    # 媒体消息清理时间
    media: int = 0


class NotificationHistoryItem(BaseModel):
    """
    通知历史记录。
    """

    # 消息ID
    id: Optional[int] = None
    # 消息渠道
    channel: Optional[str] = None
    # 消息来源
    source: Optional[str] = None
    # 消息类型
    mtype: Optional[str] = None
    # 标题
    title: Optional[str] = None
    # 文本内容
    text: Optional[str] = None
    # 图片
    image: Optional[str] = None
    # 链接
    link: Optional[str] = None
    # 用户ID
    userid: Optional[str] = None
    # 登记时间
    reg_time: Optional[str] = None
    # 消息方向：0-接收消息，1-发送消息
    action: Optional[int] = None
    # 附件json
    note: Optional[Union[list, dict]] = None


class CommingMessage(BaseModel):
    """
    外来消息
    """

    # 用户ID
    userid: Optional[Union[str, int]] = None
    # 用户名称
    username: Optional[Union[str, int]] = None
    # 消息渠道
    channel: Optional[MessageChannel] = None
    # 来源（渠道名称）
    source: Optional[str] = None
    # 消息体
    text: Optional[str] = None
    # 消息ID（用于回调时定位原消息）
    message_id: Optional[Union[str, int]] = None
    # 聊天ID（用于回调时定位聊天）
    chat_id: Optional[str] = None

    def to_dict(self):
        """
        转换为字典
        """
        items = self.model_dump()
        for k, v in items.items():
            if isinstance(v, MessageChannel):
                items[k] = v.value
        return items


class Notification(BaseModel):
    """
    消息
    """

    # 消息渠道
    channel: Optional[MessageChannel] = None
    # 消息来源
    source: Optional[str] = None
    # 消息类型
    mtype: Optional[NotificationType] = None
    # 内容类型
    ctype: Optional[ContentType] = None
    # 标题
    title: Optional[str] = None
    # 文本内容
    text: Optional[str] = None
    # 图片
    image: Optional[str] = None
    # 链接
    link: Optional[str] = None
    # 用户ID
    userid: Optional[Union[str, int]] = None
    # 用户名称
    username: Optional[Union[str, int]] = None
    # 时间
    date: Optional[str] = None
    # 消息方向
    action: Optional[int] = 1
    # 消息目标用户ID字典，未指定用户ID时使用
    targets: Optional[dict] = None
    # 按钮列表，格式：[[{"text": "按钮文本", "callback_data": "回调数据", "url": "链接"}]]
    buttons: Optional[List[List[dict]]] = None
    # 是否写入消息历史
    save_history: bool = True

    def to_dict(self):
        """
        转换为字典
        """
        items = self.model_dump()
        for k, v in items.items():
            if isinstance(v, MessageChannel) or isinstance(v, NotificationType):
                items[k] = v.value
        return items
