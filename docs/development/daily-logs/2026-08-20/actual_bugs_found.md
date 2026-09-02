# 基于项目实际能力和逻辑的修复计划

## 🎯 执行摘要

根据项目的实际代码检查，我发现了以下真实情况，并制定了针对性的修复计划。

---

## 🔍 实际情况调查

### 1. bm25_search 函数签名

**实际签名**:
```python
def bm25_search(
    query: str, 
    k: int = 6, 
    allowed_sources: list[str] | None = None, 
    use_chinese_tokenizer: bool = True
) -> list[dict]:
```

**当前调用**:
```python
await loop.run_in_executor(
    _RETRIEVER_THREAD_POOL,
    bm25_search,
    request.question,  # query (位置参数1)
    _get_allowed_sources(request),  # 传给 k？❌ 错误！
)
```

**问题**: 参数顺序错误！
- 第2个位置参数应该是 `k: int`
- 但我们传递的是 `allowed_sources: list[str] | None`

**严重性**: 🔴 **高** - 这是一个真正的Bug！

---

### 2. similarity_search 函数签名

**实际签名**:
```python
def similarity_search(
    query: str, 
    k: int | None = None, 
    allowed_sources: list[str] | None = None, 
    require_source_filter: bool = True
):
```

**当前调用**:
```python
await loop.run_in_executor(
    _RETRIEVER_THREAD_POOL,
    similarity_search,
    request.question,  # query (位置参数1)
    _get_allowed_sources(request),  # 传给 k？❌ 错误！
    False,  # 传给 allowed_sources？❌ 错误！
)
```

**问题**: 参数顺序错误！
- 第2个位置参数应该是 `k: int | None`
- 第3个位置参数应该是 `allowed_sources`
- 但我们的调用完全错了

**严重性**: 🔴 **高** - 这是一个真正的Bug！

---

### 3. require_source_filter=False 的语义

**根据代码**:
```python
if require_source_filter and allowed_sources is None:
    raise ValueError("allowed_sources is required for user data isolation...")
```

**语义**: 
- `require_source_filter=True`: 强制要求 `allowed_sources`（安全）
- `require_source_filter=False`: 允许 `allowed_sources=None`（系统操作）

**当前调用的意图**: 
- 我们传递了 `_get_allowed_sources(request)`（可能是 list 或 None）
- 使用 `require_source_filter=False` 意味着"如果用户没有sources，不要报错"

**评估**: ✅ 语义正确，但参数顺序错误导致完全不work

---

## 🔴 发现的严重Bug

### Bug 1: bm25_search 参数错误

**当前代码**:
```python
records = await loop.run_in_executor(
    _RETRIEVER_THREAD_POOL,
    bm25_search,
    request.question,
    _get_allowed_sources(request),
)
```

**实际发生**:
```python
bm25_search(
    query=request.question,  # ✅ 正确
    k=_get_allowed_sources(request),  # ❌ list传给了int参数！
    # allowed_sources 使用默认值 None
)
```

**结果**: 
- 如果 `_get_allowed_sources()` 返回 list，会导致类型错误
- 但可能被某处捕获了，导致没有立即失败

---

### Bug 2: similarity_search 参数错误

**当前代码**:
```python
matches = await loop.run_in_executor(
    _RETRIEVER_THREAD_POOL,
    similarity_search,
    request.question,
    _get_allowed_sources(request),
    False,
)
```

**实际发生**:
```python
similarity_search(
    query=request.question,  # ✅ 正确
    k=_get_allowed_sources(request),  # ❌ list传给了int参数！
    allowed_sources=False,  # ❌ bool传给了list参数！
    # require_source_filter 使用默认值 True
)
```

**结果**:
- `k` 收到一个 list，可能导致错误
- `allowed_sources` 收到 False，然后在 line 92 检查时会失败

---

### Bug 3: graph 和 web 检索器可能也有同样的问题

需要检查它们的签名。

---

## ✅ 修复计划

### 修复 1: 修正 bm25_search 调用

```python
async def _bm25_retrieve(...) -> EvidenceBundle:
    """BM25 keyword-based retrieval."""
    del route, plan
    from app.retrievers.bm25_retriever import bm25_search

    loop = asyncio.get_event_loop()
    records = await loop.run_in_executor(
        _RETRIEVER_THREAD_POOL,
        bm25_search,
        request.question,  # query
        6,  # k - 默认值
        _get_allowed_sources(request),  # allowed_sources
        # use_chinese_tokenizer 使用默认值 True
    )
    return bundle_from_bm25_records(records)
```

---

### 修复 2: 修正 similarity_search 调用

```python
async def _vector_retrieve(...) -> EvidenceBundle:
    """Vector similarity retrieval."""
    del route, plan
    from app.retrievers.vector_store import similarity_search

    loop = asyncio.get_event_loop()
    matches = await loop.run_in_executor(
        _RETRIEVER_THREAD_POOL,
        similarity_search,
        request.question,  # query
        None,  # k - 使用默认值
        _get_allowed_sources(request),  # allowed_sources
        False,  # require_source_filter - 不强制要求（用户可能没有sources）
    )
    return bundle_from_vector_matches(matches)
```

---

### 修复 3: 检查并修复 graph 和 web

需要检查这些函数的签名。

---

## 🎓 为什么之前没有发现这个Bug？

### 可能的原因

1. **Python的动态类型**: 
   - 不会在定义时检查类型
   - 只在运行时失败

2. **异常被捕获**:
   - `return_exceptions=True` 捕获了所有异常
   - 测试可能使用了mock，没有真正调用

3. **测试覆盖不足**:
   - 测试可能没有真正执行检索逻辑
   - 或者测试的mock跳过了这个问题

---

## 🧪 验证策略

### 1. 检查当前是否真的有Bug

创建一个测试，真正调用检索器：

```python
@pytest.mark.asyncio
async def test_real_bm25_search():
    """Test real BM25 search to verify parameter order."""
    from app.agents.rag.service import RAGAgentService
    from app.domain.contracts import RouteDecision
    from app.orchestration.request import OrchestrationRequest
    
    route = RouteDecision(
        intent="knowledge_retrieval",
        confidence=0.9,
        requires_plan=False,
        allowed_capabilities=frozenset({"rag"}),
        reason="test"
    )
    
    service = RAGAgentService()
    
    # 这应该真正调用 bm25_search
    # 如果参数顺序错误，会失败
    result = await service.retrieve(
        OrchestrationRequest(question="test query"),
        route,
        None
    )
    
    # 如果没有抛出异常，说明要么：
    # 1. 参数顺序是对的（我们错了）
    # 2. 有其他机制处理了错误
```

---

## 🎯 优先级

### 🔴 高优先级 - 立即修复

1. ✅ 验证Bug是否真实存在
2. ✅ 修正 bm25_search 调用
3. ✅ 修正 similarity_search 调用
4. ✅ 检查 graph 和 web 检索器
5. ✅ 添加真实的集成测试

---

## 📝 总结

经过实际代码检查，我发现：

1. **之前认为的"低优先级问题"实际上是严重Bug**
2. **参数传递完全错误**
3. **需要立即修复**

这是一个很好的例子，说明为什么需要：
- ✅ 真正理解代码而不是假设
- ✅ 检查实际的函数签名
- ✅ 运行真实的集成测试
- ✅ 不要过早地认为问题"不重要"

---

**下一步**: 验证Bug并立即修复。
