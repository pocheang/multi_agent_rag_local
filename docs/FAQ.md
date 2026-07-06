# ❓ 常见问题解答 (FAQ)

## 📋 目录

1. [基础问题](#基础问题)
2. [配置问题](#配置问题)
3. [使用问题](#使用问题)
4. [性能问题](#性能问题)
5. [错误处理](#错误处理)
6. [迁移问题](#迁移问题)

---

## 基础问题

### Q1: 系统中有多少个Agent？

**A**: 从功能角度看，系统有**11个Agent**（README中列出的）：

```
路由决策层 (2个):  Router + Route Validator
检索执行层 (4个):  Vector RAG + Graph RAG + ReAct + Web Research  
质量保证层 (3个):  Retrieval Quality + Answer Validator + Context Tracker
编排合成层 (2个):  Quality Orchestrator + Synthesis Agent
```

所有11个Agent功能都完全保留并增强了。

---

### Q2: 优化后Agent数量会变吗？

**A**: **不会！** 11个Agent功能完全保留。

优化的是**实现层面**：
- 优化前：14-15个文件实现11个Agent（有重复）
- 优化后：11个文件实现11个Agent（无重复）

用户体验完全一致，只是代码更清晰。

---

### Q3: 新的统一基础设施包括什么？

**A**: 包括4个核心组件：

1. **BaseAgent** - 所有agents的统一基类
2. **UnifiedConfig** - 统一配置管理（替代4个分散配置）
3. **ResultSchemas** - 标准化返回格式
4. **SharedUtils** - 共享工具函数（消除重复）

---

### Q4: 旧代码还能用吗？

**A**: **能！** 完全向后兼容。

```python
# 旧代码（继续工作）
from app.agents.vector_rag_agent import run_vector_rag

result = run_vector_rag(question="test")

# 新代码（功能更强）
from app.agents.vector_rag_agent_unified import UnifiedVectorRAGAgent

agent = UnifiedVectorRAGAgent()
result = agent.run(query="test", enable_evaluation=True)
```

---

## 配置问题

### Q5: 如何修改Agent配置？

**A**: 使用统一配置管理：

```python
from app.agents.unified_config import get_agent_config, set_agent_config

# 获取配置
config = get_agent_config()

# 修改配置
config.vector_rag.top_k = 15
config.router.confidence_threshold = 0.7

# 应用配置
set_agent_config(config)
```

---

### Q6: 旧的配置文件还能用吗？

**A**: 可以继续用，但建议迁移到统一配置：

**旧方式**（仍然有效）:
```python
from app.agents.agent_config import MAX_CONTEXT_CHUNKS
```

**新方式**（推荐）:
```python
from app.agents.unified_config import get_agent_config

config = get_agent_config()
max_chunks = config.vector_rag.top_k
```

---

### Q7: 如何重置配置为默认值？

**A**:
```python
from app.agents.unified_config import reset_agent_config

# 重置所有配置为默认值
reset_agent_config()
```

---

## 使用问题

### Q8: 如何选择使用哪个Agent？

**A**: 根据查询类型选择：

| 查询类型 | 推荐Agent | 示例 |
|---------|----------|------|
| 简单事实 | Vector RAG | "什么是Docker？" |
| 实体关系 | Graph RAG | "Docker和K8s的关系？" |
| 对比分析 | Hybrid | "比较REST和gRPC" |
| 复杂推理 | ReAct | "分析X，然后推荐Y" |
| 最新信息 | Vector + Web | "2024年AI趋势" |

参考 [AGENT_QUICK_REFERENCE.md](./AGENT_QUICK_REFERENCE.md#agent选择决策树)

---

### Q9: 如何启用Self-RAG评估？

**A**:
```python
from app.agents.vector_rag_agent_unified import UnifiedVectorRAGAgent

agent = UnifiedVectorRAGAgent()

# 启用评估
result = agent.run(
    query="你的查询",
    enable_evaluation=True  # 启用Self-RAG
)
```

---

### Q10: 如何创建自定义Agent？

**A**: 继承BaseAgent：

```python
from app.agents.base_agent import BaseAgent

class MyCustomAgent(BaseAgent):
    def execute(self, query: str, **kwargs):
        # 实现你的逻辑
        result = self._process(query)
        return {"result": result}
    
    def _process(self, query):
        # 自定义处理逻辑
        return f"Processed: {query}"

# 使用
agent = MyCustomAgent()
result = agent.run(query="test")
# 自动包含：错误处理、计时、格式化
```

---

## 性能问题

### Q11: 哪种检索策略最快？

**A**: 性能对比：

| 策略 | 速度 | 精度 | 适用场景 |
|------|------|------|---------|
| dense | ⚡⚡⚡ 最快 | ⭐⭐ 中等 | 快速检索 |
| hybrid | ⚡⚡ 较快 | ⭐⭐⭐ 好 | 通用（推荐） |
| bm25 | ⚡⚡⚡ 很快 | ⭐⭐ 中等 | 关键词匹配 |
| rerank | ⚡ 较慢 | ⭐⭐⭐⭐ 最好 | 高质量要求 |

---

### Q12: 如何提高检索速度？

**A**: 多种优化方法：

```python
# 方法1: 减少检索数量
config.vector_rag.top_k = 5  # 默认10

# 方法2: 使用更快的策略
result = run_vector_rag(
    question="...",
    retrieval_strategy="dense"  # 最快
)

# 方法3: 启用缓存（默认已启用）
# 相同查询会返回缓存结果

# 方法4: 过滤文档源
result = run_vector_rag(
    question="...",
    allowed_sources=["specific_doc.pdf"]  # 只搜索特定文档
)
```

---

### Q13: 缓存如何工作？

**A**: 自动缓存，基于查询和参数：

```python
# 第一次查询（慢，实际检索）
result1 = run_vector_rag(question="Docker是什么？")

# 第二次相同查询（快，返回缓存）
result2 = run_vector_rag(question="Docker是什么？")

# 不同参数会触发新检索
result3 = run_vector_rag(
    question="Docker是什么？",
    retrieval_strategy="rerank"  # 不同参数
)
```

---

## 错误处理

### Q14: "Low confidence detected" 怎么办？

**A**: 路由置信度低，有3个解决方案：

```python
# 方案1: 启用推理模型
decision = decide_route(
    question="你的查询",
    use_reasoning=True  # 使用更强的模型
)

# 方案2: 提供agent类别提示
decision = decide_route(
    question="你的查询",
    agent_class_hint="cybersecurity"  # 提供提示
)

# 方案3: 简化查询
# 将复杂查询拆分为多个简单查询
```

---

### Q15: "Retrieved count: 0" 怎么办？

**A**: 检索结果为空，检查以下几点：

```python
# 1. 移除文档源过滤
result = run_vector_rag(
    question="你的查询",
    allowed_sources=None  # 不过滤
)

# 2. 检查查询是否过于具体
# 使用更通用的查询词

# 3. 启用查询扩展
config.vector_rag.enable_query_expansion = True

# 4. 降低相似度阈值
config.vector_rag.score_threshold = 0.3  # 降低阈值
```

---

### Q16: Graph RAG "ServiceUnavailable" 怎么办？

**A**: Neo4j连接问题：

```bash
# 1. 检查Neo4j状态
docker ps | grep neo4j

# 2. 如果未运行，启动Neo4j
docker start neo4j

# 3. 如果不存在，创建容器
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  neo4j:latest

# 4. 系统会自动fallback到Vector RAG
# 查看日志确认fallback
```

---

### Q17: ReAct不收敛怎么办？

**A**: 达到最大迭代次数：

```python
# 方案1: 增加迭代次数
result = run_react_agent(
    question="你的查询",
    max_iterations=10  # 默认5
)

# 方案2: 启用推理模型
result = run_react_agent(
    question="你的查询",
    use_reasoning=True  # 更强的推理能力
)

# 方案3: 简化查询
# 将复杂任务拆分为多个简单步骤

# 方案4: 查看推理历史诊断问题
print(result['react_history'])
# 看哪一步出错
```

---

## 迁移问题

### Q18: 如何迁移现有代码？

**A**: 渐进式迁移，三种方式：

**方式1: 保持旧代码不变（最简单）**
```python
# 无需任何修改，继续使用
from app.agents.vector_rag_agent import run_vector_rag
```

**方式2: 更新导入（推荐）**
```python
# 从旧导入
# from app.agents.vector_rag_agent import run_vector_rag

# 改为新导入
from app.agents.vector_rag_agent_unified import run_vector_rag
# 接口完全相同，功能更强
```

**方式3: 使用新的类接口（最佳）**
```python
from app.agents.vector_rag_agent_unified import UnifiedVectorRAGAgent

agent = UnifiedVectorRAGAgent()
result = agent.run(query="test", enable_evaluation=True)
```

参考 [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)

---

### Q19: 迁移需要多长时间？

**A**: 取决于迁移方式：

| 方式 | 时间 | 风险 | 收益 |
|------|------|------|------|
| 方式1（不迁移） | 0天 | 无 | 无变化 |
| 方式2（更新导入） | 1-2天 | 低 | 获得新功能 |
| 方式3（全面迁移） | 1-2周 | 中 | 最大化收益 |

**建议**：
- 新功能使用方式3
- 现有代码逐步迁移方式2
- 稳定运行的代码可以保持方式1

---

### Q20: 如何验证迁移成功？

**A**: 运行验证工具：

```bash
# 1. 运行Agent验证器
python -m app.agents.agent_validator

# 2. 运行单元测试
pytest tests/unit/test_unified_agents.py -v

# 3. 运行集成测试
pytest tests/integration/ -v

# 4. 检查健康状态
curl http://localhost:8000/api/v1/agents/health

# 5. 对比结果
# 新旧版本应该返回相同结果
```

---

## 高级问题

### Q21: 如何调试Agent执行？

**A**: 多种调试方法：

```python
# 方法1: 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 方法2: 查看执行追踪
from app.services.agent_execution_tracker import AgentExecutionTracker

tracker = AgentExecutionTracker.get_instance()
trace = tracker.get_execution_trace(execution_id)
print(trace)

# 方法3: 查看retrieval diagnostics
result = run_vector_rag(question="test")
print(result['retrieval_diagnostics'])

# 方法4: 使用健康检查API
curl http://localhost:8000/api/v1/agents/trace/{execution_id}
```

---

### Q22: 如何监控Agent性能？

**A**: 使用执行追踪：

```python
from app.services.agent_execution_tracker import AgentExecutionTracker

tracker = AgentExecutionTracker.get_instance()

# 获取统计信息
stats = tracker.get_execution_stats()
print(f"总执行: {stats['total_executions']}")
print(f"平均耗时: {stats['avg_duration_ms']}ms")
print(f"失败率: {stats['failure_rate']}")

# 获取特定agent统计
agent_stats = tracker.get_agent_stats("VectorRAGAgent")
```

---

### Q23: 如何扩展系统？

**A**: 创建新Agent：

```python
from app.agents.base_agent import BaseAgent
from app.agents.unified_config import get_agent_config
from app.agents.result_schemas import AgentResult

class NewCustomAgent(BaseAgent):
    """新的自定义Agent"""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.config_obj = get_agent_config()
    
    def execute(self, query: str, **kwargs):
        # 实现新功能
        result = self._my_custom_logic(query)
        
        return {
            "result": result,
            "custom_field": "value"
        }
```

---

## 📚 更多资源

### 文档
- [完整架构](./AGENT_ARCHITECTURE.md)
- [快速参考](./AGENT_QUICK_REFERENCE.md)
- [快速启动](./QUICK_START.md)
- [迁移指南](./MIGRATION_GUIDE.md)

### 示例
- [使用示例](../examples/agent_usage_examples.py)
- [单元测试](../tests/unit/test_unified_agents.py)

### 工具
- [Agent验证器](../app/agents/agent_validator.py)
- [健康检查API](../app/api/routes/agent_health.py)

---

**还有问题？查看其他文档或运行示例代码！** 📖✨
