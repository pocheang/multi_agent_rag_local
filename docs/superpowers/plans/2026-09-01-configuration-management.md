# 配置治理：收敛到 Settings，再接入 Nacos 配置中心

状态：阶段 0 已完成（2026-09-01），阶段 1-3 待实施。

## 1. 目标与非目标

### 目标

1. **配置只有一个 schema**：任何可配置的值都是 `Settings` 的字段，带类型、默认值和 alias。
2. **优先级只声明一次**，且可写在文档里：真实进程环境 > 配置中心 > 渲染出的 `.runtime/*.env` > 字段默认值。
3. **管理员在网页上改配置**，带版本历史、回滚和变更审计。
4. **配置面板显示的就是运行中的值**，并说明该值来自哪一层。

### 非目标

- 不做多环境集群配置分发（单机部署，`config/env/` 的 development/test/production 分层继续有效）。
- 不把密钥搬进配置中心（见 §6）。
- 不重写 `app/agents/shared/config.py` 的 37 个遗留常量（阶段 3 再说，且是逐批）。
- 不引入 Dynaconf/Hydra/OmegaConf——理由见 §3。

## 2. 现状盘点（2026-09-01 实测）

### 三层配置，中间有个洞

| 层 | 内容 | 修改方式 | 网页可改 |
|---|---|---|---|
| `Settings`（230 字段） | 绝大部分 | 改 `config/env/*` → `make config-render` → 重启或热重载 | ❌ |
| `system_settings` 表（SQLite） | 只有模型 provider/model/key/temperature | `POST /admin/model-settings` | ✅ |
| 模块级 `os.getenv` | 见下 | 只能是真正导出的环境变量 | ❌ |

洞的证据有三条，都在这次盘点里实测确认：

1. **`AdminRagSettings.tsx` 没有任何可编辑字段**，只有三个按钮。名字是 Settings，管的是 ops。
2. **`POST /admin/config/reload` 重载的是一个网页无法写入的文件**。它本身是对的——重载会清模型缓存、向量库缓存、Neo4j driver、bulkhead——缺的是上游那半条链：没有任何接口能写 `.runtime/{APP_ENV}.env` 或 `config/env/*`。
3. **`GET /api/advanced-rag/config` 报的每个值都是错的**（已在阶段 0 修复）：
   - `query_decomposition.enabled_by_default` 读 `ENABLE_QUERY_DECOMPOSITION`，而真正的开关叫 `QUERY_DECOMPOSE_ENABLED` 且默认 **True**——页面显示 false 而功能开着；
   - `self_rag.enabled_by_default` 读 `ENABLE_SELF_RAG`，而真正的门是 `VectorRAGConfig.enable_evaluation`；
   - `max_sub_queries` 读一个环境变量，而实际上限是 `QueryDecomposer` 里硬编码的 4。

### `os.getenv` 逃逸：47 个活键

pydantic-settings 把 `.runtime/{APP_ENV}.env` 读进 `Settings`，**不会导出到进程环境**（实测：文件里 `APP_ENV=development`，`Settings().app_env` 读得到，`os.getenv("APP_ENV")` 仍为空）。因此任何 `os.getenv` 读到的键：

- `make config-render` 设不了；
- 配置中心推下来也到不了；
- 只能是真正 export 的环境变量，且必须在模块被 import 之前就存在。

清点结果（AST 扫描 `app/`）：

| 位置 | 键数 | 处置 |
|---|---|---|
| `app/agents/router/config.py` | 2 | 阶段 0 收编，模块删除 |
| `app/api/transport/middleware.py` | 2（含 `STRICT_CSP`，安全响应头） | 阶段 0 收编 |
| `app/api/routes/public/query.py::get_config` | 5 | 阶段 0 删除，改报真实开关 |
| `app/services/retrieval/self_rag_evaluator.py` | 2（与上面重复读同一键） | 阶段 0 收编 |
| `app/agents/shared/config.py` | 37（经 4 个 helper） | 阶段 3，逐批 |
| `app/core/shared_config.py` | 5 | 阶段 0 删除（零 importer） |

合理保留的直接读环境（已在测试里显式声明理由）：`resolve_runtime_env_file`（它选的就是配置文件本身）、`_local_backend_forced`（部署要能压过管理员设置）、conda 环境自省、pytest 检测。

## 3. 为什么是 Nacos

| 方案 | 否决/选中理由 |
|---|---|
| **Nacos** ✅ | 自带控制台、版本历史、一键回滚、变更推送；官方 `nacos-sdk-python`；一个容器能进现有 compose（已经在跑 Prometheus/Grafana/Alertmanager，多一个容器不是新负担） |
| Apollo | 能力更强（发布审批流），但要跑三个 JVM 服务，且 Python SDK 是社区维护；当前是单人/小团队，审批流买不到什么 |
| Unleash / Flagsmith | 更轻，且非常适合那批 dormant 开关；但装不下 230 个带类型的标量配置，会变成"一半在这、一半在那" |
| Dynaconf | 没有网页端，而网页端是本次的硬需求；且它自带一套优先级链，与 pydantic-settings 重叠，二选一而不宜并存 |
| Consul / etcd | KV 通用界面，无类型无校验无字段文档；运维成本换来的能力比 Nacos 少 |

## 4. 接入形状：一个 settings source，不是第四层

```python
# app/core/config.py
class NacosSettingsSource(PydanticBaseSettingsSource):
    """远端配置作为一个 source。类型、校验、默认值仍在 Settings 里。

    远端不可达时回落到 SDK 的本地快照；快照也没有时返回空 dict，
    让下层 source（.runtime/*.env → 默认值）接管。绝不阻塞启动。
    """

class Settings(BaseSettings):
    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings,
                                   dotenv_settings, file_secret_settings):
        return (init_settings, env_settings, NacosSettingsSource(settings_cls),
                dotenv_settings, file_secret_settings)
```

这个顺序就是 §1 的优先级：`init > 进程环境 > Nacos > .runtime/*.env > 默认值`。

**为什么必须是 source 而不是"启动时把 Nacos 的值灌进 os.environ"**：后者会让进程环境和配置中心互相污染，`_local_backend_forced` 这类"部署钉死"的语义就没了；而且灌进去的值绕过 `Settings` 的类型校验。

**为什么进程环境要压过 Nacos**：部署方必须有一个配置中心改不动的兜底手段。这条已经有先例——`MODEL_BACKEND=local` 现在就压过持久化的管理员模型设置。

## 5. 分阶段实施

### 阶段 0：把配置收敛到 Settings —— **已完成（2026-09-01）**

没有这一步，接哪个配置中心都有一层配置在页面上不存在。

- `Settings` 新增 6 个字段：`enable_calibration`、`enable_web_route_downgrade`、`self_rag_relevance_threshold`、`self_rag_quality_threshold`、`request_metrics_maxlen`、`strict_csp`。
- 删除 `app/agents/router/config.py`（2 个模块常量）和 `app/core/shared_config.py`（5 个常量，零 importer）。
- `_calibrator` 改为**首次使用时解析**而不是 import 时绑定——import 时绑定正是这个开关只能靠 export 环境变量才生效的原因，也会让配置中心推送到不了它。加锁是因为 `decide_route` 跑在 `asyncio.to_thread` 里，两个线程各建一个 calibrator 会各自往同一个文件 flush。
- `_request_metrics` deque 同理改为惰性构造：它的容量现在是 Settings 字段，而 import 这个模块时 Settings 还没加载。
- `GET /api/advanced-rag/config` 改报真实开关；`QueryDecomposer` 的 4 提升为具名常量 `DEFAULT_MAX_SUB_QUERIES` 以便被如实报告。
- 删除 `ENABLE_CONTEXT_TRACKING`（两份定义，零读者；真正的开关是 `PipelineRequest.enable_context_tracking`）。
- 删除 `health.py::_runtime_diagnostics_summary`——死代码，且它 `_request_metrics_lock, _request_metrics = get_request_metrics()` 把一个 list 解包成两个名字，任何调用都会抛异常。`deps/admin.py` 里有能跑的那份。
- 新增 `tests/core/test_config_has_one_source.py`：AST 扫描 `app/` 的直接环境读取，允许清单按 `path::function` 键入并写明理由；遗留常量块用 ratchet 冻结在 37，只减不增。

### 阶段 1：Nacos 作为 settings source

- `docker-compose` 加 nacos + MySQL（standalone 模式），**先配鉴权再启用**（见 §6）。
- 实现 `NacosSettingsSource`：命名空间按 `APP_ENV` 分，dataId 按模块分组（`querymind-retrieval`、`querymind-router`…），格式用 properties 以对齐现有 alias。
- 离线兜底：SDK 本地快照 → 空 dict，三级降级都不阻塞启动。**这条要有测试**：断掉 Nacos 后进程仍能起来并使用 `.runtime/*.env` 的值。
- 配置变更监听 → 复用现成的 `reload_settings()` + `clear_model_caches()` + `reload_query_runtime()`。热更新语义要写清楚：哪些字段热生效，哪些需要重启（例如 `APP_DB_PATH`）。

### 阶段 2：管理端页面

- `GET /admin/config/schema`：从 `Settings.model_fields` 生成可编辑子集，每个字段带类型、范围、当前值、**来源层**。用 `json_schema_extra={"admin_editable": True, "requires_restart": False}` 标注，页面由 schema 生成而不是手写 230 个表单项。
- 写入走 Nacos API，复用 `deploy/scripts/config.py::validate_environment` 的生产规则（不许 `DEBUG=true`、CORS 不许 `*`），并走已有的 `_audit(...)`。
- `AdminRagSettings.tsx` 从"三个按钮"变成真正的配置页。

### 阶段 3：迁移 37 个遗留常量

逐批把 `app/agents/shared/config.py` 的常量搬进 `Settings`，每搬一批把 ratchet 的预算调低。它们目前是模块级 `Final` 常量，被 `from ... import X` 直接引用，所以每批都要把引用点改成 `get_settings().x`——这是行为变更（import 时求值 → 调用时求值），要按批测。

## 6. 风险与边界

- **密钥不进配置中心**。`API_SETTINGS_ENCRYPTION_KEY`、各家 API key 继续走现有加密凭据路径。轮换 `API_SETTINGS_ENCRYPTION_KEY` 会让已存凭据从"不存在"变成"解不开"，这条在 CLAUDE.md 里已经写明。
- **Nacos 默认账号是 `nacos/nacos`，历史上有过鉴权绕过 CVE**。启用鉴权、改默认口令、不暴露到公网，是阶段 1 的前置条件而不是后续优化。
- **热更新不是所有字段都安全**。凡是在 import 时被读进模块常量、或用于构造长生命周期对象（连接、线程池、deque 容量）的字段，热更新只会改到"下一次构造"。阶段 0 已经把 calibrator 和 metrics deque 改成惰性，其余要逐个判断并在 schema 里标 `requires_restart`。
- **配置中心不可达不能拖垮启动**。这是引入外部依赖最容易埋的雷，所以离线兜底是阶段 1 的验收项之一。
