# 01 — Project Overview

## System Purpose

LitePilot 是自建媒体自动化工具，由上游 MoviePilot 精简而来，只保留影视入库链条中最必要的环节：

1. **识别** — 解析文件名/种子名得到标题、季度、集数、来源、分辨率、编码等信息。
2. **刮削** — 通过 TMDB 获取元数据与图片。
3. **整理** — 重命名并按季集归档到媒体库，支持硬链接/移动。
4. **媒体服务器** — 入库后刷新 Emby 媒体库；媒体被删除时同步清理本地记录与文件。
5. **通知** — 通过 Telegram 推送入库、删除等结果。

上游的站点管理、订阅、插件市场、工作流、AI Agent 等模块**已整体移除**，不再规划恢复。

## 明确不做的事

| 能力 | 状态 |
|---|---|
| 站点（Indexer）管理、搜索、签到 | 已移除 |
| 订阅、推荐、RSS 自动下载 | 已移除 |
| 插件市场与第三方插件加载 | 已移除 |
| 工作流、AI Agent | 已移除 |
| Docker 部署 | 不支持，使用 systemd + nginx |
| 多语言 | 仅简体中文 |
| PassKey 登录 | 已移除 |

## Repository Boundaries

### What Is in This Repository

| Path | Content |
|---|---|
| `app/` | FastAPI 后端应用 |
| `app/api/endpoints/` | HTTP 接口处理 |
| `app/chain/` | 业务编排层 |
| `app/modules/` | 下载器与媒体服务器等外部集成 |
| `app/helper/` | 可复用底层工具 |
| `app/db/` | SQLAlchemy 模型与数据访问封装 |
| `app/core/meta/` | 媒体名称识别核心逻辑 |
| `database/versions/` | Alembic 迁移脚本 |
| `web/` | Vue 3 + Vuetify 3 前端 |
| `tests/` | pytest 测试 |

### Layer Rules

调用方向固定为 `api → chain → modules/helper → db`，不得反向依赖，也不得跨层直连。

## Deployment Model

- 后端由 `moviepilot` CLI 管理，systemd 单元 `moviepilot.service` 常驻。
- 前端构建产物由 nginx 托管，接口经 nginx 反代到后端端口。
- 配置与数据目录固定在 `/var/lib/moviepilot`，代码目录固定在 `/opt/moviepilot`。

## Identity Model

账号由 swizzin 用户清单同步，本系统不提供用户管理界面：

- 启动时按 `/root/.master.info` 与 `/root/*.info` 补齐本地账号。
- 口令以 swizzin 侧为准，本地不单独维护。
- 只支持用户名 + 密码登录，没有注册、角色分配、头像等能力。
