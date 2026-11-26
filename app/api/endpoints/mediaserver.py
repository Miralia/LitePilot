from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app import schemas
from app.chain.mediaserver import MediaServerChain
from app.core.security import verify_token

router = APIRouter()


def _require_mediaserver_result(result: Optional[List[Any]]) -> List[Any]:
    """
    保留媒体服务器成功空列表，并把提供方失败转换为明确的网关错误。
    """
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="媒体服务器请求失败",
        )
    return result



@router.get(
    "/latest", summary="最新入库条目", response_model=List[schemas.MediaServerPlayItem]
)
def latest(
    server: str,
    count: Optional[int] = 20,
    userinfo: schemas.TokenPayload = Depends(verify_token),
) -> Any:
    """
    获取媒体服务器最新入库条目
    """
    return _require_mediaserver_result(
        MediaServerChain().latest(
            server=server,
            count=count,
            username=userinfo.username,
        )
    )


@router.get(
    "/playing", summary="正在播放条目", response_model=List[schemas.MediaServerPlayItem]
)
def playing(
    server: str,
    count: Optional[int] = 12,
    userinfo: schemas.TokenPayload = Depends(verify_token),
) -> Any:
    """
    获取媒体服务器正在播放条目
    """
    return _require_mediaserver_result(
        MediaServerChain().playing(
            server=server,
            count=count,
            username=userinfo.username,
        )
    )


@router.get(
    "/library", summary="媒体库列表", response_model=List[schemas.MediaServerLibrary]
)
def library(
    server: str,
    hidden: Optional[bool] = False,
    userinfo: schemas.TokenPayload = Depends(verify_token),
) -> Any:
    """
    获取媒体服务器媒体库列表
    """
    return _require_mediaserver_result(
        MediaServerChain().librarys(
            server=server,
            username=userinfo.username,
            hidden=hidden,
        )
    )
