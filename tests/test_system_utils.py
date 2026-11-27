import errno
import itertools
import os
import struct
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from app.core.config import ConfigModel
from app.utils.system import SystemUtils


def test_execute_with_subprocess_keeps_stdout_when_command_fails():
    """命令失败时如果原因只写入 stdout，也需要回传给调用方用于错误提示。"""
    error = subprocess.CalledProcessError(
        returncode=1,
        cmd=["pip", "check"],
        output="demo requires pkg>=2, but you have pkg 1\n",
        stderr="",
    )

    with patch("app.utils.system.subprocess.run", side_effect=error):
        success, message = SystemUtils.execute_with_subprocess(["pip", "check"])

    assert not success
    assert "返回码：1" in message
    assert "标准输出：demo requires pkg>=2, but you have pkg 1" in message


def test_execute_with_subprocess_reports_empty_failure_output():
    """命令失败且没有任何输出时，给出明确占位信息，避免错误原因看起来被截断。"""
    error = subprocess.CalledProcessError(
        returncode=2,
        cmd=["pip", "check"],
        output="",
        stderr="",
    )

    with patch("app.utils.system.subprocess.run", side_effect=error):
        success, message = SystemUtils.execute_with_subprocess(["pip", "check"])

    assert not success
    assert "返回码：2" in message
    assert "无标准输出或错误输出" in message


def test_execute_with_subprocess_passes_env_to_subprocess():
    with patch("app.utils.system.subprocess.run") as run_mock:
        run_mock.return_value.stdout = "ok"
        run_mock.return_value.stderr = ""

        success, message = SystemUtils.execute_with_subprocess(
            ["pip", "check"],
            env={"PIP_CACHE_DIR": "/config/.cache/pip"},
        )

    assert success
    assert message == "ok"
    assert run_mock.call_args.kwargs["env"]["PIP_CACHE_DIR"] == "/config/.cache/pip"


def test_execute_with_subprocess_uses_safe_command_in_failure_message():
    error = subprocess.CalledProcessError(
        returncode=1,
        cmd=["pip", "install", "-i", "https://user:pass@mirror.example/simple"],
        output="",
        stderr="failed",
    )

    command = ["pip", "install", "-i", "https://user:pass@mirror.example/simple"]
    with patch("app.utils.system.subprocess.run", side_effect=error) as run_mock:
        success, message = SystemUtils.execute_with_subprocess(
            command,
            safe_command=["pip", "install", "-i", "https://mirror.example/simple"],
        )

    assert not success
    assert "https://mirror.example/simple" in message
    assert "user:pass" not in message
    assert run_mock.call_args.args[0] == command


def test_execute_with_subprocess_redacts_userinfo_from_stdout_and_stderr():
    error = subprocess.CalledProcessError(
        returncode=1,
        cmd=["pip", "install"],
        output="Looking in indexes: https://user:pass@mirror.example/simple",
        stderr="Proxy failed: http://proxy_user:proxy_pass@proxy.example:7890",
    )

    with patch("app.utils.system.subprocess.run", side_effect=error):
        success, message = SystemUtils.execute_with_subprocess(["pip", "install"])

    assert not success
    assert "https://mirror.example/simple" in message
    assert "http://proxy.example:7890" in message
    assert "user:pass" not in message
    assert "proxy_user:proxy_pass" not in message


def test_execute_with_subprocess_redacts_userinfo_from_non_http_scheme():
    error = subprocess.CalledProcessError(
        returncode=1,
        cmd=["pip", "install"],
        output="Proxy failed: socks5://proxy_user:proxy_pass@proxy.example:7890",
        stderr="Resolved direct URL: git+https://git_user:git_pass@example.com/org/repo.git",
    )

    with patch("app.utils.system.subprocess.run", side_effect=error):
        success, message = SystemUtils.execute_with_subprocess(["pip", "install"])

    assert not success
    assert "socks5://proxy.example:7890" in message
    assert "git+https://example.com/org/repo.git" in message
    assert "proxy_user:proxy_pass" not in message
    assert "git_user:git_pass" not in message


def test_execute_with_subprocess_redacts_success_output_userinfo():
    with patch("app.utils.system.subprocess.run") as run_mock:
        run_mock.return_value.stdout = "Using https://user:pass@mirror.example/simple\n"
        run_mock.return_value.stderr = "Proxy socks5://proxy_user:proxy_pass@proxy.example:7890\n"

        success, message = SystemUtils.execute_with_subprocess(["pip", "install"])

    assert success
    assert "https://mirror.example/simple" in message
    assert "socks5://proxy.example:7890" in message
    assert "user:pass" not in message
    assert "proxy_user:proxy_pass" not in message


def test_execute_with_subprocess_redacts_unknown_error_userinfo_and_invalid_port():
    with patch(
        "app.utils.system.subprocess.run",
        side_effect=RuntimeError("bad url https://user:pass@example.com:notaport/simple"),
    ):
        success, message = SystemUtils.execute_with_subprocess(["pip", "install"])

    assert not success
    assert "https://example.com:notaport/simple" in message
    assert "user:pass" not in message


def test_redact_url_userinfo_tolerates_malformed_ipv6_url():
    """脱敏 malformed URL 时不能二次抛出解析异常，也不能保留 userinfo。"""
    redacted = SystemUtils.redact_url_userinfo(
        "Proxy failed: http://user:proxy-secret@[::1, retrying"
    )

    assert "proxy-secret" not in redacted
    assert "user@" not in redacted
    assert "retrying" in redacted


def _fake_stat_with_devs(dev_by_path):
    """构造按路径返回指定 st_dev 的 os.stat 桩，未登记路径仍走真实 stat。"""
    real_stat = os.stat

    def _fake_stat(path, *args, **kwargs):
        key = str(path)
        if key not in dev_by_path:
            return real_stat(path, *args, **kwargs)
        result = MagicMock()
        result.st_dev = dev_by_path[key]
        return result
    return _fake_stat


def _fill_fs_info(fsid, num_devices=1, truncate=False):
    """构造填充 BTRFS_IOC_FS_INFO 缓冲区的 ioctl 桩。"""
    def _ioctl(fd, request, buffer, mutate_flag):
        assert fd == 42
        assert request == 0x8400941F
        assert mutate_flag is True
        if truncate:
            del buffer[64:]
            return 0
        struct.pack_into("=Q", buffer, 8, num_devices)
        buffer[16:32] = fsid
        return 0
    return _ioctl


@pytest.fixture
def linux_platform(monkeypatch):
    """将当前用例的平台标识切换为 Linux amd64。"""
    monkeypatch.setattr("app.utils.system.sys.platform", "linux")
    monkeypatch.setattr(SystemUtils, "is_x86_64", lambda: True)
    monkeypatch.setattr(SystemUtils, "is_aarch64", lambda: False)


@pytest.mark.parametrize("num_devices", [1, 2])
def test_get_btrfs_fsid_reads_kernel_result_and_closes_fd(num_devices, linux_platform):
    fsid = bytes.fromhex("88e3aff5fa2946d591a55977be984655")
    with patch("app.utils.system.os.open", return_value=42), \
            patch("app.utils.system.fcntl.ioctl", side_effect=_fill_fs_info(fsid, num_devices)), \
            patch("app.utils.system.os.close") as close_mock:
        result = SystemUtils._get_btrfs_fsid(Path("/data"))

    assert result == fsid
    close_mock.assert_called_once_with(42)


@pytest.mark.parametrize("error_number", [errno.ENOTTY, errno.EACCES, errno.EPERM, errno.EINVAL])
def test_get_btrfs_fsid_falls_back_on_expected_ioctl_errors(error_number, linux_platform):
    with patch("app.utils.system.os.open", return_value=42), \
            patch("app.utils.system.fcntl.ioctl", side_effect=OSError(error_number, os.strerror(error_number))), \
            patch("app.utils.system.os.close") as close_mock:
        result = SystemUtils._get_btrfs_fsid(Path("/data"))

    assert result is None
    close_mock.assert_called_once_with(42)


def test_get_btrfs_fsid_falls_back_when_directory_cannot_be_opened(linux_platform):
    with patch("app.utils.system.os.open", side_effect=OSError(errno.EACCES, "denied")), \
            patch("app.utils.system.os.close") as close_mock:
        result = SystemUtils._get_btrfs_fsid(Path("/data"))

    assert result is None
    close_mock.assert_not_called()


@pytest.mark.parametrize(
    ("fsid", "num_devices", "truncate"),
    [
        (bytes(16), 1, False),
        (b"valid-fsid-value", 0, False),
        (b"valid-fsid-value", 1, True),
    ],
)
def test_get_btrfs_fsid_rejects_invalid_kernel_results(fsid, num_devices, truncate, linux_platform):
    with patch("app.utils.system.os.open", return_value=42), \
            patch("app.utils.system.fcntl.ioctl", side_effect=_fill_fs_info(fsid, num_devices, truncate)), \
            patch("app.utils.system.os.close") as close_mock:
        result = SystemUtils._get_btrfs_fsid(Path("/data"))

    assert result is None
    close_mock.assert_called_once_with(42)


def test_get_btrfs_fsid_is_disabled_outside_linux():
    with patch("app.utils.system.sys.platform", "darwin"), \
            patch("app.utils.system.os.open") as open_mock:
        result = SystemUtils._get_btrfs_fsid(Path("/data"))

    assert result is None
    open_mock.assert_not_called()


def test_get_btrfs_fsid_is_disabled_on_unsupported_linux_architecture():
    with patch("app.utils.system.sys.platform", "linux"), \
            patch.object(SystemUtils, "is_x86_64", return_value=False), \
            patch.object(SystemUtils, "is_aarch64", return_value=False), \
            patch("app.utils.system.os.open") as open_mock:
        result = SystemUtils._get_btrfs_fsid(Path("/data"))

    assert result is None
    open_mock.assert_not_called()


def test_btrfs_fsid_dedup_setting_is_opt_in():
    assert ConfigModel().BTRFS_FSID_DEDUP is False
    assert ConfigModel(BTRFS_FSID_DEDUP="true").BTRFS_FSID_DEDUP is True


def test_space_usage_default_path_does_not_read_fsid():
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        paths = [Path(tmp1), Path(tmp2)]
        dev_by_path = {str(paths[0]): 38, str(paths[1]): 32}
        with patch("app.utils.system.os.stat", side_effect=_fake_stat_with_devs(dev_by_path)), \
                patch.object(SystemUtils, "_get_btrfs_fsid") as fsid_mock, \
                patch.object(SystemUtils, "total_space", return_value=2.0), \
                patch.object(SystemUtils, "free_space", return_value=1.0):
            total, free = SystemUtils.space_usage(paths)

    assert total == 4.0
    assert free == 2.0
    fsid_mock.assert_not_called()


@pytest.mark.parametrize("system_platform", ["darwin", "win32"])
def test_space_usage_opt_in_does_not_read_fsid_outside_linux(system_platform):
    path = MagicMock()
    path.exists.return_value = True
    path.drive = "D:"
    with patch("app.utils.system.sys.platform", system_platform), \
            patch.object(SystemUtils, "is_x86_64") as x86_mock, \
            patch.object(SystemUtils, "is_aarch64") as arm_mock, \
            patch.object(SystemUtils, "_get_btrfs_fsid") as fsid_mock, \
            patch.object(SystemUtils, "total_space", return_value=2.0), \
            patch.object(SystemUtils, "free_space", return_value=1.0), \
            patch("app.utils.system.os.stat", side_effect=_fake_stat_with_devs({str(path): 38})):
        total, free = SystemUtils.space_usage([path], btrfs_fsid_dedup=True)

    assert total == 2.0
    assert free == 1.0
    x86_mock.assert_not_called()
    arm_mock.assert_not_called()
    fsid_mock.assert_not_called()


def test_space_usage_opt_in_uses_original_behavior_on_unsupported_linux_architecture():
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        paths = [Path(tmp1), Path(tmp2)]
        dev_by_path = {str(path): 38 for path in paths}
        with patch("app.utils.system.sys.platform", "linux"), \
                patch.object(SystemUtils, "is_x86_64", return_value=False), \
                patch.object(SystemUtils, "is_aarch64", return_value=False), \
                patch("app.utils.system.os.stat", side_effect=_fake_stat_with_devs(dev_by_path)), \
                patch.object(SystemUtils, "_get_btrfs_fsid") as fsid_mock, \
                patch.object(SystemUtils, "total_space", return_value=2.0), \
                patch.object(SystemUtils, "free_space", return_value=1.0):
            total, free = SystemUtils.space_usage(paths, btrfs_fsid_dedup=True)

    assert total == 2.0
    assert free == 1.0
    fsid_mock.assert_not_called()


@pytest.mark.parametrize(("is_x86_64", "is_aarch64"), [(True, False), (False, True)])
def test_space_usage_merges_btrfs_subvolumes_with_same_fsid(is_x86_64, is_aarch64, monkeypatch):
    monkeypatch.setattr("app.utils.system.sys.platform", "linux")
    monkeypatch.setattr(SystemUtils, "is_x86_64", lambda: is_x86_64)
    monkeypatch.setattr(SystemUtils, "is_aarch64", lambda: is_aarch64)
    fsid = bytes.fromhex("88e3aff5fa2946d591a55977be984655")
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        paths = [Path(tmp1), Path(tmp2)]
        dev_by_path = {str(paths[0]): 38, str(paths[1]): 32}
        with patch("app.utils.system.os.stat", side_effect=_fake_stat_with_devs(dev_by_path)), \
                patch.object(SystemUtils, "_get_btrfs_fsid", side_effect=[fsid, fsid]), \
                patch.object(SystemUtils, "total_space", return_value=3.49 * 1024 ** 4), \
                patch.object(SystemUtils, "free_space", return_value=1.94 * 1024 ** 4):
            total, free = SystemUtils.space_usage(paths, btrfs_fsid_dedup=True)

    assert total == 3.49 * 1024 ** 4
    assert free == 1.94 * 1024 ** 4


def test_space_usage_counts_different_btrfs_fsids_separately(linux_platform):
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        paths = [Path(tmp1), Path(tmp2)]
        dev_by_path = {str(paths[0]): 38, str(paths[1]): 32}
        with patch("app.utils.system.os.stat", side_effect=_fake_stat_with_devs(dev_by_path)), \
                patch.object(SystemUtils, "_get_btrfs_fsid", side_effect=[b"a" * 16, b"b" * 16]), \
                patch.object(SystemUtils, "total_space", return_value=2.0), \
                patch.object(SystemUtils, "free_space", return_value=1.0):
            total, free = SystemUtils.space_usage(paths, btrfs_fsid_dedup=True)

    assert total == 4.0
    assert free == 2.0


def test_space_usage_falls_back_to_st_dev_when_fsid_is_unavailable(linux_platform):
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        paths = [Path(tmp1), Path(tmp2)]
        dev_by_path = {str(paths[0]): 60, str(paths[1]): 60}
        with patch("app.utils.system.os.stat", side_effect=_fake_stat_with_devs(dev_by_path)), \
                patch.object(SystemUtils, "_get_btrfs_fsid", return_value=None), \
                patch.object(SystemUtils, "total_space", return_value=2.0), \
                patch.object(SystemUtils, "free_space", return_value=1.0):
            total, free = SystemUtils.space_usage(paths, btrfs_fsid_dedup=True)

    assert total == 2.0
    assert free == 1.0


@pytest.mark.parametrize("fsids", [(b"a" * 16, None), (None, b"a" * 16)])
def test_space_usage_keeps_st_dev_dedup_when_fsid_availability_differs(fsids, linux_platform):
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        paths = [Path(tmp1), Path(tmp2)]
        dev_by_path = {str(path): 38 for path in paths}
        with patch("app.utils.system.os.stat", side_effect=_fake_stat_with_devs(dev_by_path)), \
                patch.object(SystemUtils, "_get_btrfs_fsid", side_effect=fsids), \
                patch.object(SystemUtils, "total_space", return_value=2.0), \
                patch.object(SystemUtils, "free_space", return_value=1.0):
            total, free = SystemUtils.space_usage(paths, btrfs_fsid_dedup=True)

    assert total == 2.0
    assert free == 1.0


def test_space_usage_keeps_st_dev_dedup_when_fsid_is_consistent(linux_platform):
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        paths = [Path(tmp1), Path(tmp2)]
        dev_by_path = {str(path): 38 for path in paths}
        with patch("app.utils.system.os.stat", side_effect=_fake_stat_with_devs(dev_by_path)), \
                patch.object(SystemUtils, "_get_btrfs_fsid", side_effect=[b"a" * 16, b"a" * 16]), \
                patch.object(SystemUtils, "total_space", return_value=2.0), \
                patch.object(SystemUtils, "free_space", return_value=1.0):
            total, free = SystemUtils.space_usage(paths, btrfs_fsid_dedup=True)

    assert total == 2.0
    assert free == 1.0


def test_space_usage_does_not_merge_different_st_devs_when_one_fsid_is_unavailable(linux_platform):
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        paths = [Path(tmp1), Path(tmp2)]
        dev_by_path = {str(paths[0]): 38, str(paths[1]): 32}
        with patch("app.utils.system.os.stat", side_effect=_fake_stat_with_devs(dev_by_path)), \
                patch.object(SystemUtils, "_get_btrfs_fsid", side_effect=[b"a" * 16, None]), \
                patch.object(SystemUtils, "total_space", return_value=2.0), \
                patch.object(SystemUtils, "free_space", return_value=1.0):
            total, free = SystemUtils.space_usage(paths, btrfs_fsid_dedup=True)

    assert total == 4.0
    assert free == 2.0


def test_space_usage_counts_a_repeated_path_once():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)
        with patch.object(SystemUtils, "_get_btrfs_fsid", return_value=None), \
                patch.object(SystemUtils, "total_space", return_value=2.0), \
                patch.object(SystemUtils, "free_space", return_value=1.0):
            total, free = SystemUtils.space_usage([path, path])

    assert total == 2.0
    assert free == 1.0


def test_space_usage_merges_consistent_fsid_observed_within_same_st_dev(linux_platform):
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2, \
            tempfile.TemporaryDirectory() as tmp3:
        paths = [Path(tmp1), Path(tmp2), Path(tmp3)]
        dev_by_path = {str(paths[0]): 38, str(paths[1]): 38, str(paths[2]): 32}
        with patch("app.utils.system.os.stat", side_effect=_fake_stat_with_devs(dev_by_path)), \
                patch.object(SystemUtils, "_get_btrfs_fsid", side_effect=[None, b"a" * 16, b"a" * 16]), \
                patch.object(SystemUtils, "total_space", return_value=2.0), \
                patch.object(SystemUtils, "free_space", return_value=1.0):
            total, free = SystemUtils.space_usage(paths, btrfs_fsid_dedup=True)

    assert total == 2.0
    assert free == 1.0


def test_space_usage_transitive_merge_is_independent_of_path_order(linux_platform):
    fsid = b"a" * 16
    records = [("first", 38, None), ("bridge", 38, fsid), ("other", 32, fsid)]

    for permutation in itertools.permutations(records):
        paths = [MagicMock(name=name) for name, _, _ in permutation]
        for path in paths:
            path.exists.return_value = True
        dev_by_path = {str(path): record[1] for path, record in zip(paths, permutation)}
        fsid_by_path = {str(path): record[2] for path, record in zip(paths, permutation)}
        with patch("app.utils.system.os.stat", side_effect=_fake_stat_with_devs(dev_by_path)), \
                patch.object(SystemUtils, "_get_btrfs_fsid", side_effect=lambda path: fsid_by_path[str(path)]), \
                patch.object(SystemUtils, "total_space", return_value=2.0), \
                patch.object(SystemUtils, "free_space", return_value=1.0):
            total, free = SystemUtils.space_usage(paths, btrfs_fsid_dedup=True)

        assert total == 2.0
        assert free == 1.0


def test_space_usage_conflicting_fsids_do_not_bridge_independent_groups(linux_platform):
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2, \
            tempfile.TemporaryDirectory() as tmp3, tempfile.TemporaryDirectory() as tmp4:
        paths = [Path(tmp1), Path(tmp2), Path(tmp3), Path(tmp4)]
        dev_by_path = {
            str(paths[0]): 38,
            str(paths[1]): 38,
            str(paths[2]): 32,
            str(paths[3]): 101,
        }
        with patch("app.utils.system.os.stat", side_effect=_fake_stat_with_devs(dev_by_path)), \
                patch.object(SystemUtils, "_get_btrfs_fsid",
                             side_effect=[b"a" * 16, b"b" * 16, b"a" * 16, b"b" * 16]), \
                patch.object(SystemUtils, "total_space", return_value=2.0), \
                patch.object(SystemUtils, "free_space", return_value=1.0):
            total, free = SystemUtils.space_usage(paths, btrfs_fsid_dedup=True)

    assert total == 6.0
    assert free == 3.0


def test_space_usage_uses_earliest_path_for_each_final_group(linux_platform):
    fsid = b"a" * 16
    paths = [MagicMock(name=name) for name in ("first", "same-dev", "same-fsid", "independent")]
    for path in paths:
        path.exists.return_value = True
    dev_by_path = {str(paths[0]): 38, str(paths[1]): 38, str(paths[2]): 32, str(paths[3]): 101}
    fsid_by_path = {str(paths[0]): None, str(paths[1]): fsid, str(paths[2]): fsid, str(paths[3]): None}

    with patch("app.utils.system.os.stat", side_effect=_fake_stat_with_devs(dev_by_path)), \
            patch.object(SystemUtils, "_get_btrfs_fsid", side_effect=lambda path: fsid_by_path[str(path)]), \
            patch.object(SystemUtils, "total_space", side_effect=[2.0, 3.0]) as total_mock, \
            patch.object(SystemUtils, "free_space", side_effect=[1.0, 1.5]) as free_mock:
        total, free = SystemUtils.space_usage(paths, btrfs_fsid_dedup=True)

    assert total == 5.0
    assert free == 2.5
    assert total_mock.call_args_list == [call(paths[0]), call(paths[3])]
    assert free_mock.call_args_list == [call(paths[0]), call(paths[3])]


def test_space_usage_keeps_windows_drive_behavior_without_fsid_lookup():
    path = MagicMock()
    path.exists.return_value = True
    path.drive = "D:"
    with patch("app.utils.system.os.name", "nt"), \
            patch.object(SystemUtils, "_get_btrfs_fsid") as fsid_mock, \
            patch.object(SystemUtils, "total_space", return_value=2.0), \
            patch.object(SystemUtils, "free_space", return_value=1.0):
        total, free = SystemUtils.space_usage([path])

    assert total == 2.0
    assert free == 1.0
    fsid_mock.assert_not_called()


def test_local_storage_usage_forwards_btrfs_fsid_setting():
    from app.modules.filemanager.storages import local as local_storage_module

    download_dir = MagicMock(download_path="/downloads")
    library_dir = MagicMock(library_path="/library")
    with patch.object(local_storage_module.settings, "BTRFS_FSID_DEDUP", True), \
            patch.object(local_storage_module.DirectoryHelper, "get_local_download_dirs",
                         return_value=[download_dir]), \
            patch.object(local_storage_module.DirectoryHelper, "get_local_library_dirs",
                         return_value=[library_dir]), \
            patch.object(SystemUtils, "space_usage", return_value=(4.0, 2.0)) as usage_mock:
        usage = object.__new__(local_storage_module.LocalStorage).usage()

    assert usage.total == 4.0
    assert usage.available == 2.0
    usage_mock.assert_called_once_with(
        [Path("/downloads"), Path("/library")],
        btrfs_fsid_dedup=True,
    )


def test_dashboard_downloader_forwards_btrfs_fsid_setting():
    from app.api.endpoints import dashboard as dashboard_module

    download_dir = MagicMock(download_path="/downloads")
    with patch.object(dashboard_module.settings, "BTRFS_FSID_DEDUP", True), \
            patch.object(dashboard_module.DirectoryHelper, "get_local_download_dirs",
                         return_value=[download_dir]), \
            patch.object(SystemUtils, "space_usage", return_value=(4.0, 2.0)) as usage_mock, \
            patch.object(dashboard_module.DashboardChain, "downloader_info", return_value=[]):
        dashboard_module._build_downloader()

    usage_mock.assert_called_once_with(
        [Path("/downloads")],
        btrfs_fsid_dedup=True,
    )


def test_list_sub_file_includes_broken_symlink(tmp_path):
    """损坏软链接仍占用目录项，文件管理器不应把它隐藏。"""
    broken = tmp_path / "broken.mkv"
    broken.symlink_to(tmp_path / "missing-target.mkv")

    assert broken in SystemUtils.list_sub_file(tmp_path)


def test_get_config_path_uses_install_marker_when_env_missing(monkeypatch, tmp_path):
    """仓库写入安装标记后，直接 python -m 入口也必须使用同一个配置目录。"""
    marked_config = tmp_path / "runtime config"
    monkeypatch.delenv("CONFIG_DIR", raising=False)
    monkeypatch.setattr(
        "app.utils.system._read_install_config_dir",
        lambda root: str(marked_config),
    )

    assert SystemUtils.get_config_path() == marked_config


def test_get_config_path_explicit_env_wins_over_install_marker(monkeypatch, tmp_path):
    """显式 CONFIG_DIR 仍是最高优先级，安装标记只补齐缺失环境。"""
    explicit_config = tmp_path / "explicit"
    monkeypatch.setenv("CONFIG_DIR", str(explicit_config))
    monkeypatch.setattr(
        "app.utils.system._read_install_config_dir",
        lambda root: str(tmp_path / "marked"),
    )

    assert SystemUtils.get_config_path() == explicit_config


def test_read_install_config_dir_parses_shell_quoted_path(tmp_path):
    """deploy 用 shell quoting 写入带空格路径时，Python 入口要按同一语义解析。"""
    config_dir = tmp_path / "runtime config"
    (tmp_path / ".moviepilot.env").write_text(
        f"CONFIG_DIR='{config_dir}'\n",
        encoding="utf-8",
    )

    from app.utils.system import _read_install_config_dir

    assert _read_install_config_dir(tmp_path) == str(config_dir)


def test_settings_config_path_uses_install_marker(monkeypatch, tmp_path):
    """Settings 的最终配置路径不得绕过安装标记 fallback。"""
    from app.core.config import Settings

    marked_config = tmp_path / "runtime config"
    monkeypatch.delenv("CONFIG_DIR", raising=False)
    monkeypatch.setattr(
        "app.utils.system._read_install_config_dir",
        lambda root: str(marked_config),
    )
    instance = object.__new__(Settings)
    instance.__dict__["CONFIG_DIR"] = None

    assert instance.CONFIG_PATH == marked_config


def test_clear_continues_after_file_delete_failure_and_reports_error(tmp_path, monkeypatch):
    """单个文件删除失败不能阻止后续过期文件清理，结束后仍要报告失败。"""
    first = tmp_path / "first.old"
    second = tmp_path / "second.old"
    first.write_text("first")
    second.write_text("second")
    old_time = 1
    os.utime(first, (old_time, old_time))
    os.utime(second, (old_time, old_time))
    real_unlink = Path.unlink

    def flaky_unlink(path, *args, **kwargs):
        if path == first:
            raise PermissionError("denied")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", flaky_unlink)

    with pytest.raises(OSError, match="清理"):
        SystemUtils.clear(tmp_path, days=1)

    assert first.exists()
    assert not second.exists()
