"""
MFA (Multi-Factor Authentication) API 端点
包含 OTP 相关功能
"""

from typing import Any, Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.core import security
from app.db import get_async_db
from app.db.models.user import User
from app.db.user_oper import get_current_active_user, get_current_active_user_async
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
