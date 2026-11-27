from types import SimpleNamespace

from app.chain.transfer import TransferChain
from app.api.endpoints.transfer import (
    manual_transfer,
    recommend_episode_format,
)
from app.schemas import EpisodeFormatRecommendItem, ManualTransferItem


def test_manual_transfer_from_history_preserves_download_context(monkeypatch):
    """复用历史识别信息时应传递原下载上下文。"""
    history = SimpleNamespace(
        status=0,
        mode="copy",
        src_fileitem={"storage": "local", "path": "/downloads/test.mkv", "name": "test.mkv", "type": "file"},
        dest_fileitem=None,
        downloader="qbittorrent",
        download_hash="abc123",
        type="电视剧",
        tmdbid="100",
        doubanid="200",
        bangumiid=None,
        anilistid=None,
        media_source="themoviedb",
        media_id="100",
        seasons="S01",
        episodes="E01-E02",
        episode_group="WEB-DL",
    )

    captured = {}

    def fake_get(_db, logid):
        assert logid == 1
        return history

    class FakeTransferChain:
        def manual_transfer(self, **kwargs):
            captured.update(kwargs)
            return True, ""

    monkeypatch.setattr("app.api.endpoints.transfer.TransferHistory.get", fake_get)
    monkeypatch.setattr("app.api.endpoints.transfer.TransferChain", FakeTransferChain)

    resp = manual_transfer(
        transer_item=ManualTransferItem(logid=1, from_history=True),
        background=True,
        db=object(),
        _="token",
    )

    assert resp.success is True
    assert captured["downloader"] == "qbittorrent"
    assert captured["download_hash"] == "abc123"
    assert captured["episode_group"] == "WEB-DL"
    assert captured["season"] == 1


def test_manual_transfer_without_history_recognition_ignores_old_hash(monkeypatch):
    """从历史重新识别时应忽略旧下载上下文。"""
    history = SimpleNamespace(
        status=0,
        mode="copy",
        src_fileitem={
            "storage": "local",
            "path": "/downloads/test.mkv",
            "name": "test.mkv",
            "type": "file",
        },
        dest_fileitem=None,
        downloader="qbittorrent",
        download_hash="polluted-hash",
        type="电视剧",
        tmdbid="100",
        doubanid="200",
        seasons="S01",
        episodes="E01",
        episode_group="WEB-DL",
    )
    captured = {}

    def fake_get(_db, logid):
        """返回受污染的历史记录。"""
        assert logid == 1
        return history

    class FakeTransferChain:
        """记录 API 传入整理链的参数。"""

        def manual_transfer(self, **kwargs):
            """记录手动整理参数。"""
            captured.update(kwargs)
            return True, ""

    monkeypatch.setattr("app.api.endpoints.transfer.TransferHistory.get", fake_get)
    monkeypatch.setattr("app.api.endpoints.transfer.TransferChain", FakeTransferChain)

    resp = manual_transfer(
        transer_item=ManualTransferItem(logid=1, from_history=False),
        background=True,
        db=object(),
        _="token",
    )

    assert resp.success is True
    assert captured["downloader"] is None
    assert captured["download_hash"] is None
    assert captured["tmdbid"] is None
    assert captured["doubanid"] is None
    assert captured["episode_group"] is None


def test_manual_transfer_from_history_passes_old_dest_cleanup_to_chain(monkeypatch):
    history = SimpleNamespace(
        status=0,
        mode="copy",
        src_fileitem={
            "storage": "local",
            "path": "/downloads/test.mkv",
            "name": "test.mkv",
            "type": "file",
        },
        dest_fileitem={
            "storage": "local",
            "path": "/library/test.mkv",
            "name": "test.mkv",
            "type": "file",
        },
        downloader="qbittorrent",
        download_hash="abc123",
        type=None,
        tmdbid=None,
        doubanid=None,
        seasons=None,
        episodes=None,
        episode_group=None,
    )
    captured = {}

    def fake_get(_db, logid):
        assert logid == 1
        return history

    class FakeTransferChain:
        def manual_transfer(self, **kwargs):
            captured.update(kwargs)
            return True, ""

    monkeypatch.setattr("app.api.endpoints.transfer.TransferHistory.get", fake_get)
    monkeypatch.setattr("app.api.endpoints.transfer.TransferChain", FakeTransferChain)

    resp = manual_transfer(
        transer_item=ManualTransferItem(logid=1),
        background=False,
        db=object(),
        _="token",
    )

    assert resp.success is True
    assert captured["fileitem"].path == "/downloads/test.mkv"
    assert captured["cleanup_dest_fileitem"].path == "/library/test.mkv"


def test_manual_transfer_from_history_preview_does_not_cleanup_old_dest(monkeypatch):
    history = SimpleNamespace(
        status=0,
        mode="copy",
        src_fileitem={
            "storage": "local",
            "path": "/downloads/test.mkv",
            "name": "test.mkv",
            "type": "file",
        },
        dest_fileitem={
            "storage": "local",
            "path": "/library/test.mkv",
            "name": "test.mkv",
            "type": "file",
        },
        downloader="qbittorrent",
        download_hash="abc123",
        type=None,
        tmdbid=None,
        doubanid=None,
        seasons=None,
        episodes=None,
        episode_group=None,
    )
    captured = {}

    def fake_get(_db, logid):
        assert logid == 1
        return history

    class FakeTransferChain:
        def manual_transfer(self, **kwargs):
            captured.update(kwargs)
            return True, {
                "summary": {"total": 0, "success": 0, "failed": 0},
                "items": [],
                "message": "",
            }

    monkeypatch.setattr("app.api.endpoints.transfer.TransferHistory.get", fake_get)
    monkeypatch.setattr("app.api.endpoints.transfer.TransferChain", FakeTransferChain)

    resp = manual_transfer(
        transer_item=ManualTransferItem(logid=1, preview=True),
        background=False,
        db=object(),
        _="token",
    )

    assert resp.success is True
    assert captured["cleanup_dest_fileitem"] is None


def test_manual_transfer_preview_uses_explicit_fileitems_instead_of_directory(monkeypatch):
    dir_item = {
        "storage": "local",
        "path": "/downloads/Test Show/",
        "name": "Test Show",
        "type": "dir",
    }
    file_paths = [
        "/downloads/Test Show/Test.Show.S01E01.mkv",
        "/downloads/Test Show/Test.Show.S01E02.mkv",
        "/downloads/Test Show/Test.Show.S01E03.mkv",
    ]
    selected_fileitems = [
        {
            "storage": "local",
            "path": file_path,
            "name": file_path.rsplit("/", 1)[-1],
            "type": "file",
        }
        for file_path in file_paths
    ]
    captured = []

    class FakeTransferChain:
        def manual_transfer(self, **kwargs):
            captured.append(kwargs)
            fileitem = kwargs["fileitem"]
            return True, {
                "summary": {"total": 1, "success": 1, "failed": 0},
                "items": [
                    {
                        "source": fileitem.path,
                        "target": f"/library/{fileitem.name}",
                        "target_dir": "/library",
                        "success": True,
                        "message": "",
                        "type": "电视剧",
                        "title": "Test Show (2026)",
                        "season": 1,
                        "episode": 1,
                        "episode_end": None,
                        "part": None,
                    }
                ],
                "message": "",
            }

    monkeypatch.setattr("app.api.endpoints.transfer.TransferChain", FakeTransferChain)

    resp = manual_transfer(
        transer_item=ManualTransferItem(
            fileitem=dir_item,
            fileitems=selected_fileitems,
            preview=True,
        ),
        background=False,
        db=object(),
        _="token",
    )

    assert resp.success is True
    assert len(captured) == 3
    assert [item["fileitem"].path for item in captured] == file_paths
    assert all(item["sync_extra_files"] is False for item in captured)
    assert resp.data["summary"] == {"total": 3, "success": 3, "failed": 0}
    assert [item["source"] for item in resp.data["items"]] == file_paths


def test_manual_transfer_preview_multi_select_collects_failures(monkeypatch):
    file_paths = [
        "/downloads/Test Show/Test.Show.S01E01.mkv",
        "/downloads/Test Show/Test.Show.S01E02.mkv",
    ]
    selected_fileitems = [
        {
            "storage": "local",
            "path": file_path,
            "name": file_path.rsplit("/", 1)[-1],
            "type": "file",
        }
        for file_path in file_paths
    ]

    class FakeTransferChain:
        def manual_transfer(self, **kwargs):
            fileitem = kwargs["fileitem"]
            if fileitem.path.endswith("E02.mkv"):
                return False, f"{fileitem.name} 没有找到可整理的媒体文件"
            return True, {
                "summary": {"total": 1, "success": 1, "failed": 0},
                "items": [
                    {
                        "source": fileitem.path,
                        "target": f"/library/{fileitem.name}",
                        "target_dir": "/library",
                        "success": True,
                        "message": "",
                        "type": "电视剧",
                        "title": "Test Show (2026)",
                        "season": 1,
                        "episode": 1,
                        "episode_end": None,
                        "part": None,
                    }
                ],
                "message": "",
            }

    monkeypatch.setattr("app.api.endpoints.transfer.TransferChain", FakeTransferChain)

    resp = manual_transfer(
        transer_item=ManualTransferItem(
            fileitems=selected_fileitems,
            preview=True,
        ),
        background=False,
        db=object(),
        _="token",
    )

    assert resp.success is True
    assert resp.data["summary"] == {"total": 2, "success": 1, "failed": 1}
    assert [item["source"] for item in resp.data["items"]] == file_paths
    assert resp.data["items"][1]["success"] is False


def test_recommend_episode_format_passes_selected_fileitems(monkeypatch):
    selected_fileitems = [
        {
            "storage": "local",
            "path": "/downloads/Test Show/Test.Show.S01E01.mkv",
            "name": "Test.Show.S01E01.mkv",
            "type": "file",
        },
        {
            "storage": "local",
            "path": "/downloads/Test Show/Test.Show.S01E02.mkv",
            "name": "Test.Show.S01E02.mkv",
            "type": "file",
        },
    ]
    captured = {}

    class FakeTransferChain:
        def recommend_episode_format(self, **kwargs):
            captured.update(kwargs)
            return True, "", {"episode_format": "Show.S01E{ep}.mkv"}

    monkeypatch.setattr("app.api.endpoints.transfer.TransferChain", FakeTransferChain)

    resp = recommend_episode_format(
        recommend_item=EpisodeFormatRecommendItem(
            fileitem=selected_fileitems[0],
            fileitems=selected_fileitems,
        ),
        _="token",
    )

    assert resp.success is True
    assert captured["fileitem"].path == selected_fileitems[0]["path"]
    assert [item.path for item in captured["fileitems"]] == [
        item["path"] for item in selected_fileitems
    ]


def test_recommend_episode_format_accepts_fileitems_without_fileitem(monkeypatch):
    selected_fileitems = [
        {
            "storage": "local",
            "path": "/downloads/Test Show/Test.Show.S01E01.mkv",
            "name": "Test.Show.S01E01.mkv",
            "type": "file",
        },
        {
            "storage": "local",
            "path": "/downloads/Test Show/Test.Show.S01E02.mkv",
            "name": "Test.Show.S01E02.mkv",
            "type": "file",
        },
    ]
    captured = {}

    class FakeTransferChain:
        def recommend_episode_format(self, **kwargs):
            captured.update(kwargs)
            return True, "", {"episode_format": "Show.S01E{ep}.mkv"}

    monkeypatch.setattr("app.api.endpoints.transfer.TransferChain", FakeTransferChain)

    resp = recommend_episode_format(
        recommend_item=EpisodeFormatRecommendItem(
            fileitems=selected_fileitems,
        ),
        _="token",
    )

    assert resp.success is True
    assert captured["fileitem"] is None
    assert [item.path for item in captured["fileitems"]] == [
        item["path"] for item in selected_fileitems
    ]


def test_manual_transfer_rejects_unsupported_source_before_execution():
    """直接手动整理请求不能接受已经移除集成模块的数据源。"""
    resp = manual_transfer(
        transer_item=ManualTransferItem(media_source="douban", media_id="200"),
        background=True,
        db=object(),
        _="token",
    )

    assert resp.success is False
    assert "仅支持 themoviedb 或 bangumi" in resp.message


def test_manual_transfer_from_history_keeps_legacy_douban_context(monkeypatch):
    """历史豆瓣记录重新整理时仍应传递兼容身份，由识别链安全回退。"""
    history = SimpleNamespace(
        status=0,
        mode="copy",
        src_fileitem={"storage": "local", "path": "/downloads/test.mkv", "name": "test.mkv", "type": "file"},
        dest_fileitem=None,
        downloader=None,
        download_hash=None,
        type="电影",
        tmdbid=None,
        doubanid="200",
        bangumiid=None,
        media_source="douban",
        media_id="200",
        seasons=None,
        episodes=None,
        episode_group=None,
    )
    captured = {}

    def fake_get(_db, logid):
        assert logid == 1
        return history

    class FakeTransferChain:
        def manual_transfer(self, **kwargs):
            captured.update(kwargs)
            return True, ""

    monkeypatch.setattr("app.api.endpoints.transfer.TransferHistory.get", fake_get)
    monkeypatch.setattr("app.api.endpoints.transfer.TransferChain", FakeTransferChain)

    resp = manual_transfer(
        transer_item=ManualTransferItem(logid=1, from_history=True),
        background=True,
        db=object(),
        _="token",
    )

    assert resp.success is True
    assert captured["media_source"] == "douban"
    assert captured["media_id"] == "200"
    assert captured["doubanid"] == "200"


def test_manual_transfer_from_multi_season_history_does_not_crash_or_force_single_season(monkeypatch):
    """多季包历史不是单个季号，重新整理时不得 500 或误强制为开始季。"""
    history = SimpleNamespace(
        status=0,
        mode="copy",
        src_fileitem={"storage": "local", "path": "/downloads/show", "name": "show", "type": "dir"},
        dest_fileitem=None,
        downloader=None,
        download_hash=None,
        type="电视剧",
        tmdbid="100",
        doubanid=None,
        bangumiid=None,
        media_source="themoviedb",
        media_id="100",
        seasons="S01-S02",
        episodes=None,
        episode_group=None,
    )
    captured = {}

    def fake_get(_db, logid):
        assert logid == 1
        return history

    class FakeTransferChain:
        def manual_transfer(self, **kwargs):
            captured.update(kwargs)
            return True, ""

    monkeypatch.setattr("app.api.endpoints.transfer.TransferHistory.get", fake_get)
    monkeypatch.setattr("app.api.endpoints.transfer.TransferChain", FakeTransferChain)

    resp = manual_transfer(
        transer_item=ManualTransferItem(logid=1, from_history=True),
        background=True,
        db=object(),
        _="token",
    )

    assert resp.success is True
    assert captured["season"] is None


def test_redo_transfer_history_unrecognized_media_returns_failure(monkeypatch, tmp_path):
    """自动重新整理识别失败时返回失败消息，不访问空媒体类型。"""
    source = tmp_path / "missing-media"
    source.mkdir()
    history = SimpleNamespace(
        src=str(source),
        episode_group=None,
    )

    monkeypatch.setattr(
        "app.chain.transfer.TransferHistoryOper.get",
        lambda _oper, _logid: history,
    )
    monkeypatch.setattr(
        "app.chain.transfer.MediaChain.recognize_by_path",
        lambda *_args, **_kwargs: None,
    )

    success, message = TransferChain().redo_transfer_history(1)

    assert success is False
    assert "未识别到媒体信息" in message
