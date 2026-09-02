# 批判性代码分析 - RAG Service retrieve() 方法

## 🔴 发现的问题

### 问题 1: `total_retrievers` 计算错误 ⚠️

**代码**:
```python
retrievers = self._enabled_retrievers(route)  # 例如: [("vector", fn), ("bm25", fn), ("graph", fn)]
requests = _retrieval_requests(request, plan, len(retrievers))
jobs = [
    (name, retriever, planned_request)
    for planned_request, max_retrievals in requests
    for name, retriever in retrievers[:max_retrievals]
]

total_retrievers = len(retrievers)  # ⚠️ 这是错误的！
```

**问题分析**:

1. `retrievers` 是**可用的检索器列表**（例如 3 个：vector, bm25, graph）
2. `jobs` 是**实际执行的检索任务列表**（可能少于 retrievers）
3. `total_retrievers = len(retrievers)` 计数的是**可用检索器**，不是**实际运行的检索器**

**示例场景**:
```python
# 假设有 3 个可用检索器
retrievers = [("vector", fn), ("bm25", fn), ("graph", fn)]

# 但 plan 限制只运行 1 个
max_retrievals = 1
jobs = [("vector", fn, req)]  # 只有 1 个任务

# 错误的计算
total_retrievers = 3  # ⚠️ 应该是 1！

# 如果 vector 失败
failed_retrievers = ["vector"]
successful_retrievers = 0

# 错误消息会说：
"All 3 retrieval attempts failed"  # ⚠️ 但实际只尝试了 1 个！
```

**正确的计算**:
```python
total_retrievers = len(jobs)  # 实际运行的检索器数量
```

---

### 问题 2: 错误消息可能重复计数 ⚠️

**代码**:
```python
failed_retrievers: list[str] = []

for (name, _, _), result in zip(jobs, results, strict=True):
    if isinstance(result, BaseException):
        failed_retrievers.append(name)  # ⚠️ 可能重复！
```

**问题分析**:

如果同一个检索器被调用多次（多个任务），`failed_retrievers` 会包含重复的名称：
```python
jobs = [("vector", fn, req1), ("vector", fn, req2)]
# 如果两次都失败
failed_retrievers = ["vector", "vector"]  # 重复！

# 错误消息
f"Failed retrievers: {', '.join(set(failed_retrievers))}"
# 输出: "Failed retrievers: vector"  # ✅ set() 去重了
```

**评估**: 使用 `set()` 是正确的，但 `list` 本身可能重复是不必要的

---

### 问题 3: `successful_retrievers` 语义不清 ⚠️

**代码**:
```python
successful_retrievers = len(bundles)
```

**问题**: 这计算的是**成功的任务数**，不是**成功的检索器数**

**示例**:
```python
jobs = [
    ("vector", fn, req1),  # 成功
    ("vector", fn, req2),  # 成功
    ("bm25", fn, req1),  # 失败
]
# 结果
bundles = [bundle1, bundle2]
successful_retrievers = 2  # ⚠️ 语义上应该是 "1 个检索器（vector）"
```

---

### 问题 4: 降级消息不准确 ⚠️

**代码**:
```python
if evidence_count == 0:
    await self._report_degradation(
        ExecutionEvent(
            message=(
                f"DEGRADED: {successful_retrievers}/{total_retrievers} retrievers succeeded "
                f"but found no matching documents."
            )
        )
    )
```

**问题**: 如果 `total_retrievers` 和 `successful_retrievers` 都计算错误，这个消息就不准确

---

## ✅ 建议的修复

### 修复 1: 正确计算计数器

```python
# 在 jobs 创建后
total_attempts = len(jobs)  # 实际运行的检索任务数

# 在处理结果后
successful_attempts = len(bundles)
unique_failed_retrievers = set(failed_retrievers)
unique_successful_retrievers = set(
    name for (name, _, _), result in zip(jobs, results, strict=True) if not isinstance(result, BaseException)
)
```

### 修复 2: 改进错误消息

```python
if successful_attempts == 0:
    raise RuntimeError(
        f"All {total_attempts} retrieval attempts failed across {len(unique_failed_retrievers)} retrievers. "
        f"Failed retrievers: {', '.join(unique_failed_retrievers)}. "
        f"Cannot proceed without evidence."
    )
```

### 修复 3: 改进降级消息

```python
if evidence_count == 0:
    await self._report_degradation(
        ExecutionEvent(
            stage="rag",
            status="completed",
            message=(
                f"DEGRADED: {successful_attempts} retrieval attempts succeeded "
                f"({len(unique_successful_retrievers)} unique retrievers) "
                f"but found no matching documents. Will proceed with fallback synthesis."
            ),
        )
    )
```

---

## 🎯 严重性评估

### 问题 1: `total_retrievers` 错误 - 🟠 **中等**
- **影响**: 错误消息不准确，但不影响功能
- **场景**: 当 plan 限制检索器数量时
- **用户体验**: 可能误导调试

### 问题 2: `failed_retrievers` 重复 - 🟡 **低**
- **影响**: 内部列表有重复，但 `set()` 会去重
- **用户体验**: 无影响（已有 set 去重）

### 问题 3: `successful_retrievers` 语义 - 🟡 **低**
- **影响**: 变量名不准确，但逻辑正确
- **用户体验**: 可能导致代码阅读困惑

### 问题 4: 降级消息不准确 - 🟠 **中等**
- **影响**: 基于错误计数的消息
- **用户体验**: 可能误导用户

---

## 📊 验证当前行为

让我检查是否有测试覆盖这些场景：
