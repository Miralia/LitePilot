import ipaddress
import threading
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, List, Annotated

from cachetools import TTLCache
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse

from app import schemas
from app.chain.user import MfaRequired, UserChain
from app.core import security
from app.core.config import settings
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.image import WallpaperHelper
from app.helper.swizzin import SwizzinUserSync
from app.schemas.types import SystemConfigKey


_LOGIN_FAILURE_WINDOW_SECONDS = 600
_LOGIN_ACCOUNT_FAILURE_THRESHOLD = 5
_LOGIN_IP_FAILURE_THRESHOLD = 30
_LOGIN_BLOCK_BASE_SECONDS = 15
_LOGIN_BLOCK_MAX_SECONDS = 300
_LOGIN_THROTTLE_CACHE_SIZE = 4096


@dataclass
class _LoginThrottleState:
    """单个限流键在固定统计窗口内的失败次数与解除时间。"""

    failures: int = 0
    window_started_at: float = 0.0
    blocked_until: float = 0.0


_login_throttle_lock = threading.RLock()
_login_throttle_states: TTLCache = TTLCache(
    maxsize=_LOGIN_THROTTLE_CACHE_SIZE,
    ttl=_LOGIN_FAILURE_WINDOW_SECONDS + _LOGIN_BLOCK_MAX_SECONDS,
)


def _login_client_host(request: Request) -> str:
    """
    返回用于限流的客户端地址。

    只有直连 peer 是本机反向代理时才信任 ``X-Forwarded-For``。nginx 使用
    ``$proxy_add_x_forwarded_for`` 把真实远端追加到链尾，因此取最后一个
    有效地址；客户端预置的伪造首跳不能参与限流身份。
    """
    client_host = request.client.host if request.client else "unknown"
    if client_host not in {"127.0.0.1", "::1"}:
        return client_host
    forwarded_for = request.headers.get("x-forwarded-for", "")
    candidates = [part.strip() for part in forwarded_for.split(",") if part.strip()]
    if not candidates:
        return client_host
    forwarded_host = candidates[-1]
    try:
        ipaddress.ip_address(forwarded_host)
    except ValueError:
        return client_host
    return forwarded_host


def _login_throttle_keys(request: Request, username: str | None) -> tuple[tuple[str, ...], ...]:
    """生成账号级与来源 IP 级限流键，避免单账号绕过或单账号爆破。"""
    client_host = _login_client_host(request)
    normalized_username = (username or "").strip().casefold()
    return (
        ("account", client_host, normalized_username),
        ("ip", client_host),
    )


def _login_retry_after(keys: tuple[tuple[str, ...], ...], now: float) -> int:
    """返回当前限流剩余秒数，未被限流时返回零。"""
    with _login_throttle_lock:
        retry_after = 0
        for key in keys:
            state = _login_throttle_states.get(key)
            if state and state.blocked_until > now:
                retry_after = max(retry_after, int(state.blocked_until - now) + 1)
        return retry_after


def _record_login_failures(keys: tuple[tuple[str, ...], ...], now: float) -> None:
    """记录一次真实认证失败，并按连续失败次数施加指数退避。"""
    with _login_throttle_lock:
        for key in keys:
            threshold = (
                _LOGIN_IP_FAILURE_THRESHOLD if key[0] == "ip" else _LOGIN_ACCOUNT_FAILURE_THRESHOLD
            )
            state = _login_throttle_states.get(key)
            if state is None or now - state.window_started_at >= _LOGIN_FAILURE_WINDOW_SECONDS:
                state = _LoginThrottleState(window_started_at=now)
            state.failures += 1
            if state.failures >= threshold:
                backoff_step = min(state.failures - threshold, 8)
                block_seconds = min(
                    _LOGIN_BLOCK_BASE_SECONDS * (2 ** backoff_step),
                    _LOGIN_BLOCK_MAX_SECONDS,
                )
                state.blocked_until = max(state.blocked_until, now + block_seconds)
            _login_throttle_states[key] = state


def _clear_account_login_throttle(account_key: tuple[str, ...]) -> None:
    """认证成功后只清除该账号的失败状态，保留来源 IP 的暴力破解证据。"""
    with _login_throttle_lock:
        _login_throttle_states.pop(account_key, None)


router = APIRouter()


@router.post("/access-token", summary="获取token", response_model=schemas.Token)
def login_access_token(
    request: Request,
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    otp_password: Annotated[str | None, Form()] = None,
) -> Any:
    """
    获取认证Token
    """
    throttle_keys = _login_throttle_keys(request, form_data.username)
    now = time.monotonic()
    retry_after = _login_retry_after(throttle_keys, now)
    if retry_after:
        raise HTTPException(
            status_code=429,
            detail="登录尝试过于频繁，请稍后再试",
            headers={"Retry-After": str(retry_after)},
        )

    # swizzin 环境先按用户清单补齐本地账号，未安装 swizzin 时退化为单管理员
    SwizzinUserSync().sync()
    success, user_or_message = UserChain().user_authenticate(
        username=form_data.username, password=form_data.password, mfa_code=otp_password
    )

    if not success:
        # 只有密码已经验证通过时才返回 MFA 方法，避免泄露账号安全配置。
        if isinstance(user_or_message, MfaRequired):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "需要二次验证",
                    "mfa_methods": list(user_or_message.methods),
                },
                headers={"X-MFA-Required": "true"},
            )
        _record_login_failures(throttle_keys, time.monotonic())
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    _clear_account_login_throttle(throttle_keys[0])

    # 是否显示配置向导
    show_wizard = (
        not SystemConfigOper().get(SystemConfigKey.SetupWizardState)
        and not settings.ADVANCED_MODE
    )
    access_token = security.create_access_token(
        userid=user_or_message.id,
        username=user_or_message.name,
        super_user=user_or_message.is_superuser,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    security.set_or_refresh_resource_token_cookie(
        request,
        response,
        schemas.TokenPayload(
            sub=user_or_message.id,
            username=user_or_message.name,
            super_user=user_or_message.is_superuser,
            purpose="authentication",
        ),
    )

    return schemas.Token(
        access_token=access_token,
        token_type="bearer",
        super_user=user_or_message.is_superuser,
        user_id=user_or_message.id,
        user_name=user_or_message.name,
        avatar=user_or_message.avatar,
        permissions=user_or_message.permissions or {},
        wizard=show_wizard,
    )


@router.get("/wallpapers", summary="登录页面电影海报列表", response_model=List[str])
def wallpapers() -> Any:
    """
    获取登录页面电影海报
    """
    return WallpaperHelper().get_wallpapers()
