"""
MFA (Multi-Factor Authentication) API 端点
包含 OTP 相关功能
"""

from datetime import timedelta
from typing import Any, Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Body, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.core import security
from app.core.config import settings
from app.db import get_async_db
from app.db.models.user import User
from app.db.systemconfig_oper import SystemConfigOper
from app.db.user_oper import get_current_active_user, get_current_active_user_async
from app.log import logger
from app.schemas.types import SystemConfigKey
from app.utils.otp import OtpUtils

router = APIRouter()

# ==================== 辅助函数 ====================


# ==================== 请求模型 ====================


class OtpVerifyRequest(schemas.BaseModel):
    """OTP验证请求"""

    uri: str
    otpPassword: str


class OtpDisableRequest(schemas.BaseModel):
    """OTP禁用请求"""

    password: str


# ==================== 通用 MFA 接口 ====================


@router.get(
    "/status/{username}",
    summary="判断用户是否开启二次验证",
    response_model=schemas.Response,
)
async def mfa_status(username: str, db: AsyncSession = Depends(get_async_db)) -> Any:
    """
    检查指定用户是否启用了二次验证
    """
    user: User = await User.async_get_by_name(db, username)
    if not user:
        return schemas.Response(success=False)

    # 检查是否启用了OTP
    has_otp = user.is_otp

    return schemas.Response(success=has_otp)


# ==================== OTP 相关接口 ====================


@router.post(
    "/otp/generate", summary="生成 OTP 验证 URI", response_model=schemas.Response
)
def otp_generate(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> Any:
    """生成 OTP 密钥及对应的 URI"""
    secret, uri = OtpUtils.generate_secret_key(current_user.name)
    return schemas.Response(success=secret != "", data={"secret": secret, "uri": uri})


@router.post("/otp/verify", summary="绑定并验证 OTP", response_model=schemas.Response)
async def otp_verify(
    data: OtpVerifyRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user_async),
) -> Any:
    """验证用户输入的 OTP 码，验证通过后正式开启 OTP 验证"""
    if not OtpUtils.is_legal(data.uri, data.otpPassword):
        return schemas.Response(success=False, message="验证码错误")
    await current_user.async_update_otp_by_name(
        db, current_user.name, True, OtpUtils.get_secret(data.uri)
    )
    return schemas.Response(success=True)


@router.post(
    "/otp/disable", summary="关闭当前用户的 OTP 验证", response_model=schemas.Response
)
async def otp_disable(
    data: OtpDisableRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user_async),
) -> Any:
    """关闭当前用户的 OTP 验证功能"""
    # 验证密码
    if not security.verify_password(data.password, str(current_user.hashed_password)):
        return schemas.Response(success=False, message="密码错误")
    await current_user.async_update_otp_by_name(db, current_user.name, False, "")
    return schemas.Response(success=True)
