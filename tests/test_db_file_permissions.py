"""SQLite 数据库文件权限测试。"""

import os
import sqlite3

import pytest

from app.core.config import settings
from app.db import _get_sqlite_engine, _secure_sqlite_file_permissions


@pytest.mark.skipif(os.name == "nt", reason="Windows POSIX 权限语义不同")
def test_sqlite_database_and_wal_sidecars_use_private_permissions(tmp_path):
    """含凭据与历史记录的 SQLite 文件不得因默认 umask 变成世界可读。"""
    db_path = tmp_path / "user.db"

    _secure_sqlite_file_permissions(db_path)

    assert db_path.exists()
    assert db_path.stat().st_mode & 0o777 == 0o600
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE probe (id INTEGER)")

    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = tmp_path / f"user.db{suffix}"
        sidecar.write_bytes(b"sidecar")
        sidecar.chmod(0o644)

    _secure_sqlite_file_permissions(db_path)

    for suffix in ("", "-wal", "-shm", "-journal"):
        assert (tmp_path / f"user.db{suffix}").stat().st_mode & 0o777 == 0o600


@pytest.mark.skipif(os.name == "nt", reason="Windows POSIX 权限语义不同")
def test_sqlite_engine_enforces_private_database_permissions(tmp_path, monkeypatch):
    """引擎初始化必须同时收紧既有主库与新建 WAL 侧车文件权限。"""
    monkeypatch.setattr(settings, "CONFIG_DIR", str(tmp_path))
    db_path = tmp_path / "user.db"
    db_path.write_bytes(b"")
    db_path.chmod(0o644)

    engine = _get_sqlite_engine()
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("CREATE TABLE IF NOT EXISTS permission_probe (id INTEGER)")
            connection.exec_driver_sql("INSERT INTO permission_probe (id) VALUES (1)")

            assert db_path.stat().st_mode & 0o777 == 0o600
            for suffix in ("-wal", "-shm"):
                sidecar = tmp_path / f"user.db{suffix}"
                assert sidecar.exists()
                assert sidecar.stat().st_mode & 0o777 == 0o600
    finally:
        engine.dispose()
