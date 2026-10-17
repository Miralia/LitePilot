# 极简自用版（lite）项目说明

本仓库是 MoviePilot 的个人自用精简分支（开发分支 `lite`），目标不是通用媒体自动化平台，而是**内容库维护工具**：自己把种子加到下载器或从 Usenet 下载，本程序只负责识别、整理入库、刷新媒体服务器并通知；其余能力一律删除。

## 与上游的关系

| 项 | 值 |
|---|---|
| 基线 | `jxxghp/MoviePilot` v2 分支，`APP_VERSION = v2.15.6`，基线提交 `1528176b`（2026-09-26） |
| 上游 v2 状态 | 已冻结（不再有提交），适合作为自有维护基线 |
| 上游 v3 状态 | 活跃（`jxxghp/MoviePilot` v3 分支），本仓不跟随，只按需移植个别优化 |
| 本仓 remote | `origin` = 自有 fork；`upstream` = `jxxghp/MoviePilot`（只读参考） |
| 分支约定 | `v2` 保留为上游镜像（不改动），`lite` 为开发主线 |

上游 v3 的移植策略与候选清单见 [upstream-backport.md](upstream-backport.md)。

## 保留能力（唯一清单）

- 元数据识别与刮削：TMDB（另保留 Bangumi / AniList 供动漫集数与季度识别）
- 下载器：qBittorrent（列种子、查状态、取路径、删种）
- 整理：目录监控（本地）、整理链（重命名 / 硬链接 / 分类）、手动整理、整理历史与下载历史
- 媒体服务器：Emby（刷新、播放地址）
- 通知：Telegram
- 存储：local + 文件管理
- 诊断：`moviepilot doctor`
- 用户：单管理员 + swizzin 用户同步
- 内置能力：下载文件同步、媒体同步删除、媒体库封面生成
- 前端：本仓 `web/` 源码自建，产物由后端直接托管

## 删除清单（相对 v2.15.6）

| 子系统 | 主要删除对象 |
|---|---|
| 站点 | `app/chain/site.py`、`app/api/endpoints/site.py`、`app/db/site_oper.py`、`app/db/models/site*.py`、`app/modules/indexer/`、`app/modules/subtitle/`、`app/helper/{resource,cookiecloud}.py`、站点采集器脚本与文档 |
| 搜索 / 订阅 | `app/chain/{search,subscribe,torrents,recommend}.py`、对应端点、订阅表与 Oper、`app/modules/filter/` |
| 智能体 / 工作流 | `app/agent/`、`app/workflow/`、MCP / OpenAI / Anthropic / LLM 端点、`skills/` |
| 插件体系 | `app/core/plugin.py`、`app/helper/plugin.py`、`app/api/endpoints/plugin.py`、`app/plugins/`、插件市场与 `plugindata` |
| 多用户 / 鉴权 | MFA、passkey、邀请与 Token 管理；鉴权依赖函数改为单管理员直通 |
| 下载器 | transmission、rtorrent 模块；下载任务操作界面 |
| 元数据 / 媒体服务器 / 通知 | 豆瓣、TVDB、Fanart、Jellyfin、Plex、TrimMedia、Zspace、Ugreen、微信、飞书、Slack、Discord、VoceChat、QQBot、SynologyChat、WebPush、WeChatClawBot |
| 存储 | 云盘类后端（115 / 阿里盘 / rclone / alist） |
| 部署 | Docker 相关全部移除，改为 systemd + nginx 原生部署 |

站点能力在上游本就是**仓外私有动态资源**（`.gitignore` 排除 `app/helper/sites.py`，线上为 `sites.cpython-*.so` 与 `user.sites.v2.bin`，由 `app/helper/resource.py` 拉取）。本仓改为在仓内提供纯 Python 桩 `app/helper/sites.py`，保证残留引用点与 `auth_level` 语义不断链。

## 仓库结构

单一仓库同时承载后端、前端与部署脚本，不再拆多个仓库：

| 路径 | 内容 |
|---|---|
| `app/` | 后端 Python 包（保留上游包名，避免无意义的大规模重命名） |
| `web/` | 前端源码（Vue 3 + Vuetify 3 + Vite，来自 `MoviePilot-Frontend` v2 分支 `19cead0`） |
| `public/` | 前端构建产物（`.gitignore` 排除，由 `scripts/build-frontend.sh` 生成，nginx 直接托管） |
| `database/` | Alembic 迁移 |
| `docs/fork/` | 本分支的定位、上游移植记录与已知问题 |
| `scripts/` | 安装、构建、启动与迁移脚本 |
| `tests/` | 后端 pytest 用例（前端用例在 `web/tests/`） |
| `moviepilot` | 本地 CLI 入口 |

注意：`web/public/` 是 Vite 的静态资源源目录，与仓库根目录的构建产物 `public/` 不是同一个东西。

## 阶段状态

- [x] 阶段 0：基线与仓库（分支 `lite`、`upstream` remote、fork 文档、基线测试）
- [x] 阶段 1：前端源码入库 `web/`、构建脚本、页面裁剪、依赖精简、版本号收敛
- [ ] 阶段 2：后端减法
  - [x] 2.1 站点子系统（含仓内 `SitesHelper` 垫片、索引器、站点字幕、CookieCloud、站点采集器）
  - [x] 2.2 搜索 / 订阅 / 种子缓存 / 过滤
  - [x] 2.3 智能体 / 工作流 / MCP / 技能（与 2.2 互相纠缠，合并删除）
  - [x] 2.4 插件体系（含插件市场、插件认证票据、插件数据表）
  - [ ] 2.5 鉴权收敛为单管理员 + swizzin 同步
  - [ ] 2.6 下载器收敛为 qBittorrent
  - [ ] 2.7 元数据 / 媒体服务器 / 通知收敛
  - [ ] 2.8 数据库删表迁移与配置键清理
- [ ] 阶段 3：内置化（下载文件同步、媒体同步删除、媒体库封面生成）
- [ ] 阶段 4：原生部署与一键迁移重装
- [ ] 阶段 5：验证、静态检查、冒烟与文档同步

## 站点移除方式（阶段 2.1）

站点能力在上游是仓库外的私有动态资源（`sites.cpython-*.so` + `user.sites.v2.bin`）。本分支改为：

1. 在仓库内提供只读垫片 `app/helper/sites.py`：`auth_level` 恒为 1、索引器枚举恒为空、`check/check_user` 恒返回不可用。
2. 删除站点能力本体：`app/chain/site.py`、`app/api/endpoints/site.py`、`app/modules/{indexer,subtitle}`、`app/helper/{resource,cookiecloud,browser,cloudflare,doh,ocr,display,cookie}.py`、站点采集器脚本与文档、站点相关定时任务与启动步骤。
3. 站点数据层（`app/db/site_oper.py` 与 `site*` 模型）暂时保留给后续阶段仍引用它的代码（搜索/订阅/下载器阶段），在 2.8 随迁移一并删除。
4. 依赖精简：移除 `cloakbrowser`、`PyVirtualDisplay`。

## 前端（阶段 1 结果）

| 项 | 值 |
|---|---|
| 源码来源 | `MoviePilot-Frontend` v2 分支 `19cead0`（2026-08-10，已冻结） |
| 源码位置 | `web/`（Vite + Vue 3 + Vuetify 3，包管理器 yarn 1.22，Node ≥ 20.19） |
| 构建入口 | `./scripts/build-frontend.sh [--skip-install] [--no-frozen]` |
| 产物位置 | 仓库根目录 `public/`（`.gitignore` 排除，`settings.FRONTEND_PATH` 默认指向它） |
| 保留页面 | `/dashboard`、`/history`（整理历史 + 手动整理）、`/filemanager`、`/setting`、`/profile`、`/login`、404 |
| 删除页面 | `/resource`、`/recommend`、`/discover`、`/subscribe*`、`/calendar`、`/downloading`、`/site`、`/user`、`/plugins`、`/plugin-app`、`/browse`、`/credits`、`/person`、`/media`、`/apps`、`/setup-wizard` |
| 设置页标签 | 仅保留 `system`（系统 + 下载器 + 媒体服务器）、`directory`（目录 + 存储）、`notification`（通知） |
| 依赖精简 | 移除 `@fullcalendar/*`、`@vue-flow/*`、`three` 之外的日历/工作流依赖、`body-scroll-lock`、`mousetrap`、`js-cookie` 及其 `@types`（共 18 项） |
| 版本标记 | `version.py` 的 `APP_VERSION`（现为 `v0.1.0`）写入 `public/version.txt`；已移除 `FRONTEND_VERSION` 常量 |
| 验证 | `yarn typecheck` 通过、`yarn test:run` 732 通过、`yarn build` 通过、`scripts/build-frontend.sh` 产物校验通过 |

注意：`web/public/` 是 Vite 的静态资源源目录，与仓库根目录的构建产物 `public/` 不是同一个东西。

## 部署形态（目标）

- 代码 `/opt/moviepilot`，配置 `/var/lib/moviepilot`
- systemd 系统级 unit 启动 `venv/bin/python -m app.main`
- 前端静态文件由宿主 nginx 直接托管仓库内 `public/`，`/api` 反代后端端口
- 依赖由 venv + uv 管理，配置目录与数据库可通过 CLI 备份 / 恢复 / 迁移
