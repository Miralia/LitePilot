"""日志文件权限测试。"""

import logging
import os

import pytest

from app.log import NonBlockingFileHandler


@pytest.mark.skipif(os.name == "nt", reason="Windows POSIX 权限语义不同")
def test_rotating_handler_enforces_private_log_permissions(tmp_path):
    """日志包含用户活动与路径信息，目录和文件不得被本机其它账户读取或篡改。"""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_dir.chmod(0o777)
    log_file = log_dir / "moviepilot.log"
    log_file.write_text("existing\n", encoding="utf-8")
    log_file.chmod(0o666)
    rotated = log_dir / "moviepilot.log.1"
    rotated.write_text("rotated\n", encoding="utf-8")
    rotated.chmod(0o666)

    handler = NonBlockingFileHandler()._get_rotating_handler(log_file)
    try:
        assert log_dir.stat().st_mode & 0o777 == 0o700
        assert log_file.stat().st_mode & 0o777 == 0o600
        assert rotated.stat().st_mode & 0o777 == 0o600

        handler.maxBytes = 1
        handler.backupCount = 1
        for _ in range(2):
            handler.handle(logging.LogRecord("", logging.INFO, "", 0, "x" * 20, (), None))
        assert log_file.stat().st_mode & 0o777 == 0o600
        assert rotated.stat().st_mode & 0o777 == 0o600
    finally:
        handler.close()
        NonBlockingFileHandler()._rotating_handlers.pop(log_file, None)


@pytest.mark.skipif(os.name == "nt" or not hasattr(os, "O_NOFOLLOW"), reason="需要 POSIX O_NOFOLLOW 语义")
def test_rotating_handler_refuses_symlinked_log_file(tmp_path):
    """历史宽松目录中遗留的符号链接不能让日志写入任意文件。"""
    target = tmp_path / "outside.log"
    target.write_text("original\n", encoding="utf-8")
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "moviepilot.log"
    log_file.symlink_to(target)

    with pytest.raises(OSError):
        NonBlockingFileHandler()._get_rotating_handler(log_file)

    assert target.read_text(encoding="utf-8") == "original\n"
    NonBlockingFileHandler()._rotating_handlers.pop(log_file, None)
