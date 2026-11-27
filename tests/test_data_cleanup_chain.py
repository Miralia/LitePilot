import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.db.models.downloadhistory import DownloadHistory, DownloadFiles
from app.db.models.message import Message
from app.db.models.transferhistory import TransferHistory
from app.core.config import settings
from app.scheduler import SchedulerChain


@pytest.fixture
def db_session_factory():
    """为每个测试提供独立的临时 SQLite 数据库会话工厂。"""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "cleanup.db"
        engine = create_engine(f"sqlite:///{db_path}")
        SessionFactory = sessionmaker(bind=engine)
        Base.metadata.create_all(bind=engine)
        yield SessionFactory
        engine.dispose()


def _cleanup_settings(**overrides):
    defaults = {
        "DATA_CLEANUP_ENABLE": True,
        "DATA_CLEANUP_MESSAGE_DAYS": 90,
        "DATA_CLEANUP_DOWNLOAD_HISTORY_DAYS": 180,
        "DATA_CLEANUP_TRANSFER_HISTORY_DAYS": 365 * 3,
    }
    defaults.update(overrides)
    return patch.multiple(settings, **defaults)


def _build_scheduler_chain():
    """构造不触发消息队列等外部依赖的清理链实例。"""
    return object.__new__(SchedulerChain)


def test_cleanup_removes_expired_rows_in_batches(db_session_factory):
    """
    指定表应按保留期分批删除，并保留仍在有效期内的数据。
    """
    now = datetime.now()
    old_message_time = (now - timedelta(days=120)).strftime("%Y-%m-%d %H:%M:%S")
    keep_message_time = (now - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    old_download_time = (now - timedelta(days=240)).strftime("%Y-%m-%d %H:%M:%S")
    keep_download_time = (now - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
    old_transfer_time = (now - timedelta(days=365 * 3 + 30)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    keep_transfer_time = (now - timedelta(days=30)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    with db_session_factory() as db:
        db.add_all(
            [
                Message(reg_time=old_message_time, title="old-1"),
                Message(reg_time=old_message_time, title="old-2"),
                Message(reg_time=old_message_time, title="old-3"),
                Message(reg_time=keep_message_time, title="keep"),
            ]
        )
        db.add_all(
            [
                DownloadHistory(
                    path="/downloads/old-1",
                    type="电影",
                    title="old-1",
                    download_hash="hash-old-1",
                    date=old_download_time,
                ),
                DownloadHistory(
                    path="/downloads/old-2",
                    type="电影",
                    title="old-2",
                    download_hash="hash-old-2",
                    date=old_download_time,
                ),
                DownloadHistory(
                    path="/downloads/keep",
                    type="电影",
                    title="keep",
                    download_hash="hash-keep",
                    date=keep_download_time,
                ),
            ]
        )
        db.add_all(
            [
                DownloadFiles(
                    download_hash="hash-old-1",
                    fullpath="/downloads/old-1/file.mkv",
                    savepath="/downloads/old-1",
                    filepath="file.mkv",
                ),
                DownloadFiles(
                    download_hash="hash-old-2",
                    fullpath="/downloads/old-2/file.mkv",
                    savepath="/downloads/old-2",
                    filepath="file.mkv",
                ),
                DownloadFiles(
                    download_hash="hash-keep",
                    fullpath="/downloads/keep/file.mkv",
                    savepath="/downloads/keep",
                    filepath="file.mkv",
                ),
                DownloadFiles(
                    download_hash="hash-orphan",
                    fullpath="/downloads/orphan/file.mkv",
                    savepath="/downloads/orphan",
                    filepath="file.mkv",
                ),
            ]
        )
        db.add_all(
            [
                TransferHistory(
                    src="/src/old",
                    title="old",
                    date=old_transfer_time,
                ),
                TransferHistory(
                    src="/src/keep",
                    title="keep",
                    date=keep_transfer_time,
                ),
            ]
        )
        db.commit()

    with _cleanup_settings(), patch("app.scheduler.SessionFactory", db_session_factory):
        report = _build_scheduler_chain().cleanup(batch_size=1)

    assert report["tables"]["message"]["deleted"] == 3
    assert report["tables"]["message"]["batches"] == 3
    assert report["tables"]["downloadhistory"]["deleted"] == 2
    assert "downloadfiles" not in report["tables"]
    assert report["tables"]["transferhistory"]["deleted"] == 1

    with db_session_factory() as db:
        assert db.query(Message).count() == 1
        assert db.query(DownloadHistory).count() == 1
        assert db.query(DownloadFiles).count() == 4
        assert db.query(TransferHistory).count() == 1

        remaining_hashes = {row.download_hash for row in db.query(DownloadFiles).all()}
        assert "hash-keep" in remaining_hashes
        assert "hash-orphan" in remaining_hashes


def test_transferhistory_keeps_boundary_records(db_session_factory):
    """
    恰好位于保留边界上的整理历史不应被提前清理。
    """
    now = datetime.now()
    cutoff_time = (now - timedelta(days=365 * 3)).strftime("%Y-%m-%d %H:%M:%S")

    with db_session_factory() as db:
        db.add(
            TransferHistory(
                src="/src/boundary",
                title="boundary",
                date=cutoff_time,
            )
        )
        db.commit()

    with _cleanup_settings(), patch("app.scheduler.SessionFactory", db_session_factory):
        report = _build_scheduler_chain().cleanup(batch_size=10)

    assert report["tables"]["transferhistory"]["deleted"] == 0

    with db_session_factory() as db:
        assert db.query(TransferHistory).count() == 1


def test_cleanup_skips_when_disabled(db_session_factory):
    """
    总开关关闭时应跳过清理。
    """
    now = datetime.now()
    old_message_time = (now - timedelta(days=120)).strftime("%Y-%m-%d %H:%M:%S")

    with db_session_factory() as db:
        db.add(Message(reg_time=old_message_time, title="old"))
        db.commit()

    with _cleanup_settings(DATA_CLEANUP_ENABLE=False), patch(
        "app.scheduler.SessionFactory", db_session_factory
    ):
        report = _build_scheduler_chain().cleanup(batch_size=10)

    assert not report["enabled"]
    assert report["skipped_reason"] == "disabled"
    assert report["total_deleted"] == 0

    with db_session_factory() as db:
        assert db.query(Message).count() == 1


def test_cleanup_respects_per_table_retention_days(db_session_factory):
    """
    各表保留期应使用当前配置值。
    """
    now = datetime.now()
    old_message_time = (now - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    keep_message_time = (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")

    with db_session_factory() as db:
        db.add_all(
            [
                Message(reg_time=old_message_time, title="old"),
                Message(reg_time=keep_message_time, title="keep"),
            ]
        )
        db.commit()

    with _cleanup_settings(DATA_CLEANUP_MESSAGE_DAYS=7), patch(
        "app.scheduler.SessionFactory", db_session_factory
    ):
        report = _build_scheduler_chain().cleanup(batch_size=10)

    assert report["tables"]["message"]["retention_days"] == 7
    assert report["tables"]["message"]["deleted"] == 1

    with db_session_factory() as db:
        assert db.query(Message).count() == 1


def test_cleanup_skips_table_when_retention_days_is_zero(db_session_factory):
    """
    单表保留期为 0 时应跳过该表及其附属孤儿记录清理。
    """
    now = datetime.now()
    old_download_time = (now - timedelta(days=240)).strftime("%Y-%m-%d %H:%M:%S")

    with db_session_factory() as db:
        db.add(
            DownloadHistory(
                path="/downloads/old",
                type="电影",
                title="old",
                download_hash="hash-old",
                date=old_download_time,
            )
        )
        db.add(
            DownloadFiles(
                download_hash="hash-orphan",
                fullpath="/downloads/orphan/file.mkv",
                savepath="/downloads/orphan",
                filepath="file.mkv",
            )
        )
        db.commit()

    with _cleanup_settings(DATA_CLEANUP_DOWNLOAD_HISTORY_DAYS=0), patch(
        "app.scheduler.SessionFactory", db_session_factory
    ):
        report = _build_scheduler_chain().cleanup(batch_size=10)

    assert report["tables"]["downloadhistory"]["skipped"]
    assert "downloadfiles" not in report["tables"]

    with db_session_factory() as db:
        assert db.query(DownloadHistory).count() == 1
        assert db.query(DownloadFiles).count() == 1


def test_cleanup_preserves_download_file_indexes_without_download_history(db_session_factory):
    """外部添加的种子没有下载历史父记录，数据清理不得误删其文件索引。"""
    with db_session_factory() as db:
        db.add(
            DownloadFiles(
                download_hash="external-active",
                fullpath="/downloads/external/file.mkv",
                savepath="/downloads/external",
                filepath="file.mkv",
            )
        )
        db.commit()

    with _cleanup_settings(), patch("app.scheduler.SessionFactory", db_session_factory):
        report = _build_scheduler_chain().cleanup(batch_size=10)

    assert report["total_deleted"] == 0
    with db_session_factory() as db:
        assert db.query(DownloadFiles).count() == 1
