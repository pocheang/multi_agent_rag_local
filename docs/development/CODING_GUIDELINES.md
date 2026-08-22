# Coding Guidelines

## Python Conventions

### Unused Parameters

**问题**: 代码中大量使用 `del param1, param2` 来表示参数未使用

```python
# ❌ 当前做法
async def retrieve(request, route, plan):
    del route, plan
    # ...
```

**推荐做法**:

```python
# ✅ 选项1: 使用 _ 前缀（参数仍然可访问，适合调试）
async def retrieve(request, _route, _plan):
    # ...

# ✅ 选项2: 使用 *args（参数完全忽略）
async def retrieve(request, *_):
    # ...

# ✅ 选项3: 如果是协议要求的签名，保持原样但添加注释
async def retrieve(request, route, plan):
    # route, plan required by protocol but unused in this implementation
    # ...
```

**理由**:
- `del` 用于释放内存，不是表达"不用"的惯用法
- `_` 前缀是Python社区公认的"未使用"标记
- 代码审查时更清晰

**迁移计划**:
- Phase 1: 新代码使用 `_` 前缀
- Phase 2: 逐步替换现有 `del` 语句
- Phase 3: 添加 ruff 规则检测 `del` 滥用

## Type Annotations

### ❌ 避免
- 核心数据结构使用 `Any`（除非确实是任意类型）
- `object` 作为返回值类型（太宽泛）
- 循环导入导致的字符串类型提示（应该重构模块结构）

### ✅ 推荐
- 使用 `Protocol` 定义接口
- 使用 `TypeVar` 表达泛型
- 使用 `Literal` 限定字符串选项

## Error Handling

### 一致的降级策略

**问题**: 不同服务的错误处理不一致
- RAG失败 → 静默降级
- Router失败 → 抛出异常
- Synthesizer失败 → 返回fallback

**推荐**:
```python
from enum import Enum

class ErrorStrategy(Enum):
    FAIL_FAST = "fail_fast"      # 立即失败，抛异常
    DEGRADE = "degrade"          # 降级继续，记录日志
    FALLBACK = "fallback"        # 使用备用逻辑

# 在服务初始化时明确策略
class SomeService:
    def __init__(self, error_strategy: ErrorStrategy = ErrorStrategy.FAIL_FAST):
        self._error_strategy = error_strategy
```

## Configuration

### ❌ 避免添加新常量，除非:
1. 用户可见的行为（如 max_results）
2. 外部系统限制（如 API rate limit）
3. 安全相关阈值（如 token limit）

### ✅ 考虑算法化
- 动态调整 top_k 基于查询复杂度
- 自适应超时基于历史P95
- 学习式权重替代手工配置

## Documentation

### 注释原则
- **不要**: 重复代码的逻辑（`# increment i by 1`）
- **不要**: 记录"谁改的""为什么改"（用git commit message）
- **要**: 解释非显而易见的约束（`# Must be called before init_db`）
- **要**: 记录外部系统的行为（`# ChromaDB returns normalized scores`）

## Testing

### Mock外部依赖
```python
# ✅ Mock LLM调用
@pytest.fixture
def mock_llm():
    with patch("app.services.llm.call_openai") as mock:
        mock.return_value = {"answer": "test"}
        yield mock

# ❌ 不要mock内部逻辑
# 如果需要mock内部函数，说明模块耦合太紧
```

---

**Last Updated**: 2026-08-19  
**Review Cycle**: 每季度更新一次
