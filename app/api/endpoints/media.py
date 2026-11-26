from pathlib import Path
from typing import Annotated, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app import schemas
from app.chain.media import MediaChain
from app.core.config import settings
from app.core.context import Context
from app.core.meta import MetaBase
from app.core.metainfo import MetaInfo, MetaInfoPath
from app.core.security import verify_token, verify_apitoken
from app.db.models import User
from app.db.user_oper import get_current_active_user, get_current_active_superuser
from app.schemas import MediaType
from app.utils.media import (
    MEDIA_SOURCE_ID_FIELDS,
    is_supported_media_source,
    normalize_media_source,
    parse_media_key,
)

router = APIRouter()
MediaSource = str


def _validate_active_media_source(source: Optional[str]) -> Optional[str]:
    """校验请求级媒体数据源，阻止已移除来源在接口边界静默回退。"""
    normalized_source = normalize_media_source(source)
    if normalized_source and not is_supported_media_source(normalized_source):
        raise HTTPException(
            status_code=400,
            detail=f"不支持的数据源：{normalized_source}，仅支持 themoviedb 或 bangumi",
        )
    return normalized_source


def _build_recognize_metainfo(
        title: str,
        subtitle: Optional[str] = None,
        custom_words: Optional[str] = None,
) -> MetaBase:
    """构造标题识别元数据，并兼容第三方客户端传入媒体文件路径。"""
    custom_word_list = custom_words.split("\n") if custom_words else None
    normalized_title = title.replace("\\", "/")
    title_path = Path(normalized_title)
    if (
        ("/" in title or "\\" in title)
        and "://" not in title
        and title_path.suffix.lower() in settings.RMT_MEDIAEXT
    ):
        metainfo = MetaInfoPath(
            title_path,
            custom_words=custom_word_list,
        )
        metainfo.title = title
        return metainfo
    return MetaInfo(title, subtitle, custom_words=custom_word_list)


@router.get(
    "/recognize", summary="识别媒体信息（种子）", response_model=schemas.Context
)
async def recognize(
    title: str,
    subtitle: Optional[str] = None,
    custom_words: Optional[str] = None,
    source: Optional[MediaSource] = None,
    _: schemas.TokenPayload = Depends(verify_token),
) -> Any:
    """
    根据标题、副标题识别媒体信息
    :param title: 标题
    :param subtitle: 副标题
    :param custom_words: 临时识别词（每行一条规则），传入时仅在本次识别中生效，不会保存到系统配置
    :param source: 请求级识别数据源
    :param _:
    """
    source = _validate_active_media_source(source)
    # 识别媒体信息，传入临时识别词时优先于系统配置的识别词生效
    metainfo = _build_recognize_metainfo(title, subtitle, custom_words)
    mediainfo = await MediaChain().async_recognize_by_meta(
        metainfo,
        source=source,
    )
    if mediainfo:
        return Context(meta_info=metainfo, media_info=mediainfo).to_dict()
    return schemas.Context()


@router.get(
    "/recognize2",
    summary="识别种子媒体信息（API_TOKEN）",
    response_model=schemas.Context,
)
async def recognize2(
    _: Annotated[str, Depends(verify_apitoken)],
    title: str,
    subtitle: Optional[str] = None,
    custom_words: Optional[str] = None,
    source: Optional[MediaSource] = None,
) -> Any:
    """
    根据标题、副标题识别媒体信息 API_TOKEN认证（?token=xxx）
    """
    # 识别媒体信息
    return await recognize(title, subtitle, custom_words, source)


@router.get(
    "/recognize_file", summary="识别媒体信息（文件）", response_model=schemas.Context
)
async def recognize_file(
    path: str,
    source: Optional[MediaSource] = None,
    _: schemas.TokenPayload = Depends(verify_token),
) -> Any:
    """
    根据文件路径识别媒体信息
    """
    source = _validate_active_media_source(source)
    # 识别媒体信息
    context = await MediaChain().async_recognize_by_path(path, source=source)
    if context:
        return context.to_dict()
    return schemas.Context()


@router.get(
    "/recognize_file2",
    summary="识别文件媒体信息（API_TOKEN）",
    response_model=schemas.Context,
)
async def recognize_file2(
    path: str,
    _: Annotated[str, Depends(verify_apitoken)],
    source: Optional[MediaSource] = None,
) -> Any:
    """
    根据文件路径识别媒体信息 API_TOKEN认证（?token=xxx）
    """
    # 识别媒体信息
    return await recognize_file(path, source)


@router.get("/search", summary="搜索媒体信息", response_model=List[dict])
async def search(
    title: str,
    type: Optional[str] = "media",
    page: int = 1,
    count: int = 8,
    source: Optional[MediaSource] = None,
    _: schemas.TokenPayload = Depends(verify_token),
) -> Any:
    """
    模糊搜索可用于入库识别的媒体信息列表。

    :param title: 搜索关键词
    :param type: 搜索类型，仅支持 media
    :param page: 页码
    :param count: 每页数量
    :param source: 请求级搜索数据源
    :param _: Token校验
    :return: 搜索结果列表
    """
    if type != "media":
        raise HTTPException(status_code=400, detail=f"不支持的搜索类型：{type}，仅支持媒体搜索")

    source = _validate_active_media_source(source)
    _, medias = await MediaChain().async_search(title=title, source=source)
    result = [media.to_dict() for media in medias] if medias else []
    if not result:
        return []

    # 排序和分页
    setting_order = settings.SEARCH_SOURCE.split(",") if settings.SEARCH_SOURCE else []
    sort_order = {source: index for index, source in enumerate(setting_order)}
    sorted_result = sorted(result, key=lambda item: sort_order.get(item.get("source"), 4))
    return sorted_result[(page - 1) * count : page * count]


@router.post(
    "/scrape/{storage}", summary="刮削媒体信息", response_model=schemas.Response
)
def scrape(
    fileitem: schemas.FileItem,
    storage: Optional[str] = "local",
    media_source: Optional[MediaSource] = None,
    media_id: Optional[str] = None,
    type_name: Optional[MediaType] = None,
    _: schemas.TokenPayload = Depends(verify_token),
) -> Any:
    """
    刮削媒体信息，可按请求指定媒体数据源及其原生ID

    :param fileitem: 待刮削文件项
    :param storage: 文件所在存储
    :param media_source: 请求级媒体数据源
    :param media_id: 数据源原生ID
    :param type_name: 媒体类型
    :param _: Token校验
    """
    if not fileitem or not fileitem.path:
        return schemas.Response(success=False, message="刮削路径无效")
    media_source = _validate_active_media_source(media_source)
    normalized_media_id = media_id.strip() if media_id else None
    if normalized_media_id and not media_source:
        return schemas.Response(
            success=False, message="指定媒体ID时必须同时指定媒体数据源"
        )
    if normalized_media_id and not normalized_media_id.isdigit():
        return schemas.Response(success=False, message="媒体ID格式无效")

    chain = MediaChain()
    if normalized_media_id:
        meta_info = MetaInfoPath(Path(fileitem.path))
        media_info = chain.recognize_media(
            meta=meta_info,
            mtype=type_name,
            source=media_source,
            mediaid=normalized_media_id,
        )
        if media_info:
            media_info.scrape_source = media_source
            chain.obtain_images(mediainfo=media_info)
    else:
        context = chain.recognize_by_path(
            fileitem.path,
            source=media_source,
            obtain_images=True,
        )
        meta_info = context.meta_info if context else None
        media_info = context.media_info if context else None

    if not media_info:
        return schemas.Response(success=False, message="刮削失败，无法识别媒体信息")
    if media_source:
        media_info.scrape_source = media_source
    if storage == "local":
        if not Path(fileitem.path).exists():
            return schemas.Response(success=False, message="刮削路径不存在")
    # 手动刮削 (暂时使用同步版本，可以后续优化为异步)
    chain.scrape_metadata(
        fileitem=fileitem,
        meta=meta_info,
        mediainfo=media_info,
        overwrite=True,
    )
    return schemas.Response(success=True, message=f"{fileitem.path} 刮削完成")


@router.get("/category", summary="查询自动分类配置", response_model=dict)
async def category(_: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    查询自动分类配置。

    二级分类已取消，恒返回空的电影与剧集分类列表，保留端点是为了
    避免既有调用方（前端缓存、外部脚本）因 404 而报错。
    """
    return MediaChain().media_category() or {}


@router.get("/groups/{tmdbid}", summary="查询媒体剧集组", response_model=List[dict])
async def groups(tmdbid: int, _: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    查询媒体剧集组列表（themoviedb）
    """
    mediainfo = await MediaChain().async_recognize_media(
        tmdbid=tmdbid, mtype=MediaType.TV
    )
    if not mediainfo:
        return []
    return mediainfo.episode_groups


@router.get("/{mediaid}", summary="查询媒体详情", response_model=schemas.MediaInfo)
async def detail(
    mediaid: str,
    type_name: str,
    title: Optional[str] = None,
    year: str = None,
    _: schemas.TokenPayload = Depends(verify_token),
) -> Any:
    """
    根据带来源前缀的媒体ID查询媒体信息，type_name: 电影/电视剧
    """
    mtype = MediaType(type_name)
    mediainfo = None
    mediachain = MediaChain()
    media_source, source_media_id = parse_media_key(mediaid)
    media_source = _validate_active_media_source(media_source)
    if media_source and source_media_id:
        mediainfo = await mediachain.async_recognize_media(
            source=media_source,
            mediaid=source_media_id,
            mtype=mtype,
        )
    if not mediainfo and (
        not media_source or media_source not in MEDIA_SOURCE_ID_FIELDS
    ):
        if title:
            # 使用名称识别兜底
            meta = MetaInfo(title)
            if year:
                meta.year = year
            if mtype:
                meta.type = mtype
            mediainfo = await mediachain.async_recognize_by_meta(
                meta,
                obtain_images=False,
            )
    # 识别
    if mediainfo:
        await mediachain.async_obtain_images(mediainfo)
        return mediainfo.to_dict()

    return schemas.MediaInfo()
