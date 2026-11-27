# 收敛审计状态（Go + Svelte 重写过渡基线）

本文记录 Python 版 LitePilot 在整体重写前的收敛审计结果。审计目标不是继续扩展现有产品，而是：

1. 保障重写过渡期内生产系统稳定与安全；
2. 让当前 Python 代码库成为可信的行为规格参考。

本轮审计只处理用户指定的后端必审清单。除生产级正确性问题外，不新增前端审计，不修复纯视觉、交互打磨或可访问性问题。

## 已审计覆盖范围

### 识别核心

| 文件 | 审计结论 |
|---|---|
| `app/core/meta/metaanime.py` | 已审计。修复无括号尾部分类标记导致片名最后一个字被误删的问题。 |
| `app/core/meta/releasegroup.py` | 已审计。修复用户词表中单条无效 `re:` 正则会使整个制作组规则失效的问题；无效条目现在跳过，纯文本组名仍按字面量匹配。 |
| `app/core/meta/wordlist.py` | 已审计。配置读取、分词应用和异常降级路径未发现可红测复现的高置信缺陷。 |
| `app/core/meta/customization.py` | 已审计。修复无效自定义占位符正则中断识别链路的问题；坏规则现在只跳过本次匹配并记录 warning。 |
| `app/core/meta/infopath.py` | 已审计。父目录标题合并、清空空降标题字段和文件/目录语义未发现高置信缺陷；补齐公开函数中文 docstring。 |
| `app/core/meta/streamingplatform.py` | 按数据表快速审计。加载逻辑与静态映射未发现高置信缺陷。 |

### 刮削与媒体探测

| 文件 | 审计结论 |
|---|---|
| `app/modules/themoviedb/scraper.py` | 已审计。修复第 0 集被真值判断降级为季元数据/季图片的问题，并修复显式目标集号被 `meta.begin_episode` 覆盖的问题。 |
| `app/helper/mediainfo.py` | 已审计。外部 `mediainfo` 调用使用固定参数、无 shell 拼接、30 秒超时，工具缺失和异常输出均降级为 `None`；未发现高置信缺陷。 |
| `app/helper/scraper.py` | 已审计。通用 NFO 生成、CDATA、图片扩展名归一化和空输入降级未发现高置信缺陷。 |

### 快照、事件与模块基础设施

| 文件 | 审计结论 |
|---|---|
| `app/monitor/snapshot.py` | 已审计。修复存储名中的路径分隔符可通过 `FileCache` key 拼接逃逸快照目录的问题；普通存储名保持兼容，危险名称派生为单段安全 key 并附加短摘要。 |
| `app/utils/coalesce.py` | 已审计。事件循环本地状态、窗口期合并、关闭取消和回调异常隔离均有既有测试覆盖；未发现新增高置信缺陷。 |
| `app/core/module.py` | 已审计。模块加载失败按模块隔离，停止失败不阻断其它模块，运行态查询有防御；未发现可安全修改的高置信缺陷。 |

### Webhook、仪表板与 API 边界

| 文件 | 审计结论 |
|---|---|
| `app/chain/dashboard.py` | 已审计。仅转发统计与下载器信息，无本地状态；未发现高置信缺陷。 |
| `app/chain/webhook.py` | 已审计。解析失败返回、解析成功才广播 `WebhookMessage`；事件模型本身为后台 best-effort 语义。 |
| `app/api/endpoints/tmdb.py` | 已审计。识别缓存管理接口要求超级管理员；删除只作用于运行时缓存键并通过缓存层持久化，不把 `cache_key` 直接拼成文件路径。 |
| `app/api/endpoints/webhook.py` | 已审计。GET/POST 均要求 API token；请求立即返回，解析与分发由 FastAPI 后台任务执行。未改变既有 at-most-once 语义。 |

### 数据库与启动生命周期

| 文件 | 审计结论 |
|---|---|
| `app/db/init.py` | 已审计。`init_db` 只注册模型并 `create_all`，`update_db` 构造 Alembic 配置并执行 `upgrade(head)`；未发现可安全直接修改的明确缺陷，迁移失败语义见“不修清单”。 |
| `app/startup/lifecycle.py` | 已审计。启动保存事件循环，安全模式跳过调度/监控/命令，关闭阶段逐一隔离异常并最后关闭日志。关闭顺序风险见“不修清单”。 |
| `app/startup/modules_initializer.py` | 已审计。模块、事件、线程池、消息、Redis、数据库和临时文件关闭均按阶段隔离；事件链模块显式导入以保证装饰器注册。 |
| `app/startup/command_initializer.py` | 已审计。仅为 `Command` 生命周期薄封装，未发现高置信缺陷。 |
| `app/startup/monitor_initializer.py` | 已审计。仅为 `Monitor` 生命周期薄封装，未发现高置信缺陷。 |
| `app/startup/scheduler_initializer.py` | 已审计。仅为 `Scheduler` 生命周期薄封装，未发现高置信缺陷。 |
| `app/startup/routers_initializer.py` | 已审计。v1/v2 路由注册和 OpenAPI 配置无本地状态，未发现高置信缺陷。 |
| `app/startup/__init__.py` | 已审计。空包初始化文件。 |

## 本轮修复与回归测试

| 提交 | 修复 | 回归测试 |
|---|---|---|
| `005cbcd0` | 动漫尾部分类标记不再误删片名 | `tests/test_metainfo.py::test_anime_trailing_category_marker_does_not_corrupt_title` |
| `005cbcd0` | 无效自定义占位符正则不中断识别 | `tests/test_customization_matcher.py::test_invalid_customization_regex_does_not_break_recognition` |
| `005cbcd0` | 无效制作组正则只跳过坏条目 | `tests/test_release_group.py::test_invalid_custom_group_regex_is_skipped_without_breaking_valid_groups` |
| `10e8809c` | 第 0 集生成集 NFO 与集剧照 | `tests/test_tmdb_scraper.py::test_episode_zero_generates_episode_nfo_not_season_nfo`、`test_episode_zero_generates_episode_thumbnail` |
| `10e8809c` | NFO 使用显式目标集号 | `tests/test_tmdb_scraper.py::test_episode_nfo_detail_follows_explicit_episode_number` |
| `83c43bda` | 快照缓存 key 不能越出快照目录 | `tests/test_monitor_snapshot_semantics.py::test_snapshot_storage_name_cannot_escape_cache_directory` |

定向验证：上述相关测试 `53 passed`；相关 Python 文件 pylint `10.00/10`。

## 审计期间发现但选择不修的问题

以下问题或语义会影响 Go + Svelte 重写，但当前 Python 版不宜在缺少产品决策的情况下强行改变：

1. **数据库迁移失败只记录日志，启动继续**  
   位置：`app/db/init.py::update_db`。  
   风险：迁移失败时进程可能以不匹配的数据库 schema 继续运行，后续错误转移到业务请求路径。  
   未修原因：fail-fast 会造成生产启动中断，降级启动则会掩盖迁移失败；这是部署可用性策略，不应在收尾审计中擅自选择。重写时应显式定义迁移健康门、失败页面/只读模式和恢复流程。

2. **关闭顺序是先停模块，再停止事件消费与线程池**  
   位置：`app/startup/modules_initializer.py::stop_modules`。  
   风险：模块资源关闭后，队列中已有事件仍可能被分发到已停止的模块实例；反过来，如果先停事件消费，关闭期生产者新事件会被明确丢弃。  
   未修原因：两种顺序分别对应“尽量处理但可能 use-after-close”和“安全停止但明确丢弃”，属于重写生命周期语义决策。当前关闭流程已将各阶段异常隔离，避免单个失败扩大影响。

3. **Webhook 是 at-most-once，无重试与持久化队列**  
   位置：`app/api/endpoints/webhook.py`、`app/chain/webhook.py`。  
   风险：进程退出、后台任务异常或事件消费者停止时，媒体服务器删除/播放事件可能丢失。  
   未修原因：引入持久化队列或重放机制是新架构能力，不属于审计修复。重写时应明确 webhook 交付等级，并考虑事件确认、去重和重放。

4. **NFO 生成接口标注为 `Optional[str]`，实际返回 UTF-8 `bytes`**  
   位置：`app/modules/themoviedb/scraper.py`、`app/helper/scraper.py`。  
   风险：类型标注与真实契约不一致，可能误导重写。  
   未修原因：下游 `_save_file` 明确兼容 `bytes` 与 `str`，且 Bangumi/TMDB 当前均遵循 bytes 事实契约；在收尾阶段仅修正标注不会改变运行行为，但可能引起跨模块类型契约连锁调整。重写时应统一规定 NFO 在内存中是 bytes 还是 str。

5. **`display_width` 被探测但几乎无下游消费者**  
   位置：`app/helper/mediainfo.py`。  
   风险：重写时无法判断这是必要行为还是历史残留。  
   未修原因：删除字段属于行为裁剪而非缺陷修复。建议重写时确认媒体信息展示/重命名是否真正需要该值。

6. **重启完成通知依赖内部缓存文件，异常缓存可能导致每次启动重复失败**  
   位置：`app/chain/system.py::restart_finish` 与 `app/startup/lifecycle.py::init_extra` 的调用关系。  
   风险：理论上损坏缓存会让重启收尾任务反复失败。  
   未修原因：缓存由系统内部写入且损坏概率低；修复点在非必审文件，当前不扩大范围。重写时应把重启通知设计为幂等、可校验的持久状态。

## 明确跳过的视觉体系与风险评估

以下区域即将随 Go + Svelte 重写废弃。本轮按要求未审计、未修复、未重构：

- `web/src/components/theme/` 全部
- `web/src/rendering/glass/` 全部
- `web/src/composables/useThemeCustomizer.ts`
- `web/src/composables/useTransparencySettings.ts`
- `web/src/composables/usePagePresentationMotion.ts`
- `web/src/utils/glassOptics.ts`
- `web/src/utils/themeManager.ts`
- `web/src/components/dialog/GlassSettingsDialog.vue`
- `web/src/components/dialog/TransparencySettingsDialog.vue`
- `web/src/components/misc/PrismaticLogo.vue`
- `web/src/plugins/vuetify/theme.ts`
- 上述文件对应测试与样式

风险评估：这些文件主要影响视觉呈现、主题状态与动效，不直接执行媒体删除、整理、认证或外部请求。残余风险以界面显示异常、主题状态不一致和测试脆弱性为主；若存在缺陷，重写后不会继承该实现。只有在重写延期且生产出现数据级错误时才值得重新评估。

## 未审计残留区域

| 区域 | 风险评估 |
|---|---|
| 必审清单之外的 Python 业务链、helper、modules | 前序长期审计已覆盖大量生产路径，但本轮不声称全仓完备。残留风险主要是个别异常路径与上游兼容逻辑。 |
| 前端非视觉体系 | 本轮未新增审计。仅当发现数据丢失或错误操作执行级问题时才处理；普通交互与展示问题不再投入。 |
| 第三方依赖内部行为 | 只审计项目调用契约，不审计依赖实现。风险通过锁版本、测试 mock 边界和生产日志监控控制。 |
| Alembic 历史迁移脚本 | 本轮只审计 `db/init.py` 调用契约，没有逐条重审全部历史迁移。生产已成功通过当前迁移链；残留风险主要是极旧数据库跨版本升级。 |
| 已删除上游能力的兼容表/历史字段 | 作为既有数据库兼容层保留。风险低，但重写时不应无条件继承。 |

## 门禁状态

| 门禁 | 结果 |
|---|---|
| `python tests/run.py` | `1655 passed, 2 warnings` |
| `yarn typecheck` | 通过 |
| `yarn test:run` | `108` 个测试文件、`783` 项测试全部通过 |
| `pylint app/` | `10.00/10`；convention/refactor/warning/error 均为 0 |

前端没有出现需要归因于跳过视觉体系的既有失败。
