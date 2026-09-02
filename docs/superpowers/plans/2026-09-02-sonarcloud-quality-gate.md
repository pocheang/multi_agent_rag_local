# SonarCloud Quality Gate 修复计划

状态：已核实分类，未开始修复（2026-09-02）。

## 0. 先说结论

Quality Gate 卡在**新代码**的两个评级：Reliability D、Security D（要求 ≥ A）。总量是
41 bugs / 31 vulnerabilities / 803 code smells，其中"新代码"占 27 / 16 / 464。

**"新代码"这个范围需要注意**：147 个 commit 刚合进 main，所以 Sonar 眼里几乎整个仓库都是新的。
这些评级反映的是仓库的历史积累，不是这几天的改动质量。

**分类过的结论是：真正该修的远少于总数。** 我逐条核实过下面每一类，不是照搬扫描器输出——
这一轮已经有三次是我自己的检查脚本误报，扫描器同样会错。

## 1. 已核实为真，且会在运行时炸（P0）

### `python:S930` × 5 —— PDF 的两个加载模式必然 TypeError

`app/ingestion/loaders/dispatch.py:84,85,98,99,100` 用三个具名参数调用
`load_pdf_enhanced`，而它的签名是 `(path: Path, by_page: bool = True)`，没有 `**kwargs`。

实测确认：

```
TypeError: load_pdf_enhanced() got an unexpected keyword argument 'enable_cleaning'
```

影响 `PDF_LOADER_MODE=docling_advanced` 和 `docling_enhanced` 两个模式。默认是 `pypdf`，
所以不是每个人都会撞上——但谁一旦按文档切过去就立即崩，而且 `PDF_ENABLE_CLEANING` /
`PDF_ENABLE_TABLE_MERGING` 这两个配置项**今天没有任何效果**，因为接收它们的函数根本不接受它们。

修法有两个方向，需要先判断哪个是本意：

- 如果 `load_pdf_enhanced` **应该**支持这些开关 → 给它加参数并透传到
  `pdf_loader_enhanced.load_pdf_enhanced`；
- 如果不该 → 删掉调用点的三个参数，并把那两个 Settings 字段一并处理（要么删，要么接到真正
  读它们的地方）。**保留一个没有读者的配置项，正是配置治理那一轮反复清理的东西。**

落地时带一个测试：按签名调用，而不是断言"不抛异常"。

## 2. 已核实为真，小而便宜（P1）—— **已完成（2026-09-02）**

逐条核实后，这一组**12 条里只有 5 条是真的**，另外 7 条是误报或有意为之。这个比例本身值得记：
照单全改会引入 7 个无谓的改动，其中至少两个会破坏正确的代码。

**改掉的 5 条：**

| 位置 | 是什么 |
|---|---|
| `agent_execution_tracker.py:506` | `_cleanup_loop` 捕获 `CancelledError` 后 `break`，协程**正常结束**而非取消状态——`task.cancel()` 之后 `await task` 不抛异常，取消方分不出"照办了"和"自己跑完了" |
| `enhanced_session.py` | `_save_file_sessions` 吞掉写入异常只打日志，`set()` 无论如何返回 `True`——**会话没存上，调用方却被告知成功**。对会话存储来说就是"登录不会存活但没人知道" |
| `chunking/classification.py:58` | `text.lower().strip()` 结果被丢弃，下面所有检查读的都是原始 `text`。**删掉**而不是改成赋值：改成赋值会改变每个文档的分类结果，那是决定不是清理 |
| `extraction/tables_nested.py:167` | 裸表达式 `lines[i + 1]`，什么也不做 |
| `processing/coreference.py:96` | `recent_entities[-1] if recent_entities else None` 的 else 分支不可达——函数开头的守卫已经返回过了 |

**没改的 7 条，及理由：**

- `python:S7497` 另一处（`stop_periodic_cleanup` 的 `except CancelledError: pass`）——**这是取消自己刚
  cancel 的任务的标准写法**。在这里重新抛出会把取消传播进关闭流程，是错的。加了注释说明意图。
- `python:S5863` × 2 —— `assert question_ref(x) == question_ref(x)` 和
  `assert _search("alice") == _search("alice")`。规则假设"两边表达式相同"是笔误，但这里**表达式相同正是主题**：
  测的是哈希的确定性和缓存的复用。
- `python:S1244` × 4 —— `calibration.py` 里比较的是与字面量边界值（`== 1.0`、`== 0.5`）。改成 `math.isclose`
  会改变分桶边界行为，收益为零。

前两组应在 Sonar 里标记为 won't fix 并写明理由。**一个被压下去但写明原因的告警，好过一个为了让灯变绿而做的假修改。**

有行为后果的两条带了测试（`tests/services/test_cancellation_and_session_truth.py`），并验证过去掉修复后会失败。
另外三条是删除不可达代码，行为不变，没有可断言的新性质。

### 原始清单（供对照）

| 规则 | 位置 | 是什么 |
|---|---|---|
| `python:S7497` × 2 | `observability/agent_execution_tracker.py:506,518` | 捕获 `asyncio.CancelledError` 后没有重新抛出——会把取消吞掉，任务无法被中断 |
| `python:S2201` × 2 | `chunking/classification.py:58`、`extraction/tables_nested.py:167` | 调用了 `str.strip()` / `__getitem__` 却不用返回值，即这一行什么也没做 |
| `python:S5863` × 2 | 测试里 | 断言的实际值和期望值是同一个表达式——**测试等于没测** |
| `pythonbugs:S2583` | | 条件恒为真 |
| `python:S3516` | `auth/enhanced_session.py:55` | 方法永远返回同一个值 |
| `python:S1244` × 4 | | 浮点数相等比较 |

这一组都是"读一眼就能判断对错"的，逐个看、逐个修，每个带一行断言。

## 3. 供应链加固，改配置即可（P1）

`docker:S8541/S8544/S6505`、`githubactions:S8541/S8544/S6505`、`text:S8565` 共 8 条，说的是同一件事：
安装依赖时没有锁定和禁用安装脚本。

- `pip install` 加 `--only-binary :all:`（阻止 sdist 执行 `setup.py`）
- `npm ci` 加 `--ignore-scripts`（阻止 lifecycle 脚本）
- 用 lock 文件固定解析结果

**与刚做完的 ruff 钉版本是同一个道理**：浮动的依赖既是安全面也是"构建会无故变红"的来源。
注意 `--ignore-scripts` 可能影响需要构建步骤的包，要跑一次完整 CI 验证。

## 4. 需要人判断，不能照单全改（P2）

| 规则 | 数量 | 为什么要先判断 |
|---|---|---|
| `pythonsecurity:S5145` 记录用户可控数据 | 8 | 本仓库**已有**这条规则的守卫（`question_ref` + `tests/security/test_no_question_text_in_logs.py` 的 AST 检查）。命中的是 `agent_health.py`、`evaluation.py`、`cache_manager.py`、`guard.py`——要逐个看记的到底是什么字段，是真泄漏还是 Sonar 不认识这套脱敏 |
| `pythonsecurity:S2083` 路径由用户数据构造 | 1 | `auth/legacy_service.py:63`。仓库在文档访问上有很强的作用域控制，这条要看是不是漏网，还是这个 legacy 模块本就该删 |
| `python:S4790` 哈希是否安全 | 2 | `agents/rag/web.py:88` 等。多半是非加密用途的摘要（去重/缓存键），那样是安全的——但要确认，然后在 Sonar 里标记为 "won't fix" 并写明理由 |
| `typescript:S2245` `Math.random` | 3 | 前端非安全用途多半没问题 |
| `python:S5332` 用 HTTP 而非 HTTPS | 1 | 若是 localhost 则无妨 |

**这一组的产出不一定是代码改动**，也可能是在 Sonar 里标记豁免并写清理由。一个被压下去但写明原因的
告警，比一个为了让灯变绿而做的假修改要好。

## 5. 不要追的（P3）

- **`python:S3776` 认知复杂度 × ~35 条**。它们指向 `ingest.py`（71）、`splitter.py`（58）、
  `routing.py`（49）这些确实复杂的函数。但"降低复杂度"是重构，不是修 bug；在一个正在往 v0.7
  演进的代码库里，为了指标去拆函数会制造大量无意义的 diff，还会掩盖真实的改动。
- **`python:S1192` 重复字面量**。同上。
- **`typescript:S1082` 可点击元素缺少键盘可达性 × 8**。这个**值得做**，但它是可访问性工作，
  应该和前端的 a11y 一起排，而不是塞进"让 Quality Gate 变绿"里。

## 6. 已核实为**不成立**，不要修

**`css:S8778` "Invalid position for @import rule" × 12**（`styles/main.css:92-107`）。

规范上确实要求 `@import` 在样式规则之前，而这些在 `@theme { }` 块之后。但这个文件是 **Vite 的
构建输入**，Vite 在打包时会把 `@import` 内联。已在 `dist/assets/*.css` 里确认那些组件样式
（`confirm-dialog`、`thinking-indicator`、`skeleton`、`--elev-*`）**全部存在于构建产物中**。

按这条告警去挪 `@import`，会破坏 `@layer` 顺序声明必须在前的结构——**那才会真的弄坏样式**。
应在 Sonar 里标记为不适用，并写明理由。

## 7. 建议的顺序

1. **P0**：`dispatch.py` 的 5 条 S930，含那两个没有读者的 Settings 字段。一个 commit。
2. **P1**：第 2 节的 12 条小 bug，一个 commit；第 3 节的供应链加固，另一个 commit（要跑 CI 验证）。
3. **P2**：逐条判断，产出可能是修改也可能是带理由的豁免。
4. **P3**：不做，或另开与质量指标无关的议题。

做完 1–3 之后再看 Quality Gate。**它不一定会变绿**——新代码的评级由最严重的一条决定，而
"新代码"目前几乎等于整个仓库。如果目标是让灯变绿而不是让代码变好，更合适的做法是把 Sonar 的
**New Code 定义改成"自某个日期起"**，让它衡量此后的改动，而不是衡量一次 147 个 commit 的合并。
那是一个项目设置，不是代码问题。
