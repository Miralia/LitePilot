# AGENTS.md

本文件是本仓库内 AI agent 与 LLM 的主要行为约定。仓库内文档优先于通用训练知识，你必须同时遵守 `docs/rules/` 下的规则文档。

---

## 项目定位

LitePilot 是精简后的自建媒体自动化工具，只服务「识别 → 刮削 → 整理 → 媒体库 → 通知」这条链路。
站点、订阅、插件市场、工作流、AI Agent 等上游模块已移除，**不要重新引入**。
详见 `docs/rules/01-project-overview.md`。

---

## 任务与文档对应

执行任务前先判断领域，再加载对应文档。

### 架构边界
* **参考：** `docs/rules/05-architecture.md`
* **要求：** 遵守 `api → chain → modules/helper → db` 的调用方向，不得反向依赖，不得引入循环依赖。

### 业务逻辑与设计模式
* **参考：** `docs/rules/04-design-patterns.md`
* **要求：** 使用项目既有的 Chain、Event、Oper 结构，不引入项目未采用的抽象。

### 代码风格
* **参考：** `docs/rules/06-code-styles.md`
* **要求：** 与相邻代码风格保持一致；类型标注、Pydantic 模型、async 用法遵循文档。

### 命名规范
* **参考：** `docs/rules/07-naming-conventions.md`
* **要求：** 文件名、类名、函数名、常量名遵循既有分类，不使用随意缩写或混用大小写。

### 注释与文档
* **参考：** `docs/rules/08-comment-styles.md`
* **要求：** 公开类与方法必须有中文 docstring；注释解释「为什么」，不复述代码。
* **⚠️ 强制门槛：** 缺少中文 docstring 的公开接口直接视为不合格，无例外。

### 外部通信
* **参考：** `docs/rules/09-external-response.md`
* **要求：** 所有第三方 HTTP 请求经由 `RequestUtils`；响应使用项目标准 schema。

### 数据与持久化
* **参考：** `docs/rules/10-data-and-persistent.md`
* **要求：** 模型变更必须配套 Alembic 迁移；运行时配置统一走 `SystemConfigKey` + `SystemConfigOper`，禁止裸字符串键。

### 质量与安全
* **参考：** `docs/rules/11-quality-and-security.md`
* **要求：** 变更需通过 pytest 与 pylint；依赖变更需通过安全检查。

### 测试
* **参考：** `docs/testing.md`
* **要求：** 只用 pytest；测试不得访问真实数据库、网络或外部服务（TMDB、下载器、媒体服务器），在边界 mock 或回放录制响应，标准是零真实外连。新增测试必须使用 pytest 风格（函数 + `assert` + fixture），不要新增 `unittest.TestCase`。提交前运行 `python tests/run.py` 并确认全绿。

### 命令与开发流程
* **参考：** `docs/rules/03-commands.md`
* **要求：** 只建议或执行该文件记录的命令，不臆测工具默认值。

---

## 执行规则

### 开工前检查

1. 判断任务领域（架构 / 业务逻辑 / 代码风格 / 命名 / 注释 / 外部接口 / 数据 / 质量）。
2. 加载 `docs/rules/` 下对应文档。
3. 确认方案不违反三条硬约束：
   - **命名（07）**：文件、类、函数、常量命名是否正确？
   - **架构（05）**：代码是否在正确层级？调用方向是否合法？
   - **注释（08）**：新增公开类与方法是否都有中文 docstring？

### 实现要求

* **遵循既有模式：** 避免通用样板代码；若 `04-design-patterns.md` 已定义场景模式，必须使用。
* **最小变更：** 只做完成目标所必需的最小改动，不做无关重构、批量重命名或纯格式整理。
* **输出语言：** 总结、验证结果与风险说明默认使用中文。

### 冲突处理

发现代码与文档矛盾时：停止实现 → 指出具体文件与行号 → 向用户确认当前标准，不要自行选择一方继续。

---

## 联动更新

| 变更内容 | 必须同步更新 |
|---|---|
| CLI 行为 | `moviepilot` 入口、`docs/cli.md`、相关测试 |
| REST API | `docs/mcp-api.md`、相关测试 |
| 开发流程、依赖管理 | `docs/development-setup.md` |
| 数据库模型 | `database/versions/` 下新增迁移 |
| 用户可见配置或初始化流程 | 相关文档、界面文案、测试 |

---

## 文档入口

完整的文档索引与交叉引用见 **[docs/rules/README.md](./docs/rules/README.md)**。
