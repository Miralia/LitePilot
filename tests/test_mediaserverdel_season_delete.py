from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.chain.mediaserverdel import MediaServerDelChain


TORRENT_HASH = "a6fa" + "a" * 36
DOWNLOADER = "qBittorrent"


def _make_chain() -> MediaServerDelChain:
    """构造不触发真实下载器与数据库的删除链实例。"""
    chain = MediaServerDelChain()
    chain.next_state = "deleted"
    chain.pause_calls = []
    return chain


def _make_history(index: int, tmp_path: Path, season_dir: str = "/dl/Sayonara.Lara.S01"):
    """
    构造一条整季剧集的整理记录。

    源文件默认不存在，模拟用户在媒体库里删除整季、源文件已被清理的情况。
    """
    src = f"{season_dir}/Sayonara.Lara.S01E{index:02d}.mkv"
    return MagicMock(
        id=index,
        title="再见菈菈",
        dest=None,
        src=src,
        src_storage="local",
        mode="link",
        download_hash=TORRENT_HASH,
        downloader=DOWNLOADER,
    )


def _conf() -> MagicMock:
    """构造联动删除配置。"""
    return MagicMock(
        delete_source_file=True,
        delete_torrent=True,
        remove_empty_dirs=False,
        dry_run=False,
    )


class _FakeTorrent:
    """下载器种子替身，只暴露判断所需字段。"""

    def __init__(self, hash, save_path):
        self.hash = hash
        self.save_path = save_path
        self.content_path = None


def test_season_delete_removes_torrent_once(monkeypatch) -> None:
    """整季 12 集共用一个种子时，只应决策一次并删除种子。"""
    chain = _make_chain()
    chain.transferhis = MagicMock()
    chain.downloadhis = MagicMock()
    chain.downloadhis.get_files_by_hash.return_value = []
    chain._cleanup_residual_source = MagicMock()
    chain._torrent_exists = MagicMock(return_value=True)
    chain._obtain_notify_image = MagicMock(return_value=None)
    # 下载器仍报告全部 12 个文件（元数据未变），但磁盘上已全部不存在
    chain.list_torrents = MagicMock(
        return_value=[_FakeTorrent(TORRENT_HASH, "/dl/Sayonara.Lara.S01")]
    )
    chain.torrent_files = MagicMock(
        return_value=[
            MagicMock(name=f"Sayonara.Lara.S01E{i:02d}.mkv") for i in range(1, 13)
        ]
    )
    pause = MagicMock(return_value="paused")
    chain._pause_torrent = pause

    histories = [_make_history(i, Path("/tmp")) for i in range(1, 13)]
    with (
        patch.object(chain, "_query_history", return_value=("剧集", histories)),
        patch("app.chain.mediaserverdel.DownloadChain") as download_chain,
        patch("app.chain.mediaserverdel.Path.exists", autospec=True) as exists,
    ):
        # 媒体与源文件均已不存在，只有明确的 keep 才视为存在
        exists.side_effect = lambda self: False
        download_chain.return_value.remove_downloading.return_value = True
        chain.sync_del(
            media_type="Series",
            media_name="再见菈菈",
            media_path="/media/Goodbye, Lara (2026) [tmdbid=295071]",
            tmdb_id=295071,
        )

    download_chain.return_value.remove_downloading.assert_called_once()
    pause.assert_not_called()


def test_season_delete_pauses_once_when_files_remain(tmp_path) -> None:
    """仍有文件留在磁盘时只暂停一次，不应每条记录各暂停一次。"""
    chain = _make_chain()
    chain.transferhis = MagicMock()
    chain.downloadhis = MagicMock()
    chain.downloadhis.get_files_by_hash.return_value = []
    chain._torrent_exists = MagicMock(return_value=True)
    chain._cleanup_residual_source = MagicMock()
    chain.list_torrents = MagicMock(
        return_value=[_FakeTorrent(TORRENT_HASH, str(tmp_path))]
    )
    chain.torrent_files = MagicMock(
        return_value=[
            MagicMock(name=f"Sayonara.Lara.S01E{i:02d}.mkv") for i in range(1, 13)
        ]
    )
    chain._resolve_torrent_save_path = MagicMock(return_value=str(tmp_path))
    # 磁盘上只剩第 12 集，其余已被删除
    keep = tmp_path / "Sayonara.Lara.S01E12.mkv"
    keep.write_bytes(b"x")
    pause = MagicMock(return_value="paused")
    chain._pause_torrent = pause

    plan = {"downloader": DOWNLOADER, "sources": []}
    for index in range(1, 13):
        plan["sources"].append(
            _make_history(index, tmp_path, season_dir=str(tmp_path)).src
        )
    state = chain._apply_torrent_decision(TORRENT_HASH, plan)

    assert state == "paused"
    pause.assert_called_once()


def test_missing_manifest_uses_disk_state(tmp_path) -> None:
    """清单缺失时按磁盘判断：文件全没了就删种，而不是因为清单空就暂停。"""
    chain = _make_chain()
    chain.downloadhis = MagicMock()
    chain.downloadhis.get_files_by_hash.return_value = []
    chain._torrent_exists = MagicMock(return_value=True)
    chain._cleanup_residual_source = MagicMock()
    chain._pause_torrent = MagicMock(return_value="paused")
    # 下载器仍报告该文件（元数据未变），但磁盘上已不存在
    chain._list_live_torrent_files = MagicMock(
        return_value=[str(tmp_path / "gone.mkv")]
    )

    sources = [str(tmp_path / "gone.mkv")]
    with patch("app.chain.mediaserverdel.DownloadChain") as download_chain:
        download_chain.return_value.remove_downloading.return_value = True
        state = chain._decide_torrent_state(TORRENT_HASH, DOWNLOADER, sources)

    assert state == "deleted"
    chain._pause_torrent.assert_not_called()


def test_partial_delete_keeps_torrent_paused(tmp_path) -> None:
    """只删掉部分文件时应暂停种子，等剩余内容也被删除。"""
    chain = _make_chain()
    chain.downloadhis = MagicMock()
    chain.downloadhis.get_files_by_hash.return_value = []
    chain._torrent_exists = MagicMock(return_value=True)
    chain._cleanup_residual_source = MagicMock()
    pause = MagicMock(return_value="paused")
    chain._pause_torrent = pause

    keep = tmp_path / "keep.mkv"
    keep.write_bytes(b"x")
    sources = [str(tmp_path / "gone.mkv"), str(keep)]

    state = chain._decide_torrent_state(TORRENT_HASH, DOWNLOADER, sources)

    assert state == "paused"
    pause.assert_called_once()


def test_query_history_preserves_numeric_episode_zero() -> None:
    """原生 Emby webhook 的 int 0 季集号必须定位特别篇，不能降级成整剧删除。"""
    chain = object.__new__(MediaServerDelChain)
    chain.transferhis = MagicMock()
    chain.transferhis.get_by.return_value = []

    chain._query_history(
        media_type="Episode",
        media_name="Show",
        media_path="/media/Show/S00/episode0.mkv",
        tmdb_id=123,
        season_num=0,
        episode_num=0,
    )

    first_query = chain.transferhis.get_by.call_args_list[0].kwargs
    assert first_query["season"] == "S00"
    assert first_query["episode"] == "E00"


def test_query_history_matches_multi_episode_range() -> None:
    """删除多集文件的首个 Emby 条目时，应命中 E01-E02 形式的整理历史。"""
    chain = MediaServerDelChain()
    history = SimpleNamespace(
        seasons="S01",
        episodes="E01-E02",
        dest="/library/Show/Season 1/Show S01E01-E02.mkv",
    )

    def get_by(**kwargs):
        if kwargs.get("episode") is not None:
            return []
        if kwargs.get("season") == "S01":
            return [history]
        return []

    chain.transferhis = SimpleNamespace(get_by=get_by)

    _, histories = chain._query_history(
        media_type="Episode",
        media_name="Show",
        media_path=history.dest,
        tmdb_id=123,
        season_num="1",
        episode_num="1",
    )

    assert histories == [history]
