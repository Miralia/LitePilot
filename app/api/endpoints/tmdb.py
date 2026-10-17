from typing import List, Any, Optional

from fastapi import APIRouter, Depends

from app import schemas
from app.chain.tmdb import TmdbChain
from app.core.config import settings
from app.core.security import verify_token
from app.db.models.user import User
from app.db.user_oper import get_current_active_superuser_async
from app.modules.themoviedb.tmdb_cache import TmdbCache
from app.schemas.types import MediaType

router = APIRouter()


@router.get(
    "/cache", summary="查询 TheMovieDb 识别缓存", response_model=schemas.Response
)
async def tmdb_recognition_cache(
    _: User = Depends(get_current_active_superuser_async),
) -> schemas.Response:
    """查询可管理的 TheMovieDb 识别缓存。"""
    cache_items = TmdbCache().list_items()
    recognized_count = sum(1 for item in cache_items if item["tmdb_id"])
    return schemas.Response(
        success=True,
        data={
            "count": len(cache_items),
            "recognized": recognized_count,
            "unrecognized": len(cache_items) - recognized_count,
            "data": cache_items,
        },
    )


@router.delete(
    "/cache/{cache_key:path}",
    summary="删除指定 TheMovieDb 识别缓存",
    response_model=schemas.Response,
)
async def delete_tmdb_recognition_cache(
    cache_key: str,
    _: User = Depends(get_current_active_superuser_async),
) -> schemas.Response:
    """按缓存键删除单条 TheMovieDb 识别缓存。"""
    deleted_item = TmdbCache().delete(cache_key)
    if not deleted_item:
        return schemas.Response(success=False, message="TheMovieDb 识别缓存不存在")
    return schemas.Response(success=True, message="TheMovieDb 识别缓存删除成功")


@router.delete(
    "/cache", summary="清空 TheMovieDb 识别缓存", response_model=schemas.Response
)
async def clear_tmdb_recognition_cache(
    _: User = Depends(get_current_active_superuser_async),
) -> schemas.Response:
    """清空全部 TheMovieDb 识别缓存。"""
    TmdbCache().clear()
    return schemas.Response(success=True, message="TheMovieDb 识别缓存清理完成")
















