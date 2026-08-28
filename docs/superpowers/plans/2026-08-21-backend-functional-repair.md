# QueryMind Backend Functional Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复后端审计确认的现有功能、权限、运行时生命周期、数据关系、异步阻塞和信息暴露问题，不增加产品功能。

**Architecture:** `app.api.dependencies` 继续持有查询运行时的权威对象，并提供集中式安全重载；消费者在执行时动态读取该模块。其余修复沿用现有 FastAPI、Pydantic Settings 和 SQLite 服务边界，以最小改动恢复既有契约。

**Tech Stack:** Python 3.12、FastAPI、Pydantic Settings、SQLite、Ruff

**Spec:** `docs/superpowers/specs/2026-08-21-backend-repair-design.md`

## Global Constraints

- 不新增产品功能、页面、接口能力或新的存储后端。
- 不执行真实 `app.db`、`querymind.db` 或 Chroma 数据清理。
- 不重建 Chroma 第三方数据库模式。
- 不处理与 QueryMind 无直接依赖关系的 CrewAI 环境冲突。
- 按用户要求不新增或运行 pytest、Vitest 等测试套件；使用 AST、Ruff、隔离导入和临时数据库功能探针。
- 保留工作区内全部既有修改；只编辑本计划列出的文件，不重置、不清理、不提交用户改动。
- 不创建 Git 提交，除非用户另行明确要求。

---

### Task 1: 修复认证审计和澄清权限契约

**Files:**
- Modify: `app/api/routes/public/auth.py:update_profile`
- Modify: `app/api/routes/public/clarification.py:check_clarification`
- Modify: `app/api/routes/public/clarification.py:reset_clarification`
- Modify: `app/api/routes/public/clarification.py:get_clarification_context`

**Interfaces:**
- Consumes: `_audit(request, *, action, resource_type, result, user=None, resource_id=None, detail=None)`；`_require_permission(user, action, request, resource_type, resource_id=None)`。
- Produces: 个人资料更新成功后写入合法审计事件；三个澄清接口使用 `query:run`，`/check` 仅在自动创建会话时额外使用 `session:create`。

- [ ] **Step 1: 修正个人资料成功审计调用**

将成功分支改成完整关键字参数，禁止继续传入不存在的 `user_id`、`details`：

```python
_audit(
    request,
    action="profile.updated",
    resource_type="user",
    result="success",
    user=user,
    resource_id=user_id,
    detail="profile_updated",
)
```

- [ ] **Step 2: 统一澄清查询权限**

在三个端点进入历史存储前调用：

```python
_require_permission(user, "query:run", request, "query")
```

把两个现有 `query:execute` 替换为 `query:run`，并给 `/check` 补齐该检查。

三个端点在访问历史存储前均通过现有 `_require_valid_session_id(...)` 规范化会话 ID；`/check` 将返回值写回 `req.session_id`，另外两个端点写回局部 `session_id`。

- [ ] **Step 3: 仅在自动创建会话时检查创建权限**

```python
session = history_store.get_session(req.session_id)
if session is None:
    _require_permission(user, "session:create", request, "session")
    session = history_store.create_session(session_id=req.session_id)
```

继续使用 `_history_store_for_user(user)` 保持用户命名空间隔离，不新增所有权模型。

- [ ] **Step 4: 执行无测试套件的契约探针**

Run:

```powershell
python -c "import inspect; from app.api.utils.auth_helpers import _audit; print(inspect.signature(_audit))"
rg -n 'query:execute|query:run|session:create' app/api/routes/public/clarification.py
```

Expected: `_audit` 签名与成功调用一致；澄清文件不再包含 `query:execute`，并包含三个 `query:run` 和一个条件式 `session:create`。

### Task 2: 建立单一查询运行时并修复配置重载

**Files:**
- Modify: `app/api/dependencies.py`
- Modify: `app/api/routes/admin/settings.py:admin_reload_config`
- Modify: `app/api/query/request.py`
- Modify: `app/api/query/execution.py`
- Modify: `app/api/query/streaming/cache.py`
- Modify: `app/api/query/streaming/execution.py`
- Modify: `app/api/routes/public/query_stream.py`
- Modify: `app/api/application/lifespan.py`
- Modify: `app/api/routes/operations/health.py`

**Interfaces:**
- Consumes: `reload_settings() -> Settings`、`BackgroundTaskQueue.start()`、`BackgroundTaskQueue.stop(timeout: float)`。
- Produces: 不可变 `QueryRuntime`、`get_query_runtime() -> QueryRuntime`、`reload_query_runtime(new_settings: Settings) -> QueryRuntime`；调用成功后单次替换权威状态，失败保留旧对象。

- [ ] **Step 1: 在权威模块集中构建运行时对象**

增加不可变状态和私有构建函数，复用启动与重载参数：

```python
@dataclass(frozen=True, slots=True)
class QueryRuntime:
    settings: Settings
    query_guard: QueryLoadGuard
    query_result_cache: QueryResultCache
    quota_guard: QuotaGuard
    shadow_queue: BackgroundTaskQueue


def _build_query_runtime(new_settings: Settings) -> QueryRuntime:
    return QueryRuntime(
        settings=new_settings,
        query_guard=QueryLoadGuard(
            per_user_max_requests=new_settings.query_rate_limit_max_attempts,
            per_user_window_seconds=new_settings.query_rate_limit_window_seconds,
            max_concurrent=new_settings.query_max_concurrent,
            max_waiting=new_settings.query_max_waiting,
            acquire_timeout_ms=new_settings.query_acquire_timeout_ms,
            backend=new_settings.query_guard_backend,
        ),
        query_result_cache=QueryResultCache(
            backend=new_settings.query_result_cache_backend,
            ttl_seconds=new_settings.query_result_cache_ttl_seconds,
            max_items=new_settings.query_result_cache_max_items,
            session_ttl_seconds=new_settings.query_result_session_ttl_seconds,
        ),
        quota_guard=QuotaGuard(),
        shadow_queue=BackgroundTaskQueue(
            maxsize=new_settings.shadow_queue_maxsize,
            workers=new_settings.shadow_queue_workers,
            name="shadow-query",
        ),
    )
```

模块首次初始化和重载均调用同一构建函数，避免两份参数清单漂移。

- [ ] **Step 2: 实现先启动、后交换、最后停止旧队列**

用模块锁保护单一状态引用交换：

```python
def get_query_runtime() -> QueryRuntime:
    return _query_runtime


def reload_query_runtime(new_settings: Settings) -> QueryRuntime:
    global _query_runtime, settings
    new_runtime = _build_query_runtime(new_settings)
    try:
        new_runtime.shadow_queue.start()
    except Exception:
        new_runtime.shadow_queue.stop(timeout=1.0)
        raise
    with _runtime_reload_lock:
        old_runtime = _query_runtime
        _query_runtime = new_runtime
        settings = new_settings
        auto_ingest_watcher.settings = new_settings
    old_runtime.shadow_queue.stop(timeout=1.0)
    return new_runtime
```

若新队列启动失败，调用 `new_queue.stop(timeout=1.0)` 后重新抛出，旧引用不得改变。

- [ ] **Step 3: 管理端只调用权威重载入口**

`admin_reload_config` 中删除局部 `global`、运行时类导入和手工重建代码，流程固定为：

```python
new_settings = reload_settings()
runtime_snapshot = dependencies.reload_query_runtime(new_settings)
```

后续缓存清理、Neo4j driver 关闭和响应快照使用 `new_settings`；审计成功只能发生在运行时切换完成后。

- [ ] **Step 4: 消费者动态读取运行时对象**

在查询请求、执行、lifespan 和健康路由中加入：

```python
from app.api import dependencies as api_dependencies
```

把导入时复制的 `query_result_cache`、`quota_guard`、`shadow_queue`、`query_guard`、`settings` 替换成执行时调用 `api_dependencies.get_query_runtime().<name>`。`dependencies.py` 自己的运行时辅助函数同样读取 `_query_runtime`；保留函数和不可重载的 `runtime_metrics` 直接导入。

- [ ] **Step 5: 执行对象身份与生命周期探针**

Run: 用内联 Python 构建 `Settings(APP_ENV="development")`，记录旧 `QueryRuntime` 及其四个服务的 `id()`，调用 `reload_query_runtime` 后断言 `get_query_runtime() is new_runtime` 且五个身份全部改变；最后在 `finally` 中执行 `get_query_runtime().shadow_queue.stop(timeout=2.0)`，避免后台线程泄漏。

Expected: 管理路由不再定义同名单例；所有直接消费者都通过模块属性访问；探针进程正常退出。

### Task 3: 修复提示词数据关系与生产签名配置

**Files:**
- Modify: `app/services/prompts/store.py:delete_prompt`
- Modify: `app/core/config.py`
- Modify: `app/services/observability/alerting.py:resolve_signing_secret`
- Modify: `app/api/application/lifespan.py`
- Modify: `app/api/query/response.py`
- Modify: `.env.example`

**Interfaces:**
- Consumes: `resolve_signing_secret() -> tuple[str | None, str | None]`。
- Produces: `resolve_response_signing_secret(settings: Settings) -> tuple[str | None, str | None]`、`validate_security_settings(settings: Settings) -> None`；生产环境签名缺密钥时抛出 `RuntimeError`，非生产环境记录警告。

- [ ] **Step 1: 在同一事务删除提示词及版本**

```python
exists = conn.execute(
    "SELECT 1 FROM prompt_templates WHERE prompt_id=? AND user_id=?",
    (prompt_id, user_id),
).fetchone()
if exists is None:
    return False
conn.execute(
    "DELETE FROM prompt_template_versions WHERE prompt_id=? AND user_id=?",
    (prompt_id, user_id),
)
conn.execute(
    "DELETE FROM prompt_templates WHERE prompt_id=? AND user_id=?",
    (prompt_id, user_id),
)
return True
```

SQLite context manager负责一起提交或回滚；不得操作真实数据库里的既有孤儿行。

- [ ] **Step 2: 增加集中式签名校验**

在 `app/core/config.py` 增加接收显式 Settings 的密钥解析与校验函数，避免从 config 反向导入 alerting。生产环境判定接受 `production` 和 `prod`：

```python
def resolve_response_signing_secret(settings: Settings) -> tuple[str | None, str | None]:
    active_kid = settings.response_signing_active_kid.strip() or "v1"
    mapping: dict[str, str] = {}
    for pair in settings.response_signing_keys.split(";"):
        if ":" not in pair:
            continue
        kid, secret = pair.split(":", 1)
        if kid.strip() and secret.strip():
            mapping[kid.strip()] = secret.strip()
    if active_kid in mapping:
        return active_kid, mapping[active_kid]
    legacy_secret = settings.response_signing_secret.strip()
    return (active_kid, legacy_secret) if legacy_secret else (None, None)


def validate_security_settings(settings: Settings) -> None:
    if not settings.response_signing_enabled:
        return
    kid, secret = resolve_response_signing_secret(settings)
    if kid and secret:
        return
    if settings.app_env.strip().lower() in {"production", "prod"}:
        raise RuntimeError("response signing is enabled but no active signing key is configured")
    logger.warning("Response signing is enabled but no active signing key is configured")
```

`app/services/observability/alerting.py` 的 `resolve_signing_secret()` 改为 `return resolve_response_signing_secret(get_settings())`，保持现有调用接口。

- [ ] **Step 3: 在启动与管理重载时执行校验**

lifespan 启动后台队列之前调用 `validate_security_settings(api_dependencies.settings)`；管理重载在交换运行时对象之前校验 `new_settings`，校验失败时旧运行时继续服务。

- [ ] **Step 4: 响应签名动态读取设置**

`maybe_sign_response` 使用 `api_dependencies.get_query_runtime().settings.response_signing_enabled`，删除导入时复制的 `settings`，确保只读取已成功切换的配置。

- [ ] **Step 5: 对齐 `.env.example` 和 Settings 字段**

把示例键统一为 `CHROMA_PERSIST_DIR`、`CORS_ALLOW_ORIGINS`、`NEO4J_USERNAME`、`OAUTH_REDIRECT_URI`；在 Settings 增加：

```python
sqlite_busy_timeout_seconds: float = Field(default=10.0, ge=1.0, le=3600.0, alias="SQLITE_BUSY_TIMEOUT_SECONDS")
csrf_enabled: bool = Field(default=True, alias="CSRF_ENABLED")
rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
```

示例签名密钥保留空占位和生产必填说明，不写入秘密。

- [ ] **Step 6: 执行临时数据与签名探针**

Run: 在临时目录创建 `PromptStore` 数据库，创建并更新提示词后删除，查询模板和版本计数均为 `0`；分别构造 dev/prod Settings，确认 dev 仅警告、prod 抛出固定 `RuntimeError`、配置有效密钥时通过。

Expected: 临时数据关系完整；真实 `data/app.db` 未被打开为写连接。

### Task 4: 消除 FastAPI 事件循环中的同步阻塞

**Files:**
- Modify: `app/api/routes/sessions/metadata.py`
- Modify: `app/api/routes/operations/evaluation.py`

**Interfaces:**
- Consumes: 现有同步 `SessionMetadataService`、评估器和结果文件服务。
- Produces: 相同 URL、依赖、参数和响应模型的同步 `def` 路由，由 FastAPI 在线程池执行。

- [ ] **Step 1: 确认目标端点没有 await**

Run:

```powershell
rg -n '^async def |await ' app/api/routes/sessions/metadata.py app/api/routes/operations/evaluation.py
```

Expected: 文件包含 `async def` 但不包含实际 `await`。

- [ ] **Step 2: 转换会话元数据端点**

把 `update_session_metadata`、`get_session_metadata`、`delete_session_metadata`、`extract_auto_tags`、`search_sessions`、`get_all_tags`、`get_search_facets` 从 `async def` 改为 `def`，函数体、异常映射和响应模型不变。

- [ ] **Step 3: 转换同步评估端点**

把 `list_queries`、`run_evaluation`、`get_results`、`compare_systems`、`list_systems`、`health_check` 从 `async def` 改为 `def`；同时把内部异常的 500 文本改为固定通用文本，日志保留异常。

- [ ] **Step 4: 验证路由仍能被 FastAPI 注册**

Run: 隔离导入应用，枚举上述 route endpoint 并用 `inspect.iscoroutinefunction` 确认为 `False`。

Expected: URL 和方法集合不变，目标 endpoint 全部为同步函数。

### Task 5: 保护内部诊断接口并停止泄露内部异常

**Files:**
- Modify: `app/api/routes/operations/health.py`
- Modify: `app/api/routes/operations/agent_health.py`
- Modify: `app/api/routes/compatibility/advanced_rag.py`
- Modify: `app/api/routes/compatibility/enhanced_query.py`
- Modify: `app/api/routes/optimization/performance.py`

**Interfaces:**
- Consumes: `require_admin` FastAPI dependency；`internal_error(message)`。
- Produces: `/health`、`/ready`、`/metrics` 仍公开；详细运行时配置、统计和 circuit breaker 状态要求管理员；未知 500 不包含 `str(e)`。

- [ ] **Step 1: 为详细诊断路由加管理员依赖**

对以下 decorator 增加 `dependencies=[Depends(require_admin)]`：

```text
/circuit-breakers
/api/v1/agents/health
/api/v1/agents/{agent_name}/health
/api/advanced-rag/config
/api/v1/enhanced/config
/api/v1/enhanced/stats
```

已有管理员依赖不得重复添加。基础健康、就绪和 metrics 路由保持公开。

- [ ] **Step 2: 固定未知 500 的对外文本**

异常日志继续使用固定上下文，例如 `logger.exception("Enhanced query failed")`；对外改成稳定文本：

```python
raise internal_error("Unable to process the request")
```

仅清理审计报告确认的 advanced/enhanced、agent diagnostics、evaluation 和 optimization 未知 500；400/403/404 的业务校验信息保持现有语义。

- [ ] **Step 3: 检查公开路由的鉴权矩阵**

Run: 隔离导入应用并输出目标 path 的 dependency callable 名称。

Expected: `/health`、`/ready`、`/metrics` 无管理员依赖；六个详细诊断路由包含 `require_admin`。

### Task 6: 修复确定性静态问题和版本漂移

**Files:**
- Modify: `app/services/query/synonyms.py`
- Modify: `app/services/sessions/search.py`
- Modify: `app/api/routes/operations/health.py`

**Interfaces:**
- Consumes: `app.__version__`、`SessionMetadataService`。
- Produces: 无重复字典键、无未定义类型名、健康版本与包版本一致。

- [ ] **Step 1: 合并重复“安全”同义词**

删除第二个重复字典键，把两个集合的成员合并到一个 `"安全"` 项，保持所有现有词项。

- [ ] **Step 2: 补齐类型导入**

在 `app/services/sessions/search.py` 从实际定义模块导入 `SessionMetadataService`，不改运行时逻辑。

- [ ] **Step 3: 使用包版本**

在健康路由导入 `from app.__version__ import __version__`，把硬编码 `"0.6.1"` 替换为 `__version__`。

- [ ] **Step 4: 运行目标 Ruff 规则**

Run:

```powershell
ruff check app/services/query/synonyms.py app/services/sessions/search.py app/api/routes/operations/health.py --select F601,F821
```

Expected: `All checks passed!`

### Task 7: 全量功能级验证与审计记录更新

**Files:**
- Modify: `.codex-audit/backend-review-2026-08-21/audit_report.md`
- Modify: `.codex-audit/backend-review-2026-08-21/audit_report.json`

**Interfaces:**
- Consumes: Tasks 1–6 的全部修复。
- Produces: 可复核的静态、导入、路由、临时数据库和真实数据库只读证据。

- [ ] **Step 1: 记录真实数据库修改前哈希**

Run:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath data/app.db
```

Expected: 与审计基线 `2F9E040F5484DB004D2A5CF7C2C2717D48610BF1D1402E9A0297F1FD7D09D442` 一致；若不一致，只报告现状，不覆盖数据库。

- [ ] **Step 2: 解析所有后端 Python 文件**

Run:

```powershell
python -c "import ast,pathlib; files=list(pathlib.Path('app').rglob('*.py')); [ast.parse(p.read_text(encoding='utf-8'), filename=str(p)) for p in files]; print(f'parsed={len(files)}')"
```

Expected: 0 个语法错误。

- [ ] **Step 3: 运行与本轮修改相关的 Ruff 规则**

Run:

```powershell
ruff check app/api app/core/config.py app/services/prompts/store.py app/services/query/synonyms.py app/services/sessions/search.py --select F601,F821,F841
```

Expected: 本轮修改不产生 F601、F821、F841；既有无关告警单独记录，不扩大修复范围。

- [ ] **Step 4: 隔离导入 FastAPI 应用**

Run: 将所有可写数据路径指向临时目录，导入生产 FastAPI app，统计 APIRoute、重复 method+path 和目标鉴权依赖，退出前停止后台队列。

Expected: 应用导入成功；0 个重复 method+path；目标权限与 Task 1、Task 5 一致。

- [ ] **Step 5: 运行临时 SQLite 和运行时重载探针**

Run: 重复 Task 2、Task 3 的隔离探针并输出对象身份、队列状态、提示词模板/版本计数和签名校验结果。

Expected: 所有断言通过，进程无残留工作线程。

- [ ] **Step 6: 核对真实数据库哈希并更新审计报告**

再次运行 `Get-FileHash`，必须与 Step 1 完全一致。把已修复项、未执行真实数据清理、未处理第三方环境冲突和验证命令结果写回 Markdown/JSON；不得把未验证事项标记为完成。
