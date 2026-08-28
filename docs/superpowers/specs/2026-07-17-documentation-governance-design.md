# QueryMind 文档治理与结构统一设计

**日期：** 2026-07-17  
**状态：** 待用户审阅  
**范围：** 当前公开文档、历史归档、索引、命名和文档质量校验

## 1. 目标

将 QueryMind 的文档整理为适合企业协作和 GitHub 开源浏览的文档体系：入口唯一、职责清晰、命名一致、当前内容可信、历史内容可追溯，并降低新增文档再次混乱的概率。

本次工作不删除历史资料，也不覆盖工作区中已有的未提交改动。现有历史报告和旧版本页面保留为只读归档，当前页面以代码、配置和实际启动命令为准。

## 2. 现状证据

- `docs/` 当前约有 152 份 Markdown 文档。
- 当前文档目录与旧目录并存，历史材料中仍大量引用已经不存在的 `docs/guides/`、`docs/project/` 和 `internal_docs/`。
- `docs/archive/INDEX.md` 引用了不存在的当前目录，并且自身统计和更新时间已经过时。
- `docs/design/INDEX.md` 存在重复链接。
- `docs/releases/` 的文件名混用 `RELEASE_NOTES_vX.Y.Z.md`、`RELEASE_vX.Y.Z.md` 等格式，发布索引也未覆盖全部现有版本文件。
- 根目录和文档目录已有一批未提交的重组变更，本设计只规定本轮收敛方向，不假设这些变更可以回滚。

## 3. 设计原则

### 3.1 单一事实来源

- 根目录 `README.md` 是 GitHub 项目首页，负责项目定位、最短启动路径和主要链接。
- `docs/README.md` 是当前文档唯一入口，负责按受众和任务导航。
- `docs/DOCUMENTATION_POLICY.md` 是文档治理规则的唯一来源。
- `CHANGELOG.md` 负责完整变更流水；`docs/releases/` 负责面向用户的版本说明和升级提示。
- 技术事实以源码、配置样例、Compose 文件、前端 `package.json` 和现有测试命令为准；文档中的推测性内容要删除或明确标注为规划。

### 3.2 当前与历史分离

当前文档只描述仍支持的行为和路径。已完成的实施报告、每日总结、旧版索引、旧目录说明和过时的“最终完成”文档统一归入 `docs/archive/legacy/`，归档页必须标注“历史资料，不作为当前操作依据”。

### 3.3 面向受众组织

| 受众 | 入口 | 内容 |
| --- | --- | --- |
| 新用户 | `docs/getting-started/`、`docs/user-guide/` | 安装、首次运行、核心功能、业务理解 |
| 开发者 | `docs/development/`、`docs/architecture/` | 开发流程、代码规范、架构和模块边界 |
| 运维人员 | `docs/operations/` | 部署、监控、运行手册、故障排查和恢复 |
| 集成者 | `docs/reference/` | API、配置、模型、示例和 FAQ |
| 维护者 | `docs/releases/`、`docs/design/`、`docs/templates/` | 发布、设计记录、模板和治理 |

## 4. 目标目录结构

```text
README.md
CONTRIBUTING.md
SECURITY.md
CHANGELOG.md
docs/
├── README.md                    # 唯一当前文档入口
├── INDEX.md                     # 兼容旧书签的跳转页
├── DOCUMENTATION_POLICY.md      # 文档治理规则
├── getting-started/             # 安装、配置、首次运行
├── user-guide/                  # 用户和业务说明
├── architecture/                # 系统架构与设计边界
├── features/                    # 当前功能说明
├── development/                 # 开发与贡献流程
├── operations/                  # 部署、监控、运行手册、故障排查
├── reference/                   # API、配置、模型、示例、FAQ
├── releases/                    # 用户可读版本说明
├── design/                      # 已确认的设计记录
├── templates/                   # 可复用文档模板
├── zh-CN/                       # 中文导航与用户文档
├── images/                      # 文档图片与说明
└── archive/
    ├── INDEX.md                 # 归档总索引
    └── legacy/                  # 历史页面和旧入口
```

不再创建新的 `docs/guides/`、`docs/project/`、`internal_docs/` 或根目录专题 Markdown 文件。若某个历史页面仍有价值，迁移到上述目标目录并以当前事实重写；否则只保留归档副本。

## 5. 命名方案

### 5.1 当前文档

- 新增和迁移后的当前文档使用小写 `kebab-case.md`，例如 `quick-start.md`、`api-development.md`。
- 每个领域目录使用 `README.md` 作为入口；`INDEX.md` 仅用于兼容旧入口或归档索引。
- 文档标题使用产品名称 `QueryMind（智询）`，避免混用项目旧名称、内部代号和“Agent优化系统”等临时称呼。
- 文件名不包含 `FINAL`、`COMPLETE`、`NEW`、`最新`、日期堆叠或个人姓名。

### 5.2 根目录例外

遵循 GitHub 社区习惯保留 `README.md`、`CONTRIBUTING.md`、`SECURITY.md`、`CODE_OF_CONDUCT.md`、`CHANGELOG.md` 和 `LICENSE` 等标准文件名。

### 5.3 发布文档

将当前发布说明统一为 `release-notes-vX.Y.Z.md`。保留旧文件名的兼容入口或重定向说明，更新所有索引和内部链接；不修改版本号本身，不把完成报告混入发布说明。

## 6. 内容更新规则

### 6.1 页面元信息

当前运维、治理、参考和入口页面包含：`Owner`、`Status`、`Last verified`。版本发布页使用版本号和发布日期，不强制复制元信息块。

### 6.2 必须核对的事实

- 启动命令、端口、应用入口和健康检查路径。
- `.env.example`、配置目录和 Docker Compose 文件中的实际变量名。
- Python、Conda、Node.js、前端构建和测试命令。
- 当前有效的 API 路由、角色权限、模型配置和可选依赖。
- 版本索引、发布日期、变更摘要和升级/迁移说明。

### 6.3 内容去重

- 快速开始只保留一条最短可验证路径；详细安装拆到 setup/configuration。
- 部署说明、Docker 说明和快速部署说明分别定义边界，并通过链接复用，不复制整段命令。
- FAQ 只保留用户问题；运维故障移到 troubleshooting，开发问题移到 development。
- 历史报告不再作为当前功能说明的来源。

### 6.4 语言策略

英文页面作为公开技术契约。中文入口提供完整导航和用户/运维常用说明；中文页面与英文不一致时，必须标注适用范围或链接到英文 canonical page，不制作未经核验的平行技术契约。

## 7. 实施分层

### 第一层：入口与治理

整理根 README、`docs/README.md`、所有领域 README、中文入口、文档政策和归档索引，先让用户能够从 GitHub 找到正确路径。

### 第二层：当前内容

按优先级更新 getting started、operations、reference、architecture 和 releases。先修复路径、命令、版本和配置事实，再处理语言和格式。

### 第三层：命名与兼容

对当前页面采用统一文件名；更新链接和目录索引。旧链接通过兼容页或明确归档链接承接，避免 GitHub 书签突然失效。

### 第四层：历史归档

校正 `docs/archive/INDEX.md` 的分类和统计，将残留旧目录引用改为历史说明或当前目标链接。归档内容不在本轮逐篇重写，只修复会误导当前用户的入口信息。

## 8. 验证标准

- `docs/README.md` 能链接到所有当前领域入口，且不存在指向已删除目录的当前链接。
- 发布索引覆盖 `docs/releases/` 中全部版本说明，且每个版本只对应一个 canonical 页面。
- 当前文档不再把 `docs/guides/`、`docs/project/` 或 `internal_docs/` 作为可执行路径。
- 当前页面中的命令、端口和配置名能在仓库代码或配置中找到证据。
- 当前文档命名符合规则；归档中的旧命名可以保留，但必须被归档索引隔离。
- Markdown 相对链接、图片路径和代码示例通过自动化或脚本校验。
- 不修改与本次文档工作无关的代码，不覆盖已有未提交变更。

## 9. 非目标

- 不重写全部历史报告。
- 不引入外部文档平台或新的构建系统。
- 不在没有代码/配置证据的情况下补写功能承诺。
- 不删除历史文件，不重置工作区，也不清理用户已有的无关改动。

