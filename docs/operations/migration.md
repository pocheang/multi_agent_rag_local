# Agent迁移指南

从旧架构迁移到统一的Agent基础设施的完整指南。

---

## 📋 迁移概述

本指南帮助您将现有agents迁移到新的统一架构，包括：
- 使用BaseAgent基类
- 采用UnifiedConfig配置
- 使用ResultSchemas标准格式
- 利用SharedUtils工具函数

---

## 🎯 迁移优先级

### 阶段1: 新开发（立即采用）

所有新开发的agents应立即使用新架构：
```python
from app.agents.base_agent import BaseAgent
from app.agents.unified_config import get_agent_config

class NewAgent(BaseAgent):
    def execute(self, query: str, **kwargs):
        config = get_agent_config()
        # 实现逻辑
        return {"result": "..."}
```

### 阶段2: 核心Agents（1-2周）

优先迁移核心agents：
1. ✅ Vector RAG Agent - 已创建统一版本
2. ⏳ Graph RAG Agent
3. ⏳ Router Agent
4. ⏳ Synthesis Agent

### 阶段3: 辅助Agents（2-4周）

迁移辅助agents：
- Quality agents
- Validation agents
- Tracking agents

---

## 📖 迁移步骤

### 步骤1: 理解新架构

阅读文档了解新架构：
```bash
cat docs/AGENT_ARCHITECTURE.md
cat docs/AGENT_OPTIMIZATION_SUMMARY.md
```

### 步骤2: 创建新版本Agent

**旧代码**:
```python
# app/agents/my_agent.py
import logging

logger = logging.getLogger(__name__)

def run_my_agent(query: str, **kwargs) -> dict:
    """旧的函数式agent."""
    try:
        # 实现逻辑
        result = do_something(query)
        
        return {
            "result": result,
            "status": "ok"
        }
    except Exception as e:
        logger.error(f"Error: {e}")
        return {"error": str(e)}
```

**新代码**:
```python
# app/agents/my_agent_unified.py
from app.agents.base_agent import BaseAgent, AgentError
from app.agents.unified_config import get_agent_config
from app.agents.result_schemas import AgentResult
from app.agents.shared_utils import ContextFormatter

class UnifiedMyAgent(BaseAgent):
    """统一的MyAgent实现."""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.my_config = get_agent_config()
    
    def execute(self, query: str, **kwargs) -> dict:
        """
        执行agent逻辑.
        
        错误处理、计时、格式化由BaseAgent自动完成。
        """
        # 实现核心逻辑
        result = do_something(query)
        
        # 返回标准格式
        return {
            "result": result,
            "metadata": kwargs
        }

# 向后兼容的函数接口
def run_my_agent(query: str, **kwargs) -> dict:
    """向后兼容的函数接口."""
    agent = UnifiedMyAgent()
    result = agent.run(query=query, **kwargs)
    
    # 提取核心结果（移除BaseAgent包装字段）
    return {
        "result": result.get("result"),
        "status": result.get("status")
    }
```

### 步骤3: 更新配置使用

**旧代码**:
```python
from app.agents.agent_config import MAX_CONTEXT_CHUNKS
from app.agents.router_config import ENABLE_CALIBRATION

def my_function():
    max_chunks = MAX_CONTEXT_CHUNKS
    use_calibration = ENABLE_CALIBRATION
```

**新代码**:
```python
from app.agents.unified_config import get_agent_config

def my_function():
    config = get_agent_config()
    max_chunks = config.vector_rag.top_k
    use_calibration = config.router.use_calibration
```

### 步骤4: 使用共享工具

**旧代码**:
```python
# 每个agent中重复的格式化代码
def format_context(results):
    context_blocks = []
    for item in results:
        src = item.get("metadata", {}).get("source", "unknown")
        text = item.get("text", "")
        context_blocks.append(f"[SOURCE: {src}]\n{text}")
    return "\n\n".join(context_blocks)
```

**新代码**:
```python
from app.agents.shared_utils import ContextFormatter

# 使用共享工具
context = ContextFormatter.format_vector_context(results)
```

### 步骤5: 更新调用方

**旧调用**:
```python
from app.agents.my_agent import run_my_agent

result = run_my_agent(query="test")
```

**新调用**:
```python
# 方式1: 使用函数接口（向后兼容）
from app.agents.my_agent_unified import run_my_agent

result = run_my_agent(query="test")

# 方式2: 使用类接口（推荐）
from app.agents.my_agent_unified import UnifiedMyAgent

agent = UnifiedMyAgent()
result = agent.run(query="test")
```

### 步骤6: 添加测试

```python
# tests/unit/test_my_agent_unified.py
import pytest
from app.agents.my_agent_unified import UnifiedMyAgent

class TestUnifiedMyAgent:
    """测试统一的MyAgent."""
    
    def test_agent_initialization(self):
        """测试初始化."""
        agent = UnifiedMyAgent()
        assert agent is not None
    
    def test_agent_execute(self):
        """测试执行."""
        agent = UnifiedMyAgent()
        result = agent.run(query="test")
        
        assert result["status"] == "success"
        assert "result" in result
    
    def test_backward_compatible_function(self):
        """测试向后兼容函数."""
        from app.agents.my_agent_unified import run_my_agent
        
        result = run_my_agent(query="test")
        assert "result" in result
```

### 步骤7: 部署和验证

```bash
# 运行测试
pytest tests/unit/test_my_agent_unified.py -v

# 运行验证工具
python -m app.agents.agent_validator

# 检查健康状态
curl http://localhost:8000/api/v1/agents/health
```

---

## 🔄 具体迁移示例

### 示例1: 迁移Vector RAG Agent

**现状**: 
- `vector_rag_agent.py` - 基础版本
- `enhanced_vector_rag_agent.py` - 增强版本

**问题**: 功能重复，维护困难

**解决方案**: 已创建 `vector_rag_agent_unified.py`

**迁移步骤**:

1. **保留旧文件**（过渡期）
   ```bash
   # 不要删除旧文件，保持兼容性
   ls app/agents/vector_rag_agent*.py
   # vector_rag_agent.py
   # enhanced_vector_rag_agent.py
   # vector_rag_agent_unified.py (新)
   ```

2. **更新导入**（渐进式）
   ```python
   # 旧代码（继续工作）
   from app.agents.vector_rag_agent import run_vector_rag
   
   # 新代码（逐步迁移）
   from app.agents.vector_rag_agent_unified import run_vector_rag
   # 或
   from app.agents.vector_rag_agent_unified import UnifiedVectorRAGAgent
   ```

3. **测试兼容性**
   ```python
   # 测试向后兼容性
   def test_compatibility():
       from app.agents.vector_rag_agent_unified import run_vector_rag
       
       result = run_vector_rag(
           question="test",
           retrieval_strategy="hybrid"
       )
       
       assert "context" in result
       assert "citations" in result
   ```

4. **逐步替换**
   - 先在新功能中使用统一版本
   - 逐步更新现有代码
   - 最后弃用旧版本

### 示例2: 迁移Router Agent

**当前**:
```python
# app/agents/router_agent.py
def decide_route(question: str, use_reasoning: bool = False) -> dict:
    # 路由逻辑
    return {
        "route": "vector",
        "reason": "...",
        "confidence": 0.85
    }
```

**迁移到**:
```python
# app/agents/router_agent_unified.py
from app.agents.base_agent import BaseAgent
from app.agents.unified_config import get_router_config
from app.agents.result_schemas import RouterResult

class UnifiedRouterAgent(BaseAgent):
    """统一的Router Agent."""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.router_config = get_router_config()
    
    def execute(
        self,
        query: str,
        use_reasoning: bool = False,
        enable_decomposition: bool = False,
        **kwargs
    ) -> dict:
        """执行路由决策."""
        
        # 使用统一配置
        confidence_threshold = self.router_config.confidence_threshold
        
        # 实现路由逻辑
        route_decision = self._decide_route(query, use_reasoning)
        
        # 可选：查询分解
        if enable_decomposition and self._is_complex_query(query):
            decomposed = self._decompose_query(query)
            route_decision["decomposed_query"] = decomposed
        
        return route_decision
    
    def _decide_route(self, query: str, use_reasoning: bool) -> dict:
        """核心路由逻辑."""
        # 实现细节...
        return {
            "route": "vector",
            "reason": "Simple query",
            "skill": "answer_with_citations",
            "agent_class": "general",
            "confidence": 0.85
        }

# 向后兼容函数
def decide_route(
    question: str,
    use_reasoning: bool = False,
    agent_class_hint: str = None
) -> dict:
    """向后兼容的函数接口."""
    agent = UnifiedRouterAgent()
    result = agent.run(
        query=question,
        use_reasoning=use_reasoning,
        agent_class_hint=agent_class_hint
    )
    
    # 返回核心决策（保持兼容性）
    return {
        "route": result.get("route"),
        "reason": result.get("reason"),
        "skill": result.get("skill"),
        "agent_class": result.get("agent_class"),
        "confidence": result.get("confidence")
    }
```

---

## ⚠️ 常见陷阱和解决方案

### 陷阱1: 破坏向后兼容性

**问题**: 直接修改旧文件，破坏现有代码

**解决方案**: 
```python
# ❌ 错误：直接修改旧文件
# app/agents/vector_rag_agent.py
class NewVectorRAG(BaseAgent):  # 破坏性修改
    ...

# ✅ 正确：创建新文件，保留旧接口
# app/agents/vector_rag_agent_unified.py
class UnifiedVectorRAGAgent(BaseAgent):
    ...

def run_vector_rag(...):  # 向后兼容函数
    agent = UnifiedVectorRAGAgent()
    return agent.run(...)
```

### 陷阱2: 过度抽象

**问题**: 过度使用基类功能，代码变复杂

**解决方案**:
```python
# ❌ 错误：过度抽象
class MyAgent(BaseAgent):
    def execute(self, query: str, **kwargs):
        # 太多层次的抽象
        return self._super_abstract_method(query)

# ✅ 正确：简单直接
class MyAgent(BaseAgent):
    def execute(self, query: str, **kwargs):
        # 直接实现逻辑
        result = do_work(query)
        return {"result": result}
```

### 陷阱3: 忽略测试

**问题**: 迁移后没有测试，引入bug

**解决方案**:
```python
# ✅ 必须添加测试
def test_backward_compatibility():
    """确保向后兼容."""
    old_result = old_run_vector_rag("test")
    new_result = new_run_vector_rag("test")
    
    assert old_result.keys() == new_result.keys()
    assert old_result["context"] == new_result["context"]
```

---

## ✅ 迁移检查清单

### 代码迁移
- [ ] 创建新的unified agent文件
- [ ] 继承BaseAgent基类
- [ ] 使用unified_config配置
- [ ] 使用result_schemas格式
- [ ] 使用shared_utils工具
- [ ] 保留向后兼容函数
- [ ] 添加类型注解

### 测试
- [ ] 添加单元测试
- [ ] 测试向后兼容性
- [ ] 测试错误处理
- [ ] 测试配置读取
- [ ] 性能基准测试

### 文档
- [ ] 更新API文档
- [ ] 添加使用示例
- [ ] 记录迁移理由
- [ ] 更新CHANGELOG

### 部署
- [ ] 本地测试通过
- [ ] 集成测试通过
- [ ] 代码审查完成
- [ ] 灰度发布
- [ ] 监控告警配置

---

## 📊 迁移进度跟踪

### 核心Agents

| Agent | 状态 | 优先级 | 预计时间 |
|-------|------|--------|---------|
| Vector RAG | ✅ 完成 | P0 | - |
| Graph RAG | ⏳ 进行中 | P0 | 2天 |
| Router | ⏳ 计划中 | P0 | 2天 |
| Synthesis | ⏳ 计划中 | P1 | 3天 |
| ReAct | ⏳ 计划中 | P1 | 3天 |

### 辅助Agents

| Agent | 状态 | 优先级 | 预计时间 |
|-------|------|--------|---------|
| Quality Orchestrator | ⏳ 计划中 | P2 | 2天 |
| Route Validator | ⏳ 计划中 | P2 | 1天 |
| Answer Validator | ⏳ 计划中 | P2 | 1天 |

---

## 🎓 最佳实践

### 1. 渐进式迁移
```python
# 阶段1: 创建新版本，保留旧版本
# app/agents/my_agent_unified.py

# 阶段2: 新功能使用新版本
from app.agents.my_agent_unified import UnifiedMyAgent

# 阶段3: 逐步更新现有代码
# 旧: from app.agents.my_agent import run_my_agent
# 新: from app.agents.my_agent_unified import run_my_agent

# 阶段4: 弃用旧版本
# 添加deprecation警告
```

### 2. 完整的测试覆盖
```python
# 测试新功能
def test_new_features():
    pass

# 测试向后兼容
def test_backward_compatibility():
    pass

# 测试错误处理
def test_error_handling():
    pass
```

### 3. 清晰的文档
```python
class UnifiedMyAgent(BaseAgent):
    """
    统一的MyAgent实现.
    
    替代:
    - app/agents/my_agent.py
    - app/agents/my_agent_enhanced.py
    
    特性:
    - 统一错误处理
    - 标准化配置
    - 完整的测试覆盖
    
    示例:
        >>> agent = UnifiedMyAgent()
        >>> result = agent.run(query="test")
    """
```

---

## 💡 获取帮助

- 查看 [完整架构文档](../architecture/overview.md)
- 查看 [优化总结](../archive/legacy/docs-root/AGENT_OPTIMIZATION_SUMMARY.md)
- 运行 [使用示例](../../examples/agent_usage_examples.py)
- 查看 [测试文件](../../tests/unit/test_unified_agents.py)

---

**迁移成功后，您将获得**:
- ✅ 更清晰的代码结构
- ✅ 更少的重复代码
- ✅ 更容易的测试
- ✅ 更好的可维护性

祝迁移顺利！🚀
