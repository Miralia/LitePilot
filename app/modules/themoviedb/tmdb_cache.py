import io
import json
import pickle
import traceback
from math import ceil
from threading import RLock
from time import time

from app.core.cache import FileCache, TTLCache
from app.core.config import settings
from app.core.meta import MetaBase
from app.log import logger
from app.schemas.types import MediaType
from app.utils.singleton import WeakSingleton

lock = RLock()
PERSISTENCE_VERSION = 2
PERSISTENCE_REGION = "recognize"
PERSISTENCE_KEY = "tmdb"


class _RestrictedUnpickler(pickle.Unpickler):
    """只允许还原旧版 TMDB 缓存所需的 MediaType 枚举。"""

    def find_class(self, module: str, name: str):
        """拒绝除 MediaType 之外的一切全局对象引用。"""
        if module == MediaType.__module__ and name == MediaType.__name__:
            return MediaType
        raise pickle.UnpicklingError(f"禁止反序列化对象：{module}.{name}")


def _load_persisted_payload(content: bytes) -> tuple[object, bool]:
    """读取新版 JSON 缓存，或以受限方式兼容旧版 pickle 缓存。"""
    try:
        return json.loads(content.decode("utf-8")), False
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _RestrictedUnpickler(io.BytesIO(content)).load(), True


def _json_cache_value(value: dict) -> dict:
    """将缓存值转换为 JSON 可持久化结构。"""
    normalized = dict(value)
    media_type = normalized.get("type")
    if isinstance(media_type, MediaType):
        normalized["type"] = media_type.value
    return normalized


def _runtime_cache_value(value: dict) -> dict:
    """将持久化缓存值恢复为识别链需要的运行时结构。"""
    normalized = dict(value)
    media_type = normalized.get("type")
    if media_type is not None and not isinstance(media_type, MediaType):
        try:
            normalized["type"] = MediaType(media_type)
        except (TypeError, ValueError):
            pass
    return normalized


class TmdbCache(metaclass=WeakSingleton):
    """
    TMDB缓存数据
    {
        "id": '',
        "title": '',
        "year": '',
        "type": MediaType
    }
    """
    def __init__(self):
        """初始化 TMDB 识别缓存并恢复未过期的持久化数据。"""
        self.maxsize = settings.CONF.tmdb
        self.ttl = settings.CONF.meta
        self.region = "__tmdb_cache__"
        self._cache = TTLCache(region=self.region, maxsize=self.maxsize, ttl=self.ttl)
        self._expires_at: dict[str, float] = {}
        self._dirty = False
        self._file_cache = None
        self._legacy_file_cache = None
        self._legacy_cache_found = False
        if not self._cache.is_redis():
            self._file_cache = FileCache(base=settings.CACHE_PATH, ttl=self.ttl)
            self._legacy_file_cache = FileCache(base=settings.TEMP_PATH.parent, ttl=self.ttl)
            self._restore()

    def _restore(self) -> None:
        """从统一文件缓存恢复仍在有效期内的 TMDB 识别数据。"""
        try:
            content = self._file_cache.get(PERSISTENCE_KEY, region=PERSISTENCE_REGION)
            if not content:
                content = self._legacy_file_cache.get(
                    self.region,
                    region=settings.TEMP_PATH.name,
                )
                if content:
                    self._legacy_cache_found = True
                    self._dirty = True
            if not content:
                return
            payload, migrated_from_pickle = _load_persisted_payload(content)
            if migrated_from_pickle:
                self._dirty = True
            now = time()
            if (
                    isinstance(payload, dict)
                    and payload.get("version") in (1, PERSISTENCE_VERSION)
                    and isinstance(payload.get("items"), dict)
            ):
                items = payload["items"]
            elif isinstance(payload, dict):
                # 旧版缓存没有保存过期时间，迁移时从当前时刻重新计算一次有效期。
                items = {
                    key: {"value": value, "expires_at": now + self.ttl}
                    for key, value in payload.items()
                }
                self._dirty = True
            else:
                return

            for key, item in items.items():
                if not isinstance(item, dict):
                    self._dirty = True
                    continue
                value = item.get("value")
                expires_at = item.get("expires_at")
                if not isinstance(value, dict) or not isinstance(expires_at, (int, float)):
                    self._dirty = True
                    continue
                value = _runtime_cache_value(value)
                remaining_ttl = expires_at - now
                if remaining_ttl <= 0:
                    self._dirty = True
                    continue
                self._cache.set(key, value, ttl=ceil(remaining_ttl))
                self._expires_at[key] = expires_at
        except Exception as err:
            logger.error(f"加载TMDB识别缓存失败：{str(err)} - {traceback.format_exc()}")

    def _set(self, key: str, value: dict) -> None:
        """写入单条 TMDB 识别缓存并记录其独立过期时间。"""
        self._cache.set(key, _json_cache_value(value))
        if not self._cache.is_redis():
            self._expires_at[key] = time() + self.ttl
            self._dirty = True

    def clear(self):
        """
        清空所有TMDB缓存
        """
        with lock:
            self._cache.clear()
            self._expires_at.clear()
            self._dirty = True
            self.save(force=True)

    def list_items(self) -> list[dict]:
        """
        返回可供管理界面展示的 TMDB 识别缓存列表。
        """
        with lock:
            cache_items = []
            for key, value in self._cache.items():
                if not isinstance(value, dict):
                    continue
                media_type = value.get("type")
                if not isinstance(media_type, MediaType):
                    try:
                        media_type = MediaType(media_type)
                    except (TypeError, ValueError):
                        media_type = None
                cache_items.append({
                    "key": key,
                    "tmdb_id": value.get("id") or 0,
                    "title": value.get("title") or "",
                    "year": value.get("year") or "",
                    "media_type": media_type.to_api_value() if media_type else "unknown",
                    "poster_path": value.get("poster_path") or "",
                    "backdrop_path": value.get("backdrop_path") or "",
                })
            return sorted(cache_items, key=lambda item: item["key"])

    @staticmethod
    def __get_key(meta: MetaBase) -> str:
        """
        获取缓存KEY
        """
        return f"[{meta.type.value if meta.type else '未知'}][{settings.TMDB_LOCALE}]{meta.tmdbid or meta.name}-{meta.year}-{meta.begin_season}"

    def get(self, meta: MetaBase):
        """
        根据KEY值获取缓存值
        """
        key = self.__get_key(meta)

        with lock:
            cache_data = self._cache.get(key)
            if not cache_data and self._expires_at.pop(key, None) is not None:
                self._dirty = True
            return _runtime_cache_value(cache_data) if cache_data else {}

    def delete(self, key: str) -> dict:
        """
        删除缓存信息
        @param key: 缓存key
        @return: 被删除的缓存内容
        """
        with lock:
            redis_data = self._cache.get(key)
            if redis_data:
                self._cache.delete(key)
                self._expires_at.pop(key, None)
                self._dirty = True
                self.save(force=True)
                return redis_data
            return {}

    def update(self, meta: MetaBase, info: dict) -> None:
        """
        新增或更新缓存条目
        """
        key = self.__get_key(meta)
        if info:
            # 缓存标题
            cache_title = info.get("title") \
                if info.get("media_type") == MediaType.MOVIE else info.get("name")
            # 缓存年份
            cache_year = info.get('release_date') \
                if info.get("media_type") == MediaType.MOVIE else info.get('first_air_date')
            if cache_year:
                cache_year = cache_year[:4]

            with lock:
                # 缓存数据
                cache_data = {
                    "id": info.get("id"),
                    "type": info.get("media_type"),
                    "year": cache_year,
                    "title": cache_title,
                    "poster_path": info.get("poster_path"),
                    "backdrop_path": info.get("backdrop_path")
                }
                self._set(key, cache_data)

        elif info is not None:
            # None时不缓存，此时代表网络错误，允许重复请求
            with lock:
                self._set(key, {"id": 0})

    def save(self, force: bool = False) -> None:
        """
        使用统一文件缓存保存未过期的 TMDB 识别数据。
        """
        if self._cache.is_redis():
            return
        with lock:
            now = time()
            cache_items = dict(self._cache.items())
            active_keys = set(cache_items)
            stale_keys = set(self._expires_at) - active_keys
            if stale_keys:
                for key in stale_keys:
                    self._expires_at.pop(key, None)
                self._dirty = True

            persisted_items = {}
            for key, value in cache_items.items():
                expires_at = self._expires_at.get(key)
                if expires_at is None:
                    expires_at = now + self.ttl
                    self._expires_at[key] = expires_at
                    self._dirty = True
                if expires_at <= now or not value.get("id"):
                    continue
                persisted_items[key] = {
                    "value": _json_cache_value(value),
                    "expires_at": expires_at,
                }

            if not force and not self._dirty:
                return

            try:
                if persisted_items:
                    payload = {
                        "version": PERSISTENCE_VERSION,
                        "items": persisted_items,
                    }
                    self._file_cache.set(
                        PERSISTENCE_KEY,
                        json.dumps(
                            payload,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ).encode("utf-8"),
                        region=PERSISTENCE_REGION,
                    )
                else:
                    self._file_cache.delete(PERSISTENCE_KEY, region=PERSISTENCE_REGION)
                if self._legacy_cache_found:
                    self._legacy_file_cache.delete(
                        self.region,
                        region=settings.TEMP_PATH.name,
                    )
                    self._legacy_cache_found = False
                self._dirty = False
            except Exception as err:
                logger.error(f"保存TMDB识别缓存失败：{str(err)} - {traceback.format_exc()}")

    def __del__(self):
        """实例释放前保存非 Redis 缓存。"""
        self.save()
