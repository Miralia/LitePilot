"""认证凭证状态码边界测试。"""

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from app.core.security import verify_resource_token, verify_token


def _build_request() -> Request:
    """构造最小测试请求。"""
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/user/current",
            "headers": [(b"host", b"testserver")],
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 123),
        }
    )


def test_invalid_authentication_token_returns_unauthorized():
    """无效认证令牌是凭证失败，必须区别于已登录后的权限不足。"""
    with pytest.raises(HTTPException) as exc_info:
        verify_token(
            request=_build_request(),
            response=Response(),
            jwt_token="invalid-token",
            api_key=None,
            api_token=None,
        )

    assert exc_info.value.status_code == 401


def test_invalid_resource_token_returns_unauthorized():
    """无效资源令牌同样是凭证失败，不能用权限不足语义混淆。"""
    with pytest.raises(HTTPException) as exc_info:
        verify_resource_token("invalid-token")

    assert exc_info.value.status_code == 401
