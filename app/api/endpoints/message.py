import time
from typing import Any, List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.core.security import verify_token
from app.db import get_async_db
from app.db.message_oper import MessageOper
from app.db.systemconfig_oper import SystemConfigOper
from app.schemas.types import SystemConfigKey

router = APIRouter()


def _normalize_notification_clear_timestamp(value: Any) -> int:
    """
    规范化通知清理时间戳。
    """
    try:
        normalized_value = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return normalized_value if normalized_value > 0 else 0


def _get_notification_clear_before() -> schemas.NotificationClearBefore:
    """
    读取通知中心清理时间配置。
    """
    value = SystemConfigOper().get(SystemConfigKey.NotificationClearBefore)
    if isinstance(value, dict):
        return schemas.NotificationClearBefore(
            all=_normalize_notification_clear_timestamp(value.get("all")),
            system=_normalize_notification_clear_timestamp(value.get("system")),
            media=_normalize_notification_clear_timestamp(value.get("media")),
        )
    return schemas.NotificationClearBefore(
        all=_normalize_notification_clear_timestamp(value),
    )


def _format_notification_clear_time(value: int) -> Optional[str]:
    """
    将清理时间戳转换为消息表使用的时间字符串。
    """
    if not value:
        return None
    timestamp = value / 1000 if value > 10000000000 else value
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))


@router.get("/notification", summary="获取通知消息", response_model=List[schemas.NotificationHistoryItem])
async def get_notification_message(
    _: schemas.TokenPayload = Depends(verify_token),
    db: AsyncSession = Depends(get_async_db),
    page: Optional[int] = 1,
    count: Optional[int] = 20,
):
    """
    获取系统发送的通知消息列表。
    """
    clear_before = _get_notification_clear_before()
    messages = await MessageOper(db).async_list_sent_by_page(
        page=page,
        count=count,
        all_clear_before=_format_notification_clear_time(clear_before.all),
        system_clear_before=_format_notification_clear_time(clear_before.system),
        media_clear_before=_format_notification_clear_time(clear_before.media),
    )
    return [schemas.NotificationHistoryItem(**message.to_dict()) for message in messages]


@router.delete("/notification", summary="清理通知消息", response_model=schemas.Response)
async def clear_notification_message(
    scope: schemas.NotificationClearScope = schemas.NotificationClearScope.All,
    _: schemas.TokenPayload = Depends(verify_token),
):
    """
    记录通知中心清理时间，后续通知历史查询会在服务端过滤。
    """
    clear_before = _get_notification_clear_before()
    value = clear_before.model_dump()
    value[scope.value] = int(time.time() * 1000)
    await SystemConfigOper().async_set(SystemConfigKey.NotificationClearBefore, value)
    return schemas.Response(success=True, data={"clear_before": value})
