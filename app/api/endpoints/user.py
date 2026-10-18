import base64
import re
from typing import Annotated, Any, List, Union

from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.core.security import get_password_hash
from app.db import get_async_db
from app.db.models.user import User
from app.db.user_oper import (
    get_current_active_superuser_async,
    get_current_active_user_async,
    get_current_active_user,
)
from app.db.userconfig_oper import UserConfigOper
from app.helper.swizzin import SwizzinUserSync

router = APIRouter()




@router.put("/", summary="更新当前用户", response_model=schemas.Response)
async def update_user(
    *,
    db: AsyncSession = Depends(get_async_db),
    user_in: schemas.UserUpdate,
    current_user: User = Depends(get_current_active_user_async),
) -> Any:
    """
    更新当前登录用户（用户名与权限由 swizzin 统一管理，此处不可变更）
    """
    user_info = user_in.model_dump()
    user_info.pop("name", None)
    user_info.pop("is_superuser", None)
    user_info.pop("is_active", None)
    if user_info.get("password"):
        # 正则表达式匹配密码包含字母、数字、特殊字符中的至少两项
        pattern = r"^(?![a-zA-Z]+$)(?!\d+$)(?![^\da-zA-Z\s]+$).{6,50}$"
        if not re.match(pattern, user_info.get("password")):
            return schemas.Response(
                success=False,
                message="密码需要同时包含字母、数字、特殊字符中的至少两项，且长度大于6位",
            )
        user_info["hashed_password"] = get_password_hash(user_info["password"])
        user_info.pop("password")
    user_info["id"] = current_user.id
    await current_user.async_update(db, user_info)
    return schemas.Response(success=True)


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
    value = UserConfigOper().get(username=current_user.name, key=key)
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
    UserConfigOper().set(username=current_user.name, key=key, value=value)
    return schemas.Response(success=True)
