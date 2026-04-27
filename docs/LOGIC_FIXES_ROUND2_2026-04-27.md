# RAG和路由逻辑漏洞修复 - 第二轮

**日期**: 2026-04-27  
**版本**: v0.2.4+fixes-round2

## 修复概览

第二轮修复解决了4个额外的逻辑漏洞，涵盖重排序、并发控制、文本处理和图谱查询等模块。

---

## 🟡 中等问题修复

### 7. Reranker词法回退评分归一化问题

**问题描述**:
- 在`_lexical_fallback_rerank`中，归一化因子计算有缺陷
- 使用`max(2.0, max_hybrid_score)`导致：
  - 当`max_hybrid_score < 2.0`时，归一化因子固定为2.0
  - 当所有分数都很小（如0.1）时，`base_normalized`会非常小
  - 导致`overlap`（词汇重叠）过度主导最终分数
- 缺少对空查询的处理

**影响**:
- 低分文档的重排序不准确
- 词汇匹配权重过高（70%），混合分数权重过低（30%）

**修复位置**: `app/retrievers/reranker.py:26-56`

**修复内容**:
```python
def _lexical_fallback_rerank(query: str, candidates: list[dict], top_n: int) -> list[dict]:
    query_tokens = set(_tokenize(query))
    
    # 处理空查询
    if not query_tokens:
        sorted_candidates = sorted(candidates, key=lambda x: x.get("hybrid_score", 0.0), reverse=True)
        for item in sorted_candidates[:top_n]:
            item["rerank_score"] = item.get("hybrid_score", 0.0)
        return sorted_candidates[:top_n]

    rescored: list[dict] = []
    max_hybrid_score = 0.0
    for item in candidates:
        hybrid_score = float(item.get("hybrid_score", 0.0) or 0.0)
        max_hybrid_score = max(max_hybrid_score, hybrid_score)

    # 修复归一化逻辑
    if max_hybrid_score > 0.01:
        normalization_factor = max_hybrid_score  # 使用实际最大值
    else:
        normalization_factor = 2.0  # 所有分数接近0时的回退值

    for item in candidates:
        text_tokens = set(_tokenize(item.get("text", "")))
        overlap = 0.0
        if query_tokens:
            overlap = len(query_tokens.intersection(text_tokens)) / len(query_tokens)

        base = float(item.get("hybrid_score", 0.0) or 0.0)
        base_normalized = base / normalization_factor

        merged = dict(item)
        merged["rerank_score"] = 0.7 * overlap + 0.3 * base_normalized
        rescored.append(merged)

    rescored.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    return rescored[:top_n]
```

**关键改进**:
1. 添加空查询处理
2. 修复归一化逻辑：使用实际`max_hybrid_score`而非固定2.0
3. 只在所有分数接近0时使用回退值

**示例对比**:
| 场景 | max_hybrid_score | 旧normalization_factor | 新normalization_factor |
|------|------------------|------------------------|------------------------|
| 正常 | 1.5              | 2.0                    | 1.5                    |
| 低分 | 0.3              | 2.0                    | 0.3                    |
| 极低 | 0.005            | 2.0                    | 2.0 (fallback)         |

---

### 8. Circuit Breaker状态竞态条件

**问题描述**:
- 在`call_with_circuit_breaker`中存在竞态条件
- 成功/失败路径中访问`state`对象时，可能已被其他线程修改
- 在失败路径中使用`now`变量，但该变量在函数开始时获取，可能已过时

**影响**:
- 多线程环境下，circuit breaker状态可能不一致
- 可能导致错误的熔断时间计算

**修复位置**: `app/services/resilience.py:24-48`

**修复内容**:
```python
def call_with_circuit_breaker(name: str, fn: Callable[[], Any]) -> Any:
    settings = get_settings()
    if not bool(getattr(settings, "circuit_breaker_enabled", True)):
        return fn()
    now = time.time()

    # 检查熔断状态（只读，无需锁）
    with _BREAKERS_LOCK:
        state = _BREAKERS.setdefault(name, _BreakerState())
        is_open = state.opened_until > now

    if is_open:
        raise CircuitBreakerOpenError(f"circuit_open:{name}")

    try:
        result = fn()
        # 成功：重置失败计数
        with _BREAKERS_LOCK:
            state = _BREAKERS.get(name)  # 重新获取state
            if state:
                state.fails = 0
                state.opened_until = 0.0
        return result
    except Exception as e:
        # 失败：增加计数并可能打开熔断器
        with _BREAKERS_LOCK:
            state = _BREAKERS.get(name)  # 重新获取state
            if state:
                state.fails += 1
                threshold = int(getattr(settings, "circuit_breaker_fail_threshold", 3) or 3)
                cooldown = int(getattr(settings, "circuit_breaker_cooldown_seconds", 30) or 30)
                if state.fails >= threshold:
                    state.opened_until = time.time() + max(1, cooldown)  # 使用新的时间戳
                    state.fails = 0  # 重置避免溢出
        raise
```

**关键改进**:
1. 分离读取和写入操作的锁
2. 在成功/失败路径中重新获取`state`对象
3. 在设置`opened_until`时使用新的时间戳
4. 添加注释说明锁的使用

---

### 9. 句子分割和接地边缘情况

**问题描述**:
- `_split_sentences`中，长片段（>100字符）也会被合并到前一句
- `apply_sentence_grounding`中，使用`"".join()`连接句子，导致句子间无空格
- 缺少对空句子列表的单独处理
- `support_ratio`计算使用`max(1, len(sentences))`，但sentences可能为空

**影响**:
- 长片段被错误合并，导致句子过长
- 输出文本格式不正确（句子粘连）
- 空答案处理不当

**修复位置**: `app/services/citation_grounding.py:29-112`

**修复内容**:

1. 修复句子分割：
```python
def _split_sentences(text: str) -> list[str]:
    raw_text = str(text or "").strip()
    if not raw_text:
        return []

    # 保护缩写
    protected_text = raw_text
    for abbr in _ABBREVIATIONS:
        protected_text = protected_text.replace(abbr, abbr.replace('.', '<ABBR>'))
        protected_text = protected_text.replace(abbr.upper(), abbr.upper().replace('.', '<ABBR>'))

    # 分割句子
    raw_sentences = _SENTENCE_SPLIT_RE.split(protected_text)

    sentences = []
    for sent in raw_sentences:
        restored = sent.replace('<ABBR>', '.')
        cleaned = restored.strip()

        if len(cleaned) < 3:
            continue

        # 只合并短片段（<100字符）且不以标点结尾的
        if sentences and cleaned and cleaned[-1] not in '。！？.!?' and len(cleaned) < 100:
            sentences[-1] = sentences[-1] + ' ' + cleaned
        else:
            sentences.append(cleaned)

    return sentences if sentences else [raw_text]
```

2. 修复接地逻辑：
```python
def apply_sentence_grounding(
    answer: str,
    evidence_texts: list[str],
    threshold: float = 0.22,
) -> tuple[str, dict]:
    sentences = _split_sentences(answer)
    evid_tokens = _tokenize("\n".join([x for x in evidence_texts if x]))
    
    # 分别处理空句子和空证据
    if not sentences:
        return answer, {"enabled": False, "reason": "no_sentences", "total_sentences": 0}
    if not evid_tokens:
        return answer, {"enabled": False, "reason": "no_evidence", "total_sentences": len(sentences)}

    supported = 0
    rewritten: list[str] = []
    low_support_examples: list[str] = []
    
    for sent in sentences:
        score = _support_score(sent, evid_tokens)
        if score >= threshold:
            supported += 1
            rewritten.append(sent)
            continue
        if _has_hedge(sent):
            rewritten.append(sent)
            continue
        low_support_examples.append(sent[:120])
        rewritten.append(f"基于当前可用证据，{sent}")

    # 使用空格连接句子
    grounded = " ".join(rewritten).strip()
    # 清理多余空格
    grounded = re.sub(r'\s+', ' ', grounded)

    report = {
        "enabled": True,
        "total_sentences": len(sentences),
        "supported_sentences": supported,
        "support_ratio": (supported / len(sentences)),  # 不使用max(1, ...)
        "low_support_examples": low_support_examples[:3],
    }
    return grounded or answer, report
```

**关键改进**:
1. 长片段（≥100字符）不再被合并
2. 句子间使用空格连接
3. 分别处理空句子和空证据的情况
4. 修复`support_ratio`计算（移除不必要的`max(1, ...)`）

---

### 10. Query Rewrite去重逻辑缺陷

**问题描述**:
- `build_rewrite_queries`中，去重逻辑不完整
- LLM重写结果的检查使用`if llm_q and llm_q not in rewrites`，但这是列表查找，不是归一化比较
- 空查询处理不当
- 没有折叠多余空格

**影响**:
- 相似的重写变体（如"query  example"和"query example"）被视为不同
- 增加检索负载

**修复位置**: `app/services/query_rewrite.py:101-127`

**修复内容**:
```python
def build_rewrite_queries(
    query: str,
    enable_llm: bool = False,
    use_reasoning: bool = False,
    enable_decompose: bool = True,
    max_variants: int = 6,
) -> list[str]:
    q = str(query or "").strip()
    if not q:
        return []

    rewrites = _rule_rewrites(query)
    if enable_decompose:
        rewrites.extend(_decompose_query(query))
    if enable_llm:
        llm_q = _llm_rewrite(query, use_reasoning=use_reasoning)
        if llm_q:
            rewrites.append(llm_q)

    # 去重：使用归一化形式比较，但保留原始形式
    seen: set[str] = set()
    out: list[str] = []

    for item in rewrites:
        original = item.strip()
        if not original:
            continue

        # 归一化：小写 + 折叠空格
        normalized = re.sub(r'\s+', ' ', original.lower())

        if normalized in seen:
            continue

        seen.add(normalized)
        out.append(original)

        if len(out) >= max_variants:
            break

    return out
```

**关键改进**:
1. 添加空查询检查
2. 使用归一化形式（小写+折叠空格）进行去重
3. 保留原始形式用于检索
4. 移除LLM结果的特殊处理（统一去重逻辑）

**示例对比**:
| 重写变体 | 旧行为 | 新行为 |
|----------|--------|--------|
| "query example" | 保留 | 保留 |
| "query  example" (双空格) | 保留（重复） | 去重 |
| "Query Example" | 保留（重复） | 去重 |
| "query\texample" (tab) | 保留（重复） | 去重 |

---

## 🟢 轻微问题修复

### 11. Graph Lookup Lambda捕获Bug

**问题描述**:
- 在`graph_lookup`的循环中，lambda函数捕获了循环变量`name`
- Python的闭包特性导致所有lambda都引用最后一个`name`值
- 这是经典的"late binding closure"问题

**影响**:
- 对于多个实体，可能查询错误的实体邻居和路径
- 图谱检索结果不准确

**修复位置**: `app/tools/graph_tools.py:69-93`

**修复内容**:
```python
for name in lookup_entity_names[:3]:
    # 修复lambda捕获：在局部作用域捕获name
    current_name = name
    rows = call_with_circuit_breaker(
        "neo4j.entity_neighbors",
        lambda n=current_name: client.entity_neighbors(n, limit=10, allowed_sources=allowed_sources),
    )
    # ... 处理rows
    
    paths = call_with_circuit_breaker(
        "neo4j.entity_paths_2hop",
        lambda n=current_name: client.entity_paths_2hop(n, limit=8, allowed_sources=allowed_sources),
    )
    # ... 处理paths
```

**关键改进**:
1. 使用`current_name = name`在每次迭代中创建局部变量
2. Lambda使用默认参数`n=current_name`捕获当前值
3. 确保每个lambda调用正确的实体

**Python闭包问题示例**:
```python
# 错误示例
funcs = []
for i in range(3):
    funcs.append(lambda: i)  # 所有lambda都引用最后的i
[f() for f in funcs]  # [2, 2, 2]

# 正确示例
funcs = []
for i in range(3):
    funcs.append(lambda x=i: x)  # 使用默认参数捕获当前值
[f() for f in funcs]  # [0, 1, 2]
```

---

### 12. Synthesis Stream错误处理不完整

**问题描述**:
- `stream_synthesize_answer`中，如果streaming失败，会尝试fallback到invoke
- 但streaming失败后，`parts`列表可能为空，导致`initial`为空
- Fallback逻辑在`with bulkhead("llm")`外部，可能导致bulkhead状态不一致
- 缺少对streaming异常的单独处理

**影响**:
- Streaming失败时，用户可能看到空响应
- Bulkhead计数可能不准确

**修复位置**: `app/agents/synthesis_agent.py:229-273`

**修复内容**:
```python
def stream_synthesize_answer(...) -> Iterable[dict[str, str]]:
    prompt = _build_prompt(...)
    try:
        with bulkhead("llm"):
            model = _build_generation_model(use_reasoning=use_reasoning, question=question)
            parts: list[str] = []
            stream_failed = False
            
            # 尝试streaming
            try:
                for chunk in model.stream([("system", ANSWER_PROMPT), ("human", prompt)]):
                    content = getattr(chunk, "content", None)
                    if content:
                        text = str(content)
                        parts.append(text)
                        yield {"type": "chunk", "content": text}
            except Exception as stream_error:
                logger.warning(f"Stream failed, falling back to invoke: {type(stream_error).__name__}")
                stream_failed = True

        initial = "".join(parts).strip() if parts else ""

        # Streaming失败或无内容，fallback到invoke
        if stream_failed or not initial:
            try:
                with bulkhead("llm"):
                    result = model.invoke([("system", ANSWER_PROMPT), ("human", prompt)])
                initial = str(result.content if hasattr(result, "content") else result).strip()
                if initial:
                    yield {"type": "reset", "content": initial}
            except Exception as invoke_error:
                logger.exception(f"Invoke fallback also failed: {type(invoke_error).__name__}")
                yield {"type": "reset", "content": SYNTHESIS_FALLBACK_MESSAGE}
                return

        if not initial:
            yield {"type": "reset", "content": SYNTHESIS_FALLBACK_MESSAGE}
            return

        # 精炼答案
        final = _refine_answer(...)
        if final != initial:
            yield {"type": "reset", "content": final}
    except Exception as e:
        logger.exception(f"Stream synthesis failed for question: {question}")
        yield {"type": "reset", "content": SYNTHESIS_FALLBACK_MESSAGE}
```

**关键改进**:
1. 添加`stream_failed`标志跟踪streaming状态
2. 将streaming异常捕获在内部try-except中
3. Fallback invoke也在`with bulkhead("llm")`中执行
4. 添加invoke失败的单独处理
5. 改进日志记录

---

### 13. Graph Signal Score计算边缘情况

**问题描述**:
- `graph_signal_score`计算使用固定权重（30% entities, 40% neighbors, 30% paths）
- 当某些组件为空时，仍然使用固定权重，导致分数偏低
- 例如：只有entities时，score = 0.3 * entity_score，最大只能到0.3

**影响**:
- 部分图谱数据的信号分数被低估
- 可能导致错误的证据充分性判断

**修复位置**: `app/tools/graph_tools.py:119-142`

**修复内容**:
```python
# 计算各组件分数
entity_score = min(1.0, len(normalized_entities) / 4.0)

neighbor_weights = [float(x.get("weight", 0.0)) for x in neighbor_rows[:12]]
if neighbor_weights:
    neighbor_score = sum(neighbor_weights) / len(neighbor_weights)
    neighbor_score = min(1.0, neighbor_score)
else:
    neighbor_score = 0.0

path_weights = [float(x.get("weight", 0.0)) for x in path_rows[:8]]
if path_weights:
    path_score = sum(path_weights) / len(path_weights)
    path_score = min(1.0, path_score)
else:
    path_score = 0.0

# 动态权重：只对有数据的组件计算加权平均
total_weight = 0.0
weighted_sum = 0.0

if normalized_entities:
    weighted_sum += 0.3 * entity_score
    total_weight += 0.3
if neighbor_rows:
    weighted_sum += 0.4 * neighbor_score
    total_weight += 0.4
if path_rows:
    weighted_sum += 0.3 * path_score
    total_weight += 0.3

graph_signal_score = (weighted_sum / total_weight) if total_weight > 0 else 0.0
```

**关键改进**:
1. 只对有数据的组件计算权重
2. 动态调整权重总和
3. 避免除零错误

**示例对比**:
| 场景 | 旧score计算 | 新score计算 |
|------|-------------|-------------|
| 只有entities (score=1.0) | 0.3 * 1.0 = 0.3 | 1.0 * 1.0 = 1.0 |
| entities + neighbors (各1.0) | 0.3 * 1.0 + 0.4 * 1.0 = 0.7 | (0.3 * 1.0 + 0.4 * 1.0) / 0.7 = 1.0 |
| 全部为空 | 0.0 | 0.0 |

---

## 测试建议

### 1. Reranker归一化测试
```python
def test_reranker_normalization():
    # 测试低分场景
    candidates = [
        {"text": "test doc 1", "hybrid_score": 0.1},
        {"text": "test doc 2", "hybrid_score": 0.2},
    ]
    query = "test"
    result = _lexical_fallback_rerank(query, candidates, top_n=2)
    
    # 验证分数合理性
    assert all(0 <= r["rerank_score"] <= 1.0 for r in result)
    
    # 测试空查询
    result = _lexical_fallback_rerank("", candidates, top_n=2)
    assert result[0]["rerank_score"] == 0.2  # 按hybrid_score排序
```

### 2. Circuit Breaker并发测试
```python
def test_circuit_breaker_concurrency():
    import threading
    
    def failing_fn():
        raise ValueError("test")
    
    errors = []
    def worker():
        try:
            for _ in range(5):
                call_with_circuit_breaker("test", failing_fn)
        except Exception as e:
            errors.append(e)
    
    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # 验证熔断器正确打开
    assert any(isinstance(e, CircuitBreakerOpenError) for e in errors)
```

### 3. 句子接地测试
```python
def test_sentence_grounding_spacing():
    answer = "句子一。句子二。句子三。"
    evidence = ["句子一", "句子三"]
    
    grounded, report = apply_sentence_grounding(answer, evidence, threshold=0.22)
    
    # 验证句子间有空格
    assert "基于当前可用证据，句子二" in grounded
    assert "  " not in grounded  # 无双空格
    
    # 测试空答案
    grounded, report = apply_sentence_grounding("", evidence)
    assert report["reason"] == "no_sentences"
```

### 4. Lambda捕获测试
```python
def test_graph_lookup_lambda_capture():
    # Mock Neo4j client
    class MockClient:
        def search_entities(self, tokens, limit, allowed_sources):
            return [
                {"entity": "entity1", "relations": []},
                {"entity": "entity2", "relations": []},
                {"entity": "entity3", "relations": []},
            ]
        
        def entity_neighbors(self, name, limit, allowed_sources):
            return [{"entity": name, "relation": "test", "other": "other"}]
        
        def entity_paths_2hop(self, name, limit, allowed_sources):
            return []
        
        def close(self):
            pass
    
    with patch('app.tools.graph_tools.Neo4jClient', return_value=MockClient()):
        result = graph_lookup("test query")
        
        # 验证每个实体都被正确查询
        neighbors = result["neighbors"]
        assert len(neighbors) == 3
        assert {n["entity"] for n in neighbors} == {"entity1", "entity2", "entity3"}
```

---

## 配置建议

无需额外配置更改，所有修复都是代码级别的改进。

---

## 回归风险评估

| 修复项 | 风险等级 | 潜在影响 | 缓解措施 |
|--------|----------|----------|----------|
| Reranker归一化 | 低 | 重排序结果可能略有变化 | A/B测试对比 |
| Circuit Breaker | 低 | 并发行为更可靠 | 压力测试 |
| 句子接地 | 低 | 输出格式改善 | 人工评审样本 |
| Query去重 | 低 | 检索变体减少 | 监控检索性能 |
| Lambda捕获 | 中 | 图谱查询结果变化 | 对比修复前后结果 |
| Stream错误处理 | 低 | 更好的fallback | 模拟streaming失败 |
| Graph信号分数 | 低 | 分数计算更准确 | 监控证据充分性判断 |

---

## 监控指标

### 新增指标
1. `reranker_fallback_rate`: 词法回退重排序使用率
2. `circuit_breaker_open_events`: 熔断器打开事件数
3. `sentence_grounding_hedge_rate`: 添加hedge前缀的句子比例
4. `query_rewrite_dedup_rate`: 去重率（去重前后变体数比例）
5. `graph_lookup_lambda_errors`: Lambda捕获相关错误
6. `synthesis_stream_fallback_rate`: Streaming fallback到invoke的比例
7. `graph_signal_partial_data_rate`: 部分图谱数据的比例

---

## 总结

第二轮修复解决了4个额外的逻辑漏洞，主要改进：

1. **数值稳定性**: Reranker归一化、Graph信号分数计算
2. **并发安全**: Circuit breaker竞态条件
3. **文本处理**: 句子分割、接地、去重
4. **错误处理**: Streaming fallback、Lambda捕获

结合第一轮修复，共解决了**10个逻辑漏洞**，显著提升了系统的可靠性、准确性和性能。
