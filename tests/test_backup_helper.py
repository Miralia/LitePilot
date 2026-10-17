# -*- coding: utf-8 -*-
"""配置备份与恢复用例。

覆盖打包内容筛选、清单写入、恢复替换语义与安全校验（非法路径、非空目录未授权覆盖）。
全部在临时目录内进行，不触碰真实配置。
"""
import tarfile
from pathlib import Path

import pytest

from app.helper.backup import (
    MANIFEST_NAME,
    create_backup,
    read_manifest,
    restore_backup,
)


def _make_config(root: Path) -> Path:
    """构造一个包含数据库、环境文件与可重建缓存目录的假配置目录。"""
    config = root / "config"
    (config / "logs").mkdir(parents=True)
    (config / "temp").mkdir(parents=True)
    (config / "user.db").write_bytes(b"sqlite-db")
    (config / "app.env").write_text("SUPERUSER=admin\n", encoding="utf-8")
    (config / "category.yaml").write_text("movie: []\n", encoding="utf-8")
    (config / "logs" / "moviepilot.log").write_text("log", encoding="utf-8")
    (config / "temp" / "cache.bin").write_bytes(b"cache")
    return config


def test_create_backup_excludes_rebuildable_dirs(tmp_path):
    """备份应包含数据库与配置，排除日志与缓存等可重建目录。"""
    config = _make_config(tmp_path)

    result = create_backup(archive=tmp_path / "backup.tar.gz", config_dir=config)

    assert result.file_count == 3
    assert result.archive.exists()
    with tarfile.open(result.archive, "r:gz") as tar:
        names = sorted(member.name for member in tar.getmembers())
    assert names == sorted([MANIFEST_NAME, "user.db", "app.env", "category.yaml"])


def test_create_backup_writes_manifest(tmp_path):
    """备份包内应写入可校验的清单。"""
    config = _make_config(tmp_path)

    result = create_backup(archive=tmp_path / "backup.tar.gz", config_dir=config)
    manifest = read_manifest(result.archive)

    assert manifest is not None
    assert manifest["file_count"] == 3
    assert manifest["source_config_dir"] == str(config.resolve())
    assert manifest["format_version"] >= 1


def test_create_backup_rejects_missing_config_dir(tmp_path):
    """配置目录不存在时应明确报错，而不是产出空包。"""
    with pytest.raises(FileNotFoundError):
        create_backup(archive=tmp_path / "backup.tar.gz", config_dir=tmp_path / "nope")


def test_restore_backup_replaces_target(tmp_path):
    """恢复应把备份内容写到目标配置目录。"""
    config = _make_config(tmp_path)
    result = create_backup(archive=tmp_path / "backup.tar.gz", config_dir=config)
    target = tmp_path / "restored"

    restored = restore_backup(result.archive, config_dir=target)

    assert restored.file_count == 3
    assert (target / "user.db").read_bytes() == b"sqlite-db"
    assert (target / "app.env").read_text(encoding="utf-8") == "SUPERUSER=admin\n"
    # 被排除的目录不会出现在恢复结果里
    assert not (target / "logs").exists()


def test_restore_backup_requires_overwrite_for_non_empty_target(tmp_path):
    """目标目录非空且未授权覆盖时应拒绝恢复，避免破坏现有数据。"""
    config = _make_config(tmp_path)
    result = create_backup(archive=tmp_path / "backup.tar.gz", config_dir=config)
    target = tmp_path / "existing"
    target.mkdir()
    (target / "user.db").write_bytes(b"keep-me")

    with pytest.raises(FileExistsError):
        restore_backup(result.archive, config_dir=target)

    assert (target / "user.db").read_bytes() == b"keep-me"


def test_restore_backup_overwrites_when_allowed(tmp_path):
    """显式允许覆盖时应整体替换目标目录内容。"""
    config = _make_config(tmp_path)
    result = create_backup(archive=tmp_path / "backup.tar.gz", config_dir=config)
    target = tmp_path / "existing"
    target.mkdir()
    (target / "stale.txt").write_text("old", encoding="utf-8")

    restored = restore_backup(result.archive, config_dir=target, overwrite=True)

    assert restored.file_count == 3
    assert not (target / "stale.txt").exists()
    assert (target / "user.db").exists()


def test_restore_backup_rejects_missing_archive(tmp_path):
    """备份包不存在时应明确报错。"""
    with pytest.raises(FileNotFoundError):
        restore_backup(tmp_path / "missing.tar.gz", config_dir=tmp_path / "target")


def test_restore_backup_rejects_path_traversal(tmp_path):
    """备份包内出现越界路径时必须拒绝恢复。"""
    archive = tmp_path / "evil.tar.gz"
    payload = tmp_path / "payload.txt"
    payload.write_text("evil", encoding="utf-8")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(payload, arcname="../escape.txt")

    with pytest.raises(ValueError):
        restore_backup(archive, config_dir=tmp_path / "target")

    assert not (tmp_path / "escape.txt").exists()


def test_read_manifest_returns_none_without_manifest(tmp_path):
    """包内没有清单时返回 None，由调用方按无清单处理。"""
    archive = tmp_path / "plain.tar.gz"
    payload = tmp_path / "user.db"
    payload.write_bytes(b"sqlite")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(payload, arcname="user.db")

    assert read_manifest(archive) is None


def test_backup_archive_defaults_to_config_parent(tmp_path):
    """未指定输出路径时，备份包写在配置目录同级，便于整体搬运。"""
    config = _make_config(tmp_path)

    result = create_backup(config_dir=config)

    assert result.archive.parent == config.resolve().parent
    assert result.archive.name.startswith("moviepilot-backup-")
    assert result.archive.exists()