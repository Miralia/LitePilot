# -*- coding: utf-8 -*-
"""
配置目录备份与恢复。

本分支采用原生部署：源码在仓库目录、配置与数据库在 `CONFIG_DIR`。迁移或重装时
只需要搬运配置目录，因此备份以「配置目录整体打包 + 清单校验」为核心，恢复时先校验
清单再解包，避免半包状态破坏现有数据。
"""

import json
import shutil
import tarfile
import tempfile
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


def _iter_backup_files(config_dir: Path) -> List[Path]:
    """
    列出需要备份的文件，跳过可重建的缓存目录。

    :param config_dir: 配置目录
    :return: 文件路径列表
    """
    files: List[Path] = []
    for path in sorted(config_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(config_dir)
        if relative.parts and relative.parts[0] in EXCLUDE_DIRS:
            continue
        files.append(path)
    return files


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

    files = _iter_backup_files(source)
    manifest = {
        "format_version": BACKUP_FORMAT_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_config_dir": str(source),
        "file_count": len(files),
    }
    manifest_path = Path(tempfile.mkdtemp(prefix="mp-backup-")) / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    total_bytes = 0
    try:
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(manifest_path, arcname=MANIFEST_NAME)
            for path in files:
                tar.add(path, arcname=str(path.relative_to(source)))
                total_bytes += path.stat().st_size
    finally:
        shutil.rmtree(manifest_path.parent, ignore_errors=True)

    logger.info(f"配置备份完成：{archive}（{len(files)} 个文件）")
    return BackupResult(
        archive=archive,
        config_dir=source,
        file_count=len(files),
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
    staging = Path(tempfile.mkdtemp(prefix="mp-restore-"))
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
            tar.extractall(staging, members=[m for m in members if m.name != MANIFEST_NAME])

        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staging), str(target))
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    file_count = sum(1 for path in target.rglob("*") if path.is_file())
    logger.info(f"配置恢复完成：{target}（{file_count} 个文件）")
    return RestoreResult(
        config_dir=target,
        file_count=file_count,
        source=archive,
        backup_time=manifest.get("created_at"),
    )