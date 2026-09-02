# 配置治理：收敛到 Settings，再接入 Nacos 配置中心

状态：全部四个阶段完成（2026-09-01），并在真实 Nacos 2.4.3 上跑通。

### 收尾修复（2026-09-01）

- **第四个配置写入者已消除。** `runtime_ops.apply_replay_autotune` 曾直接原地改活的 `Settings`
  （`top_k`、`max_context_chunks`、`rank_feature_enabled`、`dynamic_retrieval_enabled`），
  从 `POST /admin/ops/autotune` 可达。那个改动不属于任何一层，所以下次重载就丢；而配置页的
  "来源层"那一列——页面存在的全部理由——无从知道值是哪来的。接口的响应还叫 `applied_patch`。
  现在它改名 `recommend_replay_autotune` 且不改任何东西，应用走 `write_config_values()`，
  和管理员的编辑同一条路、同样的拒绝规则。**这条路径此前零测试覆盖，现在有 6 个。**
- **版本历史与回滚已实测（§1 目标 3 的最后一块）。** 在真实 Nacos 上：`/cs/history` 列出 4 个版本
  （含从管理页保存的那次），取旧版本内容、发布回去、再用应用自己的 source 链读——`RERANKER_TOP_N`
  回到 5，`describe()` 报 `layer=config-centre`。注意 Nacos 历史条目存的是**变更前**的内容。
- **`requires_restart` 全部核实过。** 29 个字段逐个查了绑定点：要么每次调用读 `get_settings()`，
  要么挂在 `RAGPipeline` 每请求新建的对象上，要么由重载重建。唯一例外是检索缓存——它在首次构造时
  把 TTL 烘死且存在模块级全局里——所以让 `apply_config_reload()` 清它，而不是在页面上加个警告。

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
# app/core/remote_config.py
class RemoteSettingsSource(PydanticBaseSettingsSource):
    """远端配置作为一个 source。类型、校验、默认值仍在 Settings 里。

    远端不可达时回落到本层自己写的快照；快照也没有时返回空 dict，
    让下层 source（.runtime/*.env → 默认值）接管。绝不阻塞启动。
    """


# app/core/config.py
class Settings(BaseSettings):
    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
    ):
        return (init_settings, env_settings, RemoteSettingsSource(settings_cls), dotenv_settings, file_secret_settings)
```

后端是可换的：`RemoteConfigClient` 只有 `fetch` 和 `watch` 两个方法，Nacos 适配器
（`app/core/remote_config_nacos.py`）实现它，测试用 fake 实现它。

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

### 阶段 1：Nacos 作为 settings source —— **代码部分已完成（2026-09-01）**

已落地：

- `app/core/remote_config.py`：`RemoteSettingsSource` + `RemoteConfigClient` 协议 + properties 解析 + 快照。
- `app/core/remote_config_nacos.py`：SDK 适配器，**惰性 import**，`ImportError` 视为"没有客户端"并降级到快照。因此没采用配置中心的安装完全不需要装这个依赖；`pyproject.toml` 里作为 `config-centre` extra。
- `Settings.settings_customise_sources` 声明优先级：`init > 进程环境 > 配置中心 > .runtime/*.env > 默认值`。
- 三级降级：远端 → 上一次成功抓取写下的本地快照（`.runtime/remote-config/`）→ 什么都不给，由下层 source 接管。每一级都有测试，包括"远端超时 + 无快照仍能启动"。
- 变更监听接到 `app/api/application/config_reload.py::apply_config_reload()`——这个函数是从管理端 `POST /admin/config/reload` 里抽出来的**同一段序列**，两个入口共用。监听器如果自己只清一部分缓存，就会变成第二个、更安静的"已重载"定义，差异只会以"点按钮生效、在控制台保存不生效"的形式暴露出来。
- `tests/core/test_remote_config_source.py`（19 个测试）。

两个实现中确认的事实，都钉成了测试：

1. **source 必须返回 alias 键**。`{"ENABLE_CALIBRATION": True}` 生效，`{"enable_calibration": True}` 被**静默忽略**——`Settings` 按 alias 校验，`extra="ignore"` 丢掉其余，没有任何报错。好在 alias 正是 `config/env/*` 和渲染文件已经在用的名字，一个名字从仓库一路走到控制台。
2. `no_snapshot=True` 传给 SDK 的 `get_config`：这一层自己管快照，只在**真的抓取成功**后写。让 SDK 悄悄替换成它自己的缓存，会让"服务器答了"和"没答"变得无法区分，而这条日志正是值没生效时运维唯一能依据的东西。

**用真实 SDK 验证过了**，方式是本地起一个假 Nacos HTTP 服务，让真实的 `nacos.NacosClient`
打过去——不需要容器就能验证适配器。五项全过：真实 fetch、值按 alias 进入 `Settings`
（`TOP_K=23`、`STRICT_CSP=true`）、快照落在本层指定路径且 SDK 没有自建 `nacos-data/`、
轮询在无变更时静默而在文档变更后触发、服务停掉后回落快照。

验证过程中改掉的三件事：

1. **依赖 pin 从 `>=0.1.12` 改成 `>=1.0.0,<2.0`。** 原来的写法会解析到 3.2.0，而 2.x/3.x
   是一次重写：包名是 `v2.nacos` 而不是 `nacos`，`get_config` 是协程。本层由同步的
   `Settings()` 构造调用，而 `reload_settings()` 可以从请求处理器里被触达——在那里驱动
   异步客户端要么 `asyncio.run`（在运行中的 loop 里会抛），要么每次开一个私有 loop，
   正是本仓库已经修过两次的缺陷（`app/agents/rag/cache.py`、`app/agents/shared/cache.py`）。
   1.0.0 是最后一个同步客户端版本。
2. **放弃 SDK 自带的 watcher，改成自己轮询。** `add_config_watcher` 内部走 `_init_pulling`，
   它会建 `multiprocessing.Manager()`、`multiprocessing.Queue` 和一个 10 线程回调池；在
   Windows（spawn）上注册 watcher **根本没有返回**——加不加 `__main__` 守卫都验证过一次。
   一个守护线程按 `NACOS_POLL_INTERVAL_MS`（默认 30s）拉一次 HTTP GET，省掉一个进程和一个
   线程池，各平台行为一致，而且复用了已经会降级到快照的 `fetch`。代价是最长 30s 的生效延迟，
   与它替换掉的长轮询同一量级。
3. **客户端构造时 `set_options(no_snapshot=True)`。** 否则 SDK 会在工作目录建 `nacos-data/`
   写自己那份快照——两份内容不同的缓存，而且没有任何日志说明是哪一份回答了请求。

`deploy/compose/compose.config-centre.yaml` 已就绪：standalone + 内嵌 Derby（单机部署不需要
MySQL），鉴权强制开启且三个密钥用 `${VAR:?}` 声明**没有默认值**——没设就起不来，端口只绑
127.0.0.1。

验证脚本本身已提交为 `scripts/verify_config_centre.py`——改适配器或抬 SDK pin 之后跑它。
单元测试用的是 fake client，而 fake 你问它什么形状它就答什么形状，抓不到「本仓库的调用和 SDK
的签名漂移了」这一类问题，上面三个缺陷全都住在这个缺口里。

**已在真实 Nacos 2.4.3 上跑通（2026-09-01）**：容器起来、三个 dataId 发布、应用读到、快照落盘、
轮询在 0.3s 内发现控制台的改动、`Settings` 重建后拿到新值。四个来源层在管理页上同时出现过一次
（`TOP_K` 环境钉住呈琥珀色且输入禁用、`RERANKER_TOP_N` 来自配置中心、四个来自 runtime-file、
其余 default），点保存后写回 Nacos 并重载运行时。

两个只有真跑才暴露的 bug：

1. **`RemoteDocuments` 根本没有 `publish` 方法**——重构拆类时它落到了 `RemoteSettingsSource` 上。
   端点的 11 个测试全绿，因为它们用的 `FakeDocuments` 自带这个方法：**fake 你问它什么它就有什么**。
   现在有一条只 fake 网络边界（client）、用真实 store 走真实端点的测试。
2. **每次编辑都写进最后一个 dataId**。页面上显示 `RERANKER_TOP_N` 来自 `querymind-retrieval`，
   保存却写进了 `querymind-router`，同一个键于是存在于两个文档、后者静默胜出，页面和存储从那一刻起开始漂移。
   现在每个键写回**定义它的那个文档**，只有任何文档都没有的新键才落到 fallback（最后一个 id，因为
   后面的覆盖前面的）。

**Nacos 2.4 的一个部署事实**：`NACOS_AUTH_ENABLE=true` 且用内嵌 Derby 时，用户表是空的，
`nacos/nacos` 登录会返回 "User nacos not found"。需要先调一次
`POST /nacos/v1/auth/users/admin` 引导管理员账号。

热更新语义盘点仍未做——`apply_config_reload()` 的 docstring 已经点明边界：仍在遗留常量块里的值
在进程重启前不会被重新读取。

### 阶段 2：管理端页面 —— **已完成（2026-09-01）**

- `app/core/config_schema.py`：可编辑集合是一份**中心化白名单**，不是每个字段上的标注。236 个字段逐个标注会把一个安全相关的决定摊到 236 行里，而"拿到控制台的人能改到什么"这个问题将没有单一答案。opt-in：新字段不写进来就不可编辑。
- 安全守卫按**形状**断言而非枚举当前字段：凡 alias 含 KEY/SECRET/PASSWORD/TOKEN/PATH/URL/DSN/CORS/ORIGIN 一律不得可编辑，所以将来要加进去必须是刻意为之。
- `GET /admin/config/schema` 返回每个字段的当前值和**来源层**；`POST /admin/config/values` 写入配置中心并重载。两条拒绝各自防止控制台谎报改动：没有配置中心时拒绝（无处可写且进程不读），以及被进程环境钉住的值拒绝（环境压过中心，写了会"成功"但什么也没变）。前端也把这类输入禁用，但那只是便利——规则在服务端强制，因为浏览器不是能强制它的地方。
- 文档整体重写而非打补丁，内容是"本进程当前读到的 + 这次编辑"。版本历史和回滚归配置中心所有，在这里做合并等于把两者都重新实现一遍且更差。
- `AdminConfigEditor.tsx` 由 schema 生成表单，按组渲染，显示来源层徽标。挂在 `AdminRagSettings` 里，那个"名叫 Settings 却没有任何可编辑字段"的页面现在有了。

**已做视觉验证（2026-09-01）**：`scripts/create_admin.py` 建了本地开发管理员，用它登进管理端看了这个页面。
六个分组都渲染、28 个字段都在、无配置中心时输入正确禁用、Tailwind 类全部解析（`rounded-pill` 999px、
`bg-accent-soft`、`bg-warning-light` 都拿到真实颜色，不是那种静默失效）。

**看出来一个真问题**：`default` 徽标是 `--text-tertiary` 配 `--bg-tertiary`，实测对比度 **2.56:1**
（AA 小字要求 4.5），而 `--bg-tertiary` 在浅色主题下就是纯白，所以那个 pill 在行背景上根本看不见。
"来源层"这一列正是这个页面存在的理由，不能是页面上最难读的东西。改成 `bg-secondary` + `text-secondary`
+ 一道边框后是 **7.06:1**。这条 lint 和单元测试都抓不到——只有在真浏览器里量才会发现。

### 阶段 3：清理 37 个遗留常量 —— **已完成（2026-09-01）**

计划原本是"逐批搬进 `Settings`"。先做用量普查改变了结论：**37 个里有 20 个根本没有读者**，
把它们搬进 `Settings` 只会让配置面变大而不会变得更可配置。

- **删除 20 个**：19 个在 `app/` 和 `tests/` 里零引用；外加 `CASCADE_USE_FOR_VALIDATION`——
  它被引用，但那个分支打一条 "is retired" 日志之后两边做同样的事。
- **迁移 13 个**到 `Settings`：两个答案阈值、幻觉风险阈值、两个 NLI 参数、四个 cascade 开关、
  四个 cascade 超时。全部在请求路径上（`app/agents/validation/{public,nli}.py`）。
- **4 个 `ANSWER_WEIGHT_*` 留在原地降级为普通字面量**：它们是一套必须加起来等于 1.0 的评分方案，
  四个可以各自独立设置、却又必须彼此吻合的旋钮是陷阱而不是功能。
- `NLIValidator.__init__` 的默认参数从模块常量改成调用时读 `Settings`——**默认参数在 import 时求值一次**，
  这正是这两个值对 render 步骤和配置中心不可见的原因。
- `app/agents/shared/config.py` 现在没有任何环境读取，四个 `_get_*_env` helper 一并删除，
  守卫里的 ratchet 和它对应的四条白名单也随之退休。

顺带修掉一个偶发失败：`test_entries_expire` 用 50ms TTL + sleep 60ms，套件负载高时**第一次**读取
就可能已经过期，失败信息读起来像"缓存错误地过期了"而不是"机器忙"。改成假时钟驱动。

## 6. 风险与边界

- **密钥不进配置中心**。`API_SETTINGS_ENCRYPTION_KEY`、各家 API key 继续走现有加密凭据路径。轮换 `API_SETTINGS_ENCRYPTION_KEY` 会让已存凭据从"不存在"变成"解不开"，这条在 CLAUDE.md 里已经写明。
- **Nacos 默认账号是 `nacos/nacos`，历史上有过鉴权绕过 CVE**。启用鉴权、改默认口令、不暴露到公网，是阶段 1 的前置条件而不是后续优化。
- **热更新不是所有字段都安全**。凡是在 import 时被读进模块常量、或用于构造长生命周期对象（连接、线程池、deque 容量）的字段，热更新只会改到"下一次构造"。阶段 0 已经把 calibrator 和 metrics deque 改成惰性，其余要逐个判断并在 schema 里标 `requires_restart`。
- **配置中心不可达不能拖垮启动**。这是引入外部依赖最容易埋的雷，所以离线兜底是阶段 1 的验收项之一。
