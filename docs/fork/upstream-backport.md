# 上游优化移植记录

本仓以冻结的 MoviePilot v2.15.6 为基线，不跟随活跃的 v3 主线，但对上游确有价值的设计与优化**按需移植**。本文件记录移植候选、决策与落地情况，避免重复评估。

## 为什么不做整体升级

1. v2 已冻结，没有持续合并压力；v3 活跃，跟随会引入长期冲突成本。
2. 本仓删除约 60% 代码后与上游 diff 巨大，无论以哪个版本为基线都无法顺畅合并，因此"冻结基线 + 手动移植"成本最低。
3. 现有生产库是 v2 schema；换 v3 会先在现有库上执行不可逆的大版本升级（`media_source` + `media_id` 媒体身份重构、音乐与可靠事件表等）。

## 移植流程

1. `git fetch upstream v3` 获取上游参考（只读，不合并）。
2. 定位目标提交或文件，阅读其设计动机（v3 的 `docs/adr/` 与 `docs/v2-to-v3-overview.md` 通常有说明）。
3. 在 `lite` 分支按本仓分层**重写**，不做直接 cherry-pick（架构不同，v2 无 `domain/adapters/application/runtime` 分层）。
4. 补充或更新测试，保持 `python tests/run.py` 全绿与 pylint 通过。
5. 在下表登记状态，并在"移植记录"中写明动机、落地位置与验证方式。

## 候选清单

| 上游能力 | v3 位置 | 状态 | 说明 |
|---|---|---|---|
| 前端产物 seam `frontend-dist/` | `.gitignore:50-51`、`docker/Dockerfile:214-229`（Docker 已移除，仅作上游参考） | 已由 `scripts/build-frontend.sh` 承接 | 构建产物写入 `public/`，由宿主 nginx 直接托管 |
| 数据库备份 / 校验 / 恢复 CLI | v3 `docs/cli.md` 数据库章节、`scripts/local_setup.py` | 待移植（阶段 4） | 迁移前自动备份，是本仓"一键迁移重装"的安全前提；v2 完全没有该能力 |
| 首次安装网页初始化管理员 | `docs/v2-to-v3-overview.md` §3.8 | 待评估 | 可替代 `app.env` 里写初始密码；本仓为单管理员 + swizzin 同步，收益有限 |
| 统一响应层 `{success,message,data}` | `docs/v2-to-v3-overview.md` §5.5 | 待评估 | 本仓前端同步改造，收益中等、改动面大 |
| `uv.lock` 锁定依赖 / Python 3.14 | v3 `pyproject.toml`、`uv.lock` | 待评估 | 取决于是否升级到 Python 3.14；本仓保留 v2 的 `requirements*.in` 体系 |
| `native/fts5_cjk`（SQLite FTS5 中文分词） | `native/fts5_cjk/`、v3 `app/agent/history/storage.py:30` | 不移植 | 仅服务 Agent 历史检索，本仓已删除 Agent |
| Rust 加速适配层 | v3 `app/adapters/system/rust.py:77-260`、`moviepilot-rust~=0.3.8` | 暂不移植 | 主要加速站点索引解析、资源过滤与 RSS；本仓已删除站点与搜索，收益接近零 |
| 可靠事件 Outbox | v3 `docs/adr/0007-background-action-reliability.md` | 延后 | 用于"数据库已提交但通知/后续动作未执行"的场景；若实际出现整理结果或通知丢失再移植 |
| 音乐自动化 / 多来源媒体身份 / 插件 SDK / V3t 自由线程 | v3 全仓 | 不移植 | 与本仓精简目标无关 |

## 移植记录

尚无已落地条目。每次移植在本节追加：动机、上游参考位置、本仓落地文件、验证方式。
