# 基线与已知问题

本文件记录 `lite` 分支在**未做业务改动**时就存在的上游问题，避免后续把它们误判为本仓引入的缺陷。

## 基线状态

| 项 | 值 |
|---|---|
| 基线提交 | `1528176b`（`jxxghp/MoviePilot` v2 分支 HEAD，2026-09-26，`APP_VERSION = v2.15.6`） |
| 与上游差异 | 无（本地 `git diff` 为空，sha 完全一致） |
| 依赖环境 | Python 3.14.8 + venv（`uv venv venv` + `uv pip install -r requirements.txt -r requirements-dev.in`） |
| 基线测试 | `2463 passed, 1 skipped, 2 failed`（失败项见下） |
| 基线前端构建 | `web/` 源码 `corepack yarn build` 成功（约 192 秒） |
| 基线前端测试 | `yarn test:run` 中 `DialogCloseBtn` 用例失败（见下，已在本仓修复） |

## 已在本仓修复

### `DialogCloseBtn.spec.ts` 断言图标路径失败（上游既存问题）

- 现象：用例断言 `mdi-close` 的 SVG `path`，但测试环境只渲染出空 `svg`。
- 原因：图标集合由 `src/main.ts` 动态加载（`import('@/@iconify/icons-bundle')`），测试环境不加载它。
- 已核实：在**未经改动**的上游 v2 前端副本上同样失败。
- 修复：在该用例内显式 `import '@/@iconify/icons-bundle'` 注册图标集合。

## 已知问题

### 1. `tests/test_bluray.py::BluRayTest::test` 失败（`AssertionError: 2 != 1`）

- 现象：BDMV 原盘目录在一次刮削事件中被刮削两次，`metadata_nfo` 被调用 2 次而用例期望 1 次。
- 定位：`app/chain/media.py:1044` 的 `scrape_metadata_event`——当事件传入的 `fileitem` 是原盘目录的**父目录**时，走 `else` 分支逐个子目录调用 `scrape_metadata`，子目录命中 BDMV 判定后又对原盘根目录刮削一次，与前面的根目录刮削重复。
- 已核实：在 `HEAD~1`（`66b4c8ed`）上同样失败，属上游既存问题，不是基线提交引入。
- 影响：原盘 NFO / 图片刮削被重复执行一次（重复覆盖，非数据损坏），属于保留能力（整理与刮削）范围内的问题。
- 处置：保留在待修列表，与阶段 3 的整理链回归一起修，避免在未验证真实原盘流程前盲改。

### 2. `tests/test_workflow_actions.py::test_workflow_manager_list_actions_exposes_contract` 失败（`TypeError: 'method' object is not a mapping`）

- 定位：`app/workflow/__init__.py:246`，`get_actions` 把方法对象当作映射展开。
- 处置：**不修**。工作流模块在阶段 2.3 整体删除，对应测试文件一并删除。
