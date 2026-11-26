"""活动存储能力边界回归测试。"""

from app.api.endpoints.storage import router
from app.chain.storage import StorageChain
from app.modules.filemanager import FileManagerModule
from app.modules.filemanager.storages import StorageBase
from app.schemas.file import FileItem
from app.schemas.types import StorageSchema


def test_active_storage_schema_is_local_and_smb_only() -> None:
    """活动存储实现只保留本地目录和 SMB 网络共享。"""
    assert {item.value for item in StorageSchema} == {"local", "smb"}


def test_filemanager_does_not_support_removed_cloud_or_custom_storage() -> None:
    """云盘与自定义存储类型不得再被误认为可用存储。"""
    module = FileManagerModule()
    module.init_module()

    assert set(module._support_storages) == {"local", "smb"}
    for storage in ("alipan", "u115", "rclone", "alist", "alistgo", "custom", "custom1"):
        assert module.support_transtype(storage) is None


def test_cloud_storage_authentication_interfaces_are_removed() -> None:
    """local/SMB 不需要二维码或 OAuth 登录，死接口不得继续暴露。"""
    route_paths = {route.path for route in router.routes}
    assert "/qrcode/{name}" not in route_paths
    assert "/auth_url/{name}" not in route_paths
    assert "/check/{name}" not in route_paths

    for owner in (StorageChain, FileManagerModule, StorageBase):
        assert not hasattr(owner, "generate_qrcode")
        assert not hasattr(owner, "generate_auth_url")
        assert not hasattr(owner, "check_login")

def test_fileitem_does_not_expose_removed_cloud_drive_fields() -> None:
    """云盘专用文件标识不再属于活动文件对象契约。"""
    assert "pickcode" not in FileItem.model_fields
    assert "drive_id" not in FileItem.model_fields
    assert "url" not in FileItem.model_fields
