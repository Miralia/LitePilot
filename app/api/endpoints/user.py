from typing import Annotated, Any, Union

from fastapi import APIRouter, Body, Depends, HTTPException

from app import schemas
from app.db.models.user import User
from app.db.user_oper import (
    get_current_active_user_async,
    get_current_active_user,
)
from app.db.userconfig_oper import UserConfigOper
from app.schemas.types import UserConfigKey

router = APIRouter()

_USER_CONFIG_KEYS = frozenset(item.value for item in UserConfigKey)


def _validate_user_config_key(key: str) -> str:
    """校验用户配置键属于当前前端封闭契约。"""
    if key not in _USER_CONFIG_KEYS:
        raise HTTPException(status_code=422, detail="不支持的用户配置键")
    return key


@router.get("/current", summary="当前登录用户信息", response_model=schemas.User)
async def read_current_user(
    current_user: User = Depends(get_current_active_user_async),
) -> Any:
    """
    当前登录用户信息
    """
    return current_user


@router.get("/config/{key}", summary="查询用户配置", response_model=schemas.Response)
def get_config(key: str, current_user: User = Depends(get_current_active_user)):
    """
    查询用户配置
    """
    config_key = _validate_user_config_key(key)
    value = UserConfigOper().get(username=current_user.name, key=config_key)
    return schemas.Response(success=True, data={"value": value})


@router.post("/config/{key}", summary="更新用户配置", response_model=schemas.Response)
def set_config(
    key: str,
    value: Annotated[Union[list, dict, bool, int, str] | None, Body()] = None,
    current_user: User = Depends(get_current_active_user),
):
    """
    更新用户配置
    """
    config_key = _validate_user_config_key(key)
    UserConfigOper().set(username=current_user.name, key=config_key, value=value)
    return schemas.Response(success=True)
