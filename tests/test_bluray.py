# -*- coding: utf-8 -*-
"""BDMV 原盘目录的整理与刮削行为。

覆盖两件事：原盘目录作为一个整体参与整理入库；原盘目录不参与刮削，
因为其内容为分片流文件，没有可用的媒体元数据。
"""
from pathlib import Path
from unittest.mock import patch

import pytest

from app import schemas
from app.chain.media import MediaChain
from app.chain.storage import StorageChain
from app.chain.transfer import TransferChain
from app.core.context import MediaInfo
from app.core.event import Event
from app.core.metainfo import MetaInfoPath
from app.db.models.transferhistory import TransferHistory
from app.schemas.types import EventType
from tests.cases.files import bluray_files


def _build_tree() -> dict[str, schemas.FileItem]:
    """按 fixtures 构造内存文件树，返回路径到文件项的映射。"""
    root = schemas.FileItem(path="/", name="", type="dir", extension="", size=0)
    all_items: dict[str, schemas.FileItem] = {root.path: root}

    def build(parent: schemas.FileItem, files: list) -> None:
        parent.children = []
        for name, children in files:
            sep = "" if parent.path.endswith("/") else "/"
            item = schemas.FileItem(
                path=f"{parent.path}{sep}{name}",
                name=name,
                extension=Path(name).suffix[1:],
                basename=Path(name).stem,
                type="file" if isinstance(children, int) else "dir",
                size=children if isinstance(children, int) else 0,
            )
            parent.children.append(item)
            all_items[item.path] = item
            if isinstance(children, list):
                build(item, children)

    build(root, bluray_files)
    return all_items


@pytest.fixture()
def bluray_env():
    """装配内存文件树与存储链打桩，返回 (全部文件项, 整理记录列表)。"""
    all_items = _build_tree()
    history: list[str] = []

    def get_file_item(storage, path):
        return all_items.get(path.as_posix())

    def get_parent_item(fileitem):
        return get_file_item(None, Path(fileitem.path).parent)

    def list_files(fileitem, recursion: bool = False):
        if fileitem.type != "dir":
            return None
        if recursion:
            prefix = f"{fileitem.path}/"
            return [item for path, item in all_items.items() if path.startswith(prefix)]
        return fileitem.children

    def get_by_src(src, storage=None):
        history.append(src)
        record = TransferHistory()
        record.status = True
        return record

    with patch("app.chain.storage.StorageChain.get_file_item", side_effect=get_file_item), \
            patch("app.chain.storage.StorageChain.get_parent_item", side_effect=get_parent_item), \
            patch("app.chain.storage.StorageChain.list_files", side_effect=list_files), \
            patch("app.db.transferhistory_oper.TransferHistoryOper.get_by_src",
                  side_effect=get_by_src), \
            patch("app.chain.ChainBase.__init__", return_value=None):
        yield all_items, history


def _transfer(path: str) -> None:
    """对指定路径执行一次整理。"""
    TransferChain().do_transfer(
        force=False,
        background=False,
        fileitem=StorageChain().get_file_item(None, Path(path)),
    )


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        # 原盘目录内的任意层级都整理为原盘根目录，保证整盘作为一个单位入库
        (
            "/FOLDER/Digimon/Digimon BluRay (2055)",
            ["/FOLDER/Digimon/Digimon BluRay (2055)"],
        ),
        (
            "/FOLDER/Digimon/Digimon BluRay (2055)/BDMV",
            ["/FOLDER/Digimon/Digimon BluRay (2055)"],
        ),
        (
            "/FOLDER/Digimon/Digimon BluRay (2055)/BDMV/STREAM",
            ["/FOLDER/Digimon/Digimon BluRay (2055)"],
        ),
        (
            "/FOLDER/Digimon/Digimon BluRay (2055)/BDMV/STREAM/00001.m2ts",
            ["/FOLDER/Digimon/Digimon BluRay (2055)"],
        ),
        # 普通电影目录与文件按自身路径整理
        (
            "/FOLDER/Digimon/Digimon (2199)",
            ["/FOLDER/Digimon/Digimon (2199)/Digimon.2199.mp4"],
        ),
        (
            "/FOLDER/Digimon/Digimon (2199)/Digimon.2199.mp4",
            ["/FOLDER/Digimon/Digimon (2199)/Digimon.2199.mp4"],
        ),
        ("/FOLDER/Pokemon.2029.mp4", ["/FOLDER/Pokemon.2029.mp4"]),
    ],
)
def test_bluray_transfer_targets(bluray_env, path, expected):
    """原盘目录整体入库，普通目录与文件按自身路径入库。"""
    _, history = bluray_env

    _transfer(path)

    assert history == expected


def test_transfer_directory_covers_all_children(bluray_env):
    """整理父目录时，原盘与普通媒体都被覆盖且顺序稳定。"""
    _, history = bluray_env

    _transfer("/FOLDER/Digimon")
    assert history == [
        "/FOLDER/Digimon/Digimon BluRay (2055)",
        "/FOLDER/Digimon/Digimon BluRay (2099)",
        "/FOLDER/Digimon/Digimon (2199)/Digimon.2199.mp4",
    ]

    history.clear()
    _transfer("/")
    assert history == [
        "/FOLDER/Digimon/Digimon BluRay (2055)",
        "/FOLDER/Digimon/Digimon BluRay (2099)",
        "/FOLDER/Digimon/Digimon (2199)/Digimon.2199.mp4",
        "/FOLDER/Pokemon BluRay (2016)",
        "/FOLDER/Pokemon BluRay (2021)",
        "/FOLDER/Pokemon (2028)/Pokemon.2028.mkv",
        "/FOLDER/Pokemon.2029.mp4",
        "/FOLDER/Pokemon.2039.mp4",
        "/FOLDER/Pokemon (2031)/Pokemon (2031).mp4",
    ]


def _scrape(bluray_env, path: str) -> int:
    """刮削指定路径并返回生成 NFO 的次数（手动与事件两条入口各测一次）。"""
    all_items, _ = bluray_env
    fileitem = all_items[path]
    meta = MetaInfoPath(Path(fileitem.path))
    mediainfo = MediaInfo(tmdb_info={"id": 1, "title": "Test"})
    chain = MediaChain()

    counts = []
    with patch("app.chain.media.MediaChain.metadata_img", return_value=None), \
            patch("app.chain.media.MediaChain.metadata_nfo", return_value=None) as mock_nfo:
        # 手动刮削
        chain.scrape_metadata(
            fileitem=fileitem, meta=meta, mediainfo=mediainfo, overwrite=True
        )
        counts.append(mock_nfo.call_count)

        # 事件刮削：每次都用新的 mock，避免计数跨阶段累加
        with patch("app.chain.media.MediaChain.metadata_nfo",
                   return_value=None) as event_nfo:
            chain.scrape_metadata_event(
                Event(
                    event_type=EventType.MetadataScrape,
                    event_data={
                        "meta": meta,
                        "mediainfo": mediainfo,
                        "fileitem": fileitem,
                        "file_list": [fileitem.path],
                        "overwrite": False,
                    },
                )
            )
            counts.append(event_nfo.call_count)

    assert counts[0] == counts[1], f"手动与事件刮削次数不一致：{counts}"
    return counts[0]


def test_bluray_folder_is_not_scraped(bluray_env):
    """原盘目录不参与刮削。"""
    assert _scrape(bluray_env, "/FOLDER/Digimon/Digimon BluRay (2099)") == 0


def test_movie_file_is_scraped(bluray_env):
    """普通电影文件正常生成 NFO。"""
    assert _scrape(bluray_env, "/FOLDER/Digimon/Digimon (2199)/Digimon.2199.mp4") == 1


def test_directory_scrapes_direct_media_files_only(bluray_env):
    """目录刮削只处理直属媒体文件，不进入原盘子目录。"""
    assert _scrape(bluray_env, "/FOLDER") == 2