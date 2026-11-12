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
