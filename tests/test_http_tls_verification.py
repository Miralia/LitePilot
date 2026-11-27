"""出站 HTTP TLS 证书校验默认值测试。"""

from app.core.config import settings
from app.utils.http import AsyncRequestUtils, RequestUtils


def test_sync_requests_verify_tls_by_default(monkeypatch):
    """同步外部请求默认必须校验 TLS 证书，避免代理链路静默 MITM。"""
    captured = {}

    class Response:
        def close(self):
            return None

    def fake_request(method, url, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr("app.utils.http.requests.request", fake_request)

    RequestUtils().request("get", "https://example.com/")

    assert captured["verify"] is True


def test_sync_requests_can_explicitly_opt_out_of_tls_verification(monkeypatch):
    """调用方显式传入 verify=False 时保留自签名内网服务兼容能力。"""
    captured = {}

    class Response:
        def close(self):
            return None

    def fake_request(method, url, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr("app.utils.http.requests.request", fake_request)

    RequestUtils().request("get", "https://example.com/", verify=False)

    assert captured["verify"] is False


def test_sync_requests_honor_global_tls_opt_out(monkeypatch):
    """全局配置显式关闭时才允许所有未指定调用继续兼容自签名服务。"""
    captured = {}
    monkeypatch.setattr(settings, "OUTBOUND_TLS_VERIFY", False)

    class Response:
        def close(self):
            return None

    def fake_request(method, url, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr("app.utils.http.requests.request", fake_request)

    RequestUtils().request("get", "https://example.com/")

    assert captured["verify"] is False


def test_async_requests_verify_tls_by_default():
    """异步外部请求默认必须校验 TLS 证书。"""
    assert AsyncRequestUtils()._verify is True  # pylint: disable=protected-access


def test_async_requests_can_explicitly_opt_out_of_tls_verification():
    """异步调用方显式传入 verify=False 时保留自签名内网服务兼容能力。"""
    assert AsyncRequestUtils(verify=False)._verify is False  # pylint: disable=protected-access


def test_async_requests_honor_global_tls_opt_out(monkeypatch):
    """异步请求同样使用全局显式退出配置。"""
    monkeypatch.setattr(settings, "OUTBOUND_TLS_VERIFY", False)

    assert AsyncRequestUtils()._verify is False  # pylint: disable=protected-access
