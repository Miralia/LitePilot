from enum import Enum
from typing import Optional


# 媒体类型
class MediaType(Enum):
    MOVIE = '电影'
    TV = '电视剧'
    COLLECTION = '系列'
    UNKNOWN = '未知'

    @staticmethod
    def from_agent(key: str) -> Optional["MediaType"]:
        """'movie' -> MediaType.MOVIE, 'tv' -> MediaType.TV, 否则 None"""
        _map = {"movie": MediaType.MOVIE, "tv": MediaType.TV}
        return _map.get(key.strip().lower() if key else "")

    def to_agent(self) -> str:
        """MediaType.MOVIE -> 'movie', MediaType.TV -> 'tv', 其他返回 .value"""
        return {MediaType.MOVIE: "movie", MediaType.TV: "tv"}.get(self, self.value)




# 排序类型枚举


# 种子状态
class TorrentStatus(Enum):
    TRANSFER = "可转移"
    DOWNLOADING = "下载中"


# 下载器任务查询状态
class TorrentQueryStatus(Enum):
    ALL = "all"
    TRANSFER = "transfer"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    PAUSED = "paused"


# 下载器任务归一状态
class DownloadTaskState(Enum):
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"


# 异步广播事件
class EventType(Enum):
    # 执行命令
    CommandExcute = "command.excute"
    # 媒体文件整理完成
    TransferComplete = "transfer.complete"
    # 媒体文件整理失败
    TransferFailed = "transfer.failed"
    # 字幕整理完成
    SubtitleTransferComplete = "transfer.subtitle.complete"
    # 字幕整理失败
    SubtitleTransferFailed = "transfer.subtitle.failed"
    # 音频文件整理完成
    AudioTransferComplete = "transfer.audio.complete"
    # 音频文件整理失败
    AudioTransferFailed = "transfer.audio.failed"
    # 删除下载源文件
    DownloadFileDeleted = "downloadfile.deleted"
    # 收到Webhook消息
    WebhookMessage = "webhook.message"
    # 发送消息通知
    NoticeMessage = "notice.message"
    # 系统错误
    SystemError = "system.error"
    # 刮削元数据
    MetadataScrape = "metadata.scrape"
    # 模块需要重载
    ModuleReload = "module.reload"
    # 配置项更新
    ConfigChanged = "config.updated"


# EventType中文名称翻译字典
EVENT_TYPE_NAMES = {
    EventType.CommandExcute: "执行命令",
    EventType.TransferComplete: "整理完成",
    EventType.TransferFailed: "整理失败",
    EventType.SubtitleTransferComplete: "字幕整理完成",
    EventType.SubtitleTransferFailed: "字幕整理失败",
    EventType.AudioTransferComplete: "音频整理完成",
    EventType.AudioTransferFailed: "音频整理失败",
    EventType.DownloadFileDeleted: "删除下载源文件",
    EventType.WebhookMessage: "收到Webhook消息",
    EventType.NoticeMessage: "发送消息通知",
    EventType.SystemError: "系统错误",
    EventType.MetadataScrape: "刮削元数据",
    EventType.ModuleReload: "模块重载",
    EventType.ConfigChanged: "配置项更新",
}


# 系统配置Key字典
class SystemConfigKey(Enum):
    # 入库后是否刷新媒体服务器媒体库
    RefreshMediaServerAfterTransfer = "RefreshMediaServerAfterTransfer"
    # 下载器配置
    Downloaders = "Downloaders"
    # 媒体服务器配置
    MediaServers = "MediaServers"
    # 消息通知配置
    Notifications = "Notifications"
    # 通知场景开关设置
    NotificationSwitchs = "NotificationSwitchs"
    # 目录配置
    Directories = "Directories"
    # 挂载型本地盘是否删除空目录
    MountedLocalDiskDeleteEmptyDirs = "MountedLocalDiskDeleteEmptyDirs"
    # 存储配置
    Storages = "Storages"
    # 自定义制作组/字幕组
    CustomReleaseGroups = "CustomReleaseGroups"
    # 自定义占位符
    Customization = "Customization"
    # 自定义识别词
    CustomIdentifiers = "CustomIdentifiers"
    # 集数定位规则词表
    EpisodeFormatRuleTable = "EpisodeFormatRuleTable"
    # 转移屏蔽词
    TransferExcludeWords = "TransferExcludeWords"
    # 自定义流媒体平台词表
    CustomStreamingPlatforms = "CustomStreamingPlatforms"
    # 特殊版本词表（3D / IMAX / Open Matte）
    SpecialEditionWords = "SpecialEditionWords"
    # 剪辑版本词表（Director's Cut / Extended Cut 等）
    CutVersionWords = "CutVersionWords"
    # 发布信息词表（REPACK / PROPER / Hybrid 等）
    ReleaseInfoWords = "ReleaseInfoWords"
    # 流媒体平台输出形态（全称/简称）
    StreamingPlatformDisplay = "StreamingPlatformDisplay"
    # 媒体文件技术信息探测
    MediaInfoProbe = "MediaInfoProbe"
    # 整理后源文件清理
    MediaSourceCleanup = "MediaSourceCleanup"
    # 通知发送时间
    NotificationSendTime = "NotificationSendTime"
    # 通知消息格式模板
    NotificationTemplates = "NotificationTemplates"
    # 通知中心清理时间
    NotificationClearBefore = "NotificationClearBefore"
    # 刮削开关设置
    ScrapingSwitchs = "ScrapingSwitchs"
    # 下载文件同步开关
    DownloadFileSync = "DownloadFileSync"
    # 媒体服务器删除同步开关
    SyncDelByMediaServer = "SyncDelByMediaServer"
    # 媒体库封面生成开关
    LibraryCoverGenerator = "LibraryCoverGenerator"
    # 配置向导状态
    SetupWizardState = "SetupWizardState"
    # 绿联影视登录会话缓存


# 处理进度Key字典
class ProgressKey(Enum):
    # 搜索
    Search = "search"
    # 整理
    FileTransfer = "filetransfer"
    # 批量重命名
    BatchRename = "batchrename"


# 媒体图片类型
class MediaImageType(Enum):
    Poster = "poster_path"
    Backdrop = "backdrop_path"


# 消息类型
class NotificationType(Enum):
    # 资源下载
    Download = "资源下载"
    # 整理入库
    Organize = "整理入库"
    # 媒体服务器通知
    MediaServer = "媒体服务器"
    # 处理失败需要人工干预
    Manual = "手动处理"
    # 其它消息
    Other = "其它"


class ContentType(str, Enum):
    """
    消息内容类型
    操作状态的通知消息类型标识
    """
    # 入库成功
    OrganizeSuccess = "organizeSuccess"


# 消息渠道
class MessageChannel(Enum):
    """
    消息渠道
    """
    Telegram = "Telegram"
    Web = "Web"


# 下载器类型
class DownloaderType(Enum):
    # Qbittorrent
    Qbittorrent = "Qbittorrent"
    # Aria2
    # Aria2 = "Aria2"


# 媒体服务器类型
class MediaServerType(Enum):
    # Emby
    Emby = "Emby"


# 识别器类型
class MediaRecognizeType(Enum):
    # TMDB
    TMDB = "TheMovieDb"
    # bangumi
    Bangumi = "Bangumi"


# 用户配置Key字典
class UserConfigKey(Enum):
    # 监控面板
    Dashboard = "Dashboard"


# 支持的存储类型
class StorageSchema(Enum):
    # 存储类型
    Local = "local"
    SMB = "smb"
    # 自定义（WebDAV 等由用户自建挂载，目录层面统一按本地处理）
    Custom = "custom"


# 模块类型
class ModuleType(Enum):
    # 下载器
    Downloader = "downloader"
    # 媒体服务器
    MediaServer = "mediaserver"
    # 消息服务
    Notification = "notification"
    # 媒体识别
    MediaRecognize = "mediarecognize"
    # 其它
    Other = "other"


# 其他杂项模块类型
class OtherModulesType(Enum):
    # 文件整理
    FileManager = "文件整理"
    # PostgreSQL
    PostgreSQL = "PostgreSQL"
    # Redis
    Redis = "Redis"


class NameValueEnum(Enum):
    """支持通过 name 或 value 实例化的枚举基类"""

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.name.lower() == value.lower() or member.value == value:
                    return member
        return None


# 刮削策略
class ScrapingPolicy(NameValueEnum):
    MISSINGONLY = "仅缺失"
    SKIP = "跳过"
    OVERWRITE = "覆盖"


# 刮削目标类型
class ScrapingTarget(NameValueEnum):
    MOVIE = "电影"
    TV = "电视剧"
    SEASON = "季"
    EPISODE = "集"


# 刮削元数据类型
class ScrapingMetadata(NameValueEnum):
    NFO = "NFO"
    POSTER = "海报"
    BACKDROP = "背景图"
    LOGO = "Logo"
    BANNER = "横幅图"
    THUMB = "缩略图"
    DISC = "光盘图"
    CLEARART = "透明艺术图"
    LANDSCAPE = "横版缩略图"
