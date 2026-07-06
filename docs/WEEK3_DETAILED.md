# Week 3 详细实施计划：Generation层 + 全面集成

## 📅 时间表：Day 1-7

**目标**: 实现自适应生成，完成系统集成和部署  
**交付**: AdaptiveGeneratorAgent + 完整5-Agent系统 + 生产部署

---

## 🎯 Week 3 目标

### 功能目标
- ✅ AdaptiveGeneratorAgent（自适应生成）
- ✅ 5-Agent完整集成
- ✅ LangGraph workflow更新
- ✅ API端点更新
- ✅ 前端集成

### 性能目标
- ✅ 端到端准确率>91%
- ✅ 平均延迟<2.6s
- ✅ P95延迟<5.0s
- ✅ 系统可用性>99.5%

---

## 📋 Day 1: AdaptiveGeneratorAgent

### 任务清单

#### 上午 (9:00-12:00)
- [ ] 定义生成策略模型
- [ ] 实现多模板生成
- [ ] 动态格式选择

#### 下午 (13:00-18:00)
- [ ] 实现引用注入
- [ ] 语言适配
- [ ] 单元测试

---

### 详细步骤

#### Step 1: 定义生成策略模型 (1小时)

**文件**: `app/models/generation_models.py`

```python
"""
生成相关数据模型
"""
from typing import List, Dict, Any
from pydantic import BaseModel, Field


class GenerationStrategy(BaseModel):
    """生成策略"""
    
    format_type: str = Field(
        default="structured",
        description="格式类型",
        examples=["simple", "structured", "detailed", "comparative"]
    )
    
    language: str = Field(
        default="zh",
        description="目标语言",
        examples=["zh", "en"]
    )
    
    include_citations: bool = Field(
        default=True,
        description="是否包含引用"
    )
    
    include_code_examples: bool = Field(
        default=False,
        description="是否包含代码示例"
    )
    
    max_length: int = Field(
        default=1000,
        ge=100,
        le=5000,
        description="最大长度（字）"
    )
    
    tone: str = Field(
        default="professional",
        description="语气",
        examples=["professional", "casual", "technical"]
    )


class GenerationResult(BaseModel):
    """生成结果"""
    
    answer: str = Field(..., description="生成的答案")
    
    citations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="引用列表"
    )
    
    format_used: str = Field(
        default="structured",
        description="使用的格式"
    )
    
    language_detected: str = Field(
        default="zh",
        description="检测到的语言"
    )
    
    generation_time_ms: int = Field(
        default=0,
        description="生成耗时（毫秒）"
    )
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

---

#### Step 2: 实现AdaptiveGeneratorAgent (4小时)

**文件**: `app/agents/adaptive_generator_agent.py`

```python
"""
Agent 5: 自适应生成Agent
"""
import logging
import time
from typing import Dict, Any, List

from app.models.generation_models import GenerationStrategy, GenerationResult
from app.core.models import get_chat_model

logger = logging.getLogger(__name__)


class AdaptiveGeneratorAgent:
    """
    自适应生成Agent
    
    职责：根据上下文智能选择生成策略和格式
    """
    
    def __init__(self):
        self.llm = get_chat_model()
        self._init_templates()
    
    def _init_templates(self):
        """初始化生成模板"""
        
        self.templates = {
            "simple": """基于以下信息简洁回答问题。

问题: {query}

相关信息:
{context}

回答（1-2段，包含引用[doc_id:page]）:""",
            
            "structured": """基于以下信息详细回答问题，使用结构化格式。

问题: {query}

相关信息:
{context}

回答（使用分点列表，包含引用[doc_id:page]）:""",
            
            "detailed": """基于以下信息深入回答问题，提供详细解释。

问题: {query}

相关信息:
{context}

回答（多段落，包含示例，包含引用[doc_id:page]）:""",
            
            "comparative": """基于以下信息对比分析。

问题: {query}

相关信息:
{context}

回答（使用对比表格或分点对比，包含引用[doc_id:page]）:"""
        }
    
    async def generate(
        self,
        query: str,
        context: Dict[str, Any],
        strategy: GenerationStrategy
    ) -> GenerationResult:
        """
        生成答案
        
        Args:
            query: 查询
            context: 上下文（检索结果、推理结果等）
            strategy: 生成策略
        
        Returns:
            GenerationResult对象
        """
        
        logger.info(
            f"[Generator] 开始生成: format={strategy.format_type}, "
            f"language={strategy.language}"
        )
        
        start_time = time.time()
        
        # 1. 选择模板
        template = self._select_template(strategy, context)
        
        # 2. 准备上下文
        formatted_context = self._format_context(context)
        
        # 3. 构建Prompt
        prompt = template.format(
            query=query,
            context=formatted_context
        )
        
        # 4. 调用LLM生成
        answer = await self._call_llm(prompt, strategy)
        
        # 5. 提取引用
        citations = self._extract_citations(answer, context)
        
        # 6. 语言适配
        if strategy.language != "zh":
            answer = await self._adapt_language(answer, strategy.language)
        
        generation_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            f"[Generator] 生成完成: {generation_time_ms}ms, "
            f"length={len(answer)}, citations={len(citations)}"
        )
        
        return GenerationResult(
            answer=answer,
            citations=citations,
            format_used=strategy.format_type,
            language_detected=strategy.language,
            generation_time_ms=generation_time_ms,
            metadata={
                "query": query,
                "template": strategy.format_type
            }
        )
    
    def _select_template(
        self,
        strategy: GenerationStrategy,
        context: Dict[str, Any]
    ) -> str:
        """选择生成模板"""
        
        format_type = strategy.format_type
        
        # 根据策略选择模板
        if format_type in self.templates:
            return self.templates[format_type]
        
        # 默认使用structured
        return self.templates["structured"]
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """格式化上下文"""
        
        # 获取检索结果
        retrieval_results = context.get("retrieval_results", [])
        
        if not retrieval_results:
            return "（无相关信息）"
        
        formatted = []
        
        for i, doc in enumerate(retrieval_results[:5], 1):
            doc_id = doc.get("doc_id", f"doc{i}")
            content = doc.get("content", "")
            page = doc.get("page", 1)
            
            formatted.append(
                f"[{doc_id}:p{page}] {content[:200]}..."
            )
        
        return "\n\n".join(formatted)
    
    async def _call_llm(
        self,
        prompt: str,
        strategy: GenerationStrategy
    ) -> str:
        """调用LLM生成答案"""
        
        try:
            response = await self.llm.ainvoke([("human", prompt)])
            content = response.content if hasattr(response, "content") else str(response)
            
            # 长度控制
            if len(content) > strategy.max_length:
                content = content[:strategy.max_length] + "..."
            
            return content
        
        except Exception as e:
            logger.error(f"LLM生成失败: {e}")
            return "抱歉，生成答案时遇到错误。"
    
    def _extract_citations(
        self,
        answer: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """提取引用"""
        
        import re
        
        # 匹配 [doc_id:page] 格式
        pattern = r'\[([^:]+):(?:p)?(\d+)\]'
        matches = re.findall(pattern, answer)
        
        citations = []
        seen = set()
        
        for doc_id, page in matches:
            key = f"{doc_id}:{page}"
            
            if key not in seen:
                citations.append({
                    "doc_id": doc_id,
                    "page": int(page),
                    "source": doc_id
                })
                seen.add(key)
        
        return citations
    
    async def _adapt_language(self, answer: str, target_lang: str) -> str:
        """语言适配"""
        
        if target_lang == "en":
            # Week 3 Day 1简化版：标记需要翻译
            # 真实实现应调用翻译模型
            return f"[EN] {answer}"
        
        return answer
```

---

#### Step 3: 单元测试 (2小时)

**文件**: `tests/agents/test_adaptive_generator.py`

```python
"""
AdaptiveGeneratorAgent单元测试
"""
import pytest
from app.agents.adaptive_generator_agent import AdaptiveGeneratorAgent
from app.models.generation_models import GenerationStrategy


@pytest.fixture
def generator():
    return AdaptiveGeneratorAgent()


@pytest.mark.asyncio
async def test_simple_generation(generator):
    """测试简单生成"""
    
    query = "什么是Python？"
    context = {
        "retrieval_results": [
            {"doc_id": "doc1", "page": 1, "content": "Python是一种编程语言"},
            {"doc_id": "doc2", "page": 5, "content": "Python易于学习"}
        ]
    }
    strategy = GenerationStrategy(format_type="simple", language="zh")
    
    result = await generator.generate(query, context, strategy)
    
    assert result.answer != ""
    assert result.format_used == "simple"
    assert result.language_detected == "zh"


@pytest.mark.asyncio
async def test_structured_generation(generator):
    """测试结构化生成"""
    
    query = "如何优化Django查询？"
    context = {
        "retrieval_results": [
            {"doc_id": "doc1", "page": 3, "content": "使用select_related"},
            {"doc_id": "doc2", "page": 10, "content": "添加数据库索引"}
        ]
    }
    strategy = GenerationStrategy(format_type="structured", language="zh")
    
    result = await generator.generate(query, context, strategy)
    
    assert result.answer != ""
    assert result.format_used == "structured"


@pytest.mark.asyncio
async def test_citation_extraction(generator):
    """测试引用提取"""
    
    query = "测试查询"
    context = {
        "retrieval_results": [
            {"doc_id": "doc1", "page": 1, "content": "内容1"}
        ]
    }
    strategy = GenerationStrategy(format_type="simple")
    
    result = await generator.generate(query, context, strategy)
    
    # 如果答案包含引用，应该能提取出来
    if "[" in result.answer and "]" in result.answer:
        assert len(result.citations) > 0


@pytest.mark.asyncio
async def test_generation_performance(generator):
    """测试生成性能"""
    import time
    
    query = "性能测试查询"
    context = {"retrieval_results": []}
    strategy = GenerationStrategy(format_type="simple")
    
    start = time.time()
    result = await generator.generate(query, context, strategy)
    elapsed = time.time() - start
    
    # 生成应该<2s
    assert elapsed < 2.0, f"生成耗时{elapsed*1000:.0f}ms，超过2000ms"
    assert result.generation_time_ms > 0
```

---

### Day 1 验收标准

- [ ] AdaptiveGeneratorAgent实现完成
- [ ] 4种生成模板实现完成
- [ ] 引用提取实现完成
- [ ] 单元测试通过率100%
- [ ] 生成性能<2s

---

## 📋 Day 2-3: LangGraph Workflow集成

### 任务清单

#### Day 2 上午
- [ ] 更新GraphState定义
- [ ] 创建5个Agent节点
- [ ] 实现节点间数据流

#### Day 2 下午
- [ ] 实现条件路由
- [ ] 添加错误处理
- [ ] 单元测试

#### Day 3 全天
- [ ] 端到端集成测试
- [ ] 性能优化
- [ ] 日志和监控

---

### 详细实现

**文件**: `app/graph/enhanced_workflow_v2.py`

```python
"""
5-Agent增强工作流 (LangGraph实现)
"""
import logging
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

from app.agents.intent_analyzer_agent import IntentAnalyzerAgent
from app.agents.strategy_planner_agent import StrategyPlannerAgent
from app.agents.enhanced_reasoning_agent import EnhancedReasoningAgent
from app.agents.quality_guard_agent import QualityGuardAgent
from app.agents.adaptive_generator_agent import AdaptiveGeneratorAgent

logger = logging.getLogger(__name__)


class EnhancedGraphState(TypedDict):
    """增强图状态"""
    # 输入
    query: str
    session_id: str
    
    # Agent 1: 意图分析
    intent_analysis: dict
    
    # Agent 2: 策略规划
    execution_strategy: dict
    
    # 检索结果（来自现有系统）
    retrieval_results: list
    
    # Agent 3: 推理（可选）
    reasoning_result: dict
    
    # Agent 4: 质量评估
    quality_report: dict
    
    # Agent 5: 生成
    generation_result: dict
    
    # 最终输出
    answer: str
    citations: list
    metadata: dict


class EnhancedWorkflowV2:
    """5-Agent增强工作流"""
    
    def __init__(self):
        # 初始化5个Agent
        self.intent_analyzer = IntentAnalyzerAgent()
        self.strategy_planner = StrategyPlannerAgent()
        self.reasoning_agent = EnhancedReasoningAgent()
        self.quality_guard = QualityGuardAgent()
        self.adaptive_generator = AdaptiveGeneratorAgent()
        
        # 构建图
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """构建LangGraph工作流"""
        
        workflow = StateGraph(EnhancedGraphState)
        
        # 添加节点
        workflow.add_node("intent_analysis", self._intent_analysis_node)
        workflow.add_node("strategy_planning", self._strategy_planning_node)
        workflow.add_node("retrieval", self._retrieval_node)
        workflow.add_node("reasoning", self._reasoning_node)
        workflow.add_node("generation", self._generation_node)
        workflow.add_node("quality_check", self._quality_check_node)
        
        # 定义流程
        workflow.set_entry_point("intent_analysis")
        
        workflow.add_edge("intent_analysis", "strategy_planning")
        workflow.add_edge("strategy_planning", "retrieval")
        
        # 条件路由：是否需要推理
        workflow.add_conditional_edges(
            "retrieval",
            self._should_use_reasoning,
            {
                "reasoning": "reasoning",
                "generation": "generation"
            }
        )
        
        workflow.add_edge("reasoning", "generation")
        workflow.add_edge("generation", "quality_check")
        
        # 条件路由：质量检查
        workflow.add_conditional_edges(
            "quality_check",
            self._quality_passed,
            {
                "end": END,
                "retry": "retrieval"
            }
        )
        
        return workflow.compile()
    
    async def _intent_analysis_node(self, state: EnhancedGraphState) -> EnhancedGraphState:
        """Agent 1: 意图分析节点"""
        
        logger.info("[Workflow] 执行意图分析")
        
        intent_analysis = await self.intent_analyzer.analyze(
            state["query"],
            context={"session_id": state.get("session_id")}
        )
        
        state["intent_analysis"] = intent_analysis.model_dump()
        
        return state
    
    async def _strategy_planning_node(self, state: EnhancedGraphState) -> EnhancedGraphState:
        """Agent 2: 策略规划节点"""
        
        logger.info("[Workflow] 执行策略规划")
        
        from app.models.agent_models import IntentAnalysis
        intent = IntentAnalysis(**state["intent_analysis"])
        
        execution_strategy = await self.strategy_planner.plan(
            state["query"],
            intent_analysis=intent
        )
        
        state["execution_strategy"] = execution_strategy.model_dump()
        
        return state
    
    async def _retrieval_node(self, state: EnhancedGraphState) -> EnhancedGraphState:
        """检索节点（使用现有retriever）"""
        
        logger.info("[Workflow] 执行检索")
        
        # Week 3简化版：模拟检索
        # 真实实现应调用app/retrievers/hybrid_retriever.py
        state["retrieval_results"] = [
            {"doc_id": "doc1", "page": 1, "content": "模拟检索结果1"},
            {"doc_id": "doc2", "page": 5, "content": "模拟检索结果2"}
        ]
        
        return state
    
    async def _reasoning_node(self, state: EnhancedGraphState) -> EnhancedGraphState:
        """Agent 3: 推理节点"""
        
        logger.info("[Workflow] 执行推理")
        
        reasoning_result = await self.reasoning_agent.reason(
            state["query"],
            context={"retrieval_results": state["retrieval_results"]},
            strategy=state["execution_strategy"]
        )
        
        state["reasoning_result"] = reasoning_result.model_dump()
        
        return state
    
    async def _generation_node(self, state: EnhancedGraphState) -> EnhancedGraphState:
        """Agent 5: 生成节点"""
        
        logger.info("[Workflow] 执行生成")
        
        from app.models.generation_models import GenerationStrategy
        
        # 从策略中提取生成策略
        exec_strategy = state["execution_strategy"]
        gen_strategy = GenerationStrategy(
            format_type="structured",
            language="zh"
        )
        
        generation_result = await self.adaptive_generator.generate(
            state["query"],
            context={
                "retrieval_results": state["retrieval_results"],
                "reasoning_result": state.get("reasoning_result")
            },
            strategy=gen_strategy
        )
        
        state["generation_result"] = generation_result.model_dump()
        state["answer"] = generation_result.answer
        state["citations"] = generation_result.citations
        
        return state
    
    async def _quality_check_node(self, state: EnhancedGraphState) -> EnhancedGraphState:
        """Agent 4: 质量检查节点"""
        
        logger.info("[Workflow] 执行质量检查")
        
        quality_report = await self.quality_guard.evaluate(
            state["query"],
            state["answer"],
            context={
                "retrieval_results": state["retrieval_results"],
                "citations": state.get("citations", [])
            }
        )
        
        state["quality_report"] = quality_report.model_dump()
        
        return state
    
    def _should_use_reasoning(self, state: EnhancedGraphState) -> str:
        """判断是否需要推理"""
        
        strategy = state.get("execution_strategy", {})
        
        if strategy.get("reasoning_enabled", False):
            return "reasoning"
        else:
            return "generation"
    
    def _quality_passed(self, state: EnhancedGraphState) -> str:
        """判断质量是否通过"""
        
        quality_report = state.get("quality_report", {})
        
        # Week 3简化版：总是通过
        # 真实实现应检查是否需要重试
        if quality_report.get("passed", False):
            return "end"
        else:
            # 最多重试1次
            retry_count = state.get("metadata", {}).get("retry_count", 0)
            if retry_count < 1:
                logger.warning("[Workflow] 质量检查未通过，重试检索")
                state.setdefault("metadata", {})["retry_count"] = retry_count + 1
                return "retry"
            else:
                logger.warning("[Workflow] 重试次数已达上限，返回当前结果")
                return "end"
    
    async def execute(self, query: str, session_id: str = None) -> dict:
        """执行工作流"""
        
        initial_state = EnhancedGraphState(
            query=query,
            session_id=session_id or "default",
            intent_analysis={},
            execution_strategy={},
            retrieval_results=[],
            reasoning_result={},
            quality_report={},
            generation_result={},
            answer="",
            citations=[],
            metadata={}
        )
        
        final_state = await self.graph.ainvoke(initial_state)
        
        return {
            "answer": final_state["answer"],
            "citations": final_state["citations"],
            "metadata": {
                "intent_analysis": final_state["intent_analysis"],
                "execution_strategy": final_state["execution_strategy"],
                "quality_report": final_state["quality_report"]
            }
        }
```

---

## 📋 Day 4: API端点更新

*(包含FastAPI路由更新、SSE streaming支持、向后兼容)*

---

## 📋 Day 5: 前端集成

*(包含React组件更新、Pipeline选择UI、实时状态显示)*

---

## 📋 Day 6: 性能优化与测试

*(包含基准测试、性能调优、压力测试)*

---

## 📋 Day 7: 部署与文档

*(包含部署脚本、运维文档、用户手册)*

---

## 📊 Week 3 总结

### 最终成果

| 指标 | 目标 | 实际达成 |
|------|------|---------|
| 端到端准确率 | >91% | 需benchmarking验证 |
| 平均延迟 | <2.6s | 需性能测试验证 |
| P95延迟 | <5.0s | 需性能测试验证 |
| 系统可用性 | >99.5% | 需生产验证 |

### 完整交付物

1. **代码交付**:
   - 5个Agent完整实现
   - LangGraph workflow v2
   - API端点更新
   - 前端集成
   - 测试套件

2. **文档交付**:
   - API文档
   - 部署指南
   - 运维手册
   - 用户手册

3. **测试报告**:
   - 单元测试覆盖率>80%
   - 集成测试通过
   - 性能基准报告
   - 准确率评估报告

---

## 🚀 后续优化方向

1. **性能优化**:
   - Agent并行执行
   - 缓存策略
   - 批处理优化

2. **功能增强**:
   - 更多生成模板
   - 多轮对话优化
   - 个性化推荐

3. **可观测性**:
   - 分布式追踪
   - 指标监控
   - 告警系统

---

**文档版本**: v1.0  
**最后更新**: 2026-07-06
