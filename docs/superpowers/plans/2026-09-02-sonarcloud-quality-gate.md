# SonarCloud Quality Gate 修复计划

状态：**第二版**（2026-09-02，核对过线上实况）。第一版的 P0 与 P1 已完成并生效；本版基于
SonarCloud 上 revision `5e60933`（当前 HEAD，分析时间 2026-09-02 05:58 UTC）的真实数据重写。
第一版有一条结论是错的，见第 5 节。

## 0.0 执行进度（2026-09-02，已并入 main）

**两个评级都到 B 了**（`75bfbeff` 的分析）。新代码只剩 7 条 LOW bug 和 4 条 LOW vulnerability，
全部是 LOW——这正是 B 的定义。Gate 仍是 ERROR，因为它要求 A。

| 步骤 | 状态 | commit |
|---|---|---|
| 第 1 步：`main.css` / `.sort()` / 两处 `usedforsecurity` | 完成，D → C | `28818595` |
| 第 2 步：供应链 `--only-binary` / `--ignore-scripts` | 完成 | `f2d44a10` `816871a9` `95d26228` |
| 第 3 步：日志与输入收窄 | 完成 | `3cca16db` `d3c6ccd9` |
| C → B：float 比较、自比较断言、`_resolve_query_file` | 完成，Reliability → B | `73795eff` |
| C → B：依赖锁 | 完成，Security → B | `80e3676f` `75bfbeff` |
| 第 4 步：Sonar 裁决（剩 11 条 LOW） | **未开始**，需要 SonarCloud 权限 |
| 第 5 步：`typescript:S1082` × 7 的 a11y 决定 | **未决定**，B 与 A 之间只剩它 |
| New Code 基线 | **未改**，需要 SonarCloud 界面 |

**做出来的东西超出了原计划，因为读代码读出了计划里没有的事**：那套 CSRF 是空转的（第 3 节
`S2245`）、`legacy_service.py` 没有任何消费者（第 4 节 `S2083`）、CI 的 editable 安装是多余的
（第 3 节供应链）。三样连同它们的 `Settings` 字段一起删了。

**这一轮 CI 挂了三次，三次的教训是同一个**：

1. workflow YAML 没引号，`: ` 让 GitHub 读不了文件——**CI 一个 job 都没跑**，而 run 显示成
   `failure`，看上去像测试挂了。守卫：`tests/core/test_ci_workflow_is_loadable.py`。
2. `jieba` 没有 wheel，`--only-binary :all:` 装不上。我之前说"验证过"，但那是在一个**已经装满依赖
   的环境**里跑 dry-run，pip 全程回答 already satisfied，从没去找过分发包。
3. `forbiddenfruit`（`blockbuster` 的依赖）也没有 wheel——**同一个问题的第二个实例，又用一次红色
   构建才发现**。守卫：`scripts/check_lock_wheels.py` 一次问完整个锁，`make lock` 会跑它。

写那个脚本本身还有第四个教训：第一版精确匹配解释器 tag，报出九个"没有 wheel"的包，其中七个是错的
——stable ABI 的 wheel 声明的是**最低**解释器（`cp39-abi3` 在 3.11 上能装）。九个看起来都合理的答案，
七个是错的，而照着改会把 `--no-binary` 扩大到半棵依赖树。

## 0. 线上实况

Quality Gate：**ERROR**。五个条件里三个通过：

| 条件 | 阈值 | 实际 | |
|---|---|---|---|
| `new_maintainability_rating` | A | **A** | 通过 |
| `new_duplicated_lines_density` | <= 3% | **0.8%** | 通过 |
| `new_security_hotspots_reviewed` | 100% | **100%** | 通过 |
| `new_reliability_rating` | A | **D** | 不通过 |
| `new_security_rating` | A | **D** | 不通过 |

总量 32 bugs / 31 vulnerabilities / 802 code smells；新代码 26 / 16 / 463。
（第一版写的是 41 / 31 / 803，其中 P0 的 `python:S930` × 5 和 P1 的 5 条都已从清单消失——
`f5449e07` 和 `5e609332` 两个 commit 确实生效了。）

**463 条 code smell 不影响 Quality Gate**：可维护性评级已经是 A。第一版第 5 节"不要追认知复杂度"
的结论不变，现在有数据支撑——`python:S3776` × 60、`S1192` × 30 全部通过，追它们对灯的颜色没有任何影响。

## 1. 唯一需要先记住的机制

新代码评级不是加权平均，是**最严重的一条说了算**：

```
A = 该类型下没有任何未解决问题
B = 最高为 LOW      C = 最高为 MEDIUM
D = 最高为 HIGH     E = BLOCKER
```

现在两个 D 各自的来源小得出乎意料：

- **Reliability D ← 恰好 1 条 HIGH**：`javascript:S2871`，`frontend/scripts/check-design-scale.mjs:67`
- **Security D ← 恰好 2 条 HIGH**：`python:S4790`，`app/agents/rag/web.py:88` 与
  `app/services/caching/cache_manager.py:346`

**三行代码就能把两个 D 变成 C。但 A 要求归零**——26 条 bug 和 16 条 vulnerability 里的每一条，
都必须被修掉，或者在 Sonar 里以书面理由标为 won't fix / false positive。没有中间状态。

这决定了计划的形状：**一半是改代码，一半是在 Sonar 里做有理由的裁决。**

## 2. 新代码 26 条 bug，逐条

| 规则 | 数量 | 位置 | 处置 |
|---|---|---|---|
| `css:S8778` | 12 | `styles/main.css:92-107` | **真修**（第一版判断错了，见第 5 节） |
| `typescript:S1082` | 7 | 五个组件 | 需要决定，见下 |
| `python:S1244` | 4 | `router/calibration.py:57,138` | won't fix，写理由 |
| `python:S5863` | 2 | 两个测试 | won't fix，写理由 |
| `javascript:S2871` | 1 | `check-design-scale.mjs:67` | **真修**，且是 Reliability D 的唯一来源 |

### `javascript:S2871` —— 一行，零风险

`cssFiles("src").sort()`。数组元素是字符串，默认字典序正是想要的，规则本身是冲着数字数组来的。
但显式写比较函数是一行，还能顺手让排序不再依赖默认行为：

```js
const files = cssFiles("src").sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
```

**不要用 `localeCompare`**——它依赖 locale，会让 `design-scale-baseline.json` 的键顺序在不同机器上不同，
那正好是一个 ratchet 文件最不需要的性质。

### `typescript:S1082` × 7 —— 值得做，但不要为了灯去做

`ConfirmDialog.tsx:43,44`、`PromptDialog.tsx:64,65`、`SessionExportImport.tsx:217`、
`SessionSearch.tsx:268`、`AnimatedToastLite.tsx:61`。

第一版说"这是可访问性工作，应该和前端 a11y 一起排"。这个判断仍然对，但现在多了一条信息：
**A 要求归零，所以不做这 7 条就到不了 A**。两条路，明说，不要含糊：排 a11y 工作，或者接受
Reliability 停在 B。

看过代码之后有一条补充：`ConfirmDialog` / `PromptDialog` 命中的是遮罩层
（`<div className="confirm-dialog-overlay" onClick={onCancel}>`）和它里面 `stopPropagation` 的容器，
而 Esc 关闭**已经**在 `useEffect` 里接好了。所以这四条在行为上接近误报，正确的修法是把对话框换成原生
`<dialog>`，或者给遮罩加 `role="presentation"`——**不是**给一个非交互的 div 套一个假的 `onKeyDown`。
后者只是让扫描器闭嘴，同时给屏幕阅读器制造一个不存在的控件，比不做更糟。

### `python:S1244` × 4 与 `python:S5863` × 2 —— 已核实为有意

`calibration.py` 比较的是与字面量边界值（`== 1.0`、`== 0.5`），改成 `math.isclose` 会改变分桶边界行为；
两个测试里"实际值与期望值是同一个表达式"正是主题（哈希的确定性、缓存的复用）。在 Sonar 里标 won't fix
并写明理由。**一个被压下去但写明原因的告警，好过一个为了让灯变绿而做的假修改。**

## 3. 新代码 16 条 vulnerability，逐条

| 规则 | 数量 | 位置 | 处置 |
|---|---|---|---|
| `pythonsecurity:S5145` | 6 | 见下 | 部分收窄输入，部分 FP |
| `githubactions:S8541/S8544/S6505` | 4 | `.github/workflows/ci.yml:31,40,72` | 真修，要跑 CI |
| `python:S4790` | 2 | `rag/web.py:88`、`caching/cache_manager.py:346` | **真修**，Security D 的唯一来源 |
| `typescript:S2245` | 2 | `csrf.ts:23`、两处 toast id | 一真一误 |
| `pythonsecurity:S6549` | 1 | `operations/evaluation.py:30` | 已核实为误报 |
| `python:S5332` | 1 | `chunking/metadata.py:62` | 已核实为误报 |

### `python:S4790` × 2 —— 两行，把意图写进代码

两处都是拿 md5 当缓存键，非加密用途。Python 3.9+ 有专门表达这个意图的参数，Sonar 也认它：

```python
# rag/web.py:88
md5(question.encode("utf-8"), usedforsecurity=False)

# caching/cache_manager.py:346
hashlib.md5(key_str.encode(), usedforsecurity=False)
```

比标 FP 好：它把"这不是安全用途"写在代码里，而不是写在扫描器后台——后者只有登录进 SonarCloud 的人看得见。

### 供应链 4 条 —— 改配置，但必须真跑一次 CI

`pip install` 加 `--only-binary :all:`，`npm ci` 加 `--ignore-scripts`。Dockerfile 侧还有同源的
`docker:S8541` × 2 / `S8544` × 2 / `S6505` × 1（不在新代码窗口内），一起改一次。

两个风险写清楚，不要合了才发现：

- `--only-binary :all:` 会让任何**只发 sdist** 的依赖装不上。已实测 `pip install --only-binary :all: -e .`
  **能跑通**——pip 不会把这个开关套到本地 editable 的项目自身上，所以 `-e ".[dev]"` 那一行可以直接加。
  但依赖的 wheel 供应在 CI（ubuntu / py3.11）上和本地不同，仍然要看一次 CI。
- `npm ci --ignore-scripts` 会让需要 postinstall 的包失效。前端有 Playwright（`npm run screenshots`），
  它的浏览器下载正是 postinstall——CI 不跑 screenshots 所以 CI 会绿，**但本地装完会缺浏览器**。
  要么在 screenshots 的文档里补一句 `npx playwright install`，要么给那一步单独放行。

`text:S8565`（pyproject 没有 lock 文件）是更大的一步，独立议题，不建议塞进这轮。

### `typescript:S2245` —— 已完成（2026-09-02），但修的不是告警指的那一行

`frontend/src/lib/csrf.ts:23` 是 `crypto.getRandomValues` 不可用时用 `Math.random` 生成 CSRF token 的
回退分支。**第一反应"删掉回退分支并抛错"是错的**，因为它假定这个 token 有人校验。读了另一端之后：

- `CSRFProtectionMiddleware` 要一个 `session_id` cookie 才会走到校验，**全仓库没有任何路由 set 过它**
  ——这个名字的全部出现就是中间件自己在读。所以 `if not session_id: return await call_next(request)`
  接住了每一个请求，它下面的代码不可达。
- 前端自己在浏览器里造 token，服务端从没 mint 过也没存过。**就算那个 cookie 存在，每个写请求都会 403。**

给一个没人校验的值加熵，是照着告警的形状修而不是照着缺陷的形状修。

真正在工作的是 `_enforce_cookie_csrf`（`app/api/utils/auth_helpers.py`），跑在每条路由都经过的
`_resolve_authenticated_user` 里，而且它更窄也更对：只在**用 cookie 认证**时生效（跨站页面设不了
`Authorization` 头，所以 Bearer 流量不需要 token 来证明什么），写方法要求 Origin 在白名单里，
**没有 Origin 就拒绝**。最后这条是防护的全部，`tests/security/test_cookie_csrf.py` 把它钉住了。

两套里空转的那套已删除（`3cca16db`），连带：`CSRF_ENABLED`（唯一读者就是注册那个中间件的那行，
又一个背后没有东西的开关）、`enhanced_session.py` 整个模块（唯一生产入口是那个中间件；`auth_service`
用的是另一个 `SessionManager`），以及它的 SessionStore 测试——那个"写失败却报告成功"的缺陷是真的，
但在一个请求到不了的模块里。`RATE_LIMIT_CONFIG` / `get_client_ip` 移进 `rate_limit.py`，它们本来就不是
CSRF 的事。

在跑起来的应用里验证过，不只是测试：登录 POST 只带 `content-type` 出去，回来 401 invalid credentials。

另两条 `AnimatedToastLite.tsx:129`、`useChatActions.ts:84` 生成的是 toast 元素 id，非安全用途，
已换成 `crypto.randomUUID()`（`d3c6ccd9`）。`frontend/src/` 里现在没有 `Math.random` 了。

**这一条值得单独记**：Sonar 指着 `Math.random`，缺陷却在三层之外的另一端。扫描器能告诉你哪一行可疑，
不能告诉你那一行有没有意义——读完整条链路才能。

### `pythonsecurity:S5145` × 6 —— 已完成（2026-09-02），两端都做了

命中点（全量 8 条）：`agent_health.py:186`、`evaluation.py:161,236`、`cache_manager.py:266`、
`agent_execution_tracker.py:103`、`guard.py:297,312`、`admin_token_tracker.py:76`。

逐个看过：写进日志的全部是**标识符**——`execution_id`、`user_id`、`system_name`、`user_key`、
`token_hash[:8]`、缓存 `prefix`——不是 question 文本。仓库已有的 `question_ref` 守卫针对的是另一件事，
这批不在它的射程内。

真实风险是 CRLF 日志注入：调用方能控制的 id 里塞一个 `%0A`，就能在日志里伪造一整行。

两个方向，建议都做：

- **一个 `logging.Filter`，把格式化后 record 里的控制字符去掉。** 这是属性而不是补丁，
  和仓库处理 `question_ref` 的方式同构。代价：Sonar 的污点分析看不见 filter，这 8 条仍然要手动标 FP
  并在备注里指向它。
- **在入口收窄输入**，这个 Sonar 认：`evaluation.py` 的 `system: str` 改成 `Literal[...]`
  （顺带把无效系统名从深处抛 HTTPException 变成一个 422），`agent_health.py` 的 `execution_id`
  在路由上校验成 UUID。

两个都做了（`d3c6ccd9`）：

- **边界**：`ExecutionId`（`app/api/routes/internal/path_params.py`）把路径参数限制成不含空白的字符类，
  畸形 id 变成 422 而不是更深处的 404。**六条路由全部覆盖，不是 Sonar 点名的那一条。**第六条
  （SSE 端点）是靠问 OpenAPI 文档找出来的而不是靠 grep——它写着 `max_length=128` 没有字符类，
  看上去像是约束过了。测试用同样的方式发现路由，所以第七条加不进来。
- **背后**：`install_control_character_escaping()` 装一个 `LogRecord` factory，在 record 构造时
  转义 message 和 args 里的控制字符。一处顶八处，对每个 logger、每个 handler、以及还没写的调用点都成立。
  **转义而不是删除**，这样注入的痕迹对读日志的人还是可见的。`exc_info` 故意不碰。
- `evaluation.py` 的 `system: str` → `SystemName`（`Literal`），`SUPPORTED_SYSTEMS` 反过来从它派生。

**Sonar 的污点分析看不见 record factory，所以这 8 条仍然会开着**，需要在第 4 步标 FP 并指向它。
这里做的是性质，不是告警数字。

### 两条已核实为误报

- **`pythonsecurity:S6549`** `evaluation.py:30`。`_resolve_query_file` 已经在 `resolve()` 之后检查
  `suffix == ".json"` 且 `is_relative_to(_EVALUATION_ROOT)`。这**正是**这条规则推荐的补救措施，
  污点引擎没识别出来。标 FP，理由写 "containment check in the same function"。
- **`python:S5332`** `chunking/metadata.py:62`。`"http://" in chunk_text` 是在检测**文档正文里**
  有没有 URL，不是发请求。标 FP。

## 4. 不在新代码窗口，但按严重性更该看

这些不影响 Quality Gate，所以不要为了灯去动它们；但其中一条比上面很多条都重要。

| 规则 | 位置 | |
|---|---|---|
| `pythonsecurity:S2083` **BLOCKER** | `services/auth/legacy_service.py:63` | **已删除模块（`d3c6ccd9`）**。告警本身是误报（`path` 来自 settings 不来自用户输入），但真正该问的问题是这个模块要不要留：`AuthService` 只在 `app/services/auth/__init__.py` 里被 re-export，全仓库没有任何消费者，认证跑的是 `AuthDBService`。连同两个 `Settings` 字段、两个路径 property 和两行启动 mkdir 一起删——本机的 `data/security/` 就是那个 mkdir 建出来的空目录，从没被写过。**按事实删掉，而不是标记掉。** |
| `python:S2068` | `security/admin_rate_limit.py:55` | 误报：`"password_reset": "5/hour"` 是限流表的键 |
| `docker:S6471` × 2 | `Dockerfile:22`、`Dockerfile.frontend:23` | 容器以 root 运行。真问题，属于部署加固，独立议题 |
| `pythonsecurity:S8703/S8707` | `deploy/scripts/healthcheck.py:13`、`config.py:108` | Sonar 针对"LLM 驱动执行"的新规则，命中的是部署脚本的 CLI 参数，不在请求路径上 |

## 5. 第一版判断错了的一条：`css:S8778` × 12

第一版的结论是"不适用，标 FP"，理由是"按这条告警去挪 `@import`，会破坏 `@layer` 顺序声明必须在前的结构"。

**这个理由不成立。** CSS 规范的原文是：`@import` 必须先于所有其它规则，**`@charset` 和 `@layer` 语句除外**。
所以 `@layer theme, legacy, components, design, utilities;` 留在最前面，12 行 `@import` 移到它之后、
`@theme inline { }` 之前，两个约束同时满足。

**已实测**：按上述顺序改写 `main.css` 后 `npm run build`，`dist/assets/` 下 12 个 CSS 产物与改动前
**逐字节相同**。零风险，一次 12 行的移动，消掉 26 条新代码 bug 里的 12 条。

细节：所有 `@import` 都显式带 `layer()`，层内相对顺序保持不变即可（`tokens → reset → utilities →
components → elevation/surfaces`）；`@theme inline` 是块规则、`@source` 是语句规则，两者都必须留在
`@import` 之后，这是移动的下界。

这条值得记：第一版把"我不想改"和"规范不允许改"混在了一起。判成不适用之前，应该先试着改一次再看产物。

## 6. 建议顺序

**第 1 步 · 一个 commit，约 30 分钟 —— 两个 D 变 C**

- `main.css` 移 12 行 `@import`（产物已验证逐字节相同）
- `check-design-scale.mjs:67` 加比较函数
- `web.py:88`、`cache_manager.py:346` 加 `usedforsecurity=False`

结果：新代码 bug 26 → 13，vulnerability 16 → 14；Reliability **D → C**，Security **D → C**。
Gate 仍然红，但两个评级各上一档，而且这一步没有任何行为改变，不需要新测试。

**第 2 步 · 一个 commit + 一次完整 CI —— 供应链**

CI 与两个 Dockerfile 的 `--only-binary` / `--ignore-scripts`。消掉 **3 条新代码 + 6 条全量**：
`S8541` × 4（gh 2 + docker 2）和 `S6505` × 2（gh 1 + docker 1）。

**`S8544` 不在其中**——它说的是"依赖没有锁定解析结果"，只有 lock 文件能消掉它，`--only-binary`
不行。所以 `githubactions:S8544` × 1 和 `docker:S8544` × 2 会连同 `text:S8565` 一起留到 lock 文件那一轮。
（第一版这里写的是"消掉 4 条新代码"，把 `S8544` 算了进去，是错的。）

合之前必须看到 CI 全绿，并且确认 Playwright 那一条的处理方式。

**第 3 步 · 一个 commit —— 日志与输入收窄**

`evaluation.py` 的 `Literal`、`agent_health.py` 的 UUID 校验、删掉 CSRF 回退分支、
控制字符 logging filter、两处 toast id 换 `crypto.randomUUID()`。
CSRF 那条带一个测试：断言 `crypto` 缺失时抛错而不是返回弱 token。

**第 4 步 · 没有代码改动 —— 在 Sonar 里裁决，每条写理由**

`S1244` × 4、`S5863` × 2、`S5332`、`S6549`、`S2083`、`S2068`、剩余 `S5145`、两条非安全的 `S2245`。

**第 5 步 · 决定 `typescript:S1082` × 7**

这是 A 与 B 之间唯一剩下的东西。要么排一轮真正的 a11y（原生 `<dialog>` / `role="presentation"` /
真实键盘处理），要么接受 Reliability 停在 B 并写明。**不要套假的 `onKeyDown`。**

## 7. New Code 的定义，以及两个配置观察

新代码窗口的基线是 `previous_version`，日期 **2026-07-27**——"新代码"因此等于五周多、147 个 commit，
几乎是整个仓库。评级衡量的是历史积累，不是最近的改动质量。

如果目标是"让 Gate 反映此后的改动质量"，把 New Code 改成 `Number of days` 或指定参考分支是**正当的**，
这是 Sonar 官方推荐的用法，不是作弊。如果目标是"把这批存量清干净"，就按第 6 节走。
**两个目标不同，先选一个再动手。**

另外两条，与上面的清单无关但值得知道：

- 仓库里**没有** `sonar-project.properties`，走的是 SonarCloud 自动分析。想要 exclusions
  （比如把 `tests/` 排除出某些规则）或者上传覆盖率，需要改成在 CI 里跑 scanner。
- **现在完全没有覆盖率数据**（`coverage` 指标缺失）。当前 Gate 没有覆盖率条件，所以不受影响，
  但 538 个测试跑出来的覆盖率没有进 Sonar，是白丢的信息。

## 附录：第一版已完成的部分（保留记录）

**P0 · `python:S930` × 5，`ingestion/loaders/dispatch.py`** —— `load_pdf_enhanced` 被用三个它不接受的
具名参数调用，`PDF_LOADER_MODE=docling_advanced` / `docling_enhanced` 两个模式必然 `TypeError`，
且 `PDF_ENABLE_CLEANING` / `PDF_ENABLE_TABLE_MERGING` 两个配置项当时没有任何效果。
已在 `f5449e07` 修复：给包装函数加参数并透传。

**P1 · 12 条里只有 5 条是真的**，已在 `5e609332` 修复。这个比例本身值得记：照单全改会引入 7 个无谓的改动，
其中至少两个会破坏正确的代码。

改掉的 5 条：`agent_execution_tracker.py:506`（吞掉 `CancelledError` 后 `break`，取消方分不出
"照办了"和"自己跑完了"）、`enhanced_session.py`（写入失败仍返回 `True`，会话没存上却告知成功）、
`chunking/classification.py:58`（`text.lower().strip()` 结果被丢弃——**删掉**而不是改成赋值，
改成赋值会改变每个文档的分类结果，那是决定不是清理）、`extraction/tables_nested.py:167`（裸表达式）、
`processing/coreference.py:96`（不可达分支）。有行为后果的两条带了测试
（`tests/services/test_cancellation_and_session_truth.py`），并验证过去掉修复后会失败。

没改的 7 条即本文第 2、3 节里标 won't fix 的那些，理由同上。
