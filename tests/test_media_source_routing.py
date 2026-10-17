from unittest.mock import Mock, patch

from app.chain import ChainBase
from app.core.context import MediaInfo
from app.core.meta import MetaBase
from app.schemas.types import MediaType


def _chain_without_init() -> ChainBase:
    """构造不加载真实模块和外部服务的识别链实例。"""
    return object.__new__(ChainBase)


def test_generic_source_id_wins_over_legacy_ids() -> None:
    """显式source与media_id应优先于同一请求残留的兼容ID字段。"""
    resolved = ChainBase._resolve_media_source_params(
        source="bangumi",
        mediaid="154587",
        tmdbid=999,
        doubanid="888",
    )

    assert resolved == ("bangumi", None, None, 154587)


def test_custom_plugin_source_is_not_discarded() -> None:
    """插件自定义来源应保留来源名，并通过通用原生 ID 交给插件。"""
    resolved = ChainBase._resolve_media_source_params(
        source="plugin_source",
        mediaid="custom-1",
    )

    assert resolved == ("plugin_source", None, None, None)


def test_explicit_source_recognition_reaches_plugins_with_all_ids() -> None:
    """显式选择数据源时应保留通用参数并进入完整模块调度。"""
    chain = _chain_without_init()
    media = MediaInfo(
        bangumi_info={
            "id": 154587,
            "name": "Frieren",
            "name_cn": "葬送的芙莉莲",
        }
    )
    chain.run_module = Mock(return_value=media)

    result = chain.recognize_media(
        source="bangumi",
        mediaid="154587",
        tmdbid=999,
        mtype=MediaType.TV,
    )

    assert result is media
    call = chain.run_module.call_args
    assert call.kwargs["source"] == "bangumi"
    assert call.kwargs["mediaid"] == "154587"
    assert call.kwargs["bangumiid"] == 154587
    assert call.kwargs["tmdbid"] is None


def test_default_recognition_passes_empty_generic_identity() -> None:
    """默认识别也应向插件传递完整但为空的通用媒体身份参数。"""
    chain = _chain_without_init()
    media = MediaInfo(title="测试电影", type=MediaType.MOVIE, tmdb_id=1)
    chain.run_module = Mock(return_value=media)
    meta = MetaBase("测试电影")
    meta.cn_name = "测试电影"
    meta.type = MediaType.MOVIE

    result = chain.recognize_media(meta=meta)

    assert result is media
    call = chain.run_module.call_args
    assert call.kwargs["source"] is None
    assert call.kwargs["mediaid"] is None
    assert call.kwargs["bangumiid"] is None




