export type MediaDataSource = 'themoviedb' | 'douban' | 'bangumi' | (string & {})

// 手动刮削选项
export interface ManualScrapeOptions {
  // 媒体数据源
  media_source: MediaDataSource
  // 数据源原生ID
  media_id?: string
  // 媒体类型
  type_name?: string
}

// 历史记录
export interface TransferHistory {
  // ID
  id: number
  // 源存储
  src_storage?: string
  // 目标存储
  dest_storage?: string
  // 源目录
  src?: string
  // 目的目录
  dest?: string
  // 转移模式link/copy/move/softlink/rclone_copy/rclone_move
  mode?: string
  // 类型：电影、电视剧
  type?: string
  // 二级分类
  category?: string
  // 标题
  title?: string
  // 年份
  year?: string
  // TMDBID
  tmdbid?: number
  // IMDBID
  imdbid?: string
  // TVDBID
  tvdbid?: number
  // 豆瓣ID
  doubanid?: string
  // Bangumi ID
  bangumiid?: number
  // 媒体数据源
  media_source?: MediaDataSource
  // 数据源原生ID
  media_id?: string
  // 季Sxx
  seasons?: string
  // 集Exx
  episodes?: string
  // 海报
  image?: string
  // 下载器Hash
  download_hash?: string
  // 状态 1-成功，0-失败
  status: boolean
  // 失败原因
  errmsg?: string
  // 日期
  date?: string
  // 源文件项
  src_fileitem?: FileItem
}

// 下载历史记录
export interface DownloadHistory {
  // ID
  id: number
  // 保存路径
  path?: string
  // 类型：电影、电视剧
  type?: string
  // 标题
  title?: string
  // 年份
  year?: string
  // TMDB ID
  tmdbid?: number
  // IMDB ID
  imdbid?: string
  // TVDB ID
  tvdbid?: number
  // 豆瓣 ID
  doubanid?: string
  // Bangumi ID
  bangumiid?: number
  // 媒体数据源
  media_source?: MediaDataSource
  // 数据源原生 ID
  media_id?: string
  // 季 Sxx
  seasons?: string
  // 集 Exx
  episodes?: string
  // 背景图
  image?: string
  // 海报
  poster?: string
  // 下载器 Hash
  download_hash?: string
  // 种子名称
  torrent_name?: string
  // 种子描述
  torrent_description?: string
  // 站点
  torrent_site?: string
  // 下载用户 ID
  userid?: string
  // 下载用户名或插件名
  username?: string
  // 下载渠道
  channel?: string
  // 创建时间
  date?: string
  // 附加信息
  note?: unknown
  // 自定义媒体类别
  media_category?: string
  // 自定义剧集组
  episode_group?: string
}

// 媒体信息
// TMDB季信息
export interface TmdbSeason {
  // 上映日期
  air_date?: string
  // 总集数
  episode_count?: number
  // 季名称
  name?: string
  // 描述
  overview?: string
  // 海报
  poster_path?: string
  // 季号
  season_number?: number
  // 评分
  vote_average?: number
}

// TMDB集信息
export interface TmdbEpisode {
  // 上映日期
  air_date?: string
  // 集号
  episode_number?: number
  // 剧集名称
  name?: string
  // 描述
  overview?: string
  // 时长
  runtime?: number
  // 季号
  season_number?: number
  // 海报
  still_path?: string
  // 评分
  vote_average?: number
  // 演职人员
  crew: Object[]
  // 嘉宾
  guest_stars: Object[]
}

// 发行信息
export interface MediaRelease {
  // 发行日期
  date: string
  // 发行地区
  iso_code: string
  // 备注
  note?: string
  // 发行类型
  type: number
}

export interface MediaInfo {
  // 来源：themoviedb、douban、bangumi
  source?: string
  // 类型 电影、电视剧、合集
  type?: string
  // 媒体标题
  title?: string
  // 年份
  year?: string
  // 标题（年）
  title_year?: string
  // 季号
  season?: number
  // TMDB ID
  tmdb_id?: number
  // IMDB ID
  imdb_id?: string
  // TVDB ID
  tvdb_id?: string
  // 豆瓣ID
  douban_id?: string
  // Bangumi ID
  bangumi_id?: string | number
  // AniDB ID
  anidb_id?: number
  // 合集ID
  collection_id?: number
  // 其它媒体ID前缀
  mediaid_prefix?: string
  // 其它媒体ID值
  media_id?: string
  // 媒体原语种
  original_language?: string
  // 媒体原发行标题
  original_title?: string
  // 媒体发行日期
  release_date?: string
  // 背景图片
  backdrop_path?: string
  // 海报图片
  poster_path?: string
  // 评分
  vote_average?: number
  // 描述
  overview?: string
  // 二级分类
  category?: string
  // 详情页面
  detail_link?: string
  // 季详情
  season_info?: TmdbSeason[]
  // 导演
  directors?: any[]
  // 演员
  actors?: any[]
  // 成人内容
  adult?: boolean
  // 创建人
  created_by?: string[]
  // 集时长
  episode_run_time: string[]
  // 风格
  genres?: string[]
  // 首映日期
  first_air_date?: string
  // 主页
  homepage?: string
  // 语言
  languages?: string[]
  // 最后更新日期
  last_air_date?: string
  // 流媒体
  networks?: string[]
  // 总集数
  number_of_episodes?: number
  // 总季数
  number_of_seasons?: number
  // 原产国
  origin_country: string[]
  // 原名
  original_name?: string
  // 出品公司
  production_companies?: any[]
  // 出品国
  production_countries?: any[]
  // 语种
  spoken_languages?: string[]
  // 数字/实体发行日期
  release_dates?: MediaRelease[]
  // 状态
  status?: string
  // 标签
  tagline?: string
  // 评分人数
  vote_count?: number
  // 流行度
  popularity?: number
  // 时长
  runtime?: number
  // 下一集
  next_episode_to_air?: object
  // 别名
  names?: string[]
  // 剧集组
  episode_group?: string
}

// TMDB人物信息
export interface Person {
  // 来源：themoviedb、douban、bangumi
  source?: string
  // ID
  id?: number
  // 名称
  name?: string
  // 角色
  character?: string
  // 性别
  gender?: number | string
  // 生日
  birthday?: string
  // 详情
  biography?: string
  // images large/normal douban、bangumi
  images?: { [key: string]: string }
  // themoviedb
  // themoviedb图片
  profile_path?: string
  // 原名
  original_name?: string
  // 演员ID
  credit_id?: string
  // 别名
  also_known_as?: string[]
  // 卒日
  deathday?: string
  // IMDB ID
  imdb_id?: string
  // 部门
  known_for_department?: string
  // 出生地
  place_of_birth?: string
  // 热度
  popularity?: number
  // douban
  // 角色
  roles?: string[]
  // 简介
  title?: string
  // 详情页面
  url?: string
  // 图片
  avatar?: any
  // 别名
  latin_name?: string
  // bangumi
  // 类型
  type?: number | string
  // 角色
  career?: string[]
  // 关系
  relation?: string
}

// 渲染结构
export interface RenderProps {
  component: string
  text?: string
  html?: string
  content?: any
  slots?: any
  props?: any
  events?: any
}

// 仪表板组件
export interface DashboardItem {
  // ID
  id: string
  // 名称
  name: string
  // 插件的仪表板key
  key: string
  // 全局配置
  attrs: { [key: string]: any }
  // col列数
  cols: { [key: string]: number }
  // Grid行数
  rows?: number
  // 页面元素
  elements: RenderProps[]
  // 渲染方式
  render_mode?: string
}

// 识别元数据
export interface MetaInfo {
  // 是否处理的文件
  isfile: boolean
  // 原字符串
  org_string?: string
  // 原标题（未经识别词转换）
  title?: string
  // 副标题
  subtitle?: string
  // 类型 电影、电视剧
  type: string
  // 识别的中文名
  cn_name?: string
  // 识别的英文名
  en_name?: string
  // 年份
  year?: string
  // 总季数
  total_season: number
  // 识别的开始季 数字
  begin_season?: number
  // 识别的结束季 数字
  end_season?: number
  // 总集数
  total_episode: number
  // 识别的开始集
  begin_episode?: number
  // 识别的结束集
  end_episode?: number
  // Partx Cd Dvd Disk Disc
  part?: string
  // 识别的资源类型
  resource_type?: string
  // 识别的分辨率
  resource_pix?: string
  // 识别的制作组/字幕组
  resource_team?: string
  // 视频编码
  video_encode?: string
  // 音频编码
  audio_encode?: string
  // 是否为 Dolby Atmos（仅 DD+ / TrueHD 有效）
  audio_atmos?: boolean
  // HDR 规格
  video_hdr?: string[]
  // 色彩采样
  video_chroma?: string
  // 特殊版本
  special_edition?: string[]
  // 剪辑版本
  cut_version?: string
  // 发布信息
  release_info?: string[]
  // 名称（自动中英文）
  name: string
  // SXX-SXX
  season: string
  // SXX-SXX 有季号才返回
  sea: string
  // begin_season 的数字，电视剧没有季的返回1
  season_seq: string
  // 季的数组
  season_list: number[]
  // Exx-Exx
  episode: string
  // 集的数组
  episode_list: number[]
  // ExxExx
  episodes: string
  // xx-xx
  episode_seqs: string
  // begin_episode 的数字
  episode_seq: string
  // SxxExx
  season_episode: string
  // 发布组/字幕组字符串
  release_group: string
  // 视频编码
  video_term: string
  // 音频编码
  audio_term: string
  // 流媒体平台
  web_source: string
  // 应用的自定义识别词
  apply_words: string[]
}

// 上下文信息
export interface Context {
  // 元信息
  meta_info: MetaInfo
  // 媒体信息
  media_info: MediaInfo
}

// 用户信息
export interface User {
  // 用户ID
  id: number
  // 用户名称
  name: string
  // 用户密码
  password: string
  // 用户邮箱
  email: string
  // 是否激活
  is_active: boolean
  // 是否管理员
  is_superuser: boolean
  // 头像
  avatar: string
  // 是否开启二次验证
  is_otp: boolean
  // 用户权限 json
  permissions: { [key: string]: any }
  // 用户个性化设置 json
  settings: { [key: string]: string | null }
  // 昵称
  nickname?: string
}

// 通行密钥
export interface PassKey {
  id: number
  name: string
  created_at: string
  last_used_at?: string
  aaguid?: string
  transports?: string
}

// 存储空间
export interface Storage {
  // 总空间
  total_storage: number
  // 已使用空间
  used_storage: number
}

// 媒体统计
export interface MediaStatistic {
  // 电影总数
  movie_count: number
  // 电视剧总数
  tv_count: number
  // 电视剧总集数，未获取时为 null
  episode_count: number | null
  // 用户数量
  user_count: number
  // 本月新增电影数量
  movie_count_month: number
  // 本月新增电视剧数量
  tv_count_month: number
  // 本月新增剧集数量
  episode_count_month: number
}

// 后台进程
export interface Process {
  // 进程ID
  pid: number
  // 进程名称
  name: string
  // 进程状态
  status: string
  // 进程启动时间
  create_time: number
  // 进程运行时间
  run_time: number
  // 进程CPU占用率
  cpu: number
  // 进程内存占用
  memory: number
}

// 仪表板系统摘要
export interface DashboardSystemInfo {
  // 主机名称
  hostname: string
  // 操作系统名称
  operating_system: string
  // LitePilot 运行时间，单位秒
  runtime: number
  // LitePilot 后端版本
  version: string
}

// 下载器信息
export interface DownloaderInfo {
  // 下载速度
  download_speed: number
  // 上传速度
  upload_speed: number
  // 下载量
  download_size: number
  // 上传量
  upload_size: number
  // 剩余空间
  free_space: number
}

// 仪表板系统内存信息
export interface DashboardMemoryInfo {
  // 总内存字节数
  total: number
  // 已使用内存字节数，不包含缓存
  used: number
  // 缓存与缓冲区占用字节数
  cached: number
  // 可用内存字节数
  available: number
  // 已使用内存占总内存百分比，不包含缓存
  usage: number
}

// 定时服务进度信息
export interface ScheduleProgress {
  // ID
  id?: string
  // 名称
  name?: string
  // 多语言名称
  name_i18n?: string
  // 提供者
  provider?: string
  // 多语言提供者
  provider_i18n?: string
  // 是否正在执行
  enable?: boolean
  // 当前完成百分比
  value?: number
  // 当前进度文本
  text?: string
  // 多语言进度文本
  text_i18n?: string
  // 执行状态
  status?: string
  // 最近一次执行是否成功
  success?: boolean
  // 最近一次开始时间
  started_at?: string
  // 最近一次结束时间
  finished_at?: string
  // 最近一次错误信息
  error?: string
  // 多语言错误信息
  error_i18n?: string
  // 扩展数据
  data?: Record<string, unknown>
}

// 定时服务信息
export interface ScheduleInfo {
  // ID
  id: string
  // 名称
  name: string
  // 多语言名称
  name_i18n?: string
  // 提供者
  provider: string
  // 多语言提供者
  provider_i18n?: string
  // 状态
  status: string
  // 多语言状态
  status_i18n?: string
  // 下次运行时间
  next_run: string
  // 多语言下次运行时间
  next_run_i18n?: string
  // 当前完成百分比
  progress?: number
  // 进度文本
  progress_text?: string
  // 多语言进度文本
  progress_text_i18n?: string
  // 是否正在更新进度
  progress_enable?: boolean
  // 进度详情
  progress_detail?: ScheduleProgress
}

// 消息通知
export interface NotificationSwitch {
  // 消息类型
  mtype: string
  // 开关
  wechat: boolean
  telegram: boolean
  slack: boolean
  synologychat: boolean
  vocechat: boolean
  webpush: boolean
}

// 文件浏览接口
export interface EndPoints {
  // 文件列表
  list: any
  // 创建目录
  mkdir: any
  // 删除文件
  delete: any
  // 下载文件
  download: any
  // 图片预览
  image: any
  // 重命名
  rename: any
}

// 文件浏览项目
export interface FileItem {
  // 存储
  storage: string
  // 类型 dir/file
  type: string
  // 文件名
  name: string
  // 文件名不含扩展名
  basename?: string
  // 文件路径
  path: string
  // 文件扩展名
  extension?: string
  // 文件大小
  size?: number
  // 文件子元素
  children?: FileItem[]
  // 文件创建时间
  modify_time?: number
  // 文件ID
  fileid?: string
  // 上级文件ID
  parent_fileid?: string
  // 缩略图
  thumbnail?: string
  // pickcode
  pickcode?: string
  // drive_id
  drive_id?: string
}

// 媒体服务器播放条目
export interface MediaServerPlayItem {
  // ID
  id?: string | number
  // 媒体服务器项目ID
  item_id?: string | number
  // 媒体服务器ID
  server_id?: string
  // 标题
  title: string
  // 副标题
  subtitle?: string
  // 类型
  type?: string
  // 海报
  image?: string
  // 链接
  link?: string
  // 播放百分比
  percent?: number
  // 媒体服务器类型
  server_type?: string
  // 图片是否需要Cookies
  use_cookies?: boolean
}

// 媒体服务器媒体库
export interface MediaServerLibrary {
  // 服务器名称
  server: string
  // ID
  id?: string | number
  // 媒体服务器项目ID
  item_id?: string | number
  // 媒体服务器ID
  server_id?: string
  // 名称
  name: string
  // 路径
  path?: string
  // 类型
  type?: string
  // 库内媒体数量
  item_count?: number
  // 图片
  image?: string
  // 图片列表
  image_list?: string[]
  // 链接
  link?: string
  // 媒体服务器类型
  server_type?: string
  // 图片是否需要Cookies
  use_cookies?: boolean
}

// 消息通知
export interface Message {
  // 消息ID
  id?: number
  // 消息渠道
  channel?: string
  // 消息来源
  source?: string
  // 消息类型
  mtype?: string
  // 消息标题
  title?: string
  // 消息内容
  text?: string
  // 消息链接
  link?: string
  // 消息图片
  image?: string
  // 消息时间
  date?: string
  // 登记时间
  reg_time?: string
  // 用户ID
  userid?: string
  // 消息方向：0-接收，1-发送
  action?: number
  // JSON
  note?: string | any[] | Record<string, any>
}

// 系统通知
export interface SystemNotification extends Message {
  // 通知类型 user/system/plugin/notification
  type?: string
  // 通知时间
  date?: string
  // 是否已读
  read?: boolean
}

// 下载器配置
export interface DownloaderConf {
  // 名称
  name: string
  // 类型 qbittorrent/transmission
  type: string
  // 是否默认
  default: boolean
  // 配置
  config: { [key: string]: any }
  // 是否启用
  enabled: boolean
  // 路径映射
  path_mapping?: Array<[storagePath: string, downloadPath: string]>
}

// 通知配置
export interface NotificationConf {
  // 名称
  name: string
  // 类型 telegram/wechat/vocechat/synologychat
  type: string
  // 配置
  config: { [key: string]: any }
  // 场景开关
  switchs?: string[]
  // 是否启用
  enabled: boolean
}

// 通知场景开关配置
export interface NotificationSwitchConf {
  // 场景名称
  type: string
  // 通知范围 all/user/admin
  action: string
}

// 存储配置
export interface StorageConf {
  // 名称
  name: string
  // 类型 local/alipan/u115/rclone
  type: string
  // 配置
  config?: { [key: string]: any }
}

// 媒体服务器配置
export interface MediaServerConf {
  // 名称
  name: string
  // 类型 emby
  type: string
  // 配置
  config: { [key: string]: any }
  // 是否启用
  enabled: boolean
  // 同步媒体体库列表
  sync_libraries?: string[]
  // 自动同步间隔（小时），为空时使用旧全局配置
  sync_interval?: number | null
}

// 文件整理目录配置
export interface TransferDirectoryConf {
  // 名称
  name: string
  // 优先级
  priority: number
  // 存储
  storage: string
  // 下载目录
  download_path?: string
  // 适用媒体类型
  media_type?: string
  // 适用媒体类别
  media_category?: string
  // 下载类型子目录
  download_type_folder?: boolean
  // 下载类别子目录
  download_category_folder?: boolean
  // 监控方式 downloader/monitor，None为不监控
  monitor_type?: string
  // 监控模式 fast/compatibility
  monitor_mode?: string
  // 整理方式 move/copy/link/softlink
  transfer_type: string
  // 文件覆盖模式 always/size/never/latest
  overwrite_mode?: string
  // 整理到媒体库目录
  library_path?: string
  // 媒体库目录存储
  library_storage?: string
  // 智能重命名
  renaming?: boolean
  // 刮削
  scraping?: boolean
  // 媒体库类型子目录
  library_type_folder?: boolean
  // 媒体库类别子目录
  library_category_folder?: boolean
  // 是否发送通知
  notify?: boolean
}

// 自定义规则项
export interface CustomRule {
  // 规则ID
  id: string
  // 名称
  name: string
  // 包含
  include?: string
  // 排除
  exclude?: string
  // 大小范围
  size_range?: string
  // 最少做种人数
  seeders?: string
  // 发布时间
  publish_time?: string
}

// 规则测试结果

// 整理表单
// 手动整理预览统计
export interface ManualTransferPreviewSummary {
  // 总数
  total: number
  // 成功数
  success: number
  // 失败数
  failed: number
}

export interface TransferForm {
  // 文件项
  fileitem: FileItem
  // 历史ID
  logid: number
  // 目标存储
  target_storage: string | null
  // 目标路径
  target_path: string | null
  // TMDB ID
  tmdbid?: number
  // 豆瓣 ID
  doubanid?: string
  // Bangumi ID
  bangumiid?: number
  // 媒体数据源
  media_source?: MediaDataSource
  // 数据源原生ID
  media_id?: string | null
  // 季号
  season?: number
  // 类型
  type_name?: string
  // 整理方式
  transfer_type: string | null
  // 自定义格式
  episode_format?: string
  // 指定集数
  episode_detail?: string
  // 指定PART
  episode_part?: string
  // 集数偏移
  episode_offset?: string
  // 最小文件大小
  min_filesize: number
  // 刮削
  scrape: boolean | null
  // 复用历史识别信息
  from_history: boolean
  // 媒体库类型子目录
  library_type_folder?: boolean | null
  // 媒体库类别子目录
  library_category_folder?: boolean | null
  // 剧集组编号
  episode_group?: string | null
  // 预览模式
  preview?: boolean
  // 清理已有成功记录后重新整理
  reorganize: boolean
}

// 手动整理请求
export interface ManualTransferPayload extends Omit<TransferForm, 'fileitem'> {
  // 文件项
  fileitem?: FileItem
  // 多选文件批量请求
  fileitems?: FileItem[]
}

// 手动整理命中的成功历史摘要
export interface ManualTransferHistoryInfo {
  // 是否应执行重新整理
  reorganize: boolean
  // 命中的成功历史数量
  history_count: number
}

// 手动整理预览项
export interface ManualTransferPreviewItem {
  // 原始路径
  source?: string
  // 目标路径
  target?: string
  // 目标目录
  target_dir?: string
  // 是否成功
  success?: boolean
  // 提示信息
  message?: string
  // 媒体类型
  type?: string
  // 媒体标题
  title?: string
  // 季
  season?: number | string
  // 开始集
  episode?: number | string
  // 结束集
  episode_end?: number | string
  // Part
  part?: string
  // 原始识别字符串
  org_string?: string
  // 应用的自定义识别词
  apply_words?: string[]
  // 制作组/字幕组
  resource_team?: string
  // 自定义占位符
  customization?: string
}

// 手动整理预览数据
export interface ManualTransferPreviewData {
  // 统计信息
  summary: ManualTransferPreviewSummary
  // 预览结果
  items: ManualTransferPreviewItem[]
  // 额外消息
  message?: string
}

// 整理队列
export interface TransferQueue {
  // 媒体信息
  media: MediaInfo
  // 季
  season?: number
  // 任务列表
  tasks: {
    // 文件项
    fileitem: FileItem
    // 元数据
    meta: MetaInfo
    // 状态
    state: string
  }[]
}

// 媒体识别缓存项
export interface RecognitionCacheItem {
  // 缓存键
  key: string
  // TMDB ID，0 表示未识别
  tmdb_id?: number
  // 识别缓存对应的字符串 ID
  recognition_id?: string
  // 识别后的标题
  title: string
  // 识别后的年份
  year: string
  // 媒体类型
  media_type: string
  // TMDB 海报相对路径
  poster_path?: string
  // TMDB 背景图相对路径
  backdrop_path?: string
}

// 媒体识别缓存数据
export interface RecognitionCacheData {
  // 缓存总数
  count: number
  // 已识别数量
  recognized: number
  // 未识别数量
  unrecognized: number
  // 共享识别成功命中数量
  shared_recognized: number
  // 是否开启共享识别
  shared_recognize_enabled: boolean
  // 缓存数据
  data: RecognitionCacheItem[]
}

// 通用API响应
export interface ApiResponse<T = any> {
  success: boolean
  message?: string
  message_i18n?: string
  data: T
}

// 分类配置
// 分类规则
export interface CategoryRule {
  genre_ids?: string
  original_language?: string
  production_countries?: string
  origin_country?: string
  release_year?: string
}

export interface CategoryConfig {
  movie?: { [key: string]: CategoryRule }
  tv?: { [key: string]: CategoryRule }
}
