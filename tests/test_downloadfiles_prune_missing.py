"""下载文件同步缺失种子清理测试。"""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.chain.downloadfilesync import DownloadFileSyncChain
from app.db import Base
from app.db.downloadhistory_oper import DownloadHistoryOper
from app.db.models.downloadhistory import DownloadFiles


@pytest.fixture
def database(tmp_path):
    """创建隔离的下载文件测试数据库。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'downloadfiles.db'}")
    session_factory = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield session_factory
    engine.dispose()


def _add_file(session_factory, download_hash: str, downloader: str = "qBittorrent") -> None:
    """写入一条下载文件记录。"""
    with session_factory() as db:
        db.add(
            DownloadFiles(
                downloader=downloader,
                download_hash=download_hash,
                fullpath=f"/downloads/{download_hash}/file.mkv",
                savepath="/downloads",
                filepath=f"{download_hash}/file.mkv",
                torrentname=download_hash,
                state=1,
            )
        )
        db.commit()


def _hashes(session_factory) -> set[tuple[str, str]]:
    """返回当前数据库中的下载器与 hash 组合。"""
    with session_factory() as db:
        return {
            (row.downloader, row.download_hash)
            for row in db.query(DownloadFiles).all()
        }


def test_process_prunes_missing_torrents_only_for_listed_downloader(database, monkeypatch) -> None:
    """开启 prune_missing 后，只物理清理已成功列出任务的下载器中消失的种子。"""
    _add_file(database, "hash-active")
    _add_file(database, "hash-stale")
    _add_file(database, "hash-stale", downloader="other")
    chain = object.__new__(DownloadFileSyncChain)

    monkeypatch.setattr(
        "app.chain.downloadfilesync.download_file_sync_conf",
        lambda: SimpleNamespace(
            enabled=True,
            downloaders=[],
            max_torrents=200,
            prune_missing=True,
        ),
    )
    monkeypatch.setattr(
        "app.chain.downloadfilesync.ServiceConfigHelper.get_downloader_configs",
        staticmethod(lambda: [SimpleNamespace(name="qBittorrent")]),
    )
    monkeypatch.setattr(
        chain,
        "list_torrents",
        lambda **_kwargs: [SimpleNamespace(hash="hash-active")],
    )
    monkeypatch.setattr(chain, "_sync_torrent_files", lambda *_args, **_kwargs: 0)

    with database() as db:
        monkeypatch.setattr(
            "app.chain.downloadfilesync.DownloadHistoryOper",
            lambda: DownloadHistoryOper(db),
        )
        chain.process()

    assert _hashes(database) == {
        ("qBittorrent", "hash-active"),
        ("other", "hash-stale"),
    }


def test_process_prunes_all_when_downloader_is_confirmed_empty(database, monkeypatch) -> None:
    """下载器确认没有任何任务时，该下载器残留文件索引应被清空。"""
    _add_file(database, "hash-stale")
    chain = object.__new__(DownloadFileSyncChain)

    monkeypatch.setattr(
        "app.chain.downloadfilesync.download_file_sync_conf",
        lambda: SimpleNamespace(
            enabled=True,
            downloaders=[],
            max_torrents=200,
            prune_missing=True,
        ),
    )
    monkeypatch.setattr(
        "app.chain.downloadfilesync.ServiceConfigHelper.get_downloader_configs",
        staticmethod(lambda: [SimpleNamespace(name="qBittorrent")]),
    )
    monkeypatch.setattr(chain, "list_torrents", lambda **_kwargs: [])
    monkeypatch.setattr(chain, "_sync_torrent_files", lambda *_args, **_kwargs: 0)

    with database() as db:
        monkeypatch.setattr(
            "app.chain.downloadfilesync.DownloadHistoryOper",
            lambda: DownloadHistoryOper(db),
        )
        chain.process()

    assert _hashes(database) == set()


def test_process_does_not_prune_when_downloader_query_fails(database, monkeypatch) -> None:
    """下载器查询失败时必须保留文件索引，不能把故障误判为任务全部消失。"""
    _add_file(database, "hash-stale")
    chain = object.__new__(DownloadFileSyncChain)

    monkeypatch.setattr(
        "app.chain.downloadfilesync.download_file_sync_conf",
        lambda: SimpleNamespace(
            enabled=True,
            downloaders=[],
            max_torrents=200,
            prune_missing=True,
        ),
    )
    monkeypatch.setattr(
        "app.chain.downloadfilesync.ServiceConfigHelper.get_downloader_configs",
        staticmethod(lambda: [SimpleNamespace(name="qBittorrent")]),
    )
    monkeypatch.setattr(chain, "list_torrents", lambda **_kwargs: None)
    monkeypatch.setattr(chain, "_sync_torrent_files", lambda *_args, **_kwargs: 0)

    with database() as db:
        monkeypatch.setattr(
            "app.chain.downloadfilesync.DownloadHistoryOper",
            lambda: DownloadHistoryOper(db),
        )
        chain.process()

    assert _hashes(database) == {("qBittorrent", "hash-stale")}


def test_process_does_not_prune_when_listed_torrents_missing_hash(database, monkeypatch) -> None:
    """非空任务列表缺失 hash 属于异常数据，不得作为清空本地索引的证据。"""
    _add_file(database, "hash-stale")
    chain = object.__new__(DownloadFileSyncChain)

    monkeypatch.setattr(
        "app.chain.downloadfilesync.download_file_sync_conf",
        lambda: SimpleNamespace(
            enabled=True,
            downloaders=[],
            max_torrents=200,
            prune_missing=True,
        ),
    )
    monkeypatch.setattr(
        "app.chain.downloadfilesync.ServiceConfigHelper.get_downloader_configs",
        staticmethod(lambda: [SimpleNamespace(name="qBittorrent")]),
    )
    monkeypatch.setattr(
        chain,
        "list_torrents",
        lambda **_kwargs: [SimpleNamespace(hash=None)],
    )
    monkeypatch.setattr(chain, "_sync_torrent_files", lambda *_args, **_kwargs: 0)

    with database() as db:
        monkeypatch.setattr(
            "app.chain.downloadfilesync.DownloadHistoryOper",
            lambda: DownloadHistoryOper(db),
        )
        chain.process()

    assert _hashes(database) == {("qBittorrent", "hash-stale")}
