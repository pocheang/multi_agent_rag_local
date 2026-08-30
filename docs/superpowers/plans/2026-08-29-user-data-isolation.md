# 用户数据隔离加固计划

日期：2026-08-29（阶段 1 完成于 2026-08-30）
状态：**四个阶段全部完成**（2026-08-29 ~ 2026-08-30）
⚠️ 阶段 2 的 owner 过滤要求分片带 owner 元数据 —— **有存量索引的环境上线前必须重建索引**，见阶段 2 的部署风险。
范围：`app/`（检索、编排、存储、API）+ `frontend/`（登出态）

---

## 1. 目标与非目标

### 目标（本计划要建立的不变量）

- **INV-1 检索即隔离**：任何一次检索调用，如果没有一个显式解析出来的 `AccessScope`，
  就不允许触达向量库 / BM25 / 图谱。"没有 scope" 必须等价于"零结果"，
  不能等价于"全库"。
- **INV-2 出口再校验**：证据进入模型上下文之前、答案带引用返回之前各校验一次
  （今天已成立，不要改坏）。
- **INV-3 存储层纵深**：即使上层传错了 source 列表，存储层的 metadata 过滤也应拦住
  跨 owner/tenant 的分片。
- **INV-4 资源按不可变 ID 寻址**：删除、重建索引不得以文件名为主键。
- **INV-5 无侧信道**：诊断字段、缓存键、日志、时延都不得泄露"别人有多少/哪些文档"。

### 非目标

- 不引入多租户数据库、不改 SQLite → PostgreSQL（`DATABASE_URL` 已于 2026-08-29 移除）。
- 不改 RBAC 角色模型（`app/services/security/rbac.py` 现有三角色够用）。
- 不做静态加密（uploads 明文落盘），除非后续有合规要求。
- 不动 `data/docs/` 的共享语料语义 —— 它是**故意**对所有人可见的。

---

## 2. 威胁模型

| 编号 | 攻击者 | 目标 | 现状 |
|---|---|---|---|
| T1 | 已认证的普通用户 A | 通过提问读到用户 B 上传的文档内容 | 出口 + 检索两层都挡（阶段 1） |
| T2 | 已认证用户 A | 推断 B 上传了多少 / 哪些文档（存在性泄露） | 诊断字段已脱敏（阶段 1）；缓存键已带 owner（阶段 2） |
| T3 | 已认证用户 A | 直接调 API 读 / 删 B 的会话、文档、prompt | 全部已挡（阶段 3）|
| T4 | 管理员误操作 | 删除同名的他人文件 | 已挡：按 id 寻址 + admin 范围收窄（阶段 3）|
| T5 | 共用浏览器的下一个用户 | 看到上一个用户的会话列表 | 已挡：登出与身份变化时 reset store（阶段 4）|
| T6 | 外部模型供应商 | 拿到用户文档中的敏感串 | `outbound_redaction` 默认开启，已核对（阶段 4）|

---

## 3. 现状盘点：已经成立的部分（**不要重构**）

这些是真在跑的，改动时不要破坏：

- **出口授权 fail-closed**：`app/privacy/dlp.py:18` `evidence_is_authorized()` ——
  `if not scope.document_ids and not scope.allowed_sources: return False`，
  空 scope 拒绝一切。两个调用点：
  - `app/knowledge/context.py:38`（证据进上下文前）
  - `app/orchestration/langgraph/nodes.py:401` `output_filter`（引用出站前）
- **Scope 解析 fail-closed**：`app/services/security/access_scope.py:96` —— 无 actor 直接
  `AccessScopeError`；请求的 source 若不在可见集内直接抛错，不做静默裁剪。
- **可见性规则**：`list_visible_document_rows()` 覆盖 tenant / ACL tag / owner /
  visibility / admin 跨租户，逐条判定。
- **上传**：per-user 目录 `uploads/{user_id}/`、文件名净化、魔数校验、按 owner 去重
  （`app/services/documents/dedup.py:246` `find_duplicate_for_user`）。
- **会话隔离**：`HistoryStore(base_dir=sessions_path/{user_id})`；sqlite 后端全部 SQL
  带 `namespace=?`（`app/services/sessions/history.py:380,411`）。
- **会话元数据**：按 `sha256(user_id)` 分库（`app/services/sessions/service.py:50`）。
- **Prompt / Wiki**：全部 SQL 带 `user_id=?` / `tenant_id=?`。
- **执行轨迹**：两个 SSE 端点都有 ownership 校验
  （`app/api/routes/public/orchestration.py:52`、`app/api/routes/operations/agent_tracking.py:22`）。
- **向量库默认 fail-closed**：`similarity_search(require_source_filter=True)`。
- **分片元数据已带隔离维度**：`_canonical_metadata()` 写入 `tenant_id` / `owner_user_id` /
  `visibility` / `acl_tags`，且 `normalize_metadata()` 不做白名单裁剪 ——
  **这些字段已经在 Chroma 里，阶段 2 不需要重新灌库**，仅需回填历史分片。

---

## 4. 缺口清单

### ~~P0-1 检索阶段完全没有隔离，只有出口过滤~~ —— 已修复（阶段 1，2026-08-30）

`allowed_sources=None` 曾在整条链路上被解释为"全库检索"。实测确认：一个无 scope 的
请求确实把 Bob 的文档返回给了 Alice 的检索调用。涉及的调用点（**实际是 4 个，
不是初稿写的 3 个**）：

- `app/agents/rag/service.py:504` —— `_vector_retrieve` 硬编码 `require_source_filter=False`
- `app/retrievers/hybrid/retriever.py:133` —— `allowed_sources is None` → 不过滤
- `app/retrievers/hybrid/retriever.py:137` —— 捕获 `TypeError` 后**降级为不过滤**
- `app/api/routes/internal/pipeline_contract.py:63` —— `allowed_sources=None` 原样下传
  （admin ops 基准测试走这条）
- `app/api/routes/public/clarification.py:147` —— 构造空 `RequestScope()`
- `app/knowledge/adapters.py::_retrieve_vector` —— 经 `asyncio.to_thread` 位置传参传 `False`
  （阶段 0 的守卫只认 `run_in_executor`，漏掉了它）

后果，按严重度排序：

1. **召回被别人的文档挤掉** —— 这是当前最实际的损害。top-k 在全库上算，用户自己的
   分片被别人的高分分片挤出候选集，然后在出口被丢掉，用户拿到的是"没找到"。
   这是个**质量 bug 伪装成的安全 bug**。
2. **存在性侧信道（T2）** —— `context_scope_dropped`、`pre_rerank_count`、
   `context_input_count` 直接出现在 `diagnostics` 里并进入 `execution_metadata`。
   用户能从"丢弃了 47 条"反推别人有多少文档。
3. **只差一个调用方就变成真泄漏** —— 任何绕过 `ContextBuilder` 的新路径（比如直接
   消费 `EvidenceBundle.items`）立刻就是跨用户读取。

### ~~P0-2 出口校验对 web / tool / memory 层无条件放行~~ —— 已修复（阶段 1，2026-08-30）

**修法与初稿不同**：不是让 memory 走普通 scope 校验（那会让记忆功能全废），
而是校验 `memory://{tenant}/{user}/` 归属前缀。详见阶段 1 的偏差说明。

原始判断：

`app/privacy/dlp.py:21`：`if item.layer in {"web", "tool", "memory"}: return True`。

`web` / `tool` 放行是合理的（不是用户文档）。**`memory` 不是** —— 一旦接入用户记忆
检索（`app/services/sessions/memory_store.py` 已经有 `list_global()`），它会绕过全部
scope 校验。

### ~~P0-3 `source` 查询参数绕过可见性解析 + admin 越权面过宽~~ —— 已修复（阶段 3，2026-08-30）

阶段 0 建测试时发现真实情况与初稿不同，此处已按代码更正。

**先说一个不是问题的地方**：`_resolve_manageable_source_for_filename()`
（`app/api/routes/public/documents.py:55`）是 fail-closed 的 ——
`if len(candidates) == 1` 才返回，同名多份直接返回 `None`。所以**纯文件名形式**
的端点不会误命中。这一点初稿写反了。

**真正的洞在 `source` 查询参数**。`app/api/routes/public/documents.py:110,155`：

```python
source = normalize_string(source) or _resolve_manageable_source_for_filename(filename, user)
```

调用方只要显式传 `?source=...`，上面那个 fail-closed 的解析就**整个被跳过**，
唯一剩下的校验是 `_is_source_manageable_for_user()`。而该函数
（`app/api/deps/documents.py:31`）对 admin 放行**整个 uploads 根**，
且不检查 `tenant:cross_read`（该权限已在 `access_scope.py:50` 定义并被那边使用）。

组合结果：admin 可以直接

```
DELETE /documents/report.pdf?source=/uploads/bob/report.pdf&remove_file=true
```

删掉 Bob 的文件，而审计记录里 `resource_id` 只有 `report.pdf`，
无法区分是谁的。普通用户不受影响 —— 对他们 `_is_source_manageable_for_user`
只放行 `uploads/{自己的 user_id}/` 之下，且 `Path.resolve()` 先归一化，
`..` 穿越拦得住（已由 `test_a_traversal_path_does_not_escape_the_owners_directory` 覆盖）。

`document_id`（`doc-{uuid4}`）早就存在，只是没用于路由。

### ~~P1-4 存储层没有纵深防御~~ —— 已修复（阶段 2，2026-08-30）

- Chroma 只按 `{"source": {"$in": allowed_sources}}` 过滤
  （`app/retrievers/stores/vector.py:185`）。source 是**文件系统路径列表**：
  用户文档一多，`$in` 既慢又脆。
- BM25 先把**全量语料**载入内存再在 Python 侧过滤
  （`app/retrievers/bm25_retriever.py:113`），且过滤后重建索引 —— 每查询 O(全库)。
- `owner_user_id` / `tenant_id` / `visibility` 已在分片元数据里，但**没进 where 子句**。

### ~~P1-5 图谱降级路径可能丢掉过滤~~ —— 已修复（阶段 2）；比初稿描述的小，见阶段 2 偏差

`app/graph/knowledge/cypher_validation.py:205,211`：用 `if allowed_sources` 选模板，
`None` 和 `[]` 都会选中**无过滤**模板。主查询失败时的兜底路径因此可能扫全图。

### ~~P1-6 检索缓存键维度不全~~ —— 已修复（阶段 2）

`app/retrievers/hybrid/retriever.py:33` 的 key 只含 `sorted(allowed_sources)`。
今天正确（结果只由 source 决定），但缺 `tenant_id` / `acl_tags` / `visibility`。
任何一个非 source 维度开始影响结果的那天，就是静默串号。

### ~~P1-7 `cached_vector_search` 是个待引爆的装置~~ —— 已删除（阶段 2）

`app/agents/shared/cache.py:51` 用 `kwargs.get("allowed_sources")` 组键 —— **位置传参
会让隔离维度静默消失**。当前零调用方。**直接删**，不要留着。

### ~~P1-8 `context_tracker` 是死代码且默认并桶~~ —— 已删除（阶段 4）

`app/services/sessions/context_tracker.py` 的读写函数全模块零调用方（只有清理协程被
`app/api/application/lifespan.py:77` 启动）。三个入口默认 `user_id="anonymous"`
（:129、:188、:197），会把所有无身份调用并到同一个桶。**删掉整个模块**，
同时摘掉 lifespan 里的启停。

### ~~P2-9 前端登出不清用户态~~ —— 已修复（阶段 4）；token 本来就清了，缺的是 store

- token 存 `localStorage`（`frontend/src/services/http/client.ts:59`）
- `authApi.logout()` 只清 CSRF（`frontend/src/services/api/auth.ts:34`）
- `useChatStore` / `useAdminStore` 无 reset

同一浏览器换人后，新用户在首次请求返回前会看到上一个人的会话列表。

### ~~P2-10 日志打印完整问题文本~~ —— 已修复（阶段 4）；实际 17 处，不是 2 处

`app/agents/rag/graph.py:126,254` 在 INFO 级别打完整 question。

### ~~P2-11 零隔离测试~~ —— 已解决（阶段 0，2026-08-29）

原状：`tests/` 共 14 个文件、62 条用例，没有一条跨用户用例。
现状：新增 `tests/security/` 43 条，见下方阶段 0。

---

## 5. 分阶段实施

### 阶段 0：先把不变量写成测试 —— **已完成（2026-08-29）**

**这一阶段不改任何生产代码。** 目的是让后续每一步都有可证伪的验收标准。

`tests/security/` 共 43 条，全仓库从 62 条涨到 105 条。
其中 **35 条绿**（钉住已成立的防线，防回归），**8 条 `xfail(strict=True)`**
（每个缺口一条，修好后 xpass 会**硬失败**，强制删除 marker，不会被遗忘）。

| 文件 | 绿 | xfail | 覆盖 |
|---|---|---|---|
| `test_scope_fail_closed.py` | 8 | 1 | 授权原语 fail-closed；P0-2 memory 层 |
| `test_retrieval_isolation.py` | 3 | 3 | 存储层过滤；P0-1 三个绕过点 |
| `test_scope_reaches_retrieval.py` | 3 | 2 | P0-1 步骤 4：scope 回写 |
| `test_no_side_channel.py` | 2 | 1 | T2 诊断字段计数泄露 |
| `test_document_addressing.py` | 5 | 1 | P0-3 admin uploads 根越权 |
| `test_session_isolation.py` | 12 | 0 | 会话隔离（file + sqlite 双后端） |
| `test_no_unrestricted_retrieval.py` | 3 | 0 | 静态棘轮 |

三个实现要点：

1. **静态守卫用 AST 而非 grep。** 三个越权调用点里有一个是**位置传参**穿过
   `run_in_executor` 的：

   ```python
   loop.run_in_executor(pool, similarity_search, question, None, sources, False)
   ```

   grep `require_source_filter=False` 完全找不到它。AST 检查同时覆盖直接调用和
   这种 thunk 形式，三个点全部捕获。

2. **静态守卫是棘轮不是硬断言。** `KNOWN_OFFENDERS` 记录当前每个模块的越权调用
   **数量**：数量只许降不许升，新增立刻红；某模块修好后 `test_the_known_offender_baseline_is_not_stale`
   会提示下调基线。这样 CI 在阶段 1–4 期间始终可用，同时不放过任何新增。

3. **每条 xfail 都验证过失败原因**（`--runxfail`），不是因为构造错误或
   import 失败而"碰巧红"。

**阶段 0 确认的事实**（部分与初稿不同，已回写到上面的缺口清单）：

- `_vector_retrieve` 在无 scope 的请求上确实返回了 Bob 的文档给 Alice
  （`test_vector_retrieve_refuses_a_request_with_no_resolved_scope`）。
- `privacy_permission` 之后 `request.source_scope` 仍是
  `RequestScope(allowed_sources=None, ...)`，而 resolver 解出的是
  `frozenset({'/uploads/alice/notes.pdf'})` —— 两者完全脱节。
- P0-3 的成因是 `source` 查询参数，不是文件名解析的歧义（见上）。
- 会话隔离在 file 和 sqlite 两个后端上都成立，无需改动。

---

### 阶段 1：把隔离左移到检索边界（P0-1、P0-2）—— **已完成（2026-08-30）**

投入产出比最高的一步，同时修掉了召回质量问题。7 个文件、+87/-20 行。

**实际改动**（与初稿的偏差在下面单独列出）：

1. **回写 scope（keystone）。** `app/orchestration/langgraph/nodes.py` 的
   `privacy_permission` 现在同时重写 `source_scope`，新增
   `_scope_to_request_scope()`。检索阶段**物理上拿不到**比解析结果更宽的范围，
   调用方传什么都无所谓 —— 这一条让 `pipeline_contract.py:63` 的
   `allowed_sources=None` 和 `clarification.py:147` 的空 `RequestScope`
   都变得无害，**两个文件一行没改**。

2. **`None` 与"空"分开。** `app/agents/rag/service.py::_get_allowed_sources`
   原来把空 frozenset 和 None 都折叠成 None（= 全库）。现在只有真正的 None
   才返回 None，空集返回 `[]`（= 零结果）。这正是"用户没有文档 → 看到所有人的文档"
   的成因。

3. **删掉三条 fail-open 分支。** `_vector_retrieve` 不再传 `False`；
   `_safe_similarity_search` 删掉 `allowed_sources is None → 不过滤`
   和 `except TypeError → 不过滤` 两条降级路径。

4. **`memory` 层按命名空间校验。** 见下方偏差说明。

5. **诊断字段脱敏。** `app/knowledge/context.py` 的 `context_scope_dropped`
   和 `context_input_count` 改为 `logger.warning`（带 user/tenant），不再进
   `execution_metadata`。`context_authorized_count` / `context_output_count`
   保留 —— 它们只描述调用方自己拿到了什么。

**与初稿的三处偏差**：

- **没有把 `require_source_filter` 改名成 `system_unrestricted`+reason。**
  改完 3 处调用点后越权调用归零，参数本身已无调用方使用，重命名只是搅动
  API 而不增加安全性。守卫测试已经钉死"不许有新的越权调用"，
  这比换个参数名更有效。

- **`memory` 层不是"走正常 scope 校验"，而是校验归属命名空间。**
  初稿的做法会让记忆功能全废：memory 项的 source 是
  `memory://{tenant}/{user}/{id}`，永远不会出现在 `allowed_sources`（只装文档路径）里，
  所以"走正常校验"= 全部丢弃。且 `app/memory/long_term.py:54` 的 provider
  本来就按 tenant/user 分目录，所以这不是活跃漏洞而是缺一层纵深。
  实际做法：新增 `memory_source_prefix(scope)`，memory 层校验
  `item.source.startswith("memory://{tenant}/{user}/")`。
  测试同时钉住了前缀碰撞（`memory://alice/alice2/` 不得匹配 `memory://alice/alice/`）。

- **越权调用点是 4 个不是 3 个。** `app/knowledge/adapters.py::_retrieve_vector`
  通过 `asyncio.to_thread` 位置传参传了 `False`，阶段 0 的 AST 守卫只认
  `run_in_executor`，漏掉了它。守卫已扩展为同时识别两种 thunk 形式。
  该处 `allowed` 恒为列表所以并非活跃漏洞，但已一并清理。

**验收结果**：

- `tests/security/` 43 → 48 条，其中 7 条 xfail 转绿并删除 marker，
  仅剩 1 条（P0-3，属阶段 3）。全仓库 105 → 111 条，全绿。
- `KNOWN_OFFENDERS` 基线从 `{service.py: 1, retriever.py: 2}` 清空为 `{}`。
- 新增 `test_the_graph_hands_retrieval_the_resolved_scope`：跑**真实 graph**，
  断言一个完全不传 scope 的调用方，检索器收到的仍是 `frozenset({ALICE_DOC})`。
  已用"临时还原修复"的方式确认这三条测试在修复前确实红。
- 新增两条正向测试防止过度收紧：`test_vector_retrieve_honours_a_resolved_scope`
  （正常路径仍能检索到自己的文档）、
  `test_vector_retrieve_returns_nothing_for_a_user_with_no_documents`。

**阶段 1 暴露的两个既有问题**（都不是本次引入）：

1. **admin 基准测试路径本来就是坏的。** `app/api/routes/admin/ops.py:163`
   的 `_execute_standard_profile` 调 `execute_standard_compatibility(question=...)`
   不传 `user` → `actor=None` → `AccessScopeResolver.resolve` 抛
   `AccessScopeError("authenticated user identity is required")`。
   这个 `resolve()` 调用在阶段 1 之前就存在，所以是既有 bug 而非回归。
   修法：让基准测试传发起请求的 admin 身份。

2. ~~**零文档用户连 web 检索也被短路。**~~ —— 已按产品决策修复（2026-08-30）。

   原状：`app/agents/rag/service.py:297` 的
   `if allowed_sources is not None and not allowed_sources: return EvidenceBundle()`
   会连 web 一起跳过，所以没上传过文件的用户连联网搜索都用不了。

   修法：不再整体短路，改为**只把文档类检索源摘掉**，web 保留：

   ```python
   enabled = []
   if readable_documents:            # allowed_sources is None or non-empty
       enabled.extend((("vector", ...), ("bm25", ...)))
       if route.effective_route in {"graph", "hybrid"}:
           enabled.append(("graph", ...))
   if "web" in route.allowed_capabilities:
       enabled.append(("web", ...))
   ```

   `KnowledgeOrchestrator._retrieve_source`（`app/knowledge/orchestrator.py:165`）
   **本来就**只对 `vector/bm25/graph/wiki/multimodal` 做空 scope 跳过，web 不在其列 ——
   服务层现在与编排层口径一致，而不是抢在前面短路。副作用是 `source_status`
   诊断只列真正尝试过的源，不再把没跑的源报成 failed。

   三种 scope 的行为因此被明确区分，并由
   `tests/security/test_retrieval_source_selection.py`（8 条）钉住：

   | scope | 文档检索 | web | 结果 |
   |---|---|---|---|
   | 有文档 | 跑 | 跑 | 正常 |
   | 空（零文档用户） | 不跑 | 跑 | 安静返回 web 结果 |
   | 缺失（None，调用方绕过 resolver） | 选中但被编排层跳过 | — | **抛 `RetrievalFailureError`** |

   最后一行是刻意的：把 None 也过滤掉会让"有人绕过了 resolver"变成一个
   看起来像"没搜到"的空结果。空 scope 安静、缺失 scope 响亮。

---

### 阶段 2：存储层纵深防御（P1-4、P1-5、P1-6、P1-7）—— **已完成（2026-08-30）**

> ⚠️ **上线前必须先重建索引。** 见下方"部署风险"。

**1. Chroma 加 owner 维度（P1-4a）。** `similarity_search` 新增可选
`owner: OwnerScope`，`where` 变为：

```python
{"$and": [
    {"source": {"$in": allowed_sources}},
    {"$or": [{"owner_user_id": {"$eq": owner.user_id}},
             {"visibility": {"$eq": "public"}},
             {"tenant_id": {"$eq": "shared"}}]},
]}
```

`source` 列表是从可见性规则**推导**出来的，`owner_user_id` 是入库时**独立写入**的，
所以要求两者同时成立，能收窄"可见性规则算错了"所能触及的范围。

`OwnerScope` 是 store 模块内的小 frozen dataclass，不是 `AccessScope` ——
store 需要的是一个可与分片元数据比对的身份，不是调用方的整个授权决策；
保持它小，能防止 store 长出关于授权的意见。

**2. 结果后置校验。** `_verify_sources` 检查 store 返回的每个分片的 `source`
确实在 `allowed_sources` 内，不在的丢弃并 `logger.error`。Chroma 自己会执行
`$in`，所以这只在过滤子句畸形、或超大 `$in` 行为异常时触发 —— 后者正是计划里
"用户文档一多，`$in` 既慢又脆"担心的情况。近乎零成本。

**3. owner 覆盖全部检索路径。** 计划没写但事关成败：一个只覆盖部分路径的安全守卫
比没有更糟 —— 它读起来像保护，却留着绕过的口子。owner 串到了三条路径：

| 路径 | 供给点 |
|---|---|
| 主向量检索 | `_vector_retrieve`（`request.actor`）|
| 编排器 | `_retrieve_vector`（`scope`）|
| 图谱降级 → hybrid | `_graph_retrieve` / `_retrieve_graph` → `run_graph_rag` → `_fallback_to_vector_rag` → `run_vector_rag` → `UnifiedVectorRAGAgent.execute` → `_execute_retrieval` → `hybrid_search_with_diagnostics` |

第三条是 7 层传递。在 `hybrid_search_with_diagnostics` 用
`functools.partial(_safe_similarity_search, owner=owner)` 绑定到 `vector_fn`
注入点，省掉了 `collect_candidates` 那两层 —— owner 属于向量那一跳，不属于候选收集。

`test_every_similarity_search_identifies_its_caller` 用 AST 枚举全部调用点，
要求都传 owner；两个确实没有调用方身份的（候选收集的 legacy 默认值、
离线评测 harness）在 `OWNERLESS_CALL_SITES` 里带理由列出。已验证漏掉任一处即报错。

**4. 缓存键补 owner（P1-6）。** owner 现在真的会改变 store 的返回，所以
`hybrid_search_with_diagnostics` 的 cache_key 必须带上它，否则同一 source 列表、
不同身份的两个调用方会互相串号。

**5. BM25 按 scope 缓存索引（P1-4b）。** 原来每次查询都重新过滤全库并重建索引，
一个用户连问三个问题就重建三次。新增 `_load_scoped_bm25`（LRU 32），
按排序后的 source 元组作键。同时 `bm25_search` 与 `similarity_search` 对齐：
`allowed_sources=None` 抛错而不是搜全库。

**6. 图谱降级模板（P1-5）。** `get_simpler_query` 的 `if allowed_sources` 改为
`if allowed_sources is not None`：空 scope 意味着"什么都不许读"，必须仍选带过滤的
模板（它匹配不到任何行），而不是退回无过滤模板。

**7. 删除 `cached_vector_search`（P1-7）** 及其缓存实例，连带从未被写入的
`_synthesis_cache` 和零调用方的 `get_agent_cache_stats` / `clear_agent_caches`。
`app/agents/shared/cache.py` 只剩 `cached_router_decision`（有真实调用方）。

---

#### ⚠️ 部署风险：老索引必须重建

实测（chromadb 1.5.9）：**`$eq` 不匹配不存在的键**。

```
仅 source 过滤 : ['a', 'b']
加 owner 子句  : ['a']        # b 没有 owner 元数据，被整个过滤掉
```

也就是说，任何在 `_canonical_metadata` 开始写 owner 字段**之前**入库的分片，
在 owner 子句开启后会**静默消失**（不报错，只是搜不到）。

- 本工作副本的 Chroma 是空的（0 条向量），所以无需回填。
- **有存量数据的环境必须先重建索引再上线**：重新 ingest 或对每个文档跑
  `rebuild_document_index`，两者都会写入 owner 元数据。
- 该行为由 `test_a_chunk_with_no_owner_metadata_is_excluded` 钉住，
  避免在生产上才发现。

---

#### 与计划的偏差

- **不需要回填脚本。** 计划里写"写一次性回填脚本给缺 `owner_user_id` 的历史分片补
  元数据"。实际上 store 是空的，且重建索引本身就会写入元数据 —— 一个未经真实数据
  验证的迁移脚本比一条明确的重建索引指令风险更大。

- **共享语料靠 `tenant_id == "shared"` 而非 `visibility == "public"`。**
  计划写"缺 owner 的分片按 `visibility=public` 处理"。实际上
  `app/ingestion/loaders/dispatch.py:181` 对没有 owner 的文档写
  `tenant_id="shared"`、`visibility="private"`，所以按 public 处理会漏掉整个
  `data/docs/` 共享语料。改用 `tenant_id == "shared"` 直接命中入库时的真实标记。
  上传路径恒定写入 `owner_user_id` 和 `tenant_id=owner_user_id`
  （`ingest_queue.py:118,122`），所以 `"shared"` 不会被上传文档误取。

- **不需要 admin 例外。** 一度担心 owner 过滤会比授权层更严，挡掉 admin 的跨租户读。
  实测认证后的 user dict 里**根本没有 `permissions` 字段**
  （`session_manager.py:66` 只返回 user_id/username/role/status/credit_balance），
  所以 `list_visible_document_rows` 里的
  `cross_tenant = role == "admin" and ("*" in permissions or ...)` 恒为 False ——
  **admin 今天没有跨租户文档读**。owner 过滤因此可以无条件应用。
  （`tenant_id` 和 `acl_tags` 同理，实际上是惰性的：tenant_id 恒等于 user_id。）

- **P1-5 比计划描述的小。** 计划称"`None` 和 `[]` 都会选中无过滤模板"，
  暗示是活跃漏洞。实际上 `Neo4jClient` 的三个入口
  （`search_entities` / `entity_neighbors` / `entity_paths_2hop`）都已对空列表提前
  `return []`，所以没有请求能走到那个分支。修的是函数自身的契约方向，
  并加了守卫测试钉住上游那三处提前返回。

- **P1-4b 是性能问题不是隔离问题。** 计划称 BM25"每查询 O(全库)"。
  实际上过滤本身是正确的；全库分词只做一次（`lru_cache`），每次查询的成本是
  O(全库) 扫描 + O(用户文档) 重建索引。修的是重建，不是隔离。

- **新发现并已修复（2026-08-30）**：BM25 在只有一个分片的 scope 上曾**永远返回空**。

  根因是**入选判据用错了**，不是 BM25 本身的问题：`bm25_search` 用
  `score > 0` 当作"文档是否含查询词"的代理，而这个代理在小索引上会反转 ——
  BM25 的 IDF 对"出现在多数文档中的词"为负，单文档索引里**每个**词都为负，
  于是命中的文档反而被丢掉。实测
  `BM25Okapi([...1 doc...]).get_scores(['compensation']) == [-0.27]`。
  该问题早于阶段 2，但 scoped 索引让"小语料"从例外变成常态 ——
  只上传了一个文件的用户拿不到任何 BM25 结果。

  修法：**把"匹配"和"排序"拆成两件事**。命中判定改为查询词与文档词集有交集，
  BM25 只负责排序。`_build_index` 顺带缓存每篇文档的词集，所以不会因此
  在每次查询时重新分词（那会抵消掉 scoped 索引缓存的意义）。

  顺带修掉一个同源的截断顺序错误：原来是先取 top-k 再过滤，所以非命中文档会占掉
  名额、返回少于 k 条；现在先筛命中再取 top-k。

  行为验证：单分片 scope 查存在的词返回该文档、查不存在的词返回空；
  不含查询词的文档仍然不返回（没有变成"全返回"）；排序仍按 BM25。
  返回的 `bm25_score` 可能为负 —— 这是 BM25 的正常取值，且 RRF 融合用的是
  **排名**（`rrf_score(idx, rrf_k)`）不是原始分，下游不受影响。

**验收结果**：`tests/security/` 57 → 85 条，全仓库 119 → 147 条，全绿，
仅剩 1 条 xfail（P0-3，阶段 3）。

---

### 阶段 3：资源寻址与管理面（P0-3、T4）—— **已完成（2026-08-30）**

三处改动，互相独立生效（已逐一验证）：

**1. `?source=` 从旁路变成收窄条件。** 原来是

```python
source = normalize_string(source) or _resolve_manageable_source_for_filename(filename, user)
```

—— 只要传了 `?source=`，可见性解析**整个被跳过**。现在
`_resolve_manageable_document(filename, user, source)` 先取"既可见又可管理"的行，
再用 `source` 在其中**筛选**；筛不到唯一一行就拒绝。它返回整行而不只是路径，
调用方因此能审计到底动了哪个文档、属于谁。

**2. admin 的管理范围收窄到与其可见范围一致。** 新增
`_has_cross_tenant_rights(user)`，与 `access_scope.py` 对**读**的门禁同一把尺子。
今天没有任何地方授予这些权限（认证后的 user dict 只有
user_id/username/role/status/credit_balance）—— 这正是重点：admin 在有人**刻意**接上
授权流程之前，既看不到也动不了别人的文档。原来 admin 能删他连列都列不出来的文件。

**3. 按不可变 id 寻址。** 新增
`DELETE /documents/by-id/{document_id}` 和
`POST /documents/by-id/{document_id}/reindex`。文件名不是标识符 ——
两个用户常常各有一份 `report.pdf`，所以文件名形式只能在有歧义时拒绝；
`document_id`（`doc-{uuid4}`，注册时分配）永远只指向一个。
前端已切到 by-id（`item.document_id` 已在 `IndexedFileSummary` 里），
旧行仍走文件名形式作为兜底。

**4. 审计带上身份。** 成功和拒绝都写审计，`detail` 含
`document_id` / `owner_user_id` / `source`。原来只有 `resource_id=filename`，
分不清 Alice 的 `report.pdf` 和 Bob 的。

**一个刻意的选择**："查无此文档"和"不是你的"返回**同样的 404**。
告诉一个无权调用方"该文档存在但属于别人"，本身就是一次泄露。

**与计划的偏差**：

- 计划说旧端点"多于一个匹配返回 409"。实际统一返回 404，理由同上 ——
  409 会区分"不存在"和"有歧义"，而后者等于确认了别人也有同名文件。
- 计划说"前端切到新端点后再决定是否移除旧端点"。前端已切，但旧端点保留：
  它现在是安全的（有歧义即拒绝），且为没有 `document_id` 的历史行兜底。

**验收结果**：`tests/security/` 90 → 104 条，全仓库 152 → 166 条，
**xfail 归零**（阶段 0 的 8 条全部转绿并删除 marker）。
新增 `tests/security/test_document_endpoints.py` 走**真实路由**（TestClient +
`X-Test-User` 头），因为缺陷在路由体里而不在 helper 里。已用"临时还原旁路"的方式
确认其中 3 条在修复前是红的 —— 其中 admin 那条即使还原了旁路仍然通过，
说明第 1、2 两处修复各自独立生效。

OpenAPI 操作数 149 → 151（CI 的普查是 `>= 140` 的下限，不需要改阈值）。

---

### 阶段 4：侧信道与清理（P1-8、P2-9、P2-10）—— **已完成（2026-08-30）**

**1. 删除 `context_tracker`（P1-8）。** 整个模块零读写调用方，只有清理协程被
lifespan 启动。删掉模块本身、`lifespan.py` 的启停、以及
`legacy_agent_runtime.py` 里的两个包装函数。

连带清理它独占的死代码（逐个确认过零读者）：
`quality_models.py` 里的 `ConversationTurn` / `ConversationContext` / `ContextHints`
（`app/services/context_management.py` 有同名但不同的 `ConversationContext`，未受影响），
以及 `CONTEXT_MAX_HISTORY_TURNS` / `CONTEXT_SUMMARY_FREQUENCY` /
`CONTEXT_SUMMARY_MIN_TURNS` / `CONTEXT_TTL_SECONDS` —— 这四个在
`app/core/shared_config.py` 和 `app/agents/shared/config.py` **各定义了一遍**，
两处都无人读取。它们由环境变量驱动，所以留着会误导运维：设了
`CONTEXT_TTL_SECONDS` 却什么也不会发生。

**2. 日志不再复现用户问题（P2-10）。** 新增
`app/services/observability/log_safety.py::question_ref`，返回
`q[<sha256前12位> len=N]` —— 保留日志真正需要的性质（同一问题产生同一句柄，
请求仍可跨行关联），但不含文本。

**实际站点是 17 处，不是计划里写的 2 处。** 用 AST 守卫
（`test_no_question_text_in_logs.py`）枚举所有 `logger.*` 调用中直接传入
`question` / `query` / `answer` / `content` / `text` / `prompt` 的地方，
覆盖 f-string 和 `question[:50]` 切片 —— **截断 50 字并不比全文安全**，
它照样复现了实质内容。守卫会跳过 `question_ref(...)` 等安全包装，
避免把修好的站点重新算成违规。

唯一白名单项是离线评测 harness（`api_retriever.py`），它的 query 来自固定评测集
而非用户，看到它正是那次运行的目的 —— 与 owner 守卫的白名单同一个模块、同一个理由。

**3. 前端登出清态（P2-9）。** 两个 Zustand store 加 `reset()`，
`App.tsx` 在登出、`/auth/me` 失败、以及**身份变化**时调用
（后者覆盖会话过期后换人登录这种不走 logout 的路径）。

**计划里有一处说得不准确**：原文称"`authApi.logout()` 只清 CSRF"。
`authApi.logout()` 确实只清 CSRF，但 `App.tsx` 的 `logout` 紧接着就调了
`authApi.setToken("")` —— **token 本来就清了**。真正的缺口只有 store。

字段是逐个列出来的，所以真正的风险是**漂移**而不是逻辑：两个 store 约 40 个字段，
新加一个却忘了加进 `INITIAL_STATE`，就会静默地熬过登出。两道防线：

- **编译期**：`INITIAL_STATE` 显式标注为 `ChatData` / `AdminData`，
  由映射类型从 `ChatState` 派生出"所有非函数属性"。往 state 加字段却漏了
  `INITIAL_STATE`，直接是类型错误。已验证：
  `Property 'strayField' is missing in type ... but required in type 'ChatData'`。

  这里有个坑值得记：第一版用 ``Omit<ChatState, `set${string}` | "reset">``
  按**名字前缀**排除 setter —— 但 `settingsOpen` 也以 `set` 开头，
  于是被一并排除，恰好造成了这个类型本该防住的漏字段。判据必须是**值类型**
  （排除函数），不是名字。

- **运行期**：`frontend/src/stores/storeReset.test.ts` 会**发现**字段而不是列举
  字段：脏化每一个非函数字段、reset、要求逐字段回到初始值。已验证会报
  `expected [ 'strayField' ] to deeply equal []`。

（附带教训：`npx tsc --noEmit` 通过不等于 `npm run type-check` 通过 ——
后者是 `tsc -b`（build 模式），用的是项目引用配置。以仓库脚本为准。）

vitest 本来已配置但**零测试文件且 CI 不跑**，所以同时给
`.github/workflows/ci.yml` 的 frontend job 加了 `npm test -- --run`。

**4. `outbound_redaction` 默认已开启（无需改动）。**
`outbound_llm_redaction_enabled` 和 `outbound_embedding_redaction_enabled`
在 `app/core/config.py:253,254` 都 `default=True`，且 `config/env/` 下没有任何
`OUTBOUND_*` 覆盖 —— 未渲染 `.runtime/` 时走的就是这两个 True。核对完毕。

**验收结果**：后端 166 → 174 条，前端新增 10 条（首批前端测试）。
`app/` 少了一个模块和三个死模型。lint 全绿，前端 warning 仍是 25（棘轮未被推高）。

---

## 6. 待转绿的 xfail 清单

阶段 0 落地了 8 条 `xfail(strict=True)`。修好对应缺口后**必须删掉 marker**，
否则 xpass 会硬失败 —— 这是刻意的，防止修复被遗忘或被静默回退。

阶段 1 已转绿并删除 marker 的 7 条：

| 测试（转绿后名称） | 覆盖 |
|---|---|
| `test_memory_from_another_owners_namespace_is_denied` 等 4 条 | P0-2 |
| `test_hybrid_vector_hop_refuses_to_search_unscoped` | P0-1 |
| `test_a_signature_error_does_not_degrade_into_a_global_search` | P0-1 |
| `test_vector_retrieve_refuses_a_request_with_no_resolved_scope` | P0-1 |
| `test_an_absent_caller_scope_is_replaced_by_the_resolved_one` | P0-1 步骤 4 |
| `test_the_rewritten_scope_carries_every_resolved_dimension` | P0-1 步骤 4 |
| `test_diagnostics_do_not_reveal_how_much_was_dropped` | T2 |

阶段 3 转绿的最后 1 条：

| 测试 | 覆盖 |
|---|---|
| `test_an_admin_cannot_manage_an_arbitrary_users_upload_without_cross_tenant_rights` | P0-3 |

**阶段 0 建立的 8 条 xfail 现已全部转绿，marker 全部删除。**

另需在对应阶段**新增**的测试（阶段 0 未写，因为要先有实现才有可断言的接口）：

| 用例 | 覆盖 | 阶段 |
|---|---|---|
| 越权 source 列表绕过 resolver → Chroma 层仍返回空 | INV-3 | 2 |
| BM25 单查询加载的 record 数 < 全库 | INV-3 + 性能 | 2 |
| 图谱降级模板在 `allowed_sources=[]` 时返回空而非全图 | P1-5 | 2 |
| `?source=` 显式传参不再绕过可见性解析 | P0-3 | 3 |
| 换用户后前端 store 为空 | T5 | 4 |

---

## 7. 风险

- **阶段 1 会改变召回行为。** 用户可能感知到"结果变少了" —— 那是本来就不该看到的
  别人的文档被挤掉的位置腾出来了，属于修复而非回退。上线前跑一次人工对比。
- **阶段 2 的 Chroma `$and` 依赖历史分片元数据完整。** 回填脚本必须先跑，且要有
  dry-run 模式统计缺元数据的分片数。缺 owner 的一律按 public 处理，避免把
  `data/docs/` 共享语料误锁。
- **阶段 3 改端点会影响 OpenAPI 端点 census**（CI 有基线校验），改动需同步更新
  CLAUDE.md 里记的 149。
- **阶段 2 的缓存键加维度会降低命中率**，进而抬高 P95 延迟。若超出 CLAUDE.md 的
  < 5s 目标，考虑按 tenant 分片缓存而非直接加维度。

---

## 8. 明确不做

- 不给 uploads 做静态加密（无合规驱动）。
- 不拆分 Chroma collection 为 per-tenant —— 当前规模下 metadata 过滤足够，
  且拆分会让共享语料 `data/docs/` 的处理复杂化。
- 不改 `data/docs/` 对全体可见的语义。
- 不给 `web` / `tool` 层加 scope 校验 —— 它们本来就不是用户文档。
