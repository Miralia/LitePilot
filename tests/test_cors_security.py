"""CORS 中间件凭据与通配来源组合的安全边界测试。"""

from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.factory import create_app


def _cors_kwargs(app) -> dict:
    """读取应用注册的 CORSMiddleware 配置。"""
    middleware = next(item for item in app.user_middleware if item.cls is CORSMiddleware)
    return middleware.kwargs


def test_wildcard_cors_origin_disables_credentials(monkeypatch) -> None:
    """通配来源不得携带浏览器凭据，避免任意站点反射 Origin 读取资源接口。"""
    monkeypatch.setattr(settings, "ALLOWED_HOSTS", ["*"])

    kwargs = _cors_kwargs(create_app())

    assert kwargs["allow_origins"] == ["*"]
    assert kwargs["allow_credentials"] is False


def test_explicit_cors_origins_keep_credentials(monkeypatch) -> None:
    """显式配置的受信来源仍可携带凭据，兼容确有跨源前端的部署。"""
    origins = ["https://ui.example.com"]
    monkeypatch.setattr(settings, "ALLOWED_HOSTS", origins)

    kwargs = _cors_kwargs(create_app())

    assert kwargs["allow_origins"] == origins
    assert kwargs["allow_credentials"] is True
