from dataclasses import dataclass
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


@dataclass
class ServiceInfo:
    """
    封装服务相关信息的数据类
    """

    # 名称
    name: Optional[str] = None
    # 实例
    instance: Optional[Any] = None
    # 模块
    module: Optional[Any] = None
    # 类型
    type: Optional[str] = None
    # 配置
    config: Optional[Any] = None


class MediaServerConf(BaseModel):
    """
    媒体服务器配置
    """

    # 名称
    name: Optional[str] = None
    # 类型 emby/zspace/jellyfin/plex/trimemedia/ugreen
    type: Optional[str] = None
    # 配置
    config: Optional[dict] = Field(default_factory=dict)
    # 是否启用
    enabled: Optional[bool] = False
    # 同步媒体体库列表
    sync_libraries: Optional[list] = Field(default_factory=list)
    # 自动同步间隔（小时），未设置时使用旧全局配置
    sync_interval: Optional[int] = None

    @field_validator("sync_interval", mode="before")
    @classmethod
    def validate_sync_interval(cls, value: Any) -> Optional[int]:
        """
        兼容前端清空输入框后残留的空字符串等非法值，避免历史配置导致模块初始化失败

        :param value: 原始配置值
        :return: 合法的间隔小时数，无法解析时返回 None
        """
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


class DownloaderConf(BaseModel):
    """
    下载器配置
    """

    # 名称
    name: Optional[str] = None
    # 类型 qbittorrent
    type: Optional[str] = None
    # 是否默认
    default: Optional[bool] = False
    # 配置
    config: Optional[dict] = Field(default_factory=dict)
    # 是否启用
    enabled: Optional[bool] = False
    # 路径映射
    path_mapping: Optional[list[tuple[str, str]]] = Field(default_factory=list)


class NotificationConf(BaseModel):
    """
    通知配置
    """

    # 名称
    name: Optional[str] = None
    # 类型 telegram
    type: Optional[str] = None
    # 配置
    config: Optional[dict] = Field(default_factory=dict)
    # 场景开关
    switchs: Optional[list] = Field(default_factory=list)
    # 是否启用
    enabled: Optional[bool] = False


class NotificationSwitchConf(BaseModel):
    """
    通知场景开关配置
    """

    # 场景名称
    type: str = None
    # 通知范围 all/user/admin
    action: Optional[str] = "all"




class StorageConf(BaseModel):
    """
    存储配置
    """

    # 类型 local/alipan/u115/rclone/alist
    type: Optional[str] = None
    # 名称
    name: Optional[str] = None
    # 配置
    config: Optional[dict] = Field(default_factory=dict)


class TransferDirectoryConf(BaseModel):
    """
    文件整理目录配置
    """

    # 名称
    name: Optional[str] = None
    # 优先级
    priority: Optional[int] = 0
    # 存储
    storage: Optional[str] = None
    # 下载目录
    download_path: Optional[str] = None
    # 适用媒体类型
    media_type: Optional[str] = None
    # 适用媒体类别
    media_category: Optional[str] = None
    # 下载类型子目录
    download_type_folder: Optional[bool] = False
    # 下载类别子目录
    download_category_folder: Optional[bool] = False
    # 监控方式 downloader/monitor，None为不监控
    monitor_type: Optional[str] = None
    # 监控模式 fast / compatibility
    monitor_mode: Optional[str] = "fast"
    # 整理方式 move/copy/link/softlink
    transfer_type: Optional[str] = None
    # 文件覆盖模式 always/size/never/latest
    overwrite_mode: Optional[str] = None
    # 整理到媒体库目录
    library_path: Optional[str] = None
    # 媒体库目录存储
    library_storage: Optional[str] = None
    # 智能重命名
    renaming: Optional[bool] = False
    # 刮削
    scraping: Optional[bool] = False
    # 是否发送通知
    notify: Optional[bool] = True
    # 媒体库类型子目录
    library_type_folder: Optional[bool] = False
    # 媒体库类别子目录
    library_category_folder: Optional[bool] = False


class DownloadFileSyncConf(BaseModel):
    """
    下载文件同步配置。

    定时把下载器中已完成种子的文件清单落库，供整理链判断种子是否完成、
    以及联动删除时反查种子来源使用。
    """

    # 是否启用
    enabled: bool = False
    # 同步间隔（分钟）
    interval_minutes: int = 5
    # 仅同步这些下载器（留空表示全部）
    downloaders: List[str] = Field(default_factory=list)
    # 单次同步的最大种子数，避免首次运行耗时过长
    max_torrents: int = 200
    # 同步后是否清理已不存在的种子的文件记录
    prune_missing: bool = False
    # 目录监控触发同步的节流窗口（秒），0 表示不节流
    trigger_throttle_seconds: int = 30


class SyncDelByMediaServerConf(BaseModel):
    """
    媒体服务器删除联动配置。

    监听媒体服务器的深度删除事件，反查整理记录并同步清理本地文件与下载任务。
    """

    # 是否启用
    enabled: bool = False
    # 仅处理这些媒体服务器（留空表示全部）
    servers: List[str] = Field(default_factory=list)
    # 是否同时删除下载器任务
    delete_torrent: bool = True
    # 是否同时删除下载源文件
    delete_source_file: bool = False
    # 是否清理产生的空目录
    remove_empty_dirs: bool = True
    # 试运行：只记录将要删除的内容，不实际删除
    dry_run: bool = False


class LibraryCoverGeneratorConf(BaseModel):
    """
    媒体库封面生成配置。

    取媒体库最近入库条目的海报，按固定风格渲染封面并回写媒体服务器。
    """

    # 是否启用
    enabled: bool = False
    # 执行时间（小时，0-23）
    run_hour: int = 4
    # 仅处理这些媒体库名称（留空表示全部电影/剧集库）
    libraries: List[str] = Field(default_factory=list)
    # 输出画布尺寸
    width: int = 1920
    height: int = 1080
    # 中文字号与英文字号
    zh_font_size: int = 150
    en_font_size: int = 62
    # 背景模糊半径与配色占比
    blur_size: int = 50
    color_ratio: float = 0.8


class MediaInfoProbeConf(BaseModel):
    """
    媒体文件技术信息探测配置。

    整理时调用 mediainfo 读取真实文件的宽高、编码、HDR 等信息，
    用于校正标题解析结果，并可按需写入 NFO。
    """

    # 是否启用
    enabled: bool = True
    # 是否用探测结果覆盖标题解析出的分辨率
    override_resolution: bool = True
    # 是否用探测结果补全来源（ProRes / DCP / Master 等标题里可能没有的类型）
    override_source: bool = True
    # 探测失败时是否记录告警日志
    log_failure: bool = False
