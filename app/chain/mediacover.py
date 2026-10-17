# -*- coding: utf-8 -*-
"""
媒体库封面生成链。

从社区插件 mediacovergenerator 内置而来，按本分支需要大幅裁剪：只保留静态风格 2、
只以媒体服务器最近入库的条目海报作为素材、字体固定为霞鹜真楷，不保存历史也不做缓存。
"""

from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple

from app.chain import ChainBase
from app.chain.mediaserver import MediaServerChain
from app.core.config import settings
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.mediaserver import MediaServerHelper
from app.log import logger
from app.modules.coverstyle.static_2 import create_style_static_2
from app.schemas.mediaserver import MediaServerLibrary, MediaServerPlayItem
from app.schemas.types import MediaType, SystemConfigKey
from app.utils.http import RequestUtils

# 霞鹜真楷（LXGW ZhenKai）固定字体来源
ZH_FONT_URL = (
    "https://github.com/lxgw/LxgwZhenKai/releases/download/v0.827/"
    "LXGWZhenKaiSlabGB-Regular.ttf"
)
ZH_FONT_FILENAME = "LXGWZhenKaiSlabGB-Regular.ttf"
# 输出画布尺寸，与 1080p 媒体库封面比例一致
CANVAS_SIZE = (1920, 1080)


class MediaCoverChain(ChainBase):
    """
    媒体库封面生成链

    以媒体服务器最近入库的条目海报为素材，为每个媒体库渲染一张固定风格的封面并回写。
    """

    def __init__(self):
        """
        初始化封面生成链并准备字体目录。
        """
        super().__init__()
        self.font_dir = settings.CONFIG_PATH / "fonts"
        self.font_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _font_path(self) -> Optional[Path]:
        """
        中文字体本地路径。
        """
        font_path = self.font_dir / ZH_FONT_FILENAME
        return font_path if font_path.exists() else None

    def _ensure_font(self) -> Optional[Path]:
        """
        确保本地存在中文字体，缺失时按需下载。

        :return: 字体文件路径，获取失败时返回 None
        """
        font_path = self.font_dir / ZH_FONT_FILENAME
        if font_path.exists():
            return font_path
        logger.info(f"正在下载封面字体：{ZH_FONT_URL}")
        try:
            response = RequestUtils(proxies=settings.PROXY, timeout=120).get_res(ZH_FONT_URL)
        except Exception as err:
            logger.error(f"下载封面字体失败：{err}")
            return None
        if not response or response.status_code != 200 or not response.content:
            logger.error("下载封面字体失败：响应异常")
            return None
        font_path.write_bytes(response.content)
        logger.info(f"封面字体已保存：{font_path}")
        return font_path

    def _latest_source_image(self, server: str, library: MediaServerLibrary) -> Optional[bytes]:
        """
        取该媒体库中最近入库条目的海报作为封面素材。

        :param server: 媒体服务器名称
        :param library: 媒体库信息
        :return: 图片二进制内容，无法获取时返回 None
        """
        items: List[MediaServerPlayItem] = []
        for item in MediaServerChain().items(
            server=server,
            library_id=library.item_id or library.id,
            start_index=0,
            limit=1,
        ):
            if item:
                items.append(item)
            break
        if not items:
            logger.warn(f"媒体库 {library.name} 中没有可用于生成封面的条目")
            return None
        image_url = (items[0].image or "").strip()
        if not image_url:
            logger.warn(f"媒体库 {library.name} 的最新条目没有海报")
            return None
        try:
            response = RequestUtils(proxies=settings.PROXY, timeout=30).get_res(image_url)
        except Exception as err:
            logger.error(f"下载封面素材失败：{err}")
            return None
        if not response or response.status_code != 200 or not response.content:
            logger.error(f"下载封面素材失败：{image_url}")
            return None
        return response.content

    @staticmethod
    def _library_title(library: MediaServerLibrary) -> Tuple[str, str]:
        """
        构造封面上的中英标题。

        :param library: 媒体库信息
        :return: (中文标题, 英文标题) 元组
        """
        name = str(library.name or "").strip()
        if not name:
            return "", ""
        # 媒体库名形如「电影 - Movies」时拆分为中英双行；无分隔符则只渲染单行
        for separator in (" - ", "-", "/", "|"):
            if separator in name:
                zh_title, _, en_title = name.partition(separator)
                return zh_title.strip(), en_title.strip()
        return name, ""

    def _render_cover(self, library: MediaServerLibrary) -> Optional[bytes]:
        """
        渲染单个媒体库的封面。

        :param library: 媒体库信息
        :return: PNG 图片内容，失败时返回 None
        """
        source = getattr(library, "_source_image", None)
        if not source:
            return None
        font_path = self._font_path
        if not font_path:
            return None
        title = self._library_title(library)
        if not title[0]:
            return None

        # 渲染入口以路径读取素材，先落到内存临时文件
        from tempfile import NamedTemporaryFile  # pylint: disable=import-outside-toplevel

        with NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
            temp_file.write(source)
            temp_path = Path(temp_file.name)
        try:
            image = create_style_static_2(
                image_path=str(temp_path),
                title=title,
                font_path=(str(font_path), str(font_path)),
                resolution_config=type("Resolution", (), {"size": CANVAS_SIZE})(),
            )
        finally:
            temp_path.unlink(missing_ok=True)
        if image is None:
            return None
        buffer = BytesIO()
        image.convert("RGB").save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()

    def process(self) -> None:
        """
        为每个媒体库生成封面并回写媒体服务器。
        """
        if not SystemConfigOper().get(SystemConfigKey.LibraryCoverGenerator):
            logger.debug("媒体库封面生成未启用，跳过本次任务")
            return

        services = MediaServerHelper().get_services(type_filter="emby")
        if not services:
            logger.warn("未配置 Emby 媒体服务器，跳过封面生成")
            return

        font_path = self._ensure_font()
        if not font_path:
            logger.error("缺少封面字体，跳过封面生成")
            return

        for server_name, service in services.items():
            libraries = MediaServerChain().librarys(server=server_name)
            if not libraries:
                continue
            for library in libraries:
                if library.type not in (MediaType.MOVIE.value, MediaType.TV.value):
                    continue
                source = self._latest_source_image(server_name, library)
                if not source:
                    continue
                setattr(library, "_source_image", source)
                cover = self._render_cover(library)
                if not cover:
                    continue
                if self._upload_cover(service.instance, library, cover):
                    logger.info(f"媒体库 {library.name} 封面已更新")
                else:
                    logger.error(f"媒体库 {library.name} 封面上传失败")

    @staticmethod
    def _upload_cover(instance, library: MediaServerLibrary, cover: bytes) -> bool:
        """
        将生成的封面上传到媒体服务器。

        :param instance: 媒体服务器实例
        :param library: 媒体库信息
        :param cover: PNG 图片内容
        :return: 上传是否成功
        """
        item_id = library.item_id or library.id
        host = getattr(instance, "_host", "")
        apikey = getattr(instance, "_apikey", "")
        if not host or not apikey or not item_id:
            return False
        url = f"{host}Items/{item_id}/Images/Primary"
        try:
            response = RequestUtils(timeout=60).post_res(
                url=url,
                params={"api_key": apikey},
                data=cover,
                headers={"Content-Type": "image/png"},
            )
        except Exception as err:
            logger.error(f"上传媒体库封面出错：{err}")
            return False
        return bool(response and response.status_code in (200, 204))