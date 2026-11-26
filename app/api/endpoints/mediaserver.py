from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app import schemas
from app.chain.mediaserver import MediaServerChain
from app.core.security import verify_token
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.mediaserver import MediaServerHelper
from app.schemas.types import SystemConfigKey

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


@router.get("/play/{itemid:path}", summary="在线播放")
def play_item(
    itemid: str, _: schemas.TokenPayload = Depends(verify_token)
) -> schemas.Response:
    """
    获取媒体服务器播放页面地址
    """
    if not itemid:
        return schemas.Response(success=False, message="参数错误")
    configs = MediaServerHelper().get_configs()
    if not configs:
        return schemas.Response(success=False, message="未配置媒体服务器")
    media_chain = MediaServerChain()
    for name in configs.keys():
        item = media_chain.iteminfo(server=name, item_id=itemid)
        if item:
            play_url = media_chain.get_play_url(server=name, item_id=itemid)
            if play_url:
                return schemas.Response(
                    success=True,
                    data={
                        "url": play_url,
                        "item_id": item.item_id or itemid,
                        "server_id": item.server_id,
                        "server_type": item.server,
                    },
                )
    return schemas.Response(success=False, message="未找到播放地址")


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


@router.get("/clients", summary="查询可用媒体服务器", response_model=List[dict])
async def clients(_: schemas.TokenPayload = Depends(verify_token)) -> Any:
    """
    查询可用媒体服务器
    """
    mediaservers: List[dict] = SystemConfigOper().get(SystemConfigKey.MediaServers)
    if mediaservers:
        return [
            {"name": d.get("name"), "type": d.get("type")}
            for d in mediaservers
            if d.get("enabled")
        ]
    return []
