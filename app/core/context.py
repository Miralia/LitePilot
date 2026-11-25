from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional

from app.core.config import settings
from app.core.meta import MetaBase
from app.core.metainfo import MetaInfo
from app.schemas.types import MediaType

BANGUMI_MOVIE_PLATFORMS = frozenset({"movie", "电影", "剧场版"})


@dataclass
class MediaInfo:
    """
    统一媒体信息，负责聚合各元数据源的标准字段
    """

    # 内部标记：是否命中本地识别缓存，不参与序列化
    recognize_cache_hit = False
    # 主来源：当前识别支持 themoviedb、bangumi，历史数据可能保留其他来源
    source: str = None
    # 当前数据源原生ID，主要用于保留历史与外部数据源身份
    media_id: str = None
    # 请求级刮削来源；为空时使用系统设置
    scrape_source: str = None
    # 类型 电影、电视剧
    type: MediaType = None
    # 媒体标题
    title: str = None
    # 英文标题
    en_title: str = None
    # 香港标题
    hk_title: str = None
    # 台湾标题
    tw_title: str = None
    # 新加坡标题
    sg_title: str = None
    # 年份
    year: str = None
    # 季
    season: int = None
    # TMDB ID
    tmdb_id: int = None
    # IMDB ID
    imdb_id: str = None
    # TVDB ID
    tvdb_id: int = None
    # 豆瓣ID
    douban_id: str = None
    # Bangumi ID
    bangumi_id: int = None
    # 合集ID
    collection_id: int = None
    # 媒体原语种
    original_language: str = None
    # 媒体原发行标题
    original_title: str = None
    # 媒体发行日期
    release_date: str = None
    # 背景图片
    backdrop_path: str = None
    # 海报图片
    poster_path: str = None
    # LOGO
    logo_path: str = None
    # 评分
    vote_average: float = None
    # 描述
    overview: str = None
    # 风格ID
    genre_ids: list = field(default_factory=list)
    # 所有别名和译名
    names: list = field(default_factory=list)
    # 各季的剧集清单信息
    seasons: Dict[int, list] = field(default_factory=dict)
    # 各季详情
    season_info: List[dict] = field(default_factory=list)
    # 各季的年份
    season_years: dict = field(default_factory=dict)
    # 二级分类
    category: str = ""
    # TMDB INFO
    tmdb_info: dict = field(default_factory=dict)
    # Bangumi INFO
    bangumi_info: dict = field(default_factory=dict)
    # 导演
    directors: List[dict] = field(default_factory=list)
    # 演员
    actors: List[dict] = field(default_factory=list)
    # 是否成人内容
    adult: bool = False
    # 创建人
    created_by: list = field(default_factory=list)
    # 集时长
    episode_run_time: list = field(default_factory=list)
    # 风格
    genres: List[dict] = field(default_factory=list)
    # 首播日期
    first_air_date: str = None
    # 首页
    homepage: str = None
    # 语种
    languages: list = field(default_factory=list)
    # 最后上映日期
    last_air_date: str = None
    # 流媒体平台
    networks: list = field(default_factory=list)
    # 集数
    number_of_episodes: int = None
    # 季数
    number_of_seasons: int = None
    # 原产国
    origin_country: list = field(default_factory=list)
    # 原名
    original_name: str = None
    # 出品公司
    production_companies: list = field(default_factory=list)
    # 出品国
    production_countries: list = field(default_factory=list)
    # 语种
    spoken_languages: list = field(default_factory=list)
    # 所有发行日期
    release_dates: list = field(default_factory=list)
    # 状态
    status: str = None
    # 标签
    tagline: str = None
    # 评价数量
    vote_count: int = None
    # 流行度
    popularity: float = None
    # 时长
    runtime: int = None
    # 下一集
    next_episode_to_air: dict = field(default_factory=dict)
    # 内容分级
    content_rating: str = None
    # 全部剧集组
    episode_groups: List[dict] = field(default_factory=list)
    # 剧集组
    episode_group: str = None

    def __post_init__(self):
        # 设置媒体信息
        if self.tmdb_info:
            self.set_tmdb_info(self.tmdb_info)
        if self.bangumi_info:
            self.set_bangumi_info(self.bangumi_info)

    def __setattr__(self, name: str, value: Any):
        self.__dict__[name] = value

    def __get_properties(self):
        """
        获取属性列表
        """
        property_names = []
        for member_name in dir(self.__class__):
            member = getattr(self.__class__, member_name)
            if isinstance(member, property):
                property_names.append(member_name)
        return property_names

    def from_dict(self, data: dict):
        """
        从字典中初始化
        """
        properties = self.__get_properties()
        for key, value in data.items():
            if key in properties:
                continue
            setattr(self, key, value)
        if isinstance(self.type, str):
            self.type = MediaType(self.type)

    def set_category(self, cat: str):
        """
        设置二级分类
        """
        self.category = cat or ""

    def set_tmdb_info(self, info: dict):
        """
        初始化媒信息
        """

        def __directors_actors(tmdbinfo: dict) -> Tuple[List[dict], List[dict]]:
            """
            查询导演和演员
            :param tmdbinfo: TMDB元数据
            :return: 导演列表，演员列表
            """
            """
            "cast": [
              {
                "adult": false,
                "gender": 2,
                "id": 3131,
                "known_for_department": "Acting",
                "name": "Antonio Banderas",
                "original_name": "Antonio Banderas",
                "popularity": 60.896,
                "profile_path": "/iWIUEwgn2KW50MssR7tdPeFoRGW.jpg",
                "cast_id": 2,
                "character": "Puss in Boots (voice)",
                "credit_id": "6052480e197de4006bb47b9a",
                "order": 0
              }
            ],
            "crew": [
              {
                "adult": false,
                "gender": 2,
                "id": 5524,
                "known_for_department": "Production",
                "name": "Andrew Adamson",
                "original_name": "Andrew Adamson",
                "popularity": 9.322,
                "profile_path": "/qqIAVKAe5LHRbPyZUlptsqlo4Kb.jpg",
                "credit_id": "63b86b2224b33300a0585bf1",
                "department": "Production",
                "job": "Executive Producer"
              }
            ]
            """
            if not tmdbinfo:
                return [], []
            _credits = tmdbinfo.get("credits")
            if not _credits:
                return [], []
            directors = []
            actors = []
            for cast in _credits.get("cast") or []:
                if cast.get("known_for_department") == "Acting":
                    actors.append(cast)
            for crew in _credits.get("crew") or []:
                if crew.get("job") in ["Director", "Writer", "Editor", "Producer"]:
                    directors.append(crew)
            return directors, actors

        if not info:
            return
        # 来源
        self.source = "themoviedb"
        # 本体
        self.tmdb_info = info
        # 类型
        if isinstance(info.get('media_type'), MediaType):
            self.type = info.get('media_type')
        elif info.get('media_type'):
            self.type = MediaType.MOVIE if info.get("media_type") == "movie" else MediaType.TV
        else:
            self.type = MediaType.MOVIE if info.get("title") else MediaType.TV
        # TMDBID
        self.tmdb_id = info.get('id')
        if not self.tmdb_id:
            return
        # 额外ID
        if info.get("external_ids"):
            self.tvdb_id = info.get("external_ids", {}).get("tvdb_id")
            self.imdb_id = info.get("external_ids", {}).get("imdb_id")
        # 合集ID
        self.collection_id = info.get('collection_id')
        # 评分
        self.vote_average = round(float(info.get('vote_average')), 1) if info.get('vote_average') else 0
        # 描述
        self.overview = info.get('overview')
        # 风格
        self.genre_ids = info.get('genre_ids') or []
        # 原语种
        self.original_language = info.get('original_language')
        # 英文标题
        self.en_title = info.get('en_title')
        # 香港标题
        self.hk_title = info.get('hk_title')
        # 台湾标题
        self.tw_title = info.get('tw_title')
        # 新加坡标题
        self.sg_title = info.get('sg_title')
        if self.type == MediaType.MOVIE:
            # 标题
            self.title = info.get('title')
            # 原标题
            self.original_title = info.get('original_title')
            # 发行日期
            self.release_date = info.get('release_date')
            if self.release_date:
                # 年份
                self.year = self.release_date[:4]
            # 所有发行日期
            self.release_dates = [
                {
                    "date": release_date.get("release_date"),
                    "iso_code": result.get("iso_3166_1"),
                    "note": release_date.get("note"),
                    "type": release_date.get("type"),
                }
                for result in info.get("release_dates", {}).get("results", [])
                for release_date in result.get("release_dates", [])
                if release_date.get("release_date")
            ]
        else:
            # 电视剧
            self.title = info.get('name')
            # 原标题
            self.original_title = info.get('original_name')
            # 发行日期
            self.release_date = info.get('first_air_date')
            if self.release_date:
                # 年份
                self.year = self.release_date[:4]
            # 季集信息
            if info.get('seasons'):
                self.season_info = info.get('seasons')
                for seainfo in info.get('seasons'):
                    # 季
                    season = seainfo.get("season_number")
                    if season is None:
                        continue
                    # 集
                    episode_count = seainfo.get("episode_count")
                    self.seasons[season] = list(range(1, episode_count + 1))
                    # 年份
                    air_date = seainfo.get("air_date")
                    if air_date:
                        self.season_years[season] = air_date[:4]
            # 剧集组
            if info.get("episode_groups"):
                self.episode_groups = info.pop("episode_groups").get("results") or []

        # 海报
        if path := info.get('poster_path'):
            self.poster_path = settings.TMDB_IMAGE_URL(path)
        # 背景
        if path := info.get('backdrop_path'):
            self.backdrop_path = settings.TMDB_IMAGE_URL(path)
        # 导演和演员
        self.directors, self.actors = __directors_actors(info)
        # 别名和译名
        self.names = info.get('names') or []
        # 剩余属性赋值
        for key, value in info.items():
            if not value:
                continue
            if not hasattr(self, key):
                continue
            current_value = getattr(self, key)
            if current_value:
                continue
            if current_value is None:
                setattr(self, key, value)
            elif type(current_value) is type(value):
                setattr(self, key, value)

    @staticmethod
    def get_bangumi_media_type(info: dict) -> MediaType:
        """
        根据Bangumi媒介平台获取标准媒体类型，未知平台兼容回退为电视剧

        :param info: Bangumi条目信息
        :return: 标准媒体类型
        """
        platform = str(info.get("platform") or "").strip().casefold()
        if platform in BANGUMI_MOVIE_PLATFORMS:
            return MediaType.MOVIE
        return MediaType.TV

    def set_bangumi_info(self, info: dict) -> None:
        """
        初始化Bangumi信息
        """
        if not info:
            return
        # 来源
        self.source = "bangumi"
        # 本体
        self.bangumi_info = info
        # Bangumi ID
        self.bangumi_id = info.get("id")
        # 类型
        if not self.type:
            self.type = self.get_bangumi_media_type(info)
        # 标题
        if not self.title:
            self.title = info.get("name_cn") or info.get("name")
        # 原语种标题
        if not self.original_title:
            self.original_title = info.get("name")
        # 识别标题中的季
        meta = MetaInfo(self.title)
        # 季
        if self.season is None:
            self.season = meta.begin_season
        # 评分
        if not self.vote_average:
            rating = info.get("rating")
            if rating:
                vote_average = float(rating.get("score"))
            else:
                vote_average = 0
            self.vote_average = vote_average
        # 发行日期
        if not self.release_date:
            self.release_date = info.get("date") or info.get("air_date")
            # 年份
            if not self.year:
                self.year = self.release_date[:4] if self.release_date else None
        # 海报
        if not self.poster_path:
            if info.get("images"):
                self.poster_path = info.get("images", {}).get("large")
            if not self.poster_path and info.get("image"):
                self.poster_path = info.get("image")
        # 简介
        if not self.overview:
            self.overview = info.get("summary")
        # 别名
        if not self.names:
            infobox = info.get("infobox")
            if infobox:
                akas = [item.get("value") for item in infobox if item.get("key") == "别名"]
                if akas:
                    if isinstance(akas[0], list):
                        self.names = [aka.get("v") if isinstance(aka, dict) else aka for aka in akas[0]]
                    elif isinstance(akas[0], str):
                        self.names = [akas[0]]

        # 剧集
        if self.type == MediaType.TV and not self.seasons:
            meta = MetaInfo(self.title)
            season = meta.begin_season if meta.begin_season is not None else 1
            episodes_count = info.get("total_episodes") or info.get("eps")
            if episodes_count:
                self.seasons[season] = list(range(1, episodes_count + 1))
                self.number_of_episodes = episodes_count
                self.number_of_seasons = 1
        # 风格
        if not self.genres:
            self.genres = [
                {"id": tag.get("name"), "name": tag.get("name")}
                for tag in info.get("tags") or []
                if tag.get("name")
            ]
        # 制作公司与导演
        if info.get("infobox"):
            companies = []
            directors = []
            for item in info.get("infobox"):
                values = item.get("value")
                if not isinstance(values, list):
                    values = [values]
                normalized_values = [
                    value.get("v") if isinstance(value, dict) else value
                    for value in values
                    if value
                ]
                if item.get("key") in {"动画制作", "制作"}:
                    companies.extend({"name": value} for value in normalized_values)
                elif item.get("key") == "导演":
                    directors.extend({"name": value} for value in normalized_values)
            if companies and not self.production_companies:
                self.production_companies = companies
            if directors and not self.directors:
                self.directors = directors
        # 演员
        if not self.actors:
            self.actors = info.get("actors") or []

    @property
    def title_year(self):
        if self.title:
            return "%s (%s)" % (self.title, self.year) if self.year else self.title
        return ""

    @property
    def detail_link(self):
        """
        TMDB媒体详情页地址
        """
        if self.tmdb_id:
            if self.type == MediaType.MOVIE:
                return "https://www.themoviedb.org/movie/%s" % self.tmdb_id
            else:
                return "https://www.themoviedb.org/tv/%s" % self.tmdb_id
        elif self.douban_id:
            return "https://movie.douban.com/subject/%s" % self.douban_id
        elif self.bangumi_id:
            return "http://bgm.tv/subject/%s" % self.bangumi_id
        return ""

    @property
    def stars(self):
        """
        返回评分星星个数
        """
        if not self.vote_average:
            return ""
        return "".rjust(int(self.vote_average), "★")

    @property
    def vote_star(self):
        if self.vote_average:
            return "评分：%s" % self.stars
        return ""

    def get_backdrop_image(self, default: bool = False):
        """
        返回背景图片地址
        """
        if self.backdrop_path:
            return self.backdrop_path.replace("original", "w500")
        return default or ""

    def get_message_image(self, default: Optional[bool] = None):
        """
        返回消息图片地址
        """
        if self.backdrop_path:
            return self.backdrop_path.replace("original", "w500")
        return self.get_poster_image(default=default)

    def get_poster_image(self, default: Optional[bool] = None):
        """
        返回海报图片地址
        """
        if self.poster_path:
            return self.poster_path.replace("original", "w500")
        return default or ""

    def get_overview_string(self, max_len: Optional[int] = 140):
        """
        返回带限定长度的简介信息
        :param max_len: 内容长度
        :return:
        """
        overview = str(self.overview).strip()
        placeholder = ' ...'
        max_len = max(len(placeholder), max_len - len(placeholder))
        overview = (overview[:max_len] + placeholder) if len(overview) > max_len else overview
        return overview

    def to_dict(self):
        """
        返回字典
        """
        dicts = vars(self).copy()
        dicts["type"] = self.type.value if self.type else None
        dicts["detail_link"] = self.detail_link
        dicts["title_year"] = self.title_year
        dicts["tmdb_info"] = None
        dicts["bangumi_info"] = None
        source_ids = {
            "themoviedb": self.tmdb_id,
            "bangumi": self.bangumi_id,
            "douban": self.douban_id,
        }
        media_source = self.source or next(
            (source for source, media_id in source_ids.items() if media_id is not None),
            None,
        )
        dicts["source"] = media_source
        dicts["mediaid_prefix"] = media_source
        media_id = self.media_id or source_ids.get(media_source)
        dicts["media_id"] = str(media_id) if media_id is not None else None
        return dicts

    def clear(self):
        """
        去除多余数据，减小体积
        """
        self.tmdb_info = {}
        self.bangumi_info = {}
        self.seasons = {}
        self.genres = []
        self.season_info = []
        self.names = []
        self.actors = []
        self.directors = []
        self.production_companies = []
        self.production_countries = []
        self.spoken_languages = []
        self.networks = []
        self.next_episode_to_air = {}
        self.episode_groups = []


@dataclass
class Context:
    """
    上下文对象
    """

    # 识别信息
    meta_info: MetaBase = None
    # 媒体信息
    media_info: MediaInfo = None

    def to_dict(self):
        """
        转换为字典
        """
        return {
            "meta_info": self.meta_info.to_dict() if self.meta_info else None,
            "media_info": self.media_info.to_dict() if self.media_info else None,
        }
