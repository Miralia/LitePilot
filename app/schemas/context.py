from typing import Optional, Dict, List, Union, Any

from pydantic import BaseModel, Field


class MetaInfo(BaseModel):
    """
    识别元数据
    """
    # 是否处理的文件
    isfile: Optional[bool] = False
    # 原字符串
    org_string: Optional[str] = None
    # 原标题
    title: Optional[str] = None
    # 副标题
    subtitle: Optional[str] = None
    # 类型 电影、电视剧
    type: Optional[str] = None
    # 名称
    name: Optional[str] = None
    # 识别的中文名
    cn_name: Optional[str] = None
    # 识别的英文名
    en_name: Optional[str] = None
    # 年份
    year: Optional[str] = None
    # 总季数
    total_season: Optional[int] = 0
    # 识别的开始季 数字
    begin_season: Optional[int] = None
    # 识别的结束季 数字
    end_season: Optional[int] = None
    # 总集数
    total_episode: Optional[int] = 0
    # 识别的开始集
    begin_episode: Optional[int] = None
    # 识别的结束集
    end_episode: Optional[int] = None
    # SxxExx
    season_episode: Optional[str] = None
    # 集列表
    episode_list: Optional[List[int]] = Field(default_factory=list)
    # Partx Cd Dvd Disk Disc
    part: Optional[str] = None
    # 识别的资源类型
    resource_type: Optional[str] = None
    # 识别的分辨率
    resource_pix: Optional[str] = None
    # 识别的制作组/字幕组
    resource_team: Optional[str] = None
    # 视频编码
    video_encode: Optional[str] = None
    # 音频编码
    audio_encode: Optional[str] = None
    # 是否为 Dolby Atmos（仅 DD+ / TrueHD 有效）
    audio_atmos: bool = False
    # HDR 规格（HDR10 / HDR10+ / DoVi / HLG / HDRVivid）
    video_hdr: Optional[List[str]] = None
    # 色彩采样（YUV422P / YUV444P）
    video_chroma: Optional[str] = None
    # 特殊版本（3D / IMAX / Open Matte）
    special_edition: Optional[List[str]] = None
    # 剪辑版本（Director's Cut 等）
    cut_version: Optional[str] = None
    # 发布信息（REPACK / PROPER / Hybrid 等）
    release_info: Optional[List[str]] = None
    # 流媒体平台
    web_source: Optional[str] = None
    # 应用的识别词信息
    apply_words: Optional[List[str]] = None
    # 剧集组
    episode_group: Optional[str] = None
    # 显式媒体数据源
    media_source: Optional[str] = None
    # 显式媒体数据源原生ID
    media_id: Optional[str] = None
    # TMDB ID
    tmdbid: Optional[int] = None
    # 豆瓣 ID
    doubanid: Optional[str] = None
    # Bangumi ID
    bangumiid: Optional[int] = None


class MediaInfo(BaseModel):
    """
    识别媒体信息
    """
    # 主来源：当前识别支持 themoviedb、bangumi，历史数据可能保留其他来源
    source: Optional[str] = None
    # 请求级刮削来源
    scrape_source: Optional[str] = None
    # 类型 电影、电视剧、合集
    type: Optional[str] = None
    # 媒体标题
    title: Optional[str] = None
    # 英文标题
    en_title: Optional[str] = None
    # 年份
    year: Optional[str] = None
    # 标题（年份）
    title_year: Optional[str] = None
    # 当前指定季，如有
    season: Optional[int] = None
    # TMDB ID
    tmdb_id: Optional[int] = None
    # IMDB ID
    imdb_id: Optional[str] = None
    # TVDB ID
    tvdb_id: Optional[int] = None
    # 豆瓣ID
    douban_id: Optional[str] = None
    # Bangumi ID
    bangumi_id: Optional[int] = None
    # 合集ID
    collection_id: Optional[int] = None
    # 其它媒体ID前缀
    mediaid_prefix: Optional[str] = None
    # 其它媒体ID值
    media_id: Optional[str] = None
    # 媒体原语种
    original_language: Optional[str] = None
    # 媒体原发行标题
    original_title: Optional[str] = None
    # 媒体发行日期
    release_date: Optional[str] = None
    # 背景图片
    backdrop_path: Optional[str] = None
    # 海报图片
    poster_path: Optional[str] = None
    # 评分
    vote_average: Optional[float] = 0.0
    # 描述
    overview: Optional[str] = None
    # 二级分类
    category: Optional[str] = ""
    # 季季集清单
    seasons: Optional[Dict[int, list]] = Field(default_factory=dict)
    # 季详情
    season_info: Optional[List[dict]] = Field(default_factory=list)
    # 别名和译名
    names: Optional[list] = Field(default_factory=list)
    # 演员
    actors: Optional[list] = Field(default_factory=list)
    # 导演
    directors: Optional[list] = Field(default_factory=list)
    # 详情链接
    detail_link: Optional[str] = None
    # 其它TMDB属性
    # 是否成人内容
    adult: Optional[bool] = False
    # 创建人
    created_by: Optional[list] = Field(default_factory=list)
    # 集时长
    episode_run_time: Optional[list] = Field(default_factory=list)
    # 风格
    genres: Optional[List[dict]] = Field(default_factory=list)
    # 首播日期
    first_air_date: Optional[str] = None
    # 首页
    homepage: Optional[str] = None
    # 语种
    languages: Optional[list] = Field(default_factory=list)
    # 最后上映日期
    last_air_date: Optional[str] = None
    # 流媒体平台
    networks: Optional[list] = Field(default_factory=list)
    # 集数
    number_of_episodes: Optional[int] = 0
    # 季数
    number_of_seasons: Optional[int] = 0
    # 原产国
    origin_country: Optional[list] = Field(default_factory=list)
    # 原名
    original_name: Optional[str] = None
    # 出品公司
    production_companies: Optional[list] = Field(default_factory=list)
    # 出品国
    production_countries: Optional[list] = Field(default_factory=list)
    # 语种
    spoken_languages: Optional[list] = Field(default_factory=list)
    # 所有发行日期
    release_dates: list = Field(default_factory=list)
    # 状态
    status: Optional[str] = None
    # 标签
    tagline: Optional[str] = None
    # 风格ID
    genre_ids: Optional[list] = Field(default_factory=list)
    # 评价数量
    vote_count: Optional[int] = 0
    # 流行度
    popularity: Optional[float] = 0.0
    # 时长
    runtime: Optional[int] = None
    # 下一集
    next_episode_to_air: Optional[dict] = Field(default_factory=dict)
    # 全部剧集组
    episode_groups: Optional[list] = Field(default_factory=list)
    # 剧集组
    episode_group: Optional[str] = None


class Context(BaseModel):
    """
    上下文
    """
    # 元数据
    meta_info: Optional[Union[MetaInfo, Any]] = None
    # 媒体信息
    media_info: Optional[Union[MediaInfo, Any]] = None
