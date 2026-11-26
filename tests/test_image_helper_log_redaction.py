from app.helper.image import ImageHelper


def test_fetch_image_warning_redacts_sensitive_query_params(monkeypatch):
    """图片下载失败 warning 不得泄露 Emby 或其它签名图片 URL 中的凭据。"""
    helper = object.__new__(ImageHelper)
    image_url = "https://emby.local/Items/1/Images/Primary?tag=abc&api_key=image-secret"

    class FakeResponse:
        status_code = 500
        content = b""

    class FakeRequestUtils:
        def __init__(self, **_kwargs):
            pass

        def get_res(self, **_kwargs):
            return FakeResponse()

    warnings = []
    monkeypatch.setattr("app.helper.image.RequestUtils", FakeRequestUtils)
    monkeypatch.setattr("app.helper.image.logger.warning", lambda message: warnings.append(message))

    assert helper.fetch_image_with_mime_type(image_url, use_cache=False) is None
    assert warnings
    joined = "\n".join(warnings)
    assert "image-secret" not in joined
    assert "api_key=<redacted>" in joined
