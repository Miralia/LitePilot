from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app import schemas
from app.chain.media import MediaChain, ScrapingConfig, ScrapingOption
from app.core.context import MediaInfo
from app.core.event import Event
from app.core.metainfo import MetaInfo
from app.schemas.types import EventType, MediaType, ScrapingTarget, ScrapingMetadata, ScrapingPolicy


def reset_media_chain_singleton():
    """清理 MediaChain 单例，避免测试间复用被 mock 的实例。"""
    MediaChain._instances.pop((MediaChain, (), frozenset()), None)


@pytest.fixture
def media_chain():
    """提供独立的媒体链实例，并在测试后清理单例缓存。"""
    reset_media_chain_singleton()
    chain = MediaChain()
    chain.storagechain = MagicMock()
    yield chain
    reset_media_chain_singleton()


@pytest.fixture
def nfo_context(media_chain):
    """提供 NFO 刮削测试共用的媒体链与输入对象。"""
    media_chain.metadata_nfo = MagicMock(return_value="<nfo></nfo>")
    media_chain._save_file = MagicMock()
    media_chain.scraping_policies = MagicMock()
    return SimpleNamespace(
        media_chain=media_chain,
        fileitem=schemas.FileItem(
            path="/movies/Avatar (2009)",
            name="Avatar (2009)",
            type="dir",
            storage="local",
        ),
        meta=MetaInfo("Avatar (2009)"),
        mediainfo=MediaInfo(),
    )


@pytest.fixture
def image_chain(media_chain):
    """提供图片刮削测试共用的媒体链 mock 状态。"""
    media_chain.metadata_img = MagicMock()
    media_chain._download_and_save_image = MagicMock()
    media_chain.scraping_policies = MagicMock()
    return media_chain


@pytest.fixture
def tv_directory_chain(media_chain):
    """提供剧集目录初始化测试共用的媒体链 mock 状态。"""
    media_chain._scrape_nfo_generic = MagicMock()
    media_chain._scrape_images_generic = MagicMock()
    return media_chain


def test_movie_file_nfo_path(media_chain):
    fileitem = schemas.FileItem(path="/movies/avatar.mkv", name="avatar.mkv", type="file", storage="local")
    parent_item = schemas.FileItem(path="/movies", name="movies", type="dir", storage="local")
    media_chain.storagechain.get_parent_item.return_value = parent_item

    target_item, target_path = media_chain._get_target_fileitem_and_path(
        current_fileitem=fileitem,
        item_type=ScrapingTarget.MOVIE,
        metadata_type=ScrapingMetadata.NFO
    )
    assert target_item == parent_item
    assert target_path == Path("/movies/avatar.nfo")


def test_scraping_config_does_not_share_policy_state_between_instances():
    """刮削配置实例之间不应共享已删除或覆盖过的策略。"""
    first_config = ScrapingConfig({"movie_nfo": ScrapingPolicy.SKIP})
    second_config = ScrapingConfig({})

    assert ScrapingPolicy.SKIP == first_config.option(
        ScrapingTarget.MOVIE, ScrapingMetadata.NFO
    ).policy
    assert ScrapingPolicy.MISSINGONLY == second_config.option(
        ScrapingTarget.MOVIE, ScrapingMetadata.NFO
    ).policy


def test_movie_dir_nfo_path(media_chain):
    fileitem = schemas.FileItem(path="/movies/Avatar (2009)", name="Avatar (2009)", type="dir", storage="local")

    target_item, target_path = media_chain._get_target_fileitem_and_path(
        current_fileitem=fileitem,
        item_type=ScrapingTarget.MOVIE,
        metadata_type=ScrapingMetadata.NFO
    )
    assert target_item == fileitem
    assert target_path == Path("/movies/Avatar (2009)/Avatar (2009).nfo")


def test_tv_dir_nfo_path(media_chain):
    fileitem = schemas.FileItem(path="/tv/Show", name="Show", type="dir", storage="local")
    target_item, target_path = media_chain._get_target_fileitem_and_path(
        current_fileitem=fileitem,
        item_type=ScrapingTarget.TV,
        metadata_type=ScrapingMetadata.NFO
    )
    assert target_item == fileitem
    assert target_path == Path("/tv/Show/tvshow.nfo")


def test_season_dir_nfo_path(media_chain):
    fileitem = schemas.FileItem(path="/tv/Show/Season 1", name="Season 1", type="dir", storage="local")
    target_item, target_path = media_chain._get_target_fileitem_and_path(
        current_fileitem=fileitem,
        item_type=ScrapingTarget.SEASON,
        metadata_type=ScrapingMetadata.NFO
    )
    assert target_item == fileitem
    assert target_path == Path("/tv/Show/Season 1/season.nfo")


def test_season_dir_poster_path(media_chain):
    fileitem = schemas.FileItem(path="/tv/Show/Season 1", name="Season 1", type="dir", storage="local")
    target_item, target_path = media_chain._get_target_fileitem_and_path(
        current_fileitem=fileitem,
        item_type=ScrapingTarget.SEASON,
        metadata_type=ScrapingMetadata.POSTER,
        filename_hint="season01-poster.jpg"
    )
    assert target_item == fileitem
    assert target_path == Path("/tv/Show/Season 1/poster.jpg")


def test_season_dir_poster_paths_include_root_and_season_dir(media_chain):
    """季海报应同时写剧集根目录和季目录，兼容不同媒体库。"""
    parent_item = schemas.FileItem(path="/tv/Show", name="Show", type="dir", storage="local")
    fileitem = schemas.FileItem(path="/tv/Show/Season 1", name="Season 1", type="dir", storage="local")
    targets = media_chain._get_target_fileitems_and_paths(
        current_fileitem=fileitem,
        item_type=ScrapingTarget.SEASON,
        metadata_type=ScrapingMetadata.POSTER,
        filename_hint="season01-poster.jpg",
        parent_fileitem=parent_item,
    )
    assert targets == [
            (parent_item, Path("/tv/Show/season01-poster.jpg")),
            (fileitem, Path("/tv/Show/Season 1/poster.jpg")),
        ]


def test_season_dir_specials_poster_path(media_chain):
    fileitem = schemas.FileItem(path="/tv/Show/Specials", name="Specials", type="dir", storage="local")
    target_item, target_path = media_chain._get_target_fileitem_and_path(
        current_fileitem=fileitem,
        item_type=ScrapingTarget.SEASON,
        metadata_type=ScrapingMetadata.POSTER,
        filename_hint="season-specials-poster.jpg"
    )
    assert target_item == fileitem
    assert target_path == Path("/tv/Show/Specials/poster.jpg")


def test_movie_file_image_path_uses_parent_dir(media_chain):
    """直接刮削电影文件时，图片应保存到父目录。"""
    fileitem = schemas.FileItem(path="/movies/Avatar/Avatar.mkv", name="Avatar.mkv", type="file", storage="local")
    parent_item = schemas.FileItem(path="/movies/Avatar", name="Avatar", type="dir", storage="local")
    target_item, target_path = media_chain._get_target_fileitem_and_path(
        current_fileitem=fileitem,
        item_type=ScrapingTarget.MOVIE,
        metadata_type=ScrapingMetadata.POSTER,
        filename_hint="poster.jpg",
        parent_fileitem=parent_item,
    )
    assert target_item == parent_item
    assert target_path == Path("/movies/Avatar/poster.jpg")


def test_episode_file_nfo_path(media_chain):
    fileitem = schemas.FileItem(path="/tv/Show/Season 1/S01E01.mp4", name="S01E01.mp4", type="file", storage="local")
    parent_item = schemas.FileItem(path="/tv/Show/Season 1", name="Season 1", type="dir", storage="local")
    media_chain.storagechain.get_parent_item.return_value = parent_item
    target_item, target_path = media_chain._get_target_fileitem_and_path(
        current_fileitem=fileitem,
        item_type=ScrapingTarget.EPISODE,
        metadata_type=ScrapingMetadata.NFO
    )
    assert target_item == parent_item
    assert target_path == Path("/tv/Show/Season 1/S01E01.nfo")


def test_scrape_nfo_off(nfo_context):
    nfo_context.media_chain.scraping_policies.option.return_value = ScrapingOption(
        "movie", "nfo", ScrapingPolicy.SKIP
    )
    nfo_context.media_chain._scrape_nfo_generic(
        nfo_context.fileitem,
        nfo_context.meta,
        nfo_context.mediainfo,
        ScrapingTarget.MOVIE,
    )
    nfo_context.media_chain.metadata_nfo.assert_not_called()
    nfo_context.media_chain._save_file.assert_not_called()


def test_scrape_nfo_on_exists_skip(nfo_context):
    nfo_context.media_chain.scraping_policies.option.return_value = ScrapingOption(
        "movie", "nfo", ScrapingPolicy.MISSINGONLY
    )
    # mock file exists
    nfo_context.media_chain.storagechain.get_file_item.return_value = schemas.FileItem(
        path="/movies/Avatar (2009)/Avatar (2009).nfo",
        name="Avatar (2009).nfo",
        type="file",
        storage="local",
    )

    nfo_context.media_chain._scrape_nfo_generic(
        nfo_context.fileitem,
        nfo_context.meta,
        nfo_context.mediainfo,
        ScrapingTarget.MOVIE,
    )
    nfo_context.media_chain.metadata_nfo.assert_not_called()
    nfo_context.media_chain._save_file.assert_not_called()


def test_scrape_nfo_on_not_exists_scrape(nfo_context):
    nfo_context.media_chain.scraping_policies.option.return_value = ScrapingOption(
        "movie", "nfo", ScrapingPolicy.MISSINGONLY
    )
    # mock file not exists
    nfo_context.media_chain.storagechain.get_file_item.return_value = None

    nfo_context.media_chain._scrape_nfo_generic(
        nfo_context.fileitem,
        nfo_context.meta,
        nfo_context.mediainfo,
        ScrapingTarget.MOVIE,
    )
    nfo_context.media_chain.metadata_nfo.assert_called_once()
    nfo_context.media_chain._save_file.assert_called_once()


def test_scrape_nfo_overwrite_exists_scrape(nfo_context):
    nfo_context.media_chain.scraping_policies.option.return_value = ScrapingOption(
        "movie", "nfo", ScrapingPolicy.OVERWRITE
    )
    # mock file exists
    nfo_context.media_chain.storagechain.get_file_item.return_value = schemas.FileItem(
        path="/movies/Avatar (2009)/Avatar (2009).nfo",
        name="Avatar (2009).nfo",
        type="file",
        storage="local",
    )

    nfo_context.media_chain._scrape_nfo_generic(
        nfo_context.fileitem,
        nfo_context.meta,
        nfo_context.mediainfo,
        ScrapingTarget.MOVIE,
    )
    nfo_context.media_chain.metadata_nfo.assert_called_once()
    nfo_context.media_chain._save_file.assert_called_once()


def test_scrape_images_mapping(image_chain):
    fileitem = schemas.FileItem(path="/movies/Avatar", name="Avatar", type="dir", storage="local")
    mediainfo = MediaInfo()
    image_chain.metadata_img.return_value = {
        "poster.jpg": "http://poster",
        "fanart.jpg": "http://fanart",
        "logo.png": "http://logo"
    }
    image_chain.scraping_policies.option.return_value = ScrapingOption("movie", "poster", ScrapingPolicy.OVERWRITE)
    image_chain.storagechain.get_file_item.return_value = None

    image_chain._scrape_images_generic(fileitem, mediainfo, ScrapingTarget.MOVIE)

    # Check download called for mapped metadata + aliases (fanart→backdrop)
    calls = image_chain._download_and_save_image.call_args_list
    urls = [call.kwargs["url"] for call in calls]
    paths = [call.kwargs["path"] for call in calls]
    assert "http://poster" in urls
    assert "http://fanart" in urls
    assert "http://logo" in urls
    # fanart.jpg should also generate backdrop.jpg alias
    assert Path("/movies/Avatar/fanart.jpg") in paths
    assert Path("/movies/Avatar/backdrop.jpg") in paths


def test_scrape_images_season_filter(image_chain):
    fileitem = schemas.FileItem(path="/tv/Show/Season 1", name="Season 1", type="dir", storage="local")
    mediainfo = MediaInfo()
    image_chain.metadata_img.return_value = {
        "season01-poster.jpg": "http://season01",
        "season02-poster.jpg": "http://season02"
    }
    image_chain.scraping_policies.option.return_value = ScrapingOption("season", "poster", ScrapingPolicy.OVERWRITE)
    image_chain.storagechain.get_file_item.return_value = None

    image_chain._scrape_images_generic(fileitem, mediainfo, ScrapingTarget.SEASON, season_number=1)

    calls = image_chain._download_and_save_image.call_args_list
    assert len(calls) == 2
    assert all(call.kwargs["url"] == "http://season01" for call in calls)
    assert [call.kwargs["path"] for call in calls] == [
            Path("/tv/Show/season01-poster.jpg"),
            Path("/tv/Show/Season 1/poster.jpg"),
        ]


def test_scrape_movie_file_images_when_initialized_directly(image_chain):
    """直接初始化刮削电影文件时，应生成同级 poster/backdrop 及别名。"""
    fileitem = schemas.FileItem(path="/movies/Avatar/Avatar.mkv", name="Avatar.mkv", type="file", storage="local")
    parent_item = schemas.FileItem(path="/movies/Avatar", name="Avatar", type="dir", storage="local")
    mediainfo = MediaInfo()
    image_chain.metadata_img.return_value = {
        "poster.jpg": "http://poster",
        "backdrop.jpg": "http://backdrop",
    }
    image_chain.scraping_policies.option.return_value = ScrapingOption("movie", "poster", ScrapingPolicy.OVERWRITE)
    image_chain.storagechain.get_file_item.return_value = None

    image_chain._scrape_images_generic(
        fileitem,
        mediainfo,
        ScrapingTarget.MOVIE,
        parent_fileitem=parent_item,
    )

    paths = [call.kwargs["path"] for call in image_chain._download_and_save_image.call_args_list]
    # poster has no alias, backdrop generates fanart alias
    assert Path("/movies/Avatar/poster.jpg") in paths
    assert Path("/movies/Avatar/backdrop.jpg") in paths
    assert Path("/movies/Avatar/fanart.jpg") in paths


def test_scrape_episode_thumb_image_path(image_chain):
    fileitem = schemas.FileItem(path="/tv/Show/Season 1/S01E01.mp4", name="S01E01.mp4", type="file", storage="local")
    parent_item = schemas.FileItem(path="/tv/Show/Season 1", name="Season 1", type="dir", storage="local")
    mediainfo = MediaInfo()
    image_chain.metadata_img.return_value = {
        "thumb.jpg": "http://episode-thumb"
    }
    image_chain.scraping_policies.option.return_value = ScrapingOption("episode", "thumb", ScrapingPolicy.OVERWRITE)
    image_chain.storagechain.get_file_item.return_value = None

    image_chain._scrape_images_generic(
        fileitem,
        mediainfo,
        ScrapingTarget.EPISODE,
        parent_fileitem=parent_item,
        season_number=1,
        episode_number=1
    )

    image_chain.metadata_img.assert_called_once_with(
        mediainfo=mediainfo,
        season=1,
        episode=1
    )
    image_chain._download_and_save_image.assert_called_once_with(
        fileitem=parent_item,
        path=Path("/tv/Show/Season 1/S01E01.jpg"),
        url="http://episode-thumb"
    )


def test_scrape_episode_thumb_image_path_via_parent_lookup(image_chain):
    fileitem = schemas.FileItem(path="/tv/Show/Season 1/S01E01.mp4", name="S01E01.mp4", type="file", storage="local")
    parent_item = schemas.FileItem(path="/tv/Show/Season 1", name="Season 1", type="dir", storage="local")
    mediainfo = MediaInfo()
    image_chain.metadata_img.return_value = {
        "thumb.jpg": "http://episode-thumb"
    }
    image_chain.scraping_policies.option.return_value = ScrapingOption("episode", "thumb", ScrapingPolicy.OVERWRITE)
    image_chain.storagechain.get_parent_item.return_value = parent_item
    image_chain.storagechain.get_file_item.return_value = None

    image_chain._scrape_images_generic(
        fileitem,
        mediainfo,
        ScrapingTarget.EPISODE,
        season_number=1,
        episode_number=1
    )

    image_chain.storagechain.get_parent_item.assert_called_once_with(fileitem)
    image_chain._download_and_save_image.assert_called_once_with(
        fileitem=parent_item,
        path=Path("/tv/Show/Season 1/S01E01.jpg"),
        url="http://episode-thumb"
    )


def test_expand_with_aliases_backdrop(image_chain):
    """backdrop should also generate fanart alias."""
    parent_item = schemas.FileItem(path="/movies/Avatar", name="Avatar", type="dir", storage="local")
    targets = [(parent_item, Path("/movies/Avatar/backdrop.jpg"))]
    image_chain.scraping_policies.option.return_value = ScrapingOption("movie", "backdrop", ScrapingPolicy.OVERWRITE)

    expanded = image_chain._expand_with_aliases(targets, ScrapingTarget.MOVIE)
    paths = [t[1] for t in expanded]
    assert Path("/movies/Avatar/backdrop.jpg") in paths
    assert Path("/movies/Avatar/fanart.jpg") in paths


def test_expand_with_aliases_thumb(image_chain):
    """thumb should also generate landscape alias."""
    parent_item = schemas.FileItem(path="/tv/Show", name="Show", type="dir", storage="local")
    targets = [(parent_item, Path("/tv/Show/thumb.jpg"))]
    image_chain.scraping_policies.option.return_value = ScrapingOption("tv", "thumb", ScrapingPolicy.OVERWRITE)

    expanded = image_chain._expand_with_aliases(targets, ScrapingTarget.TV)
    paths = [t[1] for t in expanded]
    assert Path("/tv/Show/thumb.jpg") in paths
    assert Path("/tv/Show/landscape.jpg") in paths


def test_expand_with_aliases_skips_season_prefix(image_chain):
    """season-prefixed files should not get aliases."""
    parent_item = schemas.FileItem(path="/tv/Show", name="Show", type="dir", storage="local")
    targets = [(parent_item, Path("/tv/Show/season01-thumb.jpg"))]
    image_chain.scraping_policies.option.return_value = ScrapingOption("season", "thumb", ScrapingPolicy.OVERWRITE)

    expanded = image_chain._expand_with_aliases(targets, ScrapingTarget.SEASON)
    assert len(expanded) == 1


def test_expand_with_aliases_respects_skip_policy(image_chain):
    """Alias should not be generated if its metadata type is set to SKIP."""
    parent_item = schemas.FileItem(path="/movies/Avatar", name="Avatar", type="dir", storage="local")
    targets = [(parent_item, Path("/movies/Avatar/backdrop.jpg"))]
    # backdrop is OVERWRITE but fanart (also BACKDROP type) is SKIP
    def option_side_effect(item_type, metadata_type):
        if metadata_type == ScrapingMetadata.BACKDROP:
            return ScrapingOption("movie", "backdrop", ScrapingPolicy.SKIP)
        return ScrapingOption("movie", "backdrop", ScrapingPolicy.OVERWRITE)
    image_chain.scraping_policies.option.side_effect = option_side_effect

    expanded = image_chain._expand_with_aliases(targets, ScrapingTarget.MOVIE)
    # fanart maps to BACKDROP which is SKIP, so no alias
    assert len(expanded) == 1


def test_season_backdrop_path(image_chain):
    """Season backdrop should be saved in season directory."""
    fileitem = schemas.FileItem(path="/tv/Show/Season 1", name="Season 1", type="dir", storage="local")
    target_item, target_path = image_chain._get_target_fileitem_and_path(
        current_fileitem=fileitem,
        item_type=ScrapingTarget.SEASON,
        metadata_type=ScrapingMetadata.BACKDROP,
        filename_hint="season01-backdrop.jpg"
    )
    assert target_item == fileitem
    assert target_path == Path("/tv/Show/Season 1/backdrop.jpg")


@patch("app.chain.media.RequestUtils")
@patch("app.chain.media.NamedTemporaryFile")
@patch("app.chain.media.Path.chmod")
@patch("app.chain.media.settings")
def test_download_and_save_image(mock_settings, mock_chmod, mock_temp_file, mock_request_utils, media_chain):
    fileitem = schemas.FileItem(path="/movies/Avatar", name="Avatar", type="dir", storage="local")
    target_path = Path("/movies/Avatar/poster.jpg")
    url = "http://poster"

    # mock temp file
    tmp_mock = MagicMock()
    tmp_mock.name = "/tmp/mockfile"
    mock_temp_file.return_value.__enter__.return_value = tmp_mock

    # mock stream
    mock_stream = MagicMock()
    mock_stream.status_code = 200
    mock_stream.iter_content.return_value = [b"data1", b"data2"]

    mock_instance = mock_request_utils.return_value
    mock_instance.get_stream.return_value.__enter__.return_value = mock_stream

    media_chain.storagechain.upload_file.return_value = fileitem

    media_chain._download_and_save_image(fileitem, target_path, url)

    mock_request_utils.assert_called_with(proxies=mock_settings.PROXY, ua=mock_settings.NORMAL_USER_AGENT)
    mock_instance.get_stream.assert_called_with(url=url)
    mock_temp_file.assert_called_once_with(delete=False, suffix=".jpg")
    tmp_mock.write.assert_any_call(b"data1")
    tmp_mock.write.assert_any_call(b"data2")
    mock_chmod.assert_called()
    media_chain.storagechain.upload_file.assert_called_once()
    call_args = media_chain.storagechain.upload_file.call_args.kwargs
    assert call_args["fileitem"] == fileitem
    assert call_args["new_name"] == "poster.jpg"


@patch("app.chain.media.NamedTemporaryFile")
@patch("app.chain.media.Path.chmod")
def test_save_file_uses_python310_compatible_tempfile(mock_chmod, mock_temp_file, media_chain):
    """保存刮削文件时不应使用 Python 3.12 才支持的 delete_on_close 参数。"""
    media_chain._cleanup_temp_file = MagicMock()

    fileitem = schemas.FileItem(path="/movies/Avatar", name="Avatar", type="dir", storage="local")
    target_path = Path("/movies/Avatar/movie.nfo")

    tmp_mock = MagicMock()
    tmp_mock.name = "/tmp/mockfile"
    mock_temp_file.return_value.__enter__.return_value = tmp_mock
    media_chain.storagechain.upload_file.return_value = fileitem

    media_chain._save_file(fileitem, target_path, "<nfo></nfo>")

    mock_temp_file.assert_called_once_with(delete=False, suffix=".nfo")
    tmp_mock.write.assert_called_once_with(b"<nfo></nfo>")
    mock_chmod.assert_called()
    media_chain.storagechain.upload_file.assert_called_once()
    media_chain._cleanup_temp_file.assert_called_once_with(Path("/tmp/mockfile"))


@patch("app.chain.media.settings")
def test_initialize_tv_directory_specials(mock_settings, tv_directory_chain):
    # mock specials directory recognition
    mock_settings.RENAME_FORMAT_S0_NAMES = ["Specials", "SPs"]

    fileitem = schemas.FileItem(path="/tv/Show/Specials", name="Specials", type="dir", storage="local")
    meta = MetaInfo("Show")
    mediainfo = MediaInfo(type=MediaType.TV)
    filepath = Path(fileitem.path)

    tv_directory_chain._initialize_tv_directory_metadata(
        fileitem=fileitem,
        filepath=filepath,
        meta=meta,
        mediainfo=mediainfo,
        parent=None,
        overwrite=False,
    )

    tv_directory_chain._scrape_nfo_generic.assert_called_once_with(
        current_fileitem=fileitem,
        meta=meta,
        mediainfo=mediainfo,
        item_type=ScrapingTarget.SEASON,
        overwrite=False,
        season_number=0
    )
    tv_directory_chain._scrape_images_generic.assert_called_once_with(
        current_fileitem=fileitem,
        mediainfo=mediainfo,
        item_type=ScrapingTarget.SEASON,
        parent_fileitem=None,
        overwrite=False,
        season_number=0
    )


@patch("app.chain.media.settings")
def test_initialize_tv_directory_season(mock_settings, tv_directory_chain):
    mock_settings.RENAME_FORMAT_S0_NAMES = ["Specials", "SPs"]

    fileitem = schemas.FileItem(path="/tv/Show/Season 1", name="Season 1", type="dir", storage="local")
    meta = MetaInfo("Show")
    mediainfo = MediaInfo(type=MediaType.TV)
    filepath = Path(fileitem.path)

    tv_directory_chain._initialize_tv_directory_metadata(
        fileitem=fileitem,
        filepath=filepath,
        meta=meta,
        mediainfo=mediainfo,
        parent=None,
        overwrite=False,
    )

    tv_directory_chain._scrape_nfo_generic.assert_called_once_with(
        current_fileitem=fileitem,
        meta=meta,
        mediainfo=mediainfo,
        item_type=ScrapingTarget.SEASON,
        overwrite=False,
        season_number=1
    )


@patch("app.chain.media.MediaChain.scrape_metadata")
def test_scrape_metadata_event_file(mock_scrape_metadata, media_chain):
    fileitem = schemas.FileItem(path="/movies/movie.mkv", name="movie.mkv", type="file", storage="local")
    parent_item = schemas.FileItem(path="/movies", name="movies", type="dir", storage="local")

    media_chain.storagechain.get_item.return_value = fileitem
    media_chain.storagechain.get_parent_item.return_value = parent_item

    mediainfo = MediaInfo()
    event = Event(
        event_type=EventType.MetadataScrape,
        event_data={
            "fileitem": fileitem,
            "mediainfo": mediainfo,
            "overwrite": True
        }
    )

    media_chain.scrape_metadata_event(event)

    mock_scrape_metadata.assert_called_once_with(
        fileitem=fileitem,
        mediainfo=mediainfo,
        init_folder=True,
        parent=parent_item,
        overwrite=True
    )


@patch("app.chain.media.MediaChain.scrape_metadata")
def test_scrape_metadata_event_dir_bluray(mock_scrape_metadata, media_chain):
    fileitem = schemas.FileItem(path="/movies/bluray_movie", name="bluray_movie", type="dir", storage="local")

    media_chain.storagechain.get_item.return_value = fileitem
    media_chain.storagechain.is_bluray_folder.return_value = True

    mediainfo = MediaInfo()
    event = Event(
        event_type=EventType.MetadataScrape,
        event_data={
            "fileitem": fileitem,
            "file_list": ["/movies/bluray_movie/BDMV/index.bdmv"],
            "mediainfo": mediainfo,
            "overwrite": False
        }
    )

    media_chain.scrape_metadata_event(event)

    # BDMV 目录不再特判：与普通目录一致，先按目录初始化再逐个文件处理，
    # 文件层的 BDMV 跳过由 scrape_metadata 内部判断。
    calls = mock_scrape_metadata.call_args_list
    assert len(calls) >= 1
    assert calls[0].kwargs["init_folder"]
    assert calls[0].kwargs["mediainfo"] == mediainfo


@patch("app.chain.media.MediaChain.scrape_metadata")
def test_scrape_metadata_event_dir_with_filelist(mock_scrape_metadata, media_chain):
    fileitem = schemas.FileItem(path="/tv/show", name="show", type="dir", storage="local")

    media_chain.storagechain.get_item.return_value = fileitem
    media_chain.storagechain.is_bluray_folder.return_value = False

    def side_effect_get_file_item(storage, path):
        path_str = str(path)
        return schemas.FileItem(path=path_str, name=Path(path_str).name, type="dir" if "." not in path_str else "file", storage="local")

    media_chain.storagechain.get_file_item.side_effect = side_effect_get_file_item

    mediainfo = MediaInfo()
    event = Event(
        event_type=EventType.MetadataScrape,
        event_data={
            "fileitem": fileitem,
            "file_list": ["/tv/show/Season 1/S01E01.mp4"],
            "mediainfo": mediainfo,
            "overwrite": True
        }
    )

    media_chain.scrape_metadata_event(event)

    calls = mock_scrape_metadata.call_args_list
    assert len(calls) == 3

    paths = [call.kwargs['fileitem'].path for call in calls]
    assert "/tv/show" in paths
    assert "/tv/show/Season 1" in paths
    assert "/tv/show/Season 1/S01E01.mp4" in paths


@patch("app.chain.media.MediaChain.scrape_metadata")
def test_scrape_metadata_event_dir_full(mock_scrape_metadata, media_chain):
    fileitem = schemas.FileItem(path="/movies/movie", name="movie", type="dir", storage="local")

    media_chain.storagechain.get_item.return_value = fileitem

    mediainfo = MediaInfo()
    meta = MetaInfo("movie")
    event = Event(
        event_type=EventType.MetadataScrape,
        event_data={
            "fileitem": fileitem,
            "meta": meta,
            "mediainfo": mediainfo,
            "overwrite": True
        }
    )

    media_chain.scrape_metadata_event(event)

    mock_scrape_metadata.assert_called_once_with(
        fileitem=fileitem,
        meta=meta,
        mediainfo=mediainfo,
        init_folder=True,
        overwrite=True
    )


@patch("app.chain.media.MediaChain._handle_movie_scraping")
@patch("app.chain.media.MediaChain.recognize_by_meta")
def test_scrape_metadata_movie(mock_recognize, mock_handle_movie, media_chain):
    fileitem = schemas.FileItem(path="/movies/movie.mkv", name="movie.mkv", type="file", storage="local")
    meta = MetaInfo("Movie")
    mediainfo = MediaInfo(type=MediaType.MOVIE)

    media_chain.scrape_metadata(
        fileitem=fileitem,
        meta=meta,
        mediainfo=mediainfo,
        init_folder=True,
        overwrite=False,
        recursive=True
    )

    mock_recognize.assert_not_called()
    mock_handle_movie.assert_called_once_with(
        fileitem=fileitem,
        meta=meta,
        mediainfo=mediainfo,
        init_folder=True,
        parent=None,
        overwrite=False,
        recursive=True
    )


@patch("app.chain.media.MediaChain._handle_tv_scraping")
@patch("app.chain.media.MediaChain.recognize_by_meta")
def test_scrape_metadata_tv(mock_recognize, mock_handle_tv, media_chain):
    fileitem = schemas.FileItem(path="/tv/show", name="show", type="dir", storage="local")
    meta = MetaInfo("Show")
    mediainfo = MediaInfo(type=MediaType.TV)
    media_chain.storagechain.is_bluray_folder.return_value = False

    media_chain.scrape_metadata(
        fileitem=fileitem,
        meta=meta,
        mediainfo=mediainfo,
        init_folder=True,
        overwrite=False,
        recursive=True
    )

    mock_handle_tv.assert_called_once_with(
        fileitem=fileitem,
        meta=meta,
        mediainfo=mediainfo,
        init_folder=True,
        parent=None,
        overwrite=False,
        recursive=True
    )


@patch("app.chain.media.MediaChain._handle_movie_scraping")
@patch("app.chain.media.MediaChain.recognize_by_meta")
def test_scrape_metadata_recognize_fallback(mock_recognize, mock_handle_movie, media_chain):
    fileitem = schemas.FileItem(path="/movies/movie.mkv", name="movie.mkv", type="file", storage="local")
    mediainfo = MediaInfo(type=MediaType.MOVIE)
    mock_recognize.return_value = mediainfo

    media_chain.scrape_metadata(
        fileitem=fileitem,
        init_folder=True,
        overwrite=False,
        recursive=True
    )

    mock_recognize.assert_called_once()
    mock_handle_movie.assert_called_once()
    args, kwargs = mock_handle_movie.call_args
    assert kwargs['mediainfo'] == mediainfo
    assert kwargs['meta'].name == "Movie"


@patch("app.chain.media.MediaChain._handle_movie_scraping")
@patch("app.chain.media.MediaChain._handle_tv_scraping")
def test_scrape_metadata_invalid_extension(mock_handle_tv, mock_handle_movie, media_chain):
    fileitem = schemas.FileItem(path="/movies/movie.txt", name="movie.txt", type="file", storage="local")

    media_chain.scrape_metadata(
        fileitem=fileitem
    )

    mock_handle_movie.assert_not_called()
    mock_handle_tv.assert_not_called()


@patch("app.chain.media.MediaChain.scrape_metadata")
def test_scrape_metadata_event_dir_with_multiple_files(mock_scrape_metadata, media_chain):
    fileitem = schemas.FileItem(path="/movies/collection", name="collection", type="dir", storage="local")

    media_chain.storagechain.get_item.return_value = fileitem
    media_chain.storagechain.is_bluray_folder.return_value = False

    def side_effect_get_file_item(storage, path):
        path_str = str(path)
        return schemas.FileItem(path=path_str, name=Path(path_str).name, type="dir" if "." not in path_str else "file", storage="local")

    media_chain.storagechain.get_file_item.side_effect = side_effect_get_file_item

    mediainfo = MediaInfo()
    event = Event(
        event_type=EventType.MetadataScrape,
        event_data={
            "fileitem": fileitem,
            "file_list": [
                "/movies/collection/movie1.mp4",
                "/movies/collection/movie2.mkv",
                "/movies/collection/movie3.avi"
            ],
            "mediainfo": mediainfo,
            "overwrite": True
        }
    )

    media_chain.scrape_metadata_event(event)

    calls = mock_scrape_metadata.call_args_list
    # Should scrape directory and then each file item
    assert len(calls) == 4

    paths = [call.kwargs['fileitem'].path for call in calls]
    assert "/movies/collection" in paths
    assert "/movies/collection/movie1.mp4" in paths
    assert "/movies/collection/movie2.mkv" in paths
    assert "/movies/collection/movie3.avi" in paths


@patch("app.chain.media.MediaChain.scrape_metadata")
def test_scrape_metadata_event_dir_with_tv_multi_seasons_episodes(mock_scrape_metadata, media_chain):
    fileitem = schemas.FileItem(path="/tv/MultiSeasonShow", name="MultiSeasonShow", type="dir", storage="local")

    media_chain.storagechain.get_item.return_value = fileitem
    media_chain.storagechain.is_bluray_folder.return_value = False

    def side_effect_get_file_item(storage, path):
        path_str = str(path)
        return schemas.FileItem(path=path_str, name=Path(path_str).name, type="dir" if "." not in path_str else "file", storage="local")

    media_chain.storagechain.get_file_item.side_effect = side_effect_get_file_item

    mediainfo = MediaInfo()
    event = Event(
        event_type=EventType.MetadataScrape,
        event_data={
            "fileitem": fileitem,
            "file_list": [
                "/tv/MultiSeasonShow/Season 1/S01E01.mp4",
                "/tv/MultiSeasonShow/Season 1/S01E02.mp4",
                "/tv/MultiSeasonShow/Season 2/S02E01.mkv",
                "/tv/MultiSeasonShow/Season 2/S02E02.mkv",
                "/tv/MultiSeasonShow/Specials/S00E01.mp4"
            ],
            "mediainfo": mediainfo,
            "overwrite": False
        }
    )

    media_chain.scrape_metadata_event(event)

    calls = mock_scrape_metadata.call_args_list
    # main dir + 3 season dirs + 5 episode files
    assert len(calls) == 9

    paths = [call.kwargs['fileitem'].path for call in calls]
    assert "/tv/MultiSeasonShow" in paths
    assert "/tv/MultiSeasonShow/Season 1" in paths
    assert "/tv/MultiSeasonShow/Season 2" in paths
    assert "/tv/MultiSeasonShow/Specials" in paths
    assert "/tv/MultiSeasonShow/Season 1/S01E01.mp4" in paths
    assert "/tv/MultiSeasonShow/Season 1/S01E02.mp4" in paths
    assert "/tv/MultiSeasonShow/Season 2/S02E01.mkv" in paths
    assert "/tv/MultiSeasonShow/Season 2/S02E02.mkv" in paths
    assert "/tv/MultiSeasonShow/Specials/S00E01.mp4" in paths


@patch("app.chain.media.MediaChain.recognize_by_meta")
def test_scrape_metadata_recognize_fail(mock_recognize, media_chain):
    fileitem = schemas.FileItem(path="/movies/movie.mkv", name="movie.mkv", type="file", storage="local")
    mock_recognize.return_value = None

    with patch('app.chain.media.logger.warning') as mock_logger:
        media_chain.scrape_metadata(
            fileitem=fileitem
        )
        mock_logger.assert_called_with(f"{Path(fileitem.path)} 无法识别文件媒体信息！")
