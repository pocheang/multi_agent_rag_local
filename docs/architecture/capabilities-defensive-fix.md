# capabilities.py 防御性编程修复

**文件**: `app/orchestration/capabilities.py`  
**日期**: 2026-08-19  
**问题**: 过度的防御性编程掩盖类型系统

---

## 修复前的问题

```python
@dataclass
class CoreCapabilities:
    # ❌ 问题1: 使用 Any 类型
    typed_router: Any = field(default_factory=RouterAgentService)
    typed_rag: Any = field(default_factory=RAGAgentService)
    # ...

    def orchestration_services(self) -> OrchestrationServices:
        # ❌ 问题2: 使用 getattr 防御
        reporter_binder = getattr(self.typed_rag, "set_degradation_reporter", None)
        return OrchestrationServices(
            # ...
            # ❌ 问题3: 再次检查 callable
            event_reporter_binder=reporter_binder if callable(reporter_binder) else None,
        )
```

### 为什么这是问题？

1. **类型系统失效**: `Any` 类型让IDE无法提供自动完成
2. **三重防御**: `getattr` + 默认值 + `callable()` 检查是过度的
3. **掩盖错误**: 如果方法不存在，应该立即失败而不是静默忽略
4. **自相矛盾**: 字段名叫 `typed_*` 但类型是 `Any`

---

## 修复后的代码

```python
@dataclass
class CoreCapabilities:
    """Injectable canonical capabilities used by production and focused tests."""

    # ✅ 使用具体类型
    typed_router: RouterAgentService = field(default_factory=RouterAgentService)
    typed_planner: PlannerAgentService = field(default_factory=PlannerAgentService)
    typed_rag: RAGAgentService = field(default_factory=RAGAgentService)
    typed_tools: ToolAgentService = field(default_factory=ToolAgentService)
    typed_synthesizer: SynthesizerAgentService = field(default_factory=SynthesizerAgentService)
    typed_finalizer: FinalizationService = field(default_factory=FinalizationService)
    context: Any = None  # Legacy context object, type varies by implementation

    def orchestration_services(self) -> OrchestrationServices:
        """Assemble orchestration services from typed capabilities.

        The event_reporter_binder allows the orchestration engine to push
        degradation events back to RAGAgentService during retrieval failures.
        """
        # ✅ 直接访问 - 类型系统保证方法存在
        return OrchestrationServices(
            router=self.typed_router.route,
            planner=self.typed_planner.plan,
            retriever=self.typed_rag.retrieve,
            tool_runner=self.typed_tools.run,
            synthesizer=self.typed_synthesizer.synthesize,
            finalizer=self.typed_finalizer.finalize,
            context=self.context,
            event_reporter_binder=self.typed_rag.set_degradation_reporter,
        )
```

---

## 为什么这是改进？

### 1. 类型安全恢复
```python
# 修复前: IDE 不知道有什么方法
capabilities.typed_rag.  # ❌ 无提示

# 修复后: IDE 能提供完整提示
capabilities.typed_rag.  # ✅ 显示 retrieve, set_degradation_reporter
```

### 2. 信任类型系统
```python
# 修复前: 不信任类型，运行时检查
reporter_binder = getattr(self.typed_rag, "set_degradation_reporter", None)
if callable(reporter_binder):
    # ...

# 修复后: 信任类型定义
event_reporter_binder=self.typed_rag.set_degradation_reporter
# 如果方法不存在，AttributeError 会立即暴露问题
```

### 3. 失败快速原则（Fail Fast）
```python
# 修复前: 方法不存在 → 返回 None → 静默忽略 → 难以调试
reporter_binder = getattr(self.typed_rag, "set_degradation_reporter", None)

# 修复后: 方法不存在 → AttributeError → 立即发现 → 容易修复
self.typed_rag.set_degradation_reporter
```

---

## 何时应该使用防御性编程？

### ✅ 合理的防御
```python
# 外部输入（用户数据、API响应）
user_input = request.get("query")
if not user_input or not isinstance(user_input, str):
    raise ValueError("Invalid query")

# 可选的外部依赖
if neo4j_client and neo4j_client.is_connected():
    result = neo4j_client.query(...)
```

### ❌ 过度的防御
```python
# 内部类型明确的对象
reporter = getattr(self.typed_rag, "set_degradation_reporter", None)
# ❌ 如果方法不存在，说明代码有bug，应该立即失败

# 自己创建的对象
if hasattr(service, "route") and callable(service.route):
    service.route()
# ❌ service 是你自己创建的，你应该知道它有什么方法
```

---

## 黄金法则

> **信任内部接口，验证外部输入**

- **内部代码**: 如果 `typed_rag: RAGAgentService`，就直接用 `typed_rag.set_degradation_reporter`
- **外部数据**: 如果 `user_query: str`，先验证 `if not user_query or len(user_query) > 1000`

---

## 影响

### 破坏性变更
- ❌ **无**: 如果 `RAGAgentService` 没有 `set_degradation_reporter`，之前会静默失败，现在会抛出 `AttributeError`
- ✅ **好事**: 这样的bug应该在开发阶段发现，而不是生产环境静默失败

### 性能
- 📊 **微小提升**: 少了 `getattr` 和 `callable()` 的开销（纳秒级）

### 开发体验
- ✅ **显著提升**: IDE自动完成恢复
- ✅ **调试更容易**: 错误立即暴露，不是隐藏在默认值里
- ✅ **代码更简洁**: 12行 → 9行，少了3个条件检查

---

## 验证

### IDE检查
```python
# 在IDE中输入：
capabilities = CoreCapabilities()
capabilities.typed_rag.  # 应该看到方法提示

# 自动完成应该显示：
# - retrieve()
# - set_degradation_reporter()
# - _enabled_retrievers()
```

### 类型检查
```bash
# 如果配置了mypy
mypy app/orchestration/capabilities.py
# 应该通过，无类型错误
```

### 运行时测试
```python
# 如果方法不存在，会立即失败
capabilities = CoreCapabilities()
services = capabilities.orchestration_services()
# ✅ 如果成功，说明所有方法都存在
# ❌ 如果失败，AttributeError会明确指出缺少什么
```

---

## 相关修复

这个文件的修复是一系列改进的一部分：

1. ✅ `CoreCapabilities` - 类型安全（本文件）
2. ✅ `RouterAgentService` - 减少getattr使用
3. ✅ `FinalizationService` - 简化getattr链
4. ✅ `RAGAgentService` - 统一错误处理

参见: [agent-fixes-report.md](./agent-fixes-report.md)

---

## 教训

### 开发者心理
```python
# 开发者想法: "万一方法不存在呢？我加个getattr保险"
reporter = getattr(obj, "method", None)

# 实际效果: 
# - 如果方法确实不存在，你静默失败了，问题在生产环境暴露
# - 如果方法存在，你的防御是无用的开销
# - 你失去了类型系统的帮助
```

### 正确的思维
```python
# 如果你不确定方法是否存在，说明：
# 1. 类型定义不清晰 → 修复类型定义
# 2. 接口设计有问题 → 重构接口
# 3. 你对代码不熟悉 → 读代码/加注释

# 不要用运行时检查掩盖设计问题
```

---

**最终状态**: ✅ 完全消除防御性编程  
**代码质量**: 从"不信任类型"到"信任类型系统"  
**开发体验**: 从"IDE无提示"到"完整自动完成"  
**错误处理**: 从"静默失败"到"快速失败"
