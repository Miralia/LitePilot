from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import sessionmaker

from app.chain.downloadfilesync import DownloadFileSyncChain
from app.chain.mediaserverdel import MediaServerDelChain
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


def _add_file(session_factory, fullpath: str, download_hash: str = "hash-a") -> None:
    """写入一条下载文件记录，state 默认为正常。"""
    with session_factory() as db:
        DownloadFiles(
            downloader="qBittorrent",
            download_hash=download_hash,
            fullpath=fullpath,
            savepath="",
            filepath=fullpath,
            torrentname="",
            state=1,
        ).create(db)


def _remain_count(session_factory, download_hash: str = "hash-a") -> int:
    """返回种子里仍标记为正常的文件数。"""
    with session_factory() as db:
        return (
            db.query(DownloadFiles)
            .filter(
                DownloadFiles.download_hash == download_hash,
                DownloadFiles.state == 1,
            )
            .count()
        )


def test_delete_by_fullpath_matches_relative_record(database) -> None:
    """历史遗留的相对路径记录应能被绝对路径删除，否则种子永远删不掉。"""
    _add_file(
        database,
        "The.Odyssey/The.Odyssey.2026.mkv",
    )

    with database() as db:
        DownloadHistoryOper(db).delete_file_by_fullpath(
            fullpath="/home/user/Downloads/Movie/The.Odyssey/The.Odyssey.2026.mkv",
            download_hash="hash-a",
        )

    assert _remain_count(database) == 0


def test_delete_by_fullpath_keeps_other_torrent_same_name(database) -> None:
    """同名文件属于其它种子时不能被连带标记，限定 hash 后必须互不影响。"""
    _add_file(database, "Some.Movie/Some.Movie.mkv", download_hash="hash-a")
    _add_file(database, "Other.Movie/Some.Movie.mkv", download_hash="hash-b")

    with database() as db:
        DownloadHistoryOper(db).delete_file_by_fullpath(
            fullpath="/downloads/Other.Movie/Some.Movie.mkv",
            download_hash="hash-b",
        )

    assert _remain_count(database, "hash-a") == 1
    assert _remain_count(database, "hash-b") == 0


def test_delete_by_fullpath_requires_hash_for_bare_filename(database) -> None:
    """只有文件名能对上时，未限定种子就不该删，避免跨种子误伤。"""
    _add_file(database, "Some.Movie.mkv", download_hash="hash-a")

    with database() as db:
        DownloadHistoryOper(db).delete_file_by_fullpath(
            fullpath="/home/user/Downloads/Movie/Some.Movie.mkv",
        )

    assert _remain_count(database) == 1


def test_resolve_save_path_falls_back_to_downloader(monkeypatch) -> None:
    """下载历史缺失时应回退到下载器自报的保存目录，而不是退化成相对路径。"""
    chain = object.__new__(DownloadFileSyncChain)

    def fake_list_torrents(**_kwargs):
        return [
            # 下载器对无效 hash 会返回全部任务，必须按 hash 精确比对
            _Torrent(hash="other", save_path="/downloads/Anime"),
            _Torrent(hash="target", save_path="/downloads/Movie"),
        ]

    monkeypatch.setattr(chain, "list_torrents", fake_list_torrents)

    assert chain._resolve_save_path("target", "qBittorrent") == "/downloads/Movie"


def test_resolve_save_path_derives_root_from_single_file_content(monkeypatch) -> None:
    """下载器只给 content_path 时，单文件种子应取父目录作为保存根目录。"""
    chain = object.__new__(DownloadFileSyncChain)
    monkeypatch.setattr(
        chain,
        "list_torrents",
        lambda **_kwargs: [
            _Torrent(
                hash="target",
                save_path=None,
                content_path="/downloads/Movie/The.Odyssey.mkv",
            )
        ],
    )

    assert chain._resolve_save_path("target", "qBittorrent") == "/downloads/Movie"


def test_resolve_save_path_returns_empty_when_unmatched(monkeypatch) -> None:
    """下载器查不到该种子时返回空串，由调用方决定如何降级。"""
    chain = object.__new__(DownloadFileSyncChain)
    monkeypatch.setattr(chain, "list_torrents", lambda **_kwargs: [])

    assert chain._resolve_save_path("target", "qBittorrent") == ""


class _Torrent:
    """构造下载器种子对象的最小替身。"""

    def __init__(self, hash, save_path=None, content_path=None):
        self.hash = hash
        self.save_path = save_path
        self.content_path = content_path


def test_process_syncs_all_torrents_not_only_transfer(monkeypatch) -> None:
    """同步必须覆盖全部种子，否则已入库种子永远拿不到文件清单。"""
    chain = object.__new__(DownloadFileSyncChain)
    captured = {}

    def fake_list_torrents(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(chain, "list_torrents", fake_list_torrents)
    monkeypatch.setattr(
        "app.chain.downloadfilesync.ServiceConfigHelper.get_downloader_configs",
        lambda: [_DownloaderConf()],
    )
    monkeypatch.setattr(
        "app.chain.downloadfilesync.download_file_sync_conf",
        lambda: _SyncConf(),
    )

    chain.process()

    # 不能再按「可转移」状态过滤：该状态会把整理过的种子排除在外
    assert "status" not in captured or captured["status"] is None
    assert captured.get("include_all_tags") is True


def test_process_reuses_listed_torrent_save_path(monkeypatch) -> None:
    """定时同步已列出种子对象时，不得再为每个种子重复查询一次保存路径。"""
    from types import SimpleNamespace

    chain = object.__new__(DownloadFileSyncChain)
    torrent = SimpleNamespace(
        hash="hash-a",
        save_path="/downloads/Movie",
        content_path="/downloads/Movie/Example",
    )
    list_calls = []
    added_files = []

    def fake_list_torrents(**kwargs):
        list_calls.append(kwargs)
        return [torrent]

    class FakeDownloadHistoryOper:
        """提供下载文件同步的最小数据库替身。"""

        @staticmethod
        def get_by_hash(download_hash):
            return None

        @staticmethod
        def backfill_savepath(torrent_hash, save_path):
            return 0

        @staticmethod
        def get_files_by_hash(torrent_hash, state=1):
            return []

        @staticmethod
        def add_files(items):
            added_files.extend(items)

    monkeypatch.setattr(chain, "list_torrents", fake_list_torrents)
    monkeypatch.setattr(
        chain,
        "torrent_files",
        lambda tid, downloader: [SimpleNamespace(name="Example/ep01.mkv")],
    )
    monkeypatch.setattr(
        "app.chain.downloadfilesync.DownloadHistoryOper",
        FakeDownloadHistoryOper,
    )
    monkeypatch.setattr(
        "app.chain.downloadfilesync.ServiceConfigHelper.get_downloader_configs",
        lambda: [_DownloaderConf()],
    )
    monkeypatch.setattr(
        "app.chain.downloadfilesync.download_file_sync_conf",
        lambda: _SyncConf(),
    )

    chain.process()

    assert len(list_calls) == 1
    assert added_files[0]["fullpath"] == "/downloads/Movie/Example/ep01.mkv"


def test_sync_does_not_resurrect_deleted_file_record(monkeypatch) -> None:
    """已标记删除的文件记录是墓碑，周期同步不得再插入重复的正常记录。"""
    from types import SimpleNamespace

    chain = object.__new__(DownloadFileSyncChain)
    deleted_path = "/downloads/Movie/Example/ep01.mkv"
    deleted_row = SimpleNamespace(fullpath=deleted_path)
    added_files = []

    class FakeDownloadHistoryOper:
        """按 state 模拟软删除记录的最小数据库替身。"""

        @staticmethod
        def get_by_hash(download_hash):
            return None

        @staticmethod
        def backfill_savepath(torrent_hash, save_path):
            return 0

        @staticmethod
        def get_files_by_hash(torrent_hash, state=None):
            if state == 1:
                return []
            return [deleted_row]

        @staticmethod
        def add_files(items):
            added_files.extend(items)

    monkeypatch.setattr(
        chain,
        "torrent_files",
        lambda tid, downloader: [SimpleNamespace(name="Example/ep01.mkv")],
    )
    monkeypatch.setattr(chain, "_resolve_save_path", lambda *_args: "/downloads/Movie")
    monkeypatch.setattr(
        "app.chain.downloadfilesync.DownloadHistoryOper",
        FakeDownloadHistoryOper,
    )

    assert chain._sync_torrent_files("hash-a", "qBittorrent") == 0
    assert added_files == []


def test_sync_does_not_merge_records_across_downloaders(monkeypatch) -> None:
    """同一 Hash 同时存在于多个下载器时，文件记录不能用 fullpath 跨下载器合并。"""
    from types import SimpleNamespace

    chain = object.__new__(DownloadFileSyncChain)
    existing_path = "/downloads/Movie/Example/ep01.mkv"
    existing_row = SimpleNamespace(
        downloader="Transmission",
        fullpath=existing_path,
    )
    added_files = []

    class FakeDownloadHistoryOper:
        """提供跨下载器已有记录的最小数据库替身。"""

        @staticmethod
        def get_by_hash(download_hash):
            return None

        @staticmethod
        def backfill_savepath(torrent_hash, save_path):
            return 0

        @staticmethod
        def get_files_by_hash(torrent_hash, state=None):
            return [existing_row]

        @staticmethod
        def add_files(items):
            added_files.extend(items)

    monkeypatch.setattr(
        chain,
        "torrent_files",
        lambda tid, downloader: [SimpleNamespace(name="Example/ep01.mkv")],
    )
    monkeypatch.setattr(chain, "_resolve_save_path", lambda *_args: "/downloads/Movie")
    monkeypatch.setattr(
        "app.chain.downloadfilesync.DownloadHistoryOper",
        FakeDownloadHistoryOper,
    )

    assert chain._sync_torrent_files("hash-a", "qBittorrent") == 1
    assert added_files[0]["downloader"] == "qBittorrent"
    assert added_files[0]["fullpath"] == existing_path


class _DownloaderConf:
    """下载器配置替身。"""

    name = "qBittorrent"


class _SyncConf:
    """下载文件同步配置替身。"""

    enabled = True
    downloaders = []
    max_torrents = 0
    trigger_throttle_seconds = 0


def _add_record(session_factory, fullpath, filepath, savepath="", hash="hash-a"):
    """写入一条下载文件记录，可指定 savepath 与 filepath。"""
    with session_factory() as db:
        DownloadFiles(
            downloader="qBittorrent",
            download_hash=hash,
            fullpath=fullpath,
            savepath=savepath,
            filepath=filepath,
            torrentname="",
            state=1,
        ).create(db)


def test_add_files_commits_batch_once(database, monkeypatch) -> None:
    """大批量种子文件应作为一个事务写入，不能每行单独 commit 放大 SQLite 写入。"""
    with database() as db:
        oper = DownloadHistoryOper(db)
        commits = 0
        original_commit = db.commit

        def counting_commit():
            nonlocal commits
            commits += 1
            return original_commit()

        monkeypatch.setattr(db, "commit", counting_commit)
        oper.add_files([
            {
                "downloader": "qBittorrent",
                "download_hash": "hash-a",
                "fullpath": f"/downloads/Show/ep{index:02d}.mkv",
                "savepath": "/downloads",
                "filepath": f"Show/ep{index:02d}.mkv",
                "torrentname": "Show",
                "state": 1,
            }
            for index in range(1, 4)
        ])

    assert commits == 1
    with database() as db:
        assert db.query(DownloadFiles).count() == 3


def test_add_files_rolls_back_whole_batch_on_failure(database, monkeypatch) -> None:
    """批量写入失败时不应留下前半部分文件记录。"""
    with database() as db:
        oper = DownloadHistoryOper(db)
        rollbacks = 0
        original_rollback = db.rollback

        def counting_rollback():
            nonlocal rollbacks
            rollbacks += 1
            return original_rollback()

        monkeypatch.setattr(db, "rollback", counting_rollback)
        with pytest.raises(StatementError):
            oper.add_files([
                {
                    "downloader": "qBittorrent",
                    "download_hash": "hash-a",
                    "fullpath": "/downloads/Show/ep01.mkv",
                    "savepath": "/downloads",
                    "filepath": "Show/ep01.mkv",
                    "torrentname": "Show",
                    "state": 1,
                },
                {
                    "downloader": "qBittorrent",
                    "download_hash": "hash-a",
                    "fullpath": "/downloads/Show/ep02.mkv",
                    "savepath": "/downloads",
                    "filepath": "Show/ep02.mkv",
                    "torrentname": "Show",
                    "state": {"invalid": "state"},
                },
            ])

        assert rollbacks == 1
        assert db.query(DownloadFiles).count() == 0


def test_backfill_converts_relative_path_to_absolute(database) -> None:
    """回填保存目录时，相对路径记录应补成绝对路径。"""
    _add_record(database, "Show.S01/Show.S01E01.mkv", "Show.S01/Show.S01E01.mkv")

    with database() as db:
        updated = DownloadHistoryOper(db).backfill_savepath(
            "hash-a", "/downloads/Anime"
        )

    assert updated == 1
    with database() as db:
        row = db.query(DownloadFiles).one()
        assert row.savepath == "/downloads/Anime"
        assert row.fullpath == "/downloads/Anime/Show.S01/Show.S01E01.mkv"


def test_backfill_keeps_existing_absolute_path(database) -> None:
    """已记录绝对路径时只补 savepath，不得重新拼接 fullpath。"""
    _add_record(
        database,
        "/downloads/Anime/Show.S01E01.mkv",
        "Show.S01E01.mkv",
    )

    with database() as db:
        DownloadHistoryOper(db).backfill_savepath("hash-a", "/downloads/Anime")

    with database() as db:
        row = db.query(DownloadFiles).one()
        assert row.savepath == "/downloads/Anime"
        # 拼接后应当与原来一致；若实现重复叠加会变成 .../Anime/Anime/...
        assert row.fullpath == "/downloads/Anime/Show.S01E01.mkv"


def test_backfill_is_idempotent(database) -> None:
    """重复回填不应反复改写同一条记录。"""
    _add_record(database, "Show.S01E01.mkv", "Show.S01E01.mkv")

    with database() as db:
        first = DownloadHistoryOper(db).backfill_savepath("hash-a", "/dl")
    with database() as db:
        second = DownloadHistoryOper(db).backfill_savepath("hash-a", "/dl")

    assert first == 1
    assert second == 0


def test_absolute_record_path_uses_savepath() -> None:
    """相对路径记录应能用 savepath 还原成绝对路径，供磁盘判断使用。"""
    chain = object.__new__(MediaServerDelChain)
    record = MagicMock(
        fullpath="Show.S01/Show.S01E01.mkv",
        savepath="/downloads/Anime",
    )

    assert (
        chain._absolute_record_path(record)
        == "/downloads/Anime/Show.S01/Show.S01E01.mkv"
    )
    # 无 savepath 时无法还原，返回空串交由调用方过滤
    assert chain._absolute_record_path(MagicMock(fullpath="a.mkv", savepath="")) == ""
