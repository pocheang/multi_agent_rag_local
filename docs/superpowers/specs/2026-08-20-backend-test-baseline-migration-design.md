# Backend Test Baseline Migration Design

## 目标

恢复当前后端架构的完整 pytest 收集与执行门禁，处理仍导入已退役 Agent/Graph 模块的旧测试，并补齐 `pyproject.toml` 已声明但当前 `.venv` 缺失的依赖。

本工作只维护后端测试基线和测试运行环境，不新增业务功能，不恢复已退役架构，不检查或修改前端。

## 当前基线

- FastAPI 应用可以导入并注册 169 条路由。
- 与上一轮后端修复相关的集中回归为 155 passed。
- 完整 `pytest -q` 收集到 1386 项，但出现 47 个 collection error。
- 主要错误来源：
  - 测试继续导入已删除的 legacy Agent compatibility wrapper。
  - 测试继续导入已删除的 LangGraph workflow、node、streaming 和 Neo4j wrapper。
  - 当前 `.venv` 缺少项目核心依赖 `mcp`、`jieba`、`psutil`。
  - 部分多模态测试导入 `pandas`，但 `pandas` 当前未在核心或 optional dependencies 中声明。
  - benchmark 测试存在测试模块自身的导入路径错误。

明确记录架构退役的提交包括：

- `d1075732`：删除 legacy agent compatibility wrappers。
- `5d05e6f5`：删除旧 LangGraph system。
- `54192131`：继续删除 agent compatibility wrappers。
- `e322be7e`：删除 obsolete EnhancedRAGWorkflow 和 legacy tests。
- `ccbaec34`：删除最后的 legacy workflow test file。

## 方案选择

采用“与退役提交对齐”的测试迁移方案。

不恢复旧 compatibility module，不通过 `pytest.ini`、`norecursedirs`、全局 skip 或 ignore 隐藏 collection error。每个失败测试文件必须依据其测试意图归入以下一种处置：

1. **删除**：测试只验证已明确退役的模块、wrapper 或 workflow，本身不再对应任何生产契约。
2. **迁移**：测试验证的业务行为仍存在，但入口已迁移到 canonical Agent、Pipeline、Orchestration、Retriever 或 Service。
3. **修复测试基础设施**：生产能力仍存在，失败来自错误的测试内导入、fixture 或包路径。
4. **补齐声明依赖**：依赖已经在 `pyproject.toml` 中声明，只是当前 `.venv` 未安装。
5. **重新归类 optional dependency**：测试确实覆盖受支持的可选能力，但依赖未声明；只在证据充分时增加对应 extra，不把重型依赖无条件加入核心。

## 删除判据

只有同时满足以下条件才删除测试文件：

- 被测 import 指向上述退役提交明确删除的模块；
- 当前生产路由、Service、Pipeline 和 Orchestration 不再调用该模块；
- 测试断言针对旧模块内部实现或旧状态结构，不能直接表达当前公开契约；
- 当前 canonical 路径已有等价行为覆盖，或该行为随旧架构一起明确退役。

删除前使用 `git log`/`git show` 核对历史，避免把意外缺失模块误判为退役模块。

## 迁移判据

满足以下任一条件时迁移而不是删除：

- 测试验证的是仍存在的 API、权限、Session 隔离、RAG 结果、路由决策、引用、降级或执行追踪契约；
- 当前 canonical 模块提供等价的公开入口；
- 生产调用链仍依赖该行为，但测试只是在 patch/import 旧路径。

迁移测试只更换入口、fixture 和期望数据结构，不为迎合旧断言修改生产业务逻辑。若旧断言与当前已批准架构冲突，以现行公开契约和生产调用链为准。

## 依赖策略

### 已声明核心依赖

使用当前项目环境安装方式补齐：

- `mcp>=1.24.0,<2.0`
- `jieba>=0.42.1`
- `psutil>=7.0.0,<8.0`

安装后通过 `pip check` 验证环境一致性。

### 未声明依赖

`pandas` 不直接加入核心 dependencies。先检查 `tests/services/multimodal/test_table_extractor.py` 和生产 table extraction 实现：

- 若生产实现把 pandas 作为必需依赖，则在最小合适的 optional extra 中声明，并让测试按该 extra 运行；
- 若生产实现不需要 pandas，只是测试构造数据时使用，则改用标准库或已有依赖构造等价输入；
- 若对应能力已经退役，则按删除判据处理测试。

## 分批执行

### 批次一：环境与测试基础设施

- 安装已声明但缺失的核心依赖。
- 修复 benchmark 等测试自身的 import path。
- 重跑 collect-only，建立新的错误清单。

### 批次二：Legacy Agent 测试

- 对照 agent wrapper 删除提交逐文件分类。
- 删除只验证 wrapper 内部实现的测试。
- 将仍有业务价值的断言迁移到 `app/agents/*` canonical services 或 `app/orchestration/*` 公开契约。

### 批次三：Legacy Graph/Workflow 测试

- 删除只验证旧 LangGraph node/state/workflow/stream processor 的测试。
- 把仍需要的执行、流式、route、citation 和 trace 行为迁移到 `RAGPipeline`、`OrchestrationEngine` 和当前 SSE execution tests。

### 批次四：多模态、MCP 和语言测试

- 在依赖补齐后重新运行 MCP 与中文处理测试。
- 依据生产实现处理 pandas 归属。
- 只修真实的当前契约失败。

### 批次五：完整运行与残余失败

- 先达到零 collection error。
- 执行完整 pytest。
- 对运行期失败使用 root-cause 分类：测试过期、环境外部服务、或真实生产缺陷。
- 测试过期则迁移；外部服务应使用项目既有 mock/fixture 边界；真实生产缺陷必须先增加失败回归再做最小修复。

## 测试与门禁

每个批次至少执行：

1. 受影响测试文件的定点 pytest。
2. `python -m pytest --collect-only -q`。
3. 当前已通过的 155 项后端集中回归，确保基线维护不破坏上一轮修复。

最终验收：

- `python -m compileall -q app tests` 通过。
- `ruff check app tests --select E9,F63,F7,F82` 不存在会阻断执行的错误。
- `python -m pytest --collect-only -q` 零 collection error。
- `python -m pytest -q` 完整执行完成。
- `pip check` 通过。
- 不新增旧 compatibility wrapper，不新增全局 skip/ignore，不修改前端。

若完整 suite 需要 Redis、Neo4j、模型服务或原生 OCR 等未提供的外部运行环境，相应用例必须使用项目既有的隔离边界，或明确归入单独的 integration marker；不能把外部服务缺失伪装成生产代码失败，也不能静默跳过普通单元测试。

## 风险控制

- 工作区已有大量用户修改，所有提交和 diff 只包含本任务明确处理的测试、依赖声明、规格和计划文件。
- 不批量删除整个测试目录；每个删除项必须能映射到退役提交和无现行调用方证据。
- 不通过恢复旧模块让旧测试通过。
- 不为了测试通过而改变当前 API、Agent、Pipeline 或数据契约。
- 若同一生产能力在新旧测试间断言冲突，先沿生产调用链确认，再保留当前契约测试。

## 交付物

- 零 collection error 的后端测试集。
- 更新后的必要依赖声明或测试 fixture。
- 每批迁移/删除清单及其历史证据。
- 完整 pytest、compileall、Ruff 和 pip check 结果。
- 对任何无法在本机完成的外部环境门禁给出明确重跑命令。
