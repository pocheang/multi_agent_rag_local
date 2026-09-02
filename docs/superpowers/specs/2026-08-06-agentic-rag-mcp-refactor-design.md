# Agentic RAG 与 Web MCP 重构设计

## 目标

将现有多条兼容工作流逐步收敛为一个可观察、可测试且支持第三方连接器的智能体编排平台。网页端保持 FastAPI + SSE 的交互方式；MCP 采用 Streamable HTTP 作为后端受控工具网关，而非由浏览器直接调用。

## 范围与非目标

本次重构覆盖前端、后端、智能体编排、检索、工具调用、MCP 连接器、安全治理、可观测性和迁移下线。

不在首期范围内：开放任意 shell 命令、任意文件写入、无审批的代码修改，或让浏览器持有第三方服务密钥。

## 目标执行流

```text
用户问题
  -> Router Agent
  -> Planner Agent
  -> RAG Agent
  -> Tool Agent
  -> Synthesizer Agent
  -> 最终答案
```

1. Router Agent 将问题归类为 `general_qa`、`knowledge_retrieval`、`web_search`、`tool_call` 或 `hybrid`，并输出置信度、是否需要规划及允许的能力集合。
2. Planner Agent 仅在复杂问题、混合问题或 Router 明确要求时执行，输出有依赖关系的 `TaskPlan`。简单问题保留一个直接子任务，避免不必要的模型调用。
3. RAG Agent 按子任务并发执行向量检索、BM25、Graph RAG 和 Web Search；统一重排、去重和来源冲突标记，产出 `EvidenceBundle`。
4. Tool Agent 根据计划、用户权限和工具策略调用内置工具或第三方连接器，产出 `ToolResult`。写操作必须等待网页端确认。
5. Synthesizer Agent 只读取 `TaskPlan`、`EvidenceBundle` 与 `ToolResult`，生成带行内引用的答案、冲突说明和可追溯执行摘要。

## 后端边界

后端采用领域边界而非按历史工作流堆叠代码。

```text
app/
  api/                 # HTTP、SSE、鉴权转换，不写 Agent 业务规则
  orchestration/       # 请求编排、状态机、执行策略、事件发布
  agents/
    router/             # 路由契约与实现
    planner/            # 任务拆分与依赖校验
    rag/                # 检索编排、融合、重排、证据标准化
    tool/               # 工具选择、审批、执行和结果适配
    synthesizer/        # 证据整合、引用与回答生成
  domain/               # Pydantic 契约、错误类型、策略接口
  retrieval/            # Vector、BM25、Graph、Web 的实现适配器
  mcp/                  # Gateway、Registry、连接器、鉴权和审计
  services/             # 数据库、密钥、审计、遥测等基础服务
```

`RAGPipeline` 是唯一的生产查询入口。在迁移期，它负责把旧 API 请求转换为新 `OrchestrationRequest`，而非继续选择三条彼此独立的业务工作流。旧 LangGraph、严格质量和高级工作流只作为带指标的兼容适配器保留，直到所有生产调用完成迁移并通过回滚观察期。

## 核心契约

所有 Agent 使用不可变 Pydantic 模型通信，禁止以无约束的 `dict[str, Any]` 作为跨层协议。

- `RouteDecision`: `intent`、`confidence`、`requires_plan`、`allowed_capabilities`、`reason`。
- `TaskPlan`: `tasks`、任务依赖 DAG、每项的 `retrieval_required`、`tool_required` 与预算。
- `EvidenceItem` / `EvidenceBundle`: 内容、来源、文档标识、页码、检索器、分数、时间戳、冲突组。
- `ToolCall` / `ToolResult`: 工具标识、经验证参数、权限范围、审批状态、结构化结果、可用户展示摘要。
- `FinalAnswer`: 回答正文、引用、未解决事项、冲突处理说明、执行摘要。
- `ExecutionEvent`: 阶段、状态、耗时、可安全展示的元数据，供 SSE 和追踪使用。

每个文件只承担一个可描述的职责；生产业务源码通常不超过约 300 行。超过该阈值时，按契约、策略、服务、适配器或 UI 子组件拆分，不以区域注释继续扩容单文件。

## MCP Gateway 与第三方连接器

独立部署 `querymind_mcp`，使用 Streamable HTTP。网页不会直接发送 MCP JSON-RPC；网页请求 FastAPI，编排器通过受鉴权的 MCP 客户端调用 Gateway。保留 stdio 入口只供本地开发工具使用。

Gateway 由以下组件组成：

- `registry`: 工具元数据、输入/输出 Schema、权限、风险标记、超时和限流策略。
- `connectors`: 数据库、REST API、企业系统和外部 MCP Server 的适配器；每个连接器独立包，不能把供应商代码放进 Agent。
- `credentials`: 用户/组织隔离的加密凭据存储，只返回脱敏展示值。
- `authorization`: 将会话身份映射为连接器和工具级 scope；不以工具注解作为安全判断。
- `approval`: 对写入、删除、发送及费用敏感操作创建一次性审批令牌，前端确认后才执行。
- `audit`: 记录调用人、连接器、参数摘要、批准人、耗时、结果状态和关联执行 ID，不记录密钥或敏感正文。

工具按 `querymind_<domain>_<action>` 命名，例如 `querymind_rag_search_evidence`、`querymind_connector_list_tables`、`querymind_ops_run_quality_check`。工具必须提供 Pydantic 输入校验、结构化输出、明确错误建议及 read-only/destructive/idempotent/open-world 标记。

`dev_*` 工具默认只读，仅提供代码索引、结构检查、定向测试、质量门禁和失败归因。任何自动修复必须由独立受控工作流创建变更、运行指定测试、生成差异和等待人工确认；禁止 MCP 暴露任意路径写入或任意命令执行。

## 前端设计

保留 React + TypeScript + Ant Design，但按功能拆分：

- `features/chat`: 提问、流式回答、引用与会话管理。
- `features/execution-trace`: 路由、计划、检索、工具、合成的实时状态与可展开诊断。
- `features/integrations`: 第三方连接器列表、创建、授权、测试连接、权限说明和凭据脱敏展示。
- `features/tool-approval`: 高风险工具调用的参数摘要、风险说明、确认或拒绝操作。
- `features/admin-quality`: 质量、延迟、失败率、连接器健康度和审计检索。

前端通过经过版本化的 REST/SSE API 获取模型，不能依赖内部 Agent 字段或直接拼接 MCP 请求。SSE 事件基于 `ExecutionEvent`，未知事件必须安全忽略并保留最终答案通道。

## 安全、可靠性与质量

- 远程 MCP 使用 OAuth 2.1 或等价的服务间令牌验证；令牌必须面向 Gateway 的受众。
- 所有连接器按用户、组织和数据源范围隔离；路径、URL、SQL/Cypher 与分页参数均做 Schema 级校验。
- Gateway 只对受信任后端网络开放；若在本地暴露 HTTP，校验 Origin 并启用 DNS rebinding 防护。
- 每个外部调用设置超时、重试边界、熔断器和降级事件；失败不会伪造成功的证据。
- 引用完整性、事实校验、语言一致性和安全检查仍是 Synthesizer 完成前的质量门禁。
- 观测指标包括路由置信度、计划任务数、每类检索命中与耗时、工具批准/失败率、引用覆盖率、P95 延迟及 MCP 连接器健康度。

## 迁移策略

1. 先建立新契约、事件模型和无副作用的编排骨架，继续由 `RAGPipeline` 对外提供现有 API。
2. 依次接入 Router、Planner、RAG、Tool、Synthesizer，并将既有 Agent 包装为适配器；每个阶段都有契约测试、影子流量比较和功能开关。
3. 上线 MCP Gateway 的只读内置工具，再接入用户配置的第三方只读连接器，最后加入审批式写工具。
4. 前端先消费稳定 SSE 与最终答案模型，再分阶段增加执行追踪、连接器管理和工具审批界面。
5. 当所有 API 和 MCP 调用都通过新编排器、指标达标且完成回滚观察期后，删除无生产引用的旧工作流包装器与重复路由逻辑。

## 验收标准

- 所有公开查询 API 仍通过 `RAGPipeline`，且现有调用可兼容迁移。
- 简单问题不产生 Planner 或 Tool 调用；复杂问题的子任务、工具和证据可追溯。
- 最终答案的事实性内容均能映射至 `EvidenceItem` 或 `ToolResult`。
- 网页可安全配置、测试和停用第三方连接器，且不会再次显示原始凭据。
- 高风险工具无网页确认和有效权限时绝不执行。
- MCP Gateway、后端和前端分别有单元、契约、集成与端到端测试；质量指标不低于当前已设基线。
- 超大文件按职责拆分，新增跨层协议不得使用无类型共享字典。
