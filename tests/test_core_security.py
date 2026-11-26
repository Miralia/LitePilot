"""认证凭证状态码边界测试。"""

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

import app.core.security as security
from app import schemas
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


def test_api_key_falls_back_to_superuser_payload(monkeypatch):
    """普通受保护端点通过统一 verify_token 接受 X-API-KEY/apikey。"""
    expected = schemas.TokenPayload(
        sub=1,
        username="admin",
        super_user=True,
        purpose="authentication",
    )
    monkeypatch.setattr(security.settings, "API_TOKEN", "test-api-token")
    monkeypatch.setattr(
        security, "__create_superuser_token_payload", lambda: expected
    )

    payload = verify_token(
        request=_build_request(),
        response=Response(),
        jwt_token=None,
        api_key="test-api-token",
        api_token=None,
    )

    assert payload is expected


def test_query_api_token_falls_back_to_superuser_payload(monkeypatch):
    """普通受保护端点通过统一 verify_token 接受 token 查询参数。"""
    expected = schemas.TokenPayload(
        sub=1,
        username="admin",
        super_user=True,
        purpose="authentication",
    )
    monkeypatch.setattr(security.settings, "API_TOKEN", "test-api-token")
    monkeypatch.setattr(
        security, "__create_superuser_token_payload", lambda: expected
    )

    payload = verify_token(
        request=_build_request(),
        response=Response(),
        jwt_token=None,
        api_key=None,
        api_token="test-api-token",
    )

    assert payload is expected


def test_invalid_api_token_fallback_returns_unauthorized(monkeypatch):
    """API_TOKEN fallback 使用错误凭据时仍是凭证失败。"""
    monkeypatch.setattr(security.settings, "API_TOKEN", "test-api-token")

    with pytest.raises(HTTPException) as exc_info:
        verify_token(
            request=_build_request(),
            response=Response(),
            jwt_token=None,
            api_key=None,
            api_token="wrong-token",
        )

    assert exc_info.value.status_code == 401
