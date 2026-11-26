# -*- coding: utf-8 -*-
"""
配置目录备份与恢复。

本分支采用原生部署：源码在仓库目录、配置与数据库在 `CONFIG_DIR`。迁移或重装时
只需要搬运配置目录，因此备份以「配置目录整体打包 + 清单校验」为核心，恢复时先校验
清单再解包，避免半包状态破坏现有数据。
"""

import json
import os
import shutil
import sqlite3
import tarfile
import tempfile
import uuid
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.core.config import settings
from app.log import logger

# 备份清单文件名，用于校验包完整性与记录来源信息
MANIFEST_NAME = "moviepilot-backup.json"
# 备份格式版本，后续格式变化时用于兼容判断
BACKUP_FORMAT_VERSION = 1
# 备份时排除的目录：均为可重建的缓存与运行期临时数据
EXCLUDE_DIRS = {"temp", "cache", ".cache", "logs"}
# 备份包与敏感配置文件只允许所有者读写，避免数据库/env 凭据被本机其它账户读取
SENSITIVE_FILE_MODE = 0o600
SENSITIVE_CONFIG_FILES = (
    "app.env",
    "user.db",
    "user.db-wal",
    "user.db-shm",
    "user.db-journal",
)
# 运行中的 SQLite 主库与侧车文件不能按普通文件直接复制，统一改用在线备份快照
SQLITE_BACKUP_FILES = {"user.db", "user.db-wal", "user.db-shm", "user.db-journal"}


@dataclass
class BackupResult:
    """备份结果。"""

    archive: Path
    config_dir: Path
    file_count: int
    total_bytes: int
    excluded: List[str] = field(default_factory=list)


@dataclass
class RestoreResult:
    """恢复结果。"""

    config_dir: Path
    file_count: int
    source: Path
    backup_time: Optional[str] = None


def _secure_sensitive_config_permissions(config_dir: Path) -> None:
    """恢复后收紧数据库与 env 文件权限，避免继承旧备份中的宽松 mode。"""
    if os.name == "nt":
        return
    for name in SENSITIVE_CONFIG_FILES:
        try:
            (config_dir / name).chmod(SENSITIVE_FILE_MODE)
        except FileNotFoundError:
            continue


def _create_sqlite_snapshot(source: Path, snapshot: Path) -> None:
    """用 SQLite 在线备份 API 创建一致性数据库快照。"""
    with closing(sqlite3.connect(source)) as source_connection:
        with closing(sqlite3.connect(snapshot)) as snapshot_connection:
            source_connection.backup(snapshot_connection)
    if os.name != "nt":
        snapshot.chmod(SENSITIVE_FILE_MODE)


def _is_litepilot_backup_archive(path: Path) -> bool:
    """识别 LitePilot 备份产物，避免历史归档被递归打进新备份。"""
    is_tar_gzip = path.suffixes[-2:] == [".tar", ".gz"] or path.suffix == ".tgz"
    if not is_tar_gzip:
        return False
    try:
        with tarfile.open(path, "r:*") as tar:
            # 清单始终由本工具第一个写入；只读取首个成员，避免为识别而解压大文件内容。
            member = tar.next()
            if member and member.name == MANIFEST_NAME:
                return True
    except (OSError, EOFError, tarfile.TarError):
        return False
    return False


def _iter_backup_files(config_dir: Path, archive: Optional[Path] = None) -> List[Path]:
    """
    列出需要备份的文件，跳过可重建的缓存目录与目标归档自身。

    :param config_dir: 配置目录
    :param archive: 目标备份包路径
    :return: 文件路径列表
    """
    archive_relative = None
    if archive is not None:
        try:
            archive_relative = archive.relative_to(config_dir)
        except ValueError:
            archive_relative = None

    files: List[Path] = []
    for path in sorted(config_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(config_dir)
        if archive_relative is not None and relative == archive_relative:
            continue
        if relative.parts and relative.parts[0] in EXCLUDE_DIRS:
            continue
        if len(relative.parts) == 1 and relative.name in SQLITE_BACKUP_FILES:
            continue
        if _is_litepilot_backup_archive(path):
            continue
        files.append(path)
    return files


def _replace_config_directory(staging: Path, target: Path) -> None:
    """用同文件系统目录替换配置目录，替换失败时恢复原目录。"""
    previous = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.previous-", dir=target.parent)
    )
    previous.rmdir()
    moved_previous = False
    try:
        if target.exists():
            target.rename(previous)
            moved_previous = True
        try:
            staging.rename(target)
        except Exception:
            if moved_previous and not target.exists():
                try:
                    previous.rename(target)
                except OSError as rollback_error:
                    logger.error(f"配置恢复回滚失败，旧配置保留在 {previous}：{rollback_error}")
            raise
    except Exception:
        if not moved_previous and previous.exists():
            previous.rmdir()
        raise

    if moved_previous:
        shutil.rmtree(previous)


def create_backup(
    archive: Optional[Path] = None,
    config_dir: Optional[Path] = None,
) -> BackupResult:
    """
    打包配置目录。

    :param archive: 目标压缩包路径，默认写入配置目录同级的 moviepilot-backup-<时间>.tar.gz
    :param config_dir: 配置目录，默认取当前运行配置
    :return: 备份结果
    :raises FileNotFoundError: 配置目录不存在
    """
    source = (config_dir or settings.CONFIG_PATH).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"配置目录不存在：{source}")

    if archive is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        archive = source.parent / f"moviepilot-backup-{stamp}.tar.gz"
    archive = archive.expanduser().resolve()
    archive.parent.mkdir(parents=True, exist_ok=True)

    files = _iter_backup_files(source, archive=archive)
    file_count = len(files) + (1 if (source / "user.db").exists() else 0)
    manifest = {
        "format_version": BACKUP_FORMAT_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_config_dir": str(source),
        "file_count": file_count,
    }
    manifest_path = Path(tempfile.mkdtemp(prefix="mp-backup-")) / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    snapshot_path = None
    source_db = source / "user.db"
    if source_db.exists():
        snapshot_path = manifest_path.parent / "user.db"
        _create_sqlite_snapshot(source_db, snapshot_path)

    total_bytes = 0
    temporary_archive = archive.with_name(f".{archive.name}.{uuid.uuid4().hex}.tmp")
    try:
        # 先以私有权限写入同目录临时归档，成功后原子发布，避免半截备份被误用。
        descriptor = os.open(
            temporary_archive,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            SENSITIVE_FILE_MODE,
        )
        with os.fdopen(descriptor, "wb") as archive_file:
            if os.name != "nt":
                os.fchmod(archive_file.fileno(), SENSITIVE_FILE_MODE)
            with tarfile.open(fileobj=archive_file, mode="w:gz") as tar:
                tar.add(manifest_path, arcname=MANIFEST_NAME)
                for path in files:
                    tar.add(path, arcname=str(path.relative_to(source)))
                    total_bytes += path.stat().st_size
                if snapshot_path is not None:
                    tar.add(snapshot_path, arcname="user.db")
                    total_bytes += snapshot_path.stat().st_size
        os.replace(temporary_archive, archive)
    finally:
        if temporary_archive.exists():
            temporary_archive.unlink()
        shutil.rmtree(manifest_path.parent, ignore_errors=True)

    logger.info(f"配置备份完成：{archive}（{file_count} 个文件）")
    return BackupResult(
        archive=archive,
        config_dir=source,
        file_count=file_count,
        total_bytes=total_bytes,
        excluded=sorted(EXCLUDE_DIRS),
    )


def read_manifest(archive: Path) -> Optional[dict]:
    """
    读取备份包中的清单。

    :param archive: 备份包路径
    :return: 清单字典，包内没有清单时返回 None
    """
    with tarfile.open(archive, "r:gz") as tar:
        try:
            member = tar.getmember(MANIFEST_NAME)
        except KeyError:
            return None
        extracted = tar.extractfile(member)
        if not extracted:
            return None
        return json.loads(extracted.read().decode("utf-8"))


def restore_backup(
    archive: Path,
    config_dir: Optional[Path] = None,
    overwrite: bool = False,
) -> RestoreResult:
    """
    从备份包恢复配置目录。

    为避免半包状态破坏现有数据，先把内容解到临时目录，确认解包完整后再整体替换目标目录；
    覆盖已有目录时必须显式声明 `overwrite`。

    :param archive: 备份包路径
    :param config_dir: 目标配置目录，默认取当前运行配置
    :param overwrite: 目标目录已存在时是否覆盖
    :return: 恢复结果
    :raises FileNotFoundError: 备份包不存在
    :raises FileExistsError: 目标目录已存在且未允许覆盖
    """
    archive = archive.expanduser().resolve()
    if not archive.exists():
        raise FileNotFoundError(f"备份包不存在：{archive}")

    target = (config_dir or settings.CONFIG_PATH).expanduser().resolve()
    if target.exists() and any(target.iterdir()) and not overwrite:
        raise FileExistsError(
            f"配置目录已存在且非空：{target}；如确认覆盖请显式允许 overwrite"
        )

    manifest = read_manifest(archive) or {}
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.restore-", dir=target.parent)
    )
    try:
        with tarfile.open(archive, "r:gz") as tar:
            # 只解出普通文件与目录，避免备份包内的链接写到目标目录之外
            members = [
                member
                for member in tar.getmembers()
                if member.isfile() or member.isdir()
            ]
            for member in members:
                if member.name == MANIFEST_NAME:
                    continue
                member_path = Path(member.name)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise ValueError(f"备份包包含非法路径：{member.name}")
            tar.extractall(
                staging,
                members=[m for m in members if m.name != MANIFEST_NAME],
                filter="data",
            )

        _replace_config_directory(staging, target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    _secure_sensitive_config_permissions(target)
    file_count = sum(1 for path in target.rglob("*") if path.is_file())
    logger.info(f"配置恢复完成：{target}（{file_count} 个文件）")
    return RestoreResult(
        config_dir=target,
        file_count=file_count,
        source=archive,
        backup_time=manifest.get("created_at"),
    )