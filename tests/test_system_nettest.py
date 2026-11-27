import asyncio
import ipaddress
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, Mock, patch

import pytest

from app.api.endpoints import system as system_endpoint


def test_fetch_image_allows_signed_private_url():
    """
    服务端签名过的私网图片 URL 可以继续代理，保证前端封面显示。
    """
    image_url = "http://192.168.1.50:8096/System/Info/Public"
    signed_url = system_endpoint.SecurityUtils.sign_url(image_url)
    image_helper = Mock()
    image_helper.async_fetch_image_with_mime_type = AsyncMock(
        return_value=(b"image-bytes", "image/jpeg")
    )

    with patch.object(system_endpoint, "ImageHelper", return_value=image_helper), patch.object(
        system_endpoint.HashUtils, "md5", return_value="etag", create=True
    ), patch.object(
        system_endpoint.RequestUtils, "generate_cache_headers", return_value={}, create=True
    ):
        resp = asyncio.run(
            system_endpoint.fetch_image(
                url=signed_url,
                allowed_domains=set(),
            )
        )

    assert resp.status_code == 200
    image_helper.async_fetch_image_with_mime_type.assert_awaited_once_with(
        url=image_url,
        proxy=None,
        use_cache=False,
        redirect_validator=ANY,
    )


def test_fetch_image_blocks_private_allowed_url_before_request():
    """
    图片代理即使拿到内网 allowlist 项，也必须在发起请求前拦截。
    """
    class FailIfCalled:
        def __init__(self, *args, **kwargs):
            raise AssertionError("fetch_image should block private URLs before fetching")

    with patch.object(system_endpoint, "ImageHelper", FailIfCalled):
        resp = asyncio.run(
            system_endpoint.fetch_image(
                url="http://127.0.0.1:8096/secret.png",
                allowed_domains={"http://127.0.0.1:8096"},
            )
        )

    assert resp is None


def test_fetch_image_allows_configured_private_range_after_domain_match():
    """
    图片代理在域名白名单命中后，可按配置放行指定非公网解析网段。
    """
    image_helper = Mock()
    image_helper.async_fetch_image_with_mime_type = AsyncMock(
        return_value=(b"image-bytes", "image/jpeg")
    )

    with patch.object(system_endpoint, "ImageHelper", return_value=image_helper), patch.object(
        system_endpoint.HashUtils, "md5", return_value="etag", create=True
    ), patch.object(
        system_endpoint.RequestUtils, "generate_cache_headers", return_value={}, create=True
    ), patch.object(
        # is_safe_image_url_async 经 evaluate_url_safety_async 走异步解析
        # _hostname_addresses_async（loop.getaddrinfo）；必须 mock 异步版本，
        # 否则真实 DNS 逃逸到 img1.doubanio.com，且私网放行分支根本不会被执行到。
        system_endpoint.SecurityUtils,
        "_hostname_addresses_async",
        new=AsyncMock(return_value=[ipaddress.ip_address("198.18.16.96")]),
    ), patch.object(
        system_endpoint.settings,
        "IMAGE_PROXY_ALLOWED_PRIVATE_RANGES",
        ["198.18.0.0/15"],
    ), patch(
        "app.utils.security.logger.debug",
    ):
        resp = asyncio.run(
            system_endpoint.fetch_image(
                url="https://img1.doubanio.com/poster.webp",
                allowed_domains={"doubanio.com"},
            )
        )

    assert resp.status_code == 200
    image_helper.async_fetch_image_with_mime_type.assert_awaited_once_with(
        url="https://img1.doubanio.com/poster.webp",
        proxy=None,
        use_cache=False,
        redirect_validator=ANY,
    )


def test_fetch_image_blocks_tampered_signed_private_url():
    """
    私网签名绑定完整 URL，改动路径后不能继续代理。
    """
    signed_url = system_endpoint.SecurityUtils.sign_url(
        "http://192.168.1.50:8096/Items/abc/Images/Primary"
    ).replace("/Items/abc/Images/Primary", "/System/Info/Public")

    class FailIfCalled:
        def __init__(self, *args, **kwargs):
            raise AssertionError("fetch_image should block tampered signed URLs")

    with patch.object(system_endpoint, "ImageHelper", FailIfCalled):
        resp = asyncio.run(
            system_endpoint.fetch_image(
                url=signed_url,
                allowed_domains=set(),
            )
        )

    assert resp is None


def test_nettest_targets_are_served_by_backend():
    resp = asyncio.run(system_endpoint.nettest_targets(_="token"))

    assert resp.success
    assert any(item["id"] == "pip_proxy" for item in resp.data)
    assert any(item["id"] == "github_proxy_web" for item in resp.data)


def test_nettest_blocks_unknown_target():
    class FailIfCalled:
        def __init__(self, *args, **kwargs):
            raise AssertionError("nettest should reject unknown targets before any outbound request")

    with patch.object(system_endpoint, "AsyncRequestUtils", FailIfCalled):
        resp = asyncio.run(
            system_endpoint.nettest(
                target_id="unknown-target",
                _="token",
            )
        )

    assert not resp.success
    assert "不存在" in resp.message


def test_nettest_blocks_unapproved_redirect():
    captured = {"calls": 0}

    class FakeResponse:
        def __init__(self, status_code, headers=None, text=""):
            self.status_code = status_code
            self.headers = headers or {}
            self.text = text

        async def aclose(self):
            return None

    class FakeAsyncRequestUtils:
        def __init__(self, **kwargs):
            captured["init_kwargs"] = kwargs

        async def get_res(self, url, allow_redirects=True):
            captured["calls"] += 1
            return FakeResponse(
                302,
                headers={"location": "https://169.254.169.254/latest/meta-data/"},
            )

    with patch.object(system_endpoint, "AsyncRequestUtils", FakeAsyncRequestUtils), patch.object(
        system_endpoint.settings,
        "GITHUB_PROXY",
        "https://ghproxy.example/",
    ):
        resp = asyncio.run(
            system_endpoint.nettest(
                target_id="github_proxy_web",
                _="token",
            )
        )

    assert not resp.success
    assert "跳转" in resp.message
    assert captured["calls"] == 1


def test_nettest_redirect_warning_redacts_sensitive_url_params():
    warnings = []
    secret = "tmdb-test-secret-0123456789abcdef"

    class FakeResponse:
        status_code = 302
        headers = {"location": "https://169.254.169.254/latest/meta-data/"}
        text = ""

        async def aclose(self):
            return None

    class FakeAsyncRequestUtils:
        def __init__(self, **kwargs):
            pass

        async def get_res(self, url, allow_redirects=True):
            return FakeResponse()

    with patch.object(
        system_endpoint,
        "AsyncRequestUtils",
        FakeAsyncRequestUtils,
    ), patch.object(
        system_endpoint.settings,
        "TMDB_API_KEY",
        secret,
    ), patch.object(
        system_endpoint.logger,
        "warning",
        side_effect=warnings.append,
    ):
        resp = asyncio.run(
            system_endpoint.nettest(
                target_id="tmdb_api",
                _="token",
            )
        )

    assert not resp.success
    assert warnings
    assert all(secret not in warning for warning in warnings)
    assert any("api_key=<redacted>" in warning for warning in warnings)


@pytest.mark.parametrize(
    "target_id,redirect_url",
    [
        ("telegram_api", "https://core.telegram.org/bots"),
        ("github_codeload", "https://github.com/"),
    ],
)
def test_nettest_allows_known_external_redirects(target_id, redirect_url):
    call_urls = []

    class FakeResponse:
        def __init__(self, status_code, headers=None, text=""):
            self.status_code = status_code
            self.headers = headers or {}
            self.text = text

        async def aclose(self):
            return None

    class FakeAsyncRequestUtils:
        def __init__(self, **kwargs):
            pass

        async def get_res(self, url, allow_redirects=True):
            call_urls.append(url)
            if len(call_urls) == 1:
                return FakeResponse(302, headers={"location": redirect_url})
            return FakeResponse(200, text="ok")

    with patch.object(
        system_endpoint,
        "AsyncRequestUtils",
        FakeAsyncRequestUtils,
    ):
        resp = asyncio.run(
            system_endpoint.nettest(
                target_id=target_id,
                _="token",
            )
        )

    assert resp.success
    assert len(call_urls) == 2


def test_nettest_uses_safe_http_options_and_server_side_content_check():
    captured = {}

    class FakeAsyncRequestUtils:
        def __init__(self, **kwargs):
            captured["init_kwargs"] = kwargs

        async def get_res(self, url, allow_redirects=True):
            captured["url"] = url
            captured["allow_redirects"] = allow_redirects
            return SimpleNamespace(status_code=200, text="LitePilot README")

    with patch.object(system_endpoint, "AsyncRequestUtils", FakeAsyncRequestUtils), patch.object(
        system_endpoint.settings,
        "GITHUB_PROXY",
        "https://ghproxy.example/",
    ):
        resp = asyncio.run(
            system_endpoint.nettest(
                target_id="github_proxy_web",
                include="tag_name",
                _="token",
            )
        )

    assert resp.success
    expected_url = "https://ghproxy.example/https://github.com/Miralia/LitePilot/blob/main/README.md"
    assert captured["url"] == expected_url
    assert not captured["allow_redirects"]
    assert captured["init_kwargs"]["verify"]
    assert not captured["init_kwargs"]["follow_redirects"]


def test_nettest_fails_when_expected_content_is_missing():
    class FakeAsyncRequestUtils:
        def __init__(self, **kwargs):
            pass

        async def get_res(self, url, allow_redirects=True):
            return SimpleNamespace(status_code=200, text="proxy landing page")

    with patch.object(system_endpoint, "AsyncRequestUtils", FakeAsyncRequestUtils), patch.object(
        system_endpoint.settings,
        "PIP_PROXY",
        "https://pypi.tuna.tsinghua.edu.cn/simple/",
    ):
        resp = asyncio.run(
            system_endpoint.nettest(
                target_id="pip_proxy",
                _="token",
            )
        )

    assert not resp.success
    assert "PIP加速代理" in resp.message
