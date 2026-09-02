# 2026-08-31 技术决策 / Decisions

## 1. 流式片段用独立的事件名，而不是复用 `execution_event`

**决定**：`answer_fragment` 是第二个事件名，走同一条订阅、同一次访问校验。

**理由**：片段是**草稿**——它没有引用编号，也没有引用来源列表，两者都由 `output_filter` 在
整个答案写完、且 DLP 决定了哪些引用能留下之后才决定。同一个事件名会让客户端有可能把草稿当
成成品答案。内部的 `[E{k}]` 标记在发布前剥掉，而不是渲染出去。

**被否**：给 `execution_event` 加一个 `kind` 字段。这把「别搞混」变成一个客户端必须记得检查
的运行时约定，而独立事件名让它成为一个协议事实。

## 2. 流式脱敏的释放条件包含「稳定性检查」

**决定**：只在 `redact(raw[:b])` 仍是 `redact(raw[:b + margin])` 的前缀时才释放到 `b`。

**理由**：我最初只在缓冲区尾部留余量，方向是反的。`password = hunter2` 这类秘密**起始于边
界之前、跨越边界**，尾部余量接不住。实测有 3 条测试挂掉才发现。

已发出内容记录为字符串而非长度，因为脱敏会改变长度，偏移量算术会失步。

`test_streaming_redaction.py` 测的是**性质而不是样例**：八种秘密形状，断言在**每一个**切分
点上流式输出都等于最终脱敏结果。固定几个 chunk size 测的是错的东西——chunk 边界正是流式
DLP 与批量 DLP 的唯一区别。

## 3. 两段式检索只在有读者时才启用

**决定**：`GraphKnowledgeAdapter.wants_prior_evidence()` 读 `GRAPH_RAG_ENHANCED`。关掉时图检
索留在第一阶段，与其他源并发，延迟完全不变。

**理由**：第二阶段的代价是真实的——被推迟的源的耗时落到关键路径上，不再藏在其他源底下。开
关关掉时先验证据没有读者，付这个代价什么也换不到。

**相关决定**：第二阶段继承 `STAGE_TIMEOUT_RETRIEVAL_MS` 的**剩余**额度，而不是各自一份计划
超时。否则两阶段可能耗 `phase_one + phase_two` 撞穿 stage 上限，把「更准的图查找」变成「降
级的 stage」——比它替换掉的那个朴素查找严格更差。

## 4. 先验证据只能调参，不能扩权

**决定**：穿过 `run_graph_rag` 的是对检索文本的质量**分数**加页码/格式元数据。
`run_graph_rag_with_pdf_context` 不从文档里读实体去查询；`allowed_sources`/`owner` 仍是
`privacy_permission` 解析的那份。

**理由**：一份「自吹重要」的文档最多给自己买到更大的 `max_neighbors`，仅此而已。让文档文本
决定去查哪些实体，就是让被检索的内容操纵检索——而被检索文档的作者未必是提问的人。这与工具
选择对证据保持盲视是同一条推理。

## 5. `GRAPH_RAG_ENHANCED` 保持默认 false

**决定**：开关修好了，默认值不动，写进 CLAUDE.md 的 dormant 清单。

**理由**：项目自己的政策就是这条——「Turning any of them on is a cost/latency decision, not a
bug fix」。这个开关之前是**坏的**而不是**关的**，现在它真的能用了，开不开是部署决定：增强查
找按实体逐个循环（最多 5 次邻居 + 3 次路径查询），基础查找是批量的，约 3 次 Neo4j 往返换最多
9 次。

## 6. `max_retrievals` 管源数量，不管宽度

**决定**：`TaskBudget.max_retrievals` 上限的是 `len(strategy.sources)`。

**理由**：我一开始描述错了，以为它是每源结果宽度。planner 按 `2 + hybrid?1 + web?1` 推出
它——这是**检索调用次数**，正好对应 `_rule_strategy` 构建的源列表。

**衍生决定**：截断按 planner 自己的推导顺序花（必需二元组 → 路由 hint → 关键词）。预算的
`+1` 是**为 web 加的**，而关键词规则把 `web` 追加在最后，按发现顺序截断会把这一格花在
`multimodal` 上，那这个数字就没有意义了。

**衍生决定**：预算合计为 0（纯工具调用 plan）**不收窄**。那是「没提出要求」，不是「要求少
搜」——路由已经决定这里允许检索。收窄到 1 是发明一个 planner 没表达过的指令。

## 7. 复杂度缩放的基数是 `TOP_K`，不是 `VECTOR_TOP_K`

**决定**：一个复杂度定义，两个调用点用不同基数。

**理由**：借用 hybrid 路径的默认值（6）会把**每一个简单查询**也一起加宽 50%——那是另一个决
定，不该混在「让复杂查询更宽」里顺手做掉。简单查询的宽度在改动前后完全一致，有测试钉住。

## 8. deadline 只收窄，不放宽

**决定**：`remaining_ms()` 取 `min(配置额度, deadline 剩余)`。

**理由**：一个比 `STAGE_TIMEOUT_TOTAL_MS` 更远的 deadline 若能延长预算，调用方就能靠「礼貌
请求」占住一个 worker 一小时。

**相关决定**：线上格式相对（`timeout_ms`），契约绝对（`deadline_at`）。两边时钟不必一致，
但一个跨阶段消耗的预算不该在每个阶段重新推导。偏移量只测一次，之后走 `perf_counter`——否则
一次 NTP 校正就能移动一个正在跑的请求的预算。

**相关决定**：`MANDATORY_STAGES` 照旧豁免。一个激进的 deadline 不能成为绕过权限解析和输出
脱敏的途径，这条单独有测试。

## 9. 技能「选择」模板，而不是「叠加」模板

**决定**：`skill_answer_template()` 在三种来源里选一种，一个 prompt 里只出现一个模板块。

**理由**：`templates.py` 已经在按问题推断 query type 并把模板塞进提示词。技能和 query type
回答的是同一个问题——「这个答案该长成什么样」——再写一套会在同一个 prompt 里放两种互相竞争
的形状。技能是更好的答案：路由器用 LLM 读了整个问题，`infer_query_type` 只匹配关键词表。

**衍生决定**：`compare_entities` **映射**到既有模板而不是新写一份。这不是省事——它让 LLM 判
定出的比较问题即使措辞里一个关键词都没有也能拿到比较模板。

**衍生决定**：未知技能降级到**改动前的行为**（按问题推断），而不是降级到没有指导。

## 10. 多轮跟随用 LLM 改写，不用规则式指代消解

**决定**：把 `conversation` 传给已有的 `_llm_rewrite`；`app/services/context_management.py`
（642 行规则式指代消解）**不接**到检索路径上。

**理由**：`CoreferenceResolver._has_coreference` 是对固定代词表的子串匹配，两个方向都在普通
中文上失效：

```
_has_coreference("成本呢？")   is False   # 漏：主语省略，没东西可匹配
_has_coreference("那延迟呢")   is True    # 误报：语气词，会被塞进一个过期实体
```

零指代（主语直接省略）是中文跟随问句最常见的形态，规则法**结构上**接不住。它还带着一份硬编
码的中美大公司实体名单。

而 LLM 改写是这个仓库自己已经建好的槽位——`QUERY_REWRITE_*` 三个设置、
`build_rewrite_queries`、`_llm_rewrite` 的时间预算、`_rewrite_once` 每请求跑一次、
`_with_queries` 合并变体——六件东西都在，只差 `conversation` 这一个参数。

**我上一版的建议是接 `ContextManagementService`，已撤回。** 改变判断的不是新信息，是第二遍
才去读 `_has_coreference` 的实现。

**不删 `context_management.py`**：它有一个真实读者（会话导出接口的实体/话题列表）。
`tests/knowledge/test_followup_rewriting.py` 把两个失败方向都钉住，让复活它成为一个在知情下
做出的决定。

## 11. 原问题永远随改写一起进检索

**决定**：`_with_queries` 把原问题并在变体**前面**；`primary_query`（重排打分用）在合并前读取。

**理由**：改写是模型在**猜用户的意思**，它会猜错。一次错误的补全应当**多加一个坏 query**，
而不是**替换掉好 query**。

## 12. `enable_context_tracking` 在消费点强制，不在 API 边缘

**决定**：`RAGAgentService.retrieve` 和 `SynthesizerAgentService.synthesize_candidate` 各自
检查一次。

**理由**：这两处分别是「决定检索能知道什么」和「决定生成能知道什么」的唯一位置。在 API 边缘
把 `conversation` 清空，会让这个 flag 在一条路径上被遵守、在另一条上被遗忘——而
`pipeline_contract.py`（消息重跑）和 `clarification.py` 是另外两个构造请求的入口。
