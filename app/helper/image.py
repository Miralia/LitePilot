import io
from pathlib import Path
from typing import Awaitable, Callable, Optional, List
from urllib.parse import urljoin

from PIL import Image

from app.chain.mediaserver import MediaServerChain
from app.chain.tmdb import TmdbChain
from app.core.cache import cached, FileCache, AsyncFileCache
from app.core.config import settings
from app.log import logger
from app.utils.http import RequestUtils, AsyncRequestUtils
from app.utils.ip import IpUtils
from app.utils.security import SecurityUtils
from app.utils.singleton import Singleton


_IMAGE_REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
_IMAGE_MAX_REDIRECTS = 5


class WallpaperHelper(metaclass=Singleton):
    """
    壁纸帮助类
    """

    def get_wallpapers(self, num: int = 10) -> List[str]:
        """
        获取登录页面壁纸列表
        """
        if settings.WALLPAPER == "bing":
            return self.get_bing_wallpapers(num)
        elif settings.WALLPAPER == "mediaserver":
            return self.get_mediaserver_wallpapers(num)
        elif settings.WALLPAPER == "customize":
            return self.get_customize_wallpapers()
        elif settings.WALLPAPER == "tmdb":
            return self.get_tmdb_wallpapers(num)
        return []

    @cached(maxsize=1, ttl=3600, skip_empty=True)
    def get_tmdb_wallpapers(self, num: int = 10) -> List[str]:
        """
        获取7天的TMDB每日壁纸
        """
        return TmdbChain().get_trending_wallpapers(num)

    @cached(maxsize=1, ttl=3600, skip_empty=True)
    def get_bing_wallpapers(self, num: int = 7) -> List[str]:
        """
        获取7天的Bing每日壁纸
        """
        url = f"https://cn.bing.com/HPImageArchive.aspx?format=js&idx=0&n={num}"
        resp = RequestUtils(timeout=5).get_res(url)
        if resp and resp.status_code == 200:
            try:
                result = resp.json()
                if isinstance(result, dict):
                    return [f"https://cn.bing.com{image.get('url')}" for image in result.get('images') or []]
            except Exception as err:
                logger.warning(f"解析Bing壁纸列表响应失败：{err}")
        return []

    @cached(maxsize=1, ttl=3600, skip_empty=True)
    def get_mediaserver_wallpapers(self, num: int = 10) -> List[str]:
        """
        获取媒体服务器壁纸列表
        """
        return MediaServerChain().get_latest_wallpapers(count=num)

    @cached(maxsize=1, ttl=3600, skip_empty=True)
    def get_customize_wallpapers(self) -> List[str]:
        """
        获取自定义壁纸api壁纸
        """

        def find_files_with_suffixes(obj, suffixes: List[str]) -> List[str]:
            """
            递归查找对象中所有包含特定后缀的文件，返回匹配的字符串列表
            支持输入：字典、列表、字符串
            """
            _result = []

            # 处理字符串
            if isinstance(obj, str):
                if obj.endswith(tuple(suffixes)):
                    _result.append(obj)

            # 处理字典
            elif isinstance(obj, dict):
                for value in obj.values():
                    _result.extend(find_files_with_suffixes(value, suffixes))

            # 处理列表
            elif isinstance(obj, list):
                for item in obj:
                    _result.extend(find_files_with_suffixes(item, suffixes))

            return _result

        # 判断是否存在自定义壁纸api
        if settings.CUSTOMIZE_WALLPAPER_API_URL:
            wallpaper_list = []
            resp = RequestUtils(timeout=15).get_res(settings.CUSTOMIZE_WALLPAPER_API_URL)
            if resp and resp.status_code == 200:
                # 如果返回的是图片格式
                content_type = resp.headers.get('Content-Type')
                if content_type and content_type.lower().startswith('image/'):
                    wallpaper_list.append(settings.CUSTOMIZE_WALLPAPER_API_URL)
                else:
                    try:
                        result = resp.json()
                        if isinstance(result, list) or isinstance(result, dict) or isinstance(result, str):
                            wallpaper_list = find_files_with_suffixes(result, settings.SECURITY_IMAGE_SUFFIXES)
                    except Exception as err:
                        logger.warning(f"解析自定义壁纸接口响应失败：{err}")
            return wallpaper_list
        else:
            return []


class ImageHelper(metaclass=Singleton):

    def __init__(self):
        _base_path = settings.CACHE_PATH
        _ttl = settings.GLOBAL_IMAGE_CACHE_DAYS * 24 * 3600
        self.file_cache = FileCache(base=_base_path, ttl=_ttl)
        self.async_file_cache = AsyncFileCache(base=_base_path, ttl=_ttl)

    @staticmethod
    def _prepare_cache_path(url: str) -> str:
        """缓存路径"""
        sanitized_path = SecurityUtils.sanitize_url_path(url)
        cache_path = Path(sanitized_path)
        if not cache_path.suffix:
            cache_path = cache_path.with_suffix(".jpg")
        return cache_path.as_posix()

    @staticmethod
    def get_image_mime_type(content: bytes, verify: bool = True) -> Optional[str]:
        """
        根据图片内容返回 Pillow 识别的图片 MIME 类型。

        外部响应在写入缓存前需要完整校验；已校验的缓存只需读取格式头。
        非图片或可脚本化的 MIME 类型不作为图片代理响应。
        """
        if not content:
            return None
        try:
            with Image.open(io.BytesIO(content)) as image:
                image_format = (image.format or "").upper()
                if verify:
                    image.verify()
            mime_type = Image.MIME.get(image_format)
            if (
                not mime_type
                or not mime_type.startswith("image/")
                or mime_type == "image/svg+xml"
            ):
                return None
            return mime_type
        except Exception as err:
            logger.warning(f"Invalid image format: {err}")
            return None

    @staticmethod
    def _get_request_params(url: str, proxy: Optional[bool]) -> dict:
        """获取参数"""
        referer = "https://movie.douban.com/" if "doubanio.com" in url else None
        if proxy is None:
            proxies = settings.PROXY if not (referer or IpUtils.is_internal(url)) else None
        else:
            proxies = settings.PROXY if proxy else None
        return {
            "ua": settings.NORMAL_USER_AGENT,
            "proxies": proxies,
            "referer": referer,
            "accept_type": "image/avif,image/webp,image/apng,*/*",
        }

    def fetch_image(
        self,
        url: str,
        proxy: Optional[bool] = None,
        use_cache: bool = True) -> Optional[bytes]:
        """
        获取图片（同步版本）
        """
        result = self.fetch_image_with_mime_type(
            url=url,
            proxy=proxy,
            use_cache=use_cache,
        )
        return result[0] if result else None

    def fetch_image_with_mime_type(
        self,
        url: str,
        proxy: Optional[bool] = None,
        use_cache: bool = True,
    ) -> Optional[tuple[bytes, str]]:
        """
        同步获取图片及其内容识别 MIME 类型。

        网络响应在写入缓存前完整验证一次；缓存命中仅重新识别格式头。
        """
        if not url:
            return None

        cache_path = self._prepare_cache_path(url)

        # 检查缓存
        if use_cache:
            content = self.file_cache.get(cache_path, region="images")
            if content:
                mime_type = self.get_image_mime_type(content, verify=False)
                if mime_type:
                    return content, mime_type

        # 请求远程图片
        params = self._get_request_params(url, proxy)
        response = RequestUtils(**params).get_res(url=url)
        if response is None or response.status_code != 200:
            redacted_url = SecurityUtils.redact_sensitive_url_params(url)
            logger.warning(f"Failed to fetch image from URL: {redacted_url}")
            return None

        content = response.content
        mime_type = self.get_image_mime_type(content)
        if not mime_type:
            return None

        # 保存缓存
        self.file_cache.set(cache_path, content, region="images")
        return content, mime_type

    async def async_fetch_image(
        self,
        url: str,
        proxy: Optional[bool] = None,
        use_cache: bool = True) -> Optional[bytes]:
        """
        获取图片（异步版本）
        """
        result = await self.async_fetch_image_with_mime_type(
            url=url,
            proxy=proxy,
            use_cache=use_cache,
        )
        return result[0] if result else None

    @staticmethod
    async def _close_async_response(response) -> None:
        """安静关闭异步响应，避免重定向链占用连接。"""
        if response is None or not hasattr(response, "aclose"):
            return
        try:
            await response.aclose()
        except Exception as err:
            logger.debug(f"关闭图片重定向响应失败: {err}")

    async def _async_request_image_response(
        self,
        url: str,
        params: dict,
        redirect_validator: Optional[Callable[[str], Awaitable[bool]]],
    ):
        """
        请求图片响应；提供重定向校验器时手动逐跳校验目标。
        """
        request = AsyncRequestUtils(**params)
        if redirect_validator is None:
            return await request.get_res(url=url)

        current_url = url
        redirect_count = 0
        while redirect_count <= _IMAGE_MAX_REDIRECTS:
            response = await request.get_res(url=current_url, allow_redirects=False)
            if response is None or response.status_code not in _IMAGE_REDIRECT_STATUS_CODES:
                return response
            location = response.headers.get("location")
            if not location:
                return response
            next_url = urljoin(current_url, location)
            await self._close_async_response(response)
            if redirect_count >= _IMAGE_MAX_REDIRECTS:
                logger.warning("拦截图片代理重定向：重定向次数过多")
                return None
            try:
                redirect_allowed = await redirect_validator(next_url)
            except Exception as err:
                logger.debug(f"图片代理重定向校验失败: {err}")
                redirect_allowed = False
            if not redirect_allowed:
                logger.warning(
                    "拦截图片代理重定向: "
                    f"{SecurityUtils.redact_sensitive_url_params(current_url)} -> "
                    f"{SecurityUtils.redact_sensitive_url_params(next_url)}"
                )
                return None
            current_url = next_url
            redirect_count += 1
        return None

    async def async_fetch_image_with_mime_type(
        self,
        url: str,
        proxy: Optional[bool] = None,
        use_cache: bool = True,
        redirect_validator: Optional[Callable[[str], Awaitable[bool]]] = None,
    ) -> Optional[tuple[bytes, str]]:
        """
        异步获取图片及其内容识别 MIME 类型。

        网络响应在写入缓存前完整验证一次；缓存命中仅重新识别格式头。
        提供重定向校验器时逐跳校验 30x 目标，避免首跳白名单被跳转绕过。
        """
        if not url:
            return None

        cache_path = self._prepare_cache_path(url)

        # 检查缓存
        if use_cache:
            content = await self.async_file_cache.get(cache_path, region="images")
            if content:
                mime_type = self.get_image_mime_type(content, verify=False)
                if mime_type:
                    return content, mime_type

        # 请求远程图片
        params = self._get_request_params(url, proxy)
        response = await self._async_request_image_response(
            url=url,
            params=params,
            redirect_validator=redirect_validator,
        )
        if response is None or response.status_code != 200:
            redacted_url = SecurityUtils.redact_sensitive_url_params(url)
            logger.warning(f"Failed to fetch image from URL: {redacted_url}")
            return None

        content = response.content
        mime_type = self.get_image_mime_type(content)
        if not mime_type:
            return None

        # 保存缓存
        await self.async_file_cache.set(cache_path, content, region="images")
        return content, mime_type
