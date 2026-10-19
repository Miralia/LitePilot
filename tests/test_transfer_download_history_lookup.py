from pathlib import Path
from types import SimpleNamespace

from app.chain.transfer import TransferChain


class FakeDownloadHistoryOper:
    """提供下载历史回查测试所需的内存桩。"""

    def __init__(
            self,
            histories_by_hash=None,
            histories_by_path=None,
            files_by_fullpath=None,
            files_by_savepath=None,
    ):
        """初始化各查询维度的测试数据。"""
        self.histories_by_hash = histories_by_hash or {}
        self.histories_by_path = histories_by_path or {}
        self.files_by_fullpath = files_by_fullpath or {}
        self.files_by_savepath = files_by_savepath or {}

    def get_by_hash(self, download_hash: str):
        """按下载哈希返回历史。"""
        return self.histories_by_hash.get(download_hash)

    def get_by_path(self, path: str):
        """按下载路径返回历史。"""
        return self.histories_by_path.get(path)

    def get_file_by_fullpath(self, fullpath: str):
        """按完整文件路径返回下载文件记录。"""
        return self.files_by_fullpath.get(fullpath)

    def get_files_by_savepath(self, savepath: str):
        """按保存路径返回下载文件记录。"""
        return self.files_by_savepath.get(savepath, [])


def _make_chain() -> TransferChain:
    """构造不启动后台线程的整理链实例。"""
    return object.__new__(TransferChain)


def _download_dir(**overrides):
    """构造下载目录配置桩。"""
    values = {
        "download_path": "/downloads",
        "media_type": None,
        "download_type_folder": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_resolve_download_history_falls_back_to_parent_download_path():
    """文件记录缺失时应按种子父目录回查下载历史。"""
    expected = SimpleNamespace(download_hash="hash1", downloader="qb")
    oper = FakeDownloadHistoryOper(
        histories_by_hash={"hash1": expected},
        histories_by_path={"/downloads/season-pack": expected},
    )

    history = _make_chain()._resolve_download_history(
        downloadhis=oper,
        file_path=Path("/downloads/season-pack/Test.Show.S01E01.mkv"),
    )

    assert history is expected


def test_resolve_download_history_falls_back_to_unique_savepath_hash():
    """父目录只有一个下载哈希时应返回对应历史。"""
    expected = SimpleNamespace(download_hash="hash1", downloader="qb")
    oper = FakeDownloadHistoryOper(
        histories_by_hash={"hash1": expected},
        files_by_savepath={
            "/downloads/season-pack": [
                SimpleNamespace(download_hash="hash1"),
                SimpleNamespace(download_hash="hash1"),
            ]
        },
    )

    history = _make_chain()._resolve_download_history(
        downloadhis=oper,
        file_path=Path("/downloads/season-pack/subs/Test.Show.S01E01.zh.ass"),
    )

    assert history is expected


def test_resolve_download_history_skips_ambiguous_savepath_hashes():
    """父目录关联多个下载哈希时不应猜测下载历史。"""
    oper = FakeDownloadHistoryOper(
        histories_by_hash={
            "hash1": SimpleNamespace(download_hash="hash1", downloader="qb"),
            "hash2": SimpleNamespace(download_hash="hash2", downloader="tr"),
        },
        files_by_savepath={
            "/downloads/shared": [
                SimpleNamespace(download_hash="hash1"),
                SimpleNamespace(download_hash="hash2"),
            ]
        },
    )

    history = _make_chain()._resolve_download_history(
        downloadhis=oper,
        file_path=Path("/downloads/shared/Test.Show.S01E01.mkv"),
    )

    assert history is None


def test_resolve_download_history_stops_at_shared_download_root_path(monkeypatch):
    """共享下载根目录上的路径历史不应污染同级文件。"""
    oper = FakeDownloadHistoryOper(
        histories_by_path={
            "/downloads": SimpleNamespace(download_hash="hash1", downloader="qb")
        }
    )
    monkeypatch.setattr(
        "app.chain.transfer.DirectoryHelper.get_download_dirs",
        lambda _: [_download_dir()],
    )

    history = _make_chain()._resolve_download_history(
        downloadhis=oper,
        file_path=Path("/downloads/Ghost.Concert.mkv"),
    )

    assert history is None


def test_resolve_download_history_stops_at_shared_download_root_savepath(monkeypatch):
    """共享下载根目录上的其它文件记录不应污染当前文件。"""
    expected = SimpleNamespace(download_hash="hash1", downloader="qb")
    oper = FakeDownloadHistoryOper(
        histories_by_hash={"hash1": expected},
        files_by_savepath={
            "/downloads": [
                SimpleNamespace(
                    download_hash="hash1",
                    fullpath="/downloads/Other.Show.mkv",
                    filepath="Other.Show.mkv",
                ),
            ]
        },
    )
    monkeypatch.setattr(
        "app.chain.transfer.DirectoryHelper.get_download_dirs",
        lambda _: [_download_dir()],
    )

    history = _make_chain()._resolve_download_history(
        downloadhis=oper,
        file_path=Path("/downloads/Ghost.Concert.mkv"),
    )

    assert history is None


def test_resolve_download_history_accepts_shared_root_savepath_for_exact_file(monkeypatch):
    """共享根目录存在当前文件的明确记录时应允许命中。"""
    expected = SimpleNamespace(download_hash="hash1", downloader="qb")
    oper = FakeDownloadHistoryOper(
        histories_by_hash={"hash1": expected},
        files_by_savepath={
            "/downloads": [
                SimpleNamespace(
                    download_hash="hash1",
                    fullpath="/downloads/Ghost.Concert.mkv",
                    filepath="Ghost.Concert.mkv",
                ),
            ]
        },
    )
    monkeypatch.setattr(
        "app.chain.transfer.DirectoryHelper.get_download_dirs",
        lambda _: [_download_dir()],
    )

    history = _make_chain()._resolve_download_history(
        downloadhis=oper,
        file_path=Path("/downloads/Ghost.Concert.mkv"),
    )

    assert history is expected

