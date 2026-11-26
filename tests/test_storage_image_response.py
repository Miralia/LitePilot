"""文件管理图片预览响应边界。"""

from unittest.mock import Mock

from starlette.responses import FileResponse

from app.api.endpoints import storage as storage_endpoint


def test_image_preview_uses_streaming_file_response(tmp_path, monkeypatch):
    """图片预览必须按后缀流式返回正确 MIME，不能整体读入内存并固定为 JPEG。"""
    image_path = tmp_path / "poster.png"
    image_path.write_bytes(b"png-bytes")
    monkeypatch.setattr(
        storage_endpoint.StorageChain,
        "download_file",
        lambda self, fileitem: image_path,
    )

    response = storage_endpoint.image(fileitem=Mock(), _=Mock())

    assert isinstance(response, FileResponse)
    assert response.media_type == "image/png"
