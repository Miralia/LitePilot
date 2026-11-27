import inspect
from types import SimpleNamespace
from typing import Optional

from app.core.context import MediaInfo
from app.modules.themoviedb.scraper import TmdbScraper
from app.schemas.types import MediaType


def _episode_zero_scraper():
    """构造只返回第 0 集数据的刮削器，不访问真实 TMDB。"""
    scraper = TmdbScraper()
    scraper._meta_tmdb = SimpleNamespace(
        get_tv_season_detail=lambda *_args, **_kwargs: {
            "name": "Season 1",
            "episodes": [
                {
                    "id": 1000,
                    "episode_number": 0,
                    "name": "Episode Zero",
                    "still_path": "/zero.jpg",
                }
            ],
        }
    )
    return scraper


def _nfo_text(nfo):
    """把刮削器既有的 bytes/str 返回契约统一成可断言文本。"""
    return nfo.decode("utf-8") if isinstance(nfo, bytes) else nfo


def test_episode_zero_generates_episode_nfo_not_season_nfo():
    """第 0 集是有效集号，不能因为真值判断被降级成季 NFO。"""
    mediainfo = MediaInfo(type=MediaType.TV, tmdb_id=123)
    meta = SimpleNamespace(begin_episode=0)

    nfo = _episode_zero_scraper().get_metadata_nfo(
        meta=meta, mediainfo=mediainfo, season=1, episode=0
    )

    text = _nfo_text(nfo)
    assert "<episodedetails>" in text
    assert "<episode>0</episode>" in text
    assert "<seasonnumber>" not in text


def test_episode_zero_generates_episode_thumbnail():
    """第 0 集剧照应按集图片刮削，不能因 0 被当作未指定集号。"""
    mediainfo = MediaInfo(type=MediaType.TV, tmdb_id=123)

    images = _episode_zero_scraper().get_metadata_img(
        mediainfo=mediainfo, season=1, episode=0
    )

    assert images["episode-thumb.jpg"].endswith("/zero.jpg")


def test_episode_nfo_detail_follows_explicit_episode_number():
    """显式传入的集号是刮削目标，不能被文件起始集号覆盖。"""
    scraper = TmdbScraper()
    scraper._meta_tmdb = SimpleNamespace(
        get_tv_season_detail=lambda *_args, **_kwargs: {
            "episodes": [
                {"id": 1000, "episode_number": 0, "name": "Episode Zero"},
                {"id": 1001, "episode_number": 1, "name": "Episode One"},
            ]
        }
    )
    mediainfo = MediaInfo(type=MediaType.TV, tmdb_id=123)

    nfo = scraper.get_metadata_nfo(
        meta=SimpleNamespace(begin_episode=0),
        mediainfo=mediainfo,
        season=1,
        episode=1,
    )

    text = _nfo_text(nfo)
    assert "<tmdbid>1001</tmdbid>" in text
    assert "<episode>1</episode>" in text



def test_nfo_public_contract_is_utf8_bytes():
    """NFO 公共链路必须明确声明既有的 UTF-8 bytes 契约，避免重写时误按 str 实现。"""
    from app.chain.media import MediaChain
    from app.helper.scraper import MediaScraperHelper
    from app.modules.bangumi import BangumiModule
    from app.modules.themoviedb import TheMovieDbModule

    functions = [
        TmdbScraper.get_metadata_nfo,
        MediaScraperHelper.get_metadata_nfo,
        MediaChain.metadata_nfo,
        BangumiModule.metadata_nfo,
        TheMovieDbModule.metadata_nfo,
    ]

    assert [inspect.signature(function).return_annotation for function in functions] == [
        Optional[bytes]
    ] * len(functions)
