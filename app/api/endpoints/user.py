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


@router.get("/", summary="所有用户", response_model=List[schemas.User])
async def list_users(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_superuser_async),
) -> Any:
    """
    查询用户列表，返回前先与 swizzin 用户同步
    """
    SwizzinUserSync().sync()
    return await current_user.async_list(db)




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


@router.post(
    "/avatar/{user_id}", summary="上传用户头像", response_model=schemas.Response
)
async def upload_avatar(
    user_id: int,
    db: AsyncSession = Depends(get_async_db),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user_async),
) -> schemas.Response:
    """
    上传用户头像
    """
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(status_code=400, detail="用户权限不足")

    # 将文件转换为Base64
    file_base64 = base64.b64encode(file.file.read())
    # 更新到用户表
    user = await User.async_get(db, user_id)
    if not user:
        return schemas.Response(success=False, message="用户不存在")
    await user.async_update(db, {"avatar": f"data:image/ico;base64,{file_base64}"})
    return schemas.Response(success=True, data={"filename": file.filename})


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






@router.get("/{username}", summary="用户详情", response_model=schemas.User)
async def read_user_by_name(
    username: str,
    current_user: User = Depends(get_current_active_user_async),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    """
    查询用户详情
    """
    user = await current_user.async_get_by_name(db, name=username)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="用户不存在",
        )
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise HTTPException(status_code=400, detail="用户权限不足")
    return user
