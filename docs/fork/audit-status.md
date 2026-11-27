# 收敛审计状态（Go + Svelte 重写过渡基线）

本文记录 Python 版 LitePilot 在整体重写前的收敛审计结果。审计目标不是继续扩展现有产品，而是：

1. 保障重写过渡期内生产系统稳定与安全；
2. 让当前 Python 代码库成为可信的行为规格参考。

本轮审计只处理用户指定的后端必审清单。除生产级正确性问题外，不新增前端审计，不修复纯视觉、交互打磨或可访问性问题。

## 已审计覆盖范围

### 识别核心

| 文件 | 审计结论 |
|---|---|
| `app/core/meta/metaanime.py` | 已审计。修复无括号尾部分类标记导致片名最后一个字被误删的问题；第三方解析器返回整数第 0 集时不再丢失。 |
| `app/core/meta/releasegroup.py` | 已审计。修复用户词表中单条无效 `re:` 正则会使整个制作组规则失效的问题；无效条目现在跳过，纯文本组名仍按字面量匹配。 |
| `app/core/meta/wordlist.py` | 已审计。配置读取、分词应用和异常降级路径未发现可红测复现的高置信缺陷。 |
| `app/core/meta/customization.py` | 已审计。修复无效自定义占位符正则中断识别链路的问题；坏规则现在只跳过本次匹配、按规则缓存失败结果并记录 warning，避免每次识别重复编译。 |
| `app/core/meta/infopath.py` | 已审计。父目录标题合并、清空空降标题字段和文件/目录语义未发现高置信缺陷；补齐公开函数中文 docstring。 |
| `app/core/meta/streamingplatform.py` | 按数据表快速审计。加载逻辑与静态映射未发现高置信缺陷。 |

### 刮削与媒体探测

| 文件 | 审计结论 |
|---|---|
| `app/modules/themoviedb/scraper.py` | 已审计。修复第 0 集被真值判断降级为季元数据/季图片的问题，并修复显式目标集号被 `meta.begin_episode` 覆盖的问题。 |
| `app/helper/mediainfo.py` | 已审计。外部 `mediainfo` 调用使用固定参数、无 shell 拼接、30 秒超时，工具缺失和异常输出均降级为 `None`；未发现高置信缺陷。 |
| `app/helper/scraper.py` | 已审计。通用 NFO 生成、CDATA、图片扩展名归一化和空输入降级未发现高置信缺陷；公共链路标注已对齐既有 UTF-8 bytes 契约。 |

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
| `app/api/endpoints/webhook.py` | 已审计。GET/POST 均要求 API token；请求立即返回，解析与分发由 FastAPI 后台任务执行。未改变既有 at-most-once 语义。原生 Emby 数字季集号现在在解析边界规范化为字符串，Season/Episode 0 不再丢失身份。 |

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

### 生产稳定性补充审计

| 文件 | 审计结论 |
|---|---|
| `app/chain/mediacover.py` | 已审计字体缓存外部响应与本地写入边界。字体验证、原子发布、损坏缓存自愈和 I/O 失败降级均有回归覆盖。 |
| `app/chain/system.py` | 已审计交互重启收据与失败反馈边界。无效收据会清理，通知发送失败保留有效收据重试，底层重启失败会撤回收据并告知用户。 |

## 本轮修复与回归测试

| 提交 | 修复 | 回归测试 |
|---|---|---|
| `005cbcd0` | 动漫尾部分类标记不再误删片名 | `tests/test_metainfo.py::test_anime_trailing_category_marker_does_not_corrupt_title` |
| `005cbcd0` | 无效自定义占位符正则不中断识别 | `tests/test_customization_matcher.py::test_invalid_customization_regex_does_not_break_recognition` |
| `005cbcd0` | 无效制作组正则只跳过坏条目 | `tests/test_release_group.py::test_invalid_custom_group_regex_is_skipped_without_breaking_valid_groups` |
| `10e8809c` | 第 0 集生成集 NFO 与集剧照 | `tests/test_tmdb_scraper.py::test_episode_zero_generates_episode_nfo_not_season_nfo`、`test_episode_zero_generates_episode_thumbnail` |
| `10e8809c` | NFO 使用显式目标集号 | `tests/test_tmdb_scraper.py::test_episode_nfo_detail_follows_explicit_episode_number` |
| `83c43bda` | 快照缓存 key 不能越出快照目录 | `tests/test_monitor_snapshot_semantics.py::test_snapshot_storage_name_cannot_escape_cache_directory` |
| `118045e1` | 无效自定义正则按规则缓存失败结果 | `tests/test_customization_matcher.py::test_invalid_customization_regex_is_cached_per_rule` |
| `9614730e` | 单文件删除失败不再中断整个临时/缓存清理 | `tests/test_system_utils.py`、`tests/test_cache_system.py` 清理容错用例 |
| `4fa11aef` | 文件缓存 region/key 不能逃逸缓存根目录，图片 URL 派生 key 中性化 `..` 段 | `tests/test_cache_system.py::test_file_backend_rejects_cache_key_path_traversal`、`tests/test_system_image_proxy.py::test_image_cache_path_cannot_escape_cache_root` |
| `dedf30cc` | 原生 Emby int 0 季集号不再导致联动删除降级为整剧/整季定位 | `tests/test_mediaserverdel_season_delete.py::test_query_history_preserves_numeric_episode_zero`、`tests/test_mediaserverdel_notify_image.py::test_notify_image_preserves_numeric_episode_zero` |
| `7b2b715a` | NFO 公共链路标注对齐 UTF-8 bytes 事实契约 | `tests/test_tmdb_scraper.py::test_nfo_public_contract_is_utf8_bytes` |
| `f357eab0` | webhook 解析边界把原生数字季集号规范化为字符串并保留 0 | `tests/test_webhook_event_scope.py::test_emby_webhook_normalizes_numeric_episode_zero_ids_to_strings` |
| `278f97d8` | 字体下载必须通过 sfnt 魔数校验，写入使用同目录临时文件原子发布 | `tests/test_media_cover_generator.py::test_font_response_must_have_sfnt_magic`、`test_font_write_failure_leaves_no_corrupt_final_file` |
| `bc080cd6` | 既有损坏字体缓存会识别并重新下载，缓存删除/临时文件清理失败不进入调度异常路径 | `tests/test_media_cover_generator.py::test_existing_corrupt_font_is_replaced_by_valid_download`、`test_corrupt_font_unlink_failure_is_graceful` |
| `a1f22097` | 结构无效的重启完成通知收据会被清理，有效收据发送失败保留重试且异常不进入启动任务 | `tests/test_system_restart.py::test_restart_finish_discards_structurally_invalid_receipt`、`test_restart_finish_keeps_valid_receipt_when_notification_fails` |
| `0a043ea4` | 交互命令底层重启失败时撤回完成通知收据并明确通知失败 | `tests/test_system_restart.py::test_command_restart_failure_retracts_receipt_and_notifies` |
| `aa8be901` | Doctor 完整读取当前活跃滚动日志，时间窗内错误不再因短尾部窗口漏报；说明不再伪装覆盖轮转归档 | `tests/test_doctor.py::test_doctor_log_window_is_not_truncated_to_short_tail` |
| `a451b5ac` | 删除无调用面的 `os.popen` shell 字符串执行残留，保留参数数组子进程路径 | `tests/test_dead_upstream_utils_scope.py` |
| `bd5b7952` | 未解析字符串注解不再中断模块链，移除重复且不安全的 `eval` fallback | `tests/test_object.py::test_check_signature_unresolved_annotation_is_unconstrained` |
| `ac3ee57e` | 搜索、动漫解析和手动刮削链路保留第 0 集，不再把整数 0 当作缺失 | `tests/test_media_search_zero_episode.py`、`tests/test_metainfo.py::test_anime_parser_preserves_numeric_episode_zero`、`tests/test_mediascrape.py::test_tv_episode_zero_scrape_continues_recognition` |
| `e981e4bd` | 通知模板能匹配 TMDB 第 0 集标题与播出日期 | `tests/test_template_context_builder.py::test_build_preserves_episode_zero_details` |
| `ec281eac` | 测试中的 `os.stat` 桩对未登记路径委托真实 stat，避免后台日志线程竞态噪声 | `tests/test_system_utils.py` |

定向验证：首批识别/刮削/快照相关测试 `53 passed`；后续缓存、清理、webhook 与删除链回归均已单独转绿。相关 Python 文件 pylint `10.00/10`。

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

4. **`display_width` 被探测但几乎无下游消费者**

   位置：`app/helper/mediainfo.py`。  
   风险：重写时无法判断这是必要行为还是历史残留。  
   未修原因：删除字段属于行为裁剪而非缺陷修复。建议重写时确认媒体信息展示/重命名是否真正需要该值。


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
| `python tests/run.py` | `1693 passed, 2 warnings` |
| `yarn typecheck` | 通过 |
| `yarn test:run` | `108` 个测试文件、`783` 项测试全部通过 |
| `pylint app/` | `10.00/10`；convention/refactor/warning/error 均为 0 |

前端没有出现需要归因于跳过视觉体系的既有失败。


## 当前生产基线

生产环境已部署并核验 `ec281eac01751de6a6b63a49b1fb1b1daa4b8ca6`。升级前备份为 `/root/litepilot-pre-ec281eac-20261127160107.tar.gz`，权限 `0600`，包含清单、环境文件、分类配置和 SQLite 一致性快照。

核验结果：`litepilot.service` active；nginx `/litepilot/` 与 `service-worker.js` 均为 200；SQLite `integrity_check` 为 ok；本次重启后的 systemd 错误计数为 0；Doctor 为 `error=0 warn=1 advisory=1`。`/system/ping` 在后端直连与 nginx 代理下均返回 401，这是登录认证边界生效，证明 API 可达，不是启动失败。

Doctor 的 `warn=1` 仍是 2026-11-27 05:26 的 Telegram 命令注册竞态历史日志，对应修复 `7cce26d7` 已包含在当前版本；本次重启后没有新增同类错误。
