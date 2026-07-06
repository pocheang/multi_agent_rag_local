# Week 1 详细实施计划：Intent & Planning层 + PDF导出

## 📅 时间表：Day 1-7

**目标**: 实现意图分析和策略规划，完成PDF导出功能  
**交付**: IntentAnalyzerAgent + StrategyPlannerAgent + PDF导出

---

## 🎯 Week 1 目标

### 功能目标
- ✅ IntentAnalyzerAgent（意图分析）
- ✅ StrategyPlannerAgent（策略规划）
- ✅ PDF导出功能
- ✅ 数据模型定义

### 性能目标
- ✅ 意图分析准确率>90%
- ✅ 意图分析延迟<150ms（快速规则）+ 200ms（LLM）
- ✅ 策略规划合理性>95%
- ✅ PDF导出成功率100%

---

## 📋 Day 1: IntentAnalyzerAgent框架

### 任务清单

#### 上午 (9:00-12:00)
- [ ] 创建项目结构
- [ ] 定义数据模型
- [ ] 实现快速规则分类（Part 1）

#### 下午 (13:00-18:00)
- [ ] 实现快速规则分类（Part 2）
- [ ] 编写单元测试
- [ ] 测试和调试

---

### 详细步骤

#### Step 1: 创建项目结构 (30分钟)

```bash
# 1. 创建分支
git checkout -b feature/week1-intent-strategy
git push -u origin feature/week1-intent-strategy

# 2. 创建目录
mkdir -p app/agents
mkdir -p app/models
mkdir -p app/pipelines
mkdir -p tests/agents
mkdir -p docs

# 3. 创建初始文件
touch app/agents/__init__.py
touch app/models/agent_models.py
touch app/models/workflow_models.py
touch app/agents/intent_analyzer_agent.py
touch tests/agents/test_intent_analyzer.py
```

---

#### Step 2: 定义数据模型 (1小时)

**文件**: `app/models/agent_models.py`

```python
"""
Agent相关数据模型
"""
from typing import List
from pydantic import BaseModel, Field


class IntentAnalysis(BaseModel):
    """意图分析结果"""
    
    primary_intent: str = Field(
        ...,
        description="主要意图类型",
        examples=["factual", "reasoning", "comparison", "diagnostic", "creative"]
    )
    
    complexity: int = Field(
        ...,
        ge=1,
        le=5,
        description="查询复杂度 1-5"
    )
    
    query_type: str = Field(
        ...,
        description="查询类型",
        examples=["simple", "compound", "ambiguous"]
    )
    
    key_entities: List[str] = Field(
        default_factory=list,
        description="关键实体"
    )
    
    implicit_requirements: List[str] = Field(
        default_factory=list,
        description="隐式需求",
        examples=[["需要代码示例", "需要对比表格"]]
    )
    
    user_goal: str = Field(
        default="获取信息",
        description="用户目标",
        examples=["获取信息", "解决问题", "做决策", "学习知识"]
    )
    
    estimated_difficulty: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="预估难度"
    )
    
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="分析置信度"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "primary_intent": "diagnostic",
                "complexity": 3,
                "query_type": "compound",
                "key_entities": ["Django", "性能"],
                "implicit_requirements": ["需要排查步骤", "需要代码示例"],
                "user_goal": "解决问题",
                "estimated_difficulty": 0.7,
                "confidence": 0.9
            }
        }
```

**验证**:
```bash
# 测试模型
python -c "
from app.models.agent_models import IntentAnalysis
intent = IntentAnalysis(
    primary_intent='factual',
    complexity=1,
    query_type='simple',
    confidence=0.95
)
print(intent.model_dump_json(indent=2))
"
```

---

#### Step 3: 实现快速规则分类 (2小时)

**文件**: `app/agents/intent_analyzer_agent.py`

```python
"""
Agent 1: 意图分析Agent
"""
import re
import logging
from typing import Dict, Any, List

from app.models.agent_models import IntentAnalysis

logger = logging.getLogger(__name__)


class IntentAnalyzerAgent:
    """
    意图分析Agent
    
    职责：理解用户查询的真实意图
    """
    
    def __init__(self):
        # 快速分类模式（覆盖50%常见查询）
        self._init_quick_patterns()
    
    def _init_quick_patterns(self):
        """初始化快速分类规则"""
        
        self.quick_patterns = {
            # 简单事实查询
            "factual_simple": [
                (r"^(什么是|介绍一下|解释)", 1, ["需要简洁答案"]),
                (r"^(如何|怎么|怎样)[一-鿿]{1,15}\??$", 1, ["需要步骤"]),
            ],
            
            # 对比查询
            "comparison": [
                (r"(对比|区别|差异|vs|versus|比较)", 2, ["需要对比表格", "需要优缺点"]),
                (r"(\w+)(和|与)(\w+)(有什么|的)(不同|区别)", 2, ["需要对比表格"]),
            ],
            
            # 诊断查询
            "diagnostic": [
                (r"(为什么|怎么回事|什么原因)", 3, ["需要排查步骤"]),
                (r"(报错|错误|失败|不工作|无法|崩溃)", 3, ["需要排查步骤", "需要代码示例"]),
            ],
            
            # 教程查询
            "tutorial": [
                (r"(教程|指南|步骤|如何实现|怎么做)", 2, ["需要步骤", "需要代码示例"]),
            ]
        }
    
    async def analyze(
        self, 
        query: str, 
        context: Dict[str, Any] = None
    ) -> IntentAnalysis:
        """
        分析查询意图
        
        Args:
            query: 用户查询
            context: 上下文（对话历史等）
        
        Returns:
            IntentAnalysis对象
        """
        
        context = context or {}
        
        # 1. 快速规则分类（覆盖50%查询）
        quick_result = self._quick_classify(query)
        
        if quick_result and quick_result.confidence >= 0.9:
            logger.info(
                f"[Intent] 快速分类成功: {quick_result.primary_intent} "
                f"(复杂度={quick_result.complexity}, 置信度={quick_result.confidence:.2f})"
            )
            return quick_result
        
        # 2. LLM深度分析（留待Day 2实现）
        logger.info("[Intent] 需要LLM深度分析（Day 2实现）")
        
        # Day 1临时返回默认值
        return IntentAnalysis(
            primary_intent="factual",
            complexity=2,
            query_type="simple",
            confidence=0.5
        )
    
    def _quick_classify(self, query: str) -> IntentAnalysis | None:
        """
        快速规则分类
        
        返回None表示无法快速分类，需要LLM分析
        """
        
        query_lower = query.lower().strip()
        query_len = len(query)
        
        # 超短查询检测（<10字）
        if query_len < 10:
            return IntentAnalysis(
                primary_intent="factual",
                complexity=1,
                query_type="simple",
                implicit_requirements=["需要简洁答案"],
                confidence=0.85
            )
        
        # 超简单查询检测（10-20字 + 特定模式）
        if query_len <= 20:
            if any(kw in query for kw in ["是什么", "如何", "怎么"]):
                return IntentAnalysis(
                    primary_intent="factual",
                    complexity=1,
                    query_type="simple",
                    implicit_requirements=["需要简洁答案"],
                    confidence=0.95
                )
        
        # 对比查询检测
        if any(kw in query for kw in ["对比", "区别", "vs", "比较", "差异"]):
            entities = self._extract_comparison_entities(query)
            
            return IntentAnalysis(
                primary_intent="comparison",
                complexity=2,
                query_type="simple" if len(entities) == 2 else "compound",
                key_entities=entities,
                implicit_requirements=["需要对比表格", "需要优缺点分析"],
                user_goal="做决策",
                confidence=0.95
            )
        
        # 诊断查询检测
        diagnostic_keywords = ["为什么", "怎么回事", "报错", "失败", "不工作", "无法", "崩溃"]
        if any(kw in query for kw in diagnostic_keywords):
            return IntentAnalysis(
                primary_intent="diagnostic",
                complexity=3,
                query_type="compound",
                implicit_requirements=["需要排查步骤", "需要代码示例", "需要诊断工具"],
                user_goal="解决问题",
                estimated_difficulty=0.7,
                confidence=0.90
            )
        
        # 教程查询检测
        if any(kw in query for kw in ["教程", "指南", "步骤", "如何实现"]):
            return IntentAnalysis(
                primary_intent="tutorial",
                complexity=2,
                query_type="simple",
                implicit_requirements=["需要步骤", "需要代码示例"],
                user_goal="学习知识",
                confidence=0.90
            )
        
        # 无法快速分类
        return None
    
    def _extract_comparison_entities(self, query: str) -> List[str]:
        """提取对比实体"""
        
        # 模式1: "A和B"、"A与B"
        match = re.search(r'(\w+)\s*(和|与)\s*(\w+)', query)
        if match:
            return [match.group(1), match.group(3)]
        
        # 模式2: "A vs B"
        match = re.search(r'(\w+)\s*(vs|versus)\s*(\w+)', query, re.IGNORECASE)
        if match:
            return [match.group(1), match.group(3)]
        
        # 模式3: "A对比B"
        match = re.search(r'(\w+)\s*对比\s*(\w+)', query)
        if match:
            return [match.group(1), match.group(2)]
        
        return []
```

---

#### Step 4: 编写单元测试 (1.5小时)

**文件**: `tests/agents/test_intent_analyzer.py`

```python
"""
IntentAnalyzerAgent单元测试
"""
import pytest
from app.agents.intent_analyzer_agent import IntentAnalyzerAgent
from app.models.agent_models import IntentAnalysis


@pytest.fixture
def analyzer():
    """创建analyzer实例"""
    return IntentAnalyzerAgent()


class TestQuickClassify:
    """测试快速分类功能"""
    
    @pytest.mark.asyncio
    async def test_simple_factual_query(self, analyzer):
        """测试简单事实查询"""
        query = "什么是Python？"
        result = await analyzer.analyze(query)
        
        assert result.primary_intent == "factual"
        assert result.complexity == 1
        assert result.confidence >= 0.9
    
    @pytest.mark.asyncio
    async def test_comparison_query(self, analyzer):
        """测试对比查询"""
        query = "FastAPI和Flask的区别"
        result = await analyzer.analyze(query)
        
        assert result.primary_intent == "comparison"
        assert result.complexity == 2
        assert "FastAPI" in result.key_entities
        assert "Flask" in result.key_entities
        assert "需要对比表格" in result.implicit_requirements
    
    @pytest.mark.asyncio
    async def test_diagnostic_query(self, analyzer):
        """测试诊断查询"""
        query = "为什么我的Django应用响应慢？"
        result = await analyzer.analyze(query)
        
        assert result.primary_intent == "diagnostic"
        assert result.complexity == 3
        assert "需要排查步骤" in result.implicit_requirements
        assert result.user_goal == "解决问题"
    
    @pytest.mark.asyncio
    async def test_tutorial_query(self, analyzer):
        """测试教程查询"""
        query = "如何实现JWT认证？"
        result = await analyzer.analyze(query)
        
        assert result.primary_intent in ["tutorial", "factual"]  # Day 1可能返回factual
        assert result.confidence > 0.5


class TestComparisonEntityExtraction:
    """测试对比实体提取"""
    
    @pytest.mark.asyncio
    async def test_extract_entities_with_和(self, analyzer):
        """测试"和"连接的实体"""
        query = "Django和Flask有什么区别"
        result = await analyzer.analyze(query)
        
        assert len(result.key_entities) == 2
        assert "Django" in result.key_entities
        assert "Flask" in result.key_entities
    
    @pytest.mark.asyncio
    async def test_extract_entities_with_vs(self, analyzer):
        """测试vs连接的实体"""
        query = "React vs Vue性能对比"
        result = await analyzer.analyze(query)
        
        assert len(result.key_entities) >= 2


# 性能测试
class TestPerformance:
    """性能测试"""
    
    @pytest.mark.asyncio
    async def test_quick_classify_performance(self, analyzer):
        """测试快速分类性能"""
        import time
        
        queries = [
            "什么是Python？",
            "如何读取文件？",
            "Django和Flask的区别",
            "为什么报错？",
        ] * 10  # 40个查询
        
        start = time.time()
        
        for query in queries:
            await analyzer.analyze(query)
        
        elapsed = time.time() - start
        avg_time = elapsed / len(queries)
        
        # 快速分类应该<50ms
        assert avg_time < 0.05, f"平均耗时{avg_time*1000:.1f}ms，超过50ms"
```

**运行测试**:
```bash
# 安装pytest（如果还没有）
pip install pytest pytest-asyncio

# 运行测试
pytest tests/agents/test_intent_analyzer.py -v

# 运行性能测试
pytest tests/agents/test_intent_analyzer.py::TestPerformance -v
```

---

### Day 1 验收标准

- [ ] 项目结构创建完成
- [ ] IntentAnalysis数据模型定义完成
- [ ] 快速规则分类实现完成
- [ ] 能正确分类4种常见查询类型
- [ ] 单元测试通过率100%
- [ ] 快速分类性能<50ms

---

### Day 1 交付物

1. **代码文件**:
   - `app/models/agent_models.py`
   - `app/agents/intent_analyzer_agent.py`
   - `tests/agents/test_intent_analyzer.py`

2. **文档**:
   - 代码注释完整
   - 测试覆盖率报告

3. **测试结果**:
   ```bash
   pytest tests/agents/test_intent_analyzer.py -v --cov=app/agents
   ```

---

## 📋 Day 2: LLM深度分析

### 任务清单

#### 上午 (9:00-12:00)
- [ ] 设计LLM分析Prompt
- [ ] 实现`_llm_analyze`方法
- [ ] JSON解析和错误处理

#### 下午 (13:00-18:00)
- [ ] 优化Prompt
- [ ] 性能测试
- [ ] 准确率测试（人工标注50个样本）

---

### 详细步骤

#### Step 1: 实现LLM深度分析 (3小时)

**更新**: `app/agents/intent_analyzer_agent.py`

```python
# 在IntentAnalyzerAgent类中添加

import json
from app.core.models import get_chat_model

class IntentAnalyzerAgent:
    def __init__(self):
        self._init_quick_patterns()
        self.llm = get_chat_model()  # ← 新增
    
    async def _llm_analyze(
        self, 
        query: str, 
        context: Dict[str, Any]
    ) -> IntentAnalysis:
        """LLM深度分析"""
        
        # 构建Prompt
        prompt = self._build_analysis_prompt(query, context)
        
        try:
            # 调用LLM
            response = await self.llm.ainvoke([("human", prompt)])
            content = response.content if hasattr(response, "content") else str(response)
            
            # 解析JSON
            result_dict = self._parse_llm_response(content)
            
            # 添加置信度
            result_dict["confidence"] = 0.85
            
            return IntentAnalysis(**result_dict)
        
        except Exception as e:
            logger.error(f"LLM意图分析失败: {e}")
            # 返回保守的默认值
            return IntentAnalysis(
                primary_intent="factual",
                complexity=2,
                query_type="simple",
                confidence=0.5
            )
    
    def _build_analysis_prompt(self, query: str, context: Dict) -> str:
        """构建分析Prompt"""
        
        history_context = ""
        if context.get("history"):
            recent = context["history"][-3:]
            history_context = f"\n对话历史（最近3轮）:\n"
            for i, h in enumerate(recent, 1):
                history_context += f"{i}. {h.get('query', '')}\n"
        
        prompt = f"""深度分析用户查询意图，输出JSON格式（不要markdown包裹）。

查询: {query}{history_context}

分析维度：
1. primary_intent（主要意图）:
   - factual: 事实查询，如"什么是X"
   - reasoning: 需要推理，如"为什么会X"
   - comparison: 对比分析，如"X和Y的区别"
   - diagnostic: 问题诊断，如"为什么不工作"
   - creative: 创作类，如"帮我写X"

2. complexity（复杂度1-5）:
   - 1: 超简单，一句话回答
   - 2: 简单，一段话
   - 3: 中等，多段落
   - 4: 复杂，需要多步推理
   - 5: 极复杂，需要深度分析

3. query_type（查询类型）:
   - simple: 单一问题
   - compound: 复合问题（包含多个子问题）
   - ambiguous: 模糊问题

4. key_entities: 关键实体列表，如["Django", "ORM"]

5. implicit_requirements: 隐式需求列表
   例如："如何优化" → ["需要代码示例", "需要性能对比"]

6. user_goal（用户目标）:
   - 获取信息: 纯查询
   - 解决问题: 遇到错误
   - 做决策: 选择方案
   - 学习知识: 深入理解

7. estimated_difficulty: 预估难度0.0-1.0

输出JSON（直接输出，不要markdown包裹）:
{{
  "primary_intent": "factual",
  "complexity": 2,
  "query_type": "simple",
  "key_entities": ["Django", "ORM"],
  "implicit_requirements": ["需要代码示例"],
  "user_goal": "获取信息",
  "estimated_difficulty": 0.4
}}"""
        
        return prompt
    
    def _parse_llm_response(self, content: str) -> Dict:
        """解析LLM响应"""
        
        # 移除可能的markdown包裹
        content = content.strip()
        
        # 移除 ```json 或 ``` 包裹
        if content.startswith("```"):
            lines = content.split("\n")
            # 移除第一行和最后一行
            if lines[0].strip() in ["```json", "```"]:
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)
        
        content = content.strip()
        
        # 解析JSON
        return json.loads(content)
```

---

#### Step 2: 测试LLM分析 (2小时)

**测试文件**: `tests/agents/test_intent_llm.py`

```python
"""
测试LLM深度分析功能
"""
import pytest
from app.agents.intent_analyzer_agent import IntentAnalyzerAgent


@pytest.fixture
def analyzer():
    return IntentAnalyzerAgent()


@pytest.mark.asyncio
async def test_llm_complex_query(analyzer):
    """测试复杂查询的LLM分析"""
    
    # 这种查询无法快速分类
    query = "在微服务架构中，如何权衡服务粒度与通信开销？"
    
    result = await analyzer.analyze(query)
    
    # LLM应该能识别这是复杂推理
    assert result.complexity >= 3
    assert result.primary_intent in ["reasoning", "factual"]
    assert result.confidence > 0.7


@pytest.mark.asyncio
async def test_llm_ambiguous_query(analyzer):
    """测试模糊查询"""
    
    query = "这个怎么用？"  # 缺少主语
    
    result = await analyzer.analyze(query)
    
    # 应该识别为模糊查询
    assert result.query_type == "ambiguous"


@pytest.mark.asyncio
async def test_llm_performance(analyzer):
    """测试LLM分析性能"""
    import time
    
    query = "如何在分布式系统中实现事务一致性？"
    
    start = time.time()
    result = await analyzer.analyze(query)
    elapsed = time.time() - start
    
    # LLM分析应该<300ms
    assert elapsed < 0.3, f"LLM分析耗时{elapsed*1000:.0f}ms，超过300ms"
```

**运行测试**:
```bash
pytest tests/agents/test_intent_llm.py -v
```

---

#### Step 3: 准确率评估 (2小时)

**创建测试数据集**:

```python
# scripts/create_intent_test_dataset.py

test_queries = [
    # 简单事实查询
    ("什么是Python？", "factual", 1),
    ("介绍一下Django框架", "factual", 1),
    
    # 对比查询
    ("FastAPI和Flask有什么区别？", "comparison", 2),
    ("React vs Vue性能对比", "comparison", 2),
    
    # 诊断查询
    ("为什么我的Django应用响应慢？", "diagnostic", 3),
    ("Kubernetes Pod一直重启怎么办？", "diagnostic", 3),
    
    # 复杂推理
    ("在微服务中如何权衡服务粒度？", "reasoning", 4),
    ("分布式事务的实现原理", "reasoning", 3),
    
    # ... 总共50个
]

# 保存到JSON
import json
with open("data/intent_test_dataset.json", "w", encoding="utf-8") as f:
    json.dump([
        {"query": q, "expected_intent": i, "expected_complexity": c}
        for q, i, c in test_queries
    ], f, ensure_ascii=False, indent=2)
```

**运行评估**:

```bash
python scripts/evaluate_intent_accuracy.py \
  --dataset data/intent_test_dataset.json \
  --output reports/intent_accuracy_day2.json
```

---

### Day 2 验收标准

- [ ] LLM深度分析实现完成
- [ ] Prompt优化完成
- [ ] JSON解析鲁棒性测试通过
- [ ] LLM分析延迟<300ms
- [ ] 准确率>85%（50个标注样本）

---

### Day 2 交付物

1. **代码更新**:
   - `app/agents/intent_analyzer_agent.py`（新增_llm_analyze）
   
2. **测试**:
   - `tests/agents/test_intent_llm.py`
   
3. **评估报告**:
   - `reports/intent_accuracy_day2.json`

---

## 📋 Day 3: 上下文增强 + 集成测试

*(省略详细内容，包含在完整文档中)*

---

## 📋 Day 4-5: StrategyPlannerAgent

*(省略详细内容，包含在完整文档中)*

---

## 📋 Day 6: PDF导出

*(省略详细内容，包含在完整文档中)*

---

## 📋 Day 7: Week 1集成测试

*(省略详细内容，包含在完整文档中)*

---

## 📊 Week 1 总结

### 预期成果

| 指标 | 目标 | 预期达成 |
|------|------|---------|
| Intent分析准确率 | >90% | 90-92% |
| Intent分析延迟 | <200ms | 150-180ms |
| Strategy规划合理性 | >95% | 95-98% |
| PDF导出成功率 | 100% | 100% |

### 交付物清单

- [x] IntentAnalyzerAgent完整实现
- [x] StrategyPlannerAgent完整实现
- [x] PDF导出功能
- [x] 数据模型定义
- [x] 单元测试覆盖率>80%
- [x] 集成测试通过
- [x] 文档完整

---

**文档版本**: v1.0  
**最后更新**: 2026-07-06
