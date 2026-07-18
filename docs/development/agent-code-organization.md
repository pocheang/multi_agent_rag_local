# 📝 Agent代码组织最佳实践

## 🎯 核心原则

**单个Agent文件不应超过500行代码**

这样可以：
- ✅ 更容易理解和维护
- ✅ 减少合并冲突
- ✅ 提高代码可读性
- ✅ 便于单元测试

---

## 📏 代码大小指南

### 文件大小建议

| 文件类型 | 推荐行数 | 最大行数 | 说明 |
|---------|---------|---------|------|
| **Agent主文件** | 200-300行 | 500行 | 核心执行逻辑 |
| **辅助模块** | 100-200行 | 300行 | 工具函数 |
| **配置文件** | 50-100行 | 200行 | 配置定义 |
| **测试文件** | 200-400行 | 600行 | 测试用例 |

### 超过限制怎么办？

**拆分原则**：功能模块化

```
原文件（600行）：
├── my_agent.py

拆分后（3个文件）：
├── my_agent.py          (200行) - 核心Agent类
├── my_agent_tools.py    (200行) - 工具函数
└── my_agent_config.py   (100行) - 配置和常量
```

---

## 🏗️ 推荐的文件组织结构

### 方式1: 单文件Agent（简单场景）

**适用**: 功能简单，代码少于300行

```python
# app/agents/simple_agent.py (250行)

"""
Simple Agent - 简单agent实现
"""

from app.agents.base_agent import BaseAgent

class SimpleAgent(BaseAgent):
    """简单agent，所有逻辑在一个文件"""
    
    def execute(self, query: str, **kwargs):
        # 核心逻辑（200行以内）
        pass
```

---

### 方式2: 模块化Agent（推荐）

**适用**: 功能复杂，代码超过300行

```
app/agents/vector_rag/
├── __init__.py           (20行)  - 导出接口
├── agent.py              (200行) - Agent核心类
├── retrieval.py          (200行) - 检索逻辑
├── evaluation.py         (150行) - 评估逻辑
├── formatting.py         (100行) - 格式化工具
└── config.py             (80行)  - 配置常量
```

#### 文件职责划分

**agent.py** - 核心Agent类
```python
"""Vector RAG Agent核心类"""

from app.agents.base_agent import BaseAgent
from .retrieval import execute_retrieval
from .evaluation import evaluate_results
from .formatting import format_context

class VectorRAGAgent(BaseAgent):
    """统一的Vector RAG Agent"""
    
    def execute(self, query: str, **kwargs):
        # 1. 调用检索模块
        results = execute_retrieval(query, **kwargs)
        
        # 2. 评估结果（可选）
        if kwargs.get('enable_evaluation'):
            results = evaluate_results(results)
        
        # 3. 格式化返回
        return format_context(results)
```

**retrieval.py** - 检索逻辑
```python
"""检索相关功能"""

def execute_retrieval(query: str, **kwargs):
    """执行检索"""
    # 检索逻辑
    pass

def expand_query(query: str):
    """查询扩展"""
    pass

def apply_filters(results, filters):
    """应用过滤器"""
    pass
```

**evaluation.py** - 评估逻辑
```python
"""结果评估功能"""

def evaluate_results(results):
    """评估检索结果"""
    pass

def calculate_quality_score(result):
    """计算质量分数"""
    pass
```

**formatting.py** - 格式化工具
```python
"""格式化工具函数"""

def format_context(results):
    """格式化上下文"""
    pass

def build_citations(results):
    """构建引用"""
    pass
```

**config.py** - 配置常量
```python
"""Vector RAG配置"""

DEFAULT_TOP_K = 10
MIN_SCORE_THRESHOLD = 0.5
RETRIEVAL_STRATEGIES = ["hybrid", "dense", "bm25"]
```

**__init__.py** - 导出接口
```python
"""Vector RAG Agent模块"""

from .agent import VectorRAGAgent

# 向后兼容的函数接口
def run_vector_rag(question: str, **kwargs):
    agent = VectorRAGAgent()
    return agent.run(query=question, **kwargs)

__all__ = ['VectorRAGAgent', 'run_vector_rag']
```

---

### 方式3: 大型Agent系统（复杂场景）

**适用**: 非常复杂，多个子模块

```
app/agents/react/
├── __init__.py           (30行)
├── agent.py              (250行) - Agent核心
├── reasoning/
│   ├── __init__.py       (10行)
│   ├── thought.py        (150行) - 思考模块
│   ├── action.py         (150行) - 行动模块
│   └── observation.py    (150行) - 观察模块
├── tools/
│   ├── __init__.py       (10行)
│   ├── vector_tool.py    (100行)
│   ├── graph_tool.py     (100行)
│   └── web_tool.py       (100行)
└── config.py             (80行)
```

---

## 📐 代码拆分实例

### 案例：Vector RAG Agent（原600行 → 拆分后）

#### 拆分前（不推荐）
```python
# app/agents/vector_rag_agent.py (600行)

class VectorRAGAgent(BaseAgent):
    def execute(self, query, **kwargs):
        # 100行：查询处理
        # 150行：检索执行
        # 100行：结果评估
        # 150行：格式化
        # 100行：辅助函数
        pass
```

**问题**：
- ❌ 文件太大，难以维护
- ❌ 功能耦合，难以测试
- ❌ 修改风险高

#### 拆分后（推荐）✅

**1. agent.py** (200行) - 核心逻辑
```python
from .retrieval import VectorRetrieval
from .evaluation import ResultEvaluator
from .formatting import ContextFormatter

class VectorRAGAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.retrieval = VectorRetrieval()
        self.evaluator = ResultEvaluator()
        self.formatter = ContextFormatter()
    
    def execute(self, query, **kwargs):
        # 清晰的流程编排（50行）
        results = self.retrieval.search(query)
        
        if kwargs.get('enable_evaluation'):
            results = self.evaluator.evaluate(results)
        
        return self.formatter.format(results)
```

**2. retrieval.py** (200行) - 检索逻辑
```python
class VectorRetrieval:
    def search(self, query):
        """执行检索"""
        query = self._expand_query(query)
        params = self._tune_parameters(query)
        return self._execute_search(query, params)
    
    def _expand_query(self, query):
        """查询扩展（50行）"""
        pass
    
    def _tune_parameters(self, query):
        """参数调优（50行）"""
        pass
    
    def _execute_search(self, query, params):
        """执行搜索（50行）"""
        pass
```

**3. evaluation.py** (150行) - 评估逻辑
```python
class ResultEvaluator:
    def evaluate(self, results):
        """评估结果"""
        scores = self._calculate_scores(results)
        return self._filter_by_quality(results, scores)
    
    def _calculate_scores(self, results):
        """计算分数（70行）"""
        pass
    
    def _filter_by_quality(self, results, scores):
        """质量过滤（70行）"""
        pass
```

**4. formatting.py** (100行) - 格式化
```python
class ContextFormatter:
    def format(self, results):
        """格式化结果"""
        context = self._build_context(results)
        citations = self._build_citations(results)
        return {"context": context, "citations": citations}
    
    def _build_context(self, results):
        """构建上下文（50行）"""
        pass
    
    def _build_citations(self, results):
        """构建引用（40行）"""
        pass
```

**优势**：
- ✅ 每个文件职责单一
- ✅ 易于理解和测试
- ✅ 降低修改风险
- ✅ 便于团队协作

---

## 🧩 拆分决策树

```
代码行数 < 300行?
├─ 是 → 保持单文件
└─ 否 → 
    功能是否独立?
    ├─ 是 → 拆分为独立模块
    └─ 否 → 
        能否按流程拆分?
        ├─ 是 → 按执行流程拆分
        └─ 否 → 按功能职责拆分
```

---

## ✅ 拆分检查清单

### 何时需要拆分？

- [ ] 文件超过500行
- [ ] 有多个独立的功能模块
- [ ] 有大量辅助函数（10个以上）
- [ ] 测试文件变得很大
- [ ] 多人经常同时修改

### 如何拆分？

1. **识别功能模块**
   ```
   当前Agent做了什么？
   - 检索
   - 评估
   - 格式化
   - 配置管理
   ```

2. **创建模块结构**
   ```
   为每个功能创建独立文件
   ```

3. **重构代码**
   ```python
   # 从
   class Agent:
       def complex_function(self):
           # 200行代码
   
   # 改为
   class Agent:
       def complex_function(self):
           return self.module.process()
   ```

4. **更新导入**
   ```python
   # __init__.py
   from .agent import MyAgent
   __all__ = ['MyAgent']
   ```

5. **添加测试**
   ```python
   # 为每个模块添加独立测试
   ```

---

## 📊 当前系统检查

### 需要重构的文件

让我检查当前哪些文件超过建议大小：

| 文件 | 当前行数 | 建议 | 优先级 |
|------|---------|------|--------|
| vector_rag_agent_unified.py | 400行 | ✅ 可接受 | 低 |
| graph_rag_agent.py | ~300行 | ✅ 良好 | 低 |
| react_agent.py | ~500行 | ⚠️ 考虑拆分 | 中 |
| synthesis_agent.py | ~300行 | ✅ 良好 | 低 |
| router_agent.py | ~350行 | ✅ 良好 | 低 |

### 重构建议

#### ReAct Agent（优先级：中）

当前可能超过500行，建议拆分：

```
app/agents/react/
├── __init__.py
├── agent.py              (200行) - 核心Agent
├── thought_engine.py     (150行) - 思考逻辑
├── action_executor.py    (150行) - 行动执行
└── observation_parser.py (100行) - 观察解析
```

---

## 🎓 最佳实践总结

### DO ✅

- ✅ **保持文件小巧** - 单文件不超过500行
- ✅ **职责单一** - 一个文件做一件事
- ✅ **模块化** - 功能独立，便于复用
- ✅ **清晰命名** - 文件名反映功能
- ✅ **添加文档** - 每个模块都有docstring
- ✅ **独立测试** - 每个模块有独立测试

### DON'T ❌

- ❌ **巨型文件** - 不要单文件超过1000行
- ❌ **混合职责** - 不要在一个文件做多件事
- ❌ **过度拆分** - 不要拆分成几十个小文件
- ❌ **循环依赖** - 避免模块间循环导入
- ❌ **深层嵌套** - 避免超过3层的目录结构

---

## 📖 示例：重构ReAct Agent

### 当前结构（假设600行）

```python
# app/agents/react_agent.py (600行)

class ReActAgent(BaseAgent):
    def execute(self, query, **kwargs):
        # 思考逻辑 (150行)
        # 行动执行 (200行)
        # 观察解析 (150行)
        # 辅助函数 (100行)
        pass
```

### 重构后结构

```
app/agents/react/
├── __init__.py
├── agent.py
├── thought.py
├── action.py
└── observation.py
```

**agent.py** (200行)
```python
from .thought import ThoughtEngine
from .action import ActionExecutor
from .observation import ObservationParser

class ReActAgent(BaseAgent):
    def __init__(self):
        self.thought = ThoughtEngine()
        self.action = ActionExecutor()
        self.observation = ObservationParser()
    
    def execute(self, query, **kwargs):
        history = []
        for i in range(max_iterations):
            # 思考
            thought = self.thought.think(query, history)
            
            # 行动
            action_result = self.action.execute(thought)
            
            # 观察
            observation = self.observation.parse(action_result)
            
            history.append({
                "thought": thought,
                "action": action_result,
                "observation": observation
            })
            
            if self._should_stop(observation):
                break
        
        return self._synthesize_answer(history)
```

---

## 🚀 实施步骤

### 重构现有Agent

1. **评估当前代码**
   ```bash
   wc -l app/agents/*.py
   ```

2. **识别可拆分的功能**
   ```
   分析代码，找出独立模块
   ```

3. **创建模块结构**
   ```bash
   mkdir app/agents/my_agent
   touch app/agents/my_agent/{__init__,agent,module1,module2}.py
   ```

4. **逐步迁移代码**
   ```python
   # 一次迁移一个模块
   ```

5. **更新测试**
   ```python
   # 为新模块添加测试
   ```

6. **验证功能**
   ```bash
   pytest tests/unit/test_my_agent.py -v
   ```

---

## 📝 总结

### 核心原则

1. **单文件不超过500行**
2. **职责单一，功能独立**
3. **模块化，易于维护**
4. **清晰命名，便于理解**

### 立即行动

- ✅ 检查当前文件大小
- ✅ 识别需要拆分的文件
- ✅ 创建模块化结构
- ✅ 逐步重构代码

---

**保持代码整洁，从控制文件大小开始！** 🎯✨
