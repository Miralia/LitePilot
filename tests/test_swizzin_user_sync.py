"""swizzin 用户同步边界测试。"""

import pytest

import app.helper.swizzin as swizzin
from app.helper.swizzin import SwizzinUserSync


def test_available_treats_permission_error_as_unavailable(monkeypatch) -> None:
    """非 root 环境无法读取 `/root` 时应退化为非 swizzin 模式。"""
    target = swizzin._SWIZZIN_ROOT / ".master.info"
    path_type = type(swizzin._SWIZZIN_ROOT)
    original_is_file = path_type.is_file

    def raise_for_target(self):
        if self == target:
            raise PermissionError(13, "Permission denied", str(self))
        return original_is_file(self)

    monkeypatch.setattr(path_type, "is_file", raise_for_target)

    assert SwizzinUserSync.available() is False
    assert SwizzinUserSync().list_users() == []
