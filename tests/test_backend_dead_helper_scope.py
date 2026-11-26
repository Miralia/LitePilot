"""后端无消费者 helper 边界测试。"""

from app.helper import builtinconf, directory, mediaserver, module, storage


def test_removed_download_entrypoint_helpers_are_not_retained():
    """订阅和下载入口移除后，不再保留下载保存路径 allowlist helper。"""
    assert not hasattr(directory.DirectoryHelper, "get_download_dir_by_save_path")
    assert not hasattr(directory, "validate_download_save_path")
    for helper_name in (
        "_split_file_uri",
        "_normalize_safe_posix_path",
        "_normalize_safe_windows_path",
        "_normalize_download_path",
        "_download_path_uri",
        "_normalize_download_root",
    ):
        assert not hasattr(directory, helper_name)


def test_removed_plugin_style_module_loaders_are_not_retained():
    """当前模块体系只使用 ModuleHelper.load，不保留插件式动态加载变体。"""
    assert hasattr(module.ModuleHelper, "load")
    assert not hasattr(module.ModuleHelper, "load_with_pre_filter")
    assert not hasattr(module.ModuleHelper, "dynamic_import_all_modules")


def test_closed_storage_and_media_server_helpers_do_not_keep_unused_writers():
    """封闭的 local/SMB 存储与 Emby 边界不保留无消费者的泛化写入和类型判断。"""
    assert not hasattr(storage.StorageHelper, "add_storage")
    assert not hasattr(mediaserver.MediaServerHelper, "is_media_server")
    assert not hasattr(builtinconf, "save_conf")
