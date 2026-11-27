import asyncio
import io
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from PIL import Image

from app.api.endpoints import system as system_endpoint
from app.helper.image import ImageHelper


def _image_bytes(image_format: str, trailing: bytes = b"") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color=(32, 96, 160)).save(buffer, format=image_format)
    return buffer.getvalue() + trailing


@pytest.mark.parametrize(
    ("image_format", "expected_mime"),
    [
        ("PNG", "image/png"),
        ("JPEG", "image/jpeg"),
        ("GIF", "image/gif"),
        ("WEBP", "image/webp"),
        ("PCX", "image/x-pcx"),
        ("PPM", "image/x-portable-anymap"),
    ],
)
def test_get_image_mime_type_uses_pillow_detected_format(
    image_format: str,
    expected_mime: str,
):
    assert ImageHelper.get_image_mime_type(_image_bytes(image_format)) == expected_mime


def test_get_image_mime_type_rejects_non_image_pillow_mime():
    assert ImageHelper.get_image_mime_type(_image_bytes("EPS")) is None


def test_get_image_mime_type_rejects_scriptable_svg_mime():
    with patch.dict(Image.MIME, {"PNG": "image/svg+xml"}):
        assert ImageHelper.get_image_mime_type(_image_bytes("PNG")) is None


def test_fetch_image_with_mime_type_only_reads_cached_format_header():
    content = _image_bytes("PNG")
    image_helper = ImageHelper()

    with patch.object(
        image_helper.file_cache,
        "get",
        return_value=content,
    ), patch.object(
        image_helper,
        "get_image_mime_type",
        return_value="image/png",
    ) as get_mime_type:
        result = image_helper.fetch_image_with_mime_type(
            "https://images.example/wallpaper.png"
        )

    assert result == (content, "image/png")
    get_mime_type.assert_called_once_with(content, verify=False)


def test_fetch_image_with_mime_type_validates_network_content_once():
    content = _image_bytes("PNG")
    image_helper = ImageHelper()
    response = Mock(status_code=200, content=content)
    request = Mock()
    request.get_res.return_value = response

    with patch.object(
        image_helper.file_cache,
        "get",
        return_value=None,
    ), patch.object(
        image_helper.file_cache,
        "set",
    ), patch(
        "app.helper.image.RequestUtils",
        return_value=request,
    ), patch.object(
        image_helper,
        "get_image_mime_type",
        return_value="image/png",
    ) as get_mime_type:
        result = image_helper.fetch_image_with_mime_type(
            "https://images.example/wallpaper.png"
        )

    assert result == (content, "image/png")
    get_mime_type.assert_called_once_with(content)


def test_async_fetch_image_with_mime_type_only_reads_cached_format_header():
    content = _image_bytes("PNG")
    image_helper = ImageHelper()

    with patch.object(
        image_helper.async_file_cache,
        "get",
        new=AsyncMock(return_value=content),
    ), patch.object(
        image_helper,
        "get_image_mime_type",
        return_value="image/png",
    ) as get_mime_type:
        result = asyncio.run(
            image_helper.async_fetch_image_with_mime_type(
                "https://images.example/wallpaper.png"
            )
        )

    assert result == (content, "image/png")
    get_mime_type.assert_called_once_with(content, verify=False)


def test_async_fetch_image_with_mime_type_validates_network_content_once():
    content = _image_bytes("PNG")
    image_helper = ImageHelper()
    response = Mock(status_code=200, content=content)
    request = Mock()
    request.get_res = AsyncMock(return_value=response)

    with patch.object(
        image_helper.async_file_cache,
        "get",
        new=AsyncMock(return_value=None),
    ), patch.object(
        image_helper.async_file_cache,
        "set",
        new=AsyncMock(),
    ), patch(
        "app.helper.image.AsyncRequestUtils",
        return_value=request,
    ), patch.object(
        image_helper,
        "get_image_mime_type",
        return_value="image/png",
    ) as get_mime_type:
        result = asyncio.run(
            image_helper.async_fetch_image_with_mime_type(
                "https://images.example/wallpaper.png"
            )
        )

    assert result == (content, "image/png")
    get_mime_type.assert_called_once_with(content)


def test_async_fetch_image_rejects_redirect_to_disallowed_target():
    content = _image_bytes("PNG")
    image_helper = ImageHelper()
    redirect_response = Mock(
        status_code=302,
        headers={"location": "http://127.0.0.1/internal.png"},
    )
    redirect_response.aclose = AsyncMock()
    final_response = Mock(status_code=200, content=content)
    request = Mock()
    request.get_res = AsyncMock(side_effect=[redirect_response, final_response])
    redirect_validator = AsyncMock(return_value=False)

    with patch.object(
        image_helper.async_file_cache,
        "get",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.helper.image.AsyncRequestUtils",
        return_value=request,
    ):
        result = asyncio.run(
            image_helper.async_fetch_image_with_mime_type(
                "https://images.example/wallpaper.png",
                redirect_validator=redirect_validator,
            )
        )

    assert result is None
    redirect_validator.assert_awaited_once_with("http://127.0.0.1/internal.png")
    assert request.get_res.await_count == 1


def test_async_fetch_image_follows_validated_relative_redirect():
    content = _image_bytes("PNG")
    image_helper = ImageHelper()
    redirect_response = Mock(
        status_code=302,
        headers={"location": "/media/wallpaper-final.png"},
    )
    redirect_response.aclose = AsyncMock()
    final_response = Mock(status_code=200, content=content)
    request = Mock()
    request.get_res = AsyncMock(side_effect=[redirect_response, final_response])
    redirect_validator = AsyncMock(return_value=True)

    with patch.object(
        image_helper.async_file_cache,
        "get",
        new=AsyncMock(return_value=None),
    ), patch.object(
        image_helper.async_file_cache,
        "set",
        new=AsyncMock(),
    ), patch(
        "app.helper.image.AsyncRequestUtils",
        return_value=request,
    ):
        result = asyncio.run(
            image_helper.async_fetch_image_with_mime_type(
                "https://images.example/wallpaper.png",
                redirect_validator=redirect_validator,
            )
        )

    assert result == (content, "image/png")
    redirect_validator.assert_awaited_once_with(
        "https://images.example/media/wallpaper-final.png"
    )
    assert request.get_res.await_count == 2


def test_fetch_image_does_not_trust_active_url_suffix():
    content = _image_bytes("PNG", b"<script>window.xss = true</script>")
    image_helper = Mock()
    image_helper.async_fetch_image_with_mime_type = AsyncMock(
        return_value=(content, "image/png")
    )

    with patch.object(
        system_endpoint.SecurityUtils,
        "is_safe_image_url_async",
        new=AsyncMock(return_value=True),
    ), patch.object(system_endpoint, "ImageHelper", return_value=image_helper):
        response = asyncio.run(
            system_endpoint.fetch_image(
                url="https://images.example/wallpaper.html",
                allowed_domains={"images.example"},
            )
        )

    assert response is not None
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.body == content


def test_fetch_image_rejects_unverified_content():
    image_helper = Mock()
    image_helper.async_fetch_image_with_mime_type = AsyncMock(return_value=None)

    with patch.object(
        system_endpoint.SecurityUtils,
        "is_safe_image_url_async",
        new=AsyncMock(return_value=True),
    ), patch.object(system_endpoint, "ImageHelper", return_value=image_helper):
        response = asyncio.run(
            system_endpoint.fetch_image(
                url="https://images.example/wallpaper.png",
                allowed_domains={"images.example"},
            )
        )

    assert response is None


def test_fetch_image_wires_redirect_validator_with_proxy_security_rules():
    content = _image_bytes("PNG")
    image_helper = Mock()
    image_helper.async_fetch_image_with_mime_type = AsyncMock(
        return_value=(content, "image/png")
    )
    safety_check = AsyncMock(return_value=True)

    with patch.object(
        system_endpoint.SecurityUtils,
        "is_safe_image_url_async",
        new=safety_check,
    ), patch.object(system_endpoint, "ImageHelper", return_value=image_helper):
        response = asyncio.run(
            system_endpoint.fetch_image(
                url="https://images.example/wallpaper.png",
                allowed_domains={"images.example"},
            )
        )

        assert response is not None
        call_kwargs = image_helper.async_fetch_image_with_mime_type.await_args.kwargs
        redirect_validator = call_kwargs.get("redirect_validator")
        assert callable(redirect_validator)

        safety_check.reset_mock()
        assert asyncio.run(redirect_validator("https://images.example/final.png")) is True
        safety_check.assert_awaited_once_with(
            "https://images.example/final.png",
            {"images.example"},
            allowed_private_ranges=system_endpoint.settings.IMAGE_PROXY_ALLOWED_PRIVATE_RANGES,
        )


def test_fetch_image_adds_nosniff_to_not_modified_response():
    content = _image_bytes("JPEG")
    image_helper = Mock()
    image_helper.async_fetch_image_with_mime_type = AsyncMock(
        return_value=(content, "image/jpeg")
    )
    etag = system_endpoint.HashUtils.md5(content)

    with patch.object(
        system_endpoint.SecurityUtils,
        "is_safe_image_url_async",
        new=AsyncMock(return_value=True),
    ), patch.object(system_endpoint, "ImageHelper", return_value=image_helper):
        response = asyncio.run(
            system_endpoint.fetch_image(
                url="https://images.example/wallpaper.jpg",
                if_none_match=etag,
                allowed_domains={"images.example"},
            )
        )

    assert response is not None
    assert response.status_code == 304
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_proxy_img_returns_not_found_when_fetch_fails():
    """图片代理失败不得返回 200 null，避免浏览器或 Service Worker 缓存伪成功响应。"""
    with patch.object(system_endpoint, "fetch_image", new=AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                system_endpoint.proxy_img(
                    imgurl="https://images.example/missing.jpg",
                    proxy=False,
                    cache=False,
                    if_none_match=None,
                    _=Mock(),
                )
            )

    assert exc_info.value.status_code == 404


def test_cache_img_returns_not_found_when_fetch_fails():
    """图片缓存接口同样必须以 404 表达失败，而不是返回空成功。"""
    with patch.object(system_endpoint, "fetch_image", new=AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                system_endpoint.cache_img(
                    url="https://images.example/missing.jpg",
                    if_none_match=None,
                    _=Mock(),
                )
            )

    assert exc_info.value.status_code == 404
