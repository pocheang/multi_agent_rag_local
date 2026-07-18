# 提示词模块 (Prompts Module)

专业的、模块化的提示词库，用于企业级多智能体RAG系统。

## 📁 目录结构

```
app/prompts/
├── __init__.py              # 统一导出接口
├── manager.py               # 提示词管理器
├── router_prompts.py        # 路由决策提示词
├── intent_prompts.py        # 意图分类提示词
├── synthesis_prompts.py     # 答案合成提示词
├── review_prompts.py        # 答案质检提示词
├── react_prompts.py         # ReAct推理提示词
├── self_rag_prompts.py      # Self-RAG评估提示词
└── README.md                # 本文档
```

## 🎯 模块说明

### 1. router_prompts.py - 路由决策

**功能**: 分析用户查询，决定最优的检索策略和技能选择

**包含**:
- `ROUTER_SYSTEM_PROMPT`: 路由器系统提示词
- `ROUTER_USER_PROMPT_TEMPLATE`: 用户提示词模板

**支持的路由**:
- `vector`: 向量检索（70%的查询）
- `graph`: 图谱查询（关系和依赖）
- `hybrid`: 混合检索（复杂查询）
- `react`: 多步推理（分析任务）

**支持的技能**:
- `answer_with_citations`: 标准问答
- `compare_entities`: 实体对比
- `timeline_builder`: 时间线构建
- `cyber_attack_analysis`: 攻击分析
- `cyber_defense_hardening`: 防御加固
- `incident_response_playbook`: 应急响应
- `ai_knowledge_assistant`: AI知识助手
- `pdf_text_reader`: PDF阅读

---

### 2. intent_prompts.py - 意图分类

**功能**: 将用户查询分类到合适的专业领域

**包含**:
- `INTENT_CLASSIFICATION_SYSTEM_PROMPT`: 意图分类系统提示词
- `INTENT_CLASSIFICATION_USER_PROMPT_TEMPLATE`: 用户提示词模板

**支持的领域**:
- `cybersecurity`: 网络安全（90+关键词）
- `artificial_intelligence`: 人工智能（40+关键词）
- `pdf_text`: PDF文档处理
- `policy`: 策略和合规文档
- `general`: 通用知识（默认）

---

### 3. synthesis_prompts.py - 答案合成

**功能**: 综合多个信息源生成准确的答案

**包含**:
- `SYNTHESIS_SYSTEM_PROMPT`: 答案合成系统提示词
- `SYNTHESIS_USER_PROMPT_TEMPLATE`: 用户提示词模板

**核心原则**:
1. **信息优先级**: 当前问题 > 对话上下文 > 记忆 > 检索
2. **来源归因**: 每个事实都需要引用 [1], [2], [3]
3. **语言适配**: 100%中文或100%英文，禁止混用
4. **安全边界**: 不泄露系统信息和跨用户数据
5. **答案范围**: 只回答用户明确提出的问题

---

### 4. review_prompts.py - 答案质检

**功能**: 评估答案质量，自动改进不合格答案

**包含**:
- `REVIEW_SYSTEM_PROMPT`: 质检系统提示词
- `REVIEW_USER_PROMPT_TEMPLATE`: 用户提示词模板

**评估维度**:
- **相关性** (0-10): 是否回答了问题
- **准确性** (0-10): 是否忠实于上下文
- **完整性** (0-10): 是否覆盖所有方面
- **清晰度** (0-10): 表达是否清晰

**通过标准**:
```
is_correct = true 当且仅当:
  相关性 ≥ 7 AND 准确性 ≥ 8 AND 完整性 ≥ 7
```

---

### 5. react_prompts.py - ReAct推理

**功能**: 多步推理解决复杂问题

**包含**:
- `REACT_SYSTEM_PROMPT`: ReAct推理系统提示词
- `REACT_USER_PROMPT_TEMPLATE`: 用户提示词模板

**ReAct循环**:
1. Think (思考): 分析当前状态
2. Act (行动): 执行工具
3. Observe (观察): 查看结果
4. Repeat (重复): 继续或完成
5. Finish (完成): 生成最终答案

**可用工具**:
- `vector_search`: 本地文档检索（70%）
- `graph_query`: 知识图谱查询（20%）
- `web_search`: 互联网搜索（10%）
- `finish`: 完成推理

---

### 6. self_rag_prompts.py - Self-RAG评估

**功能**: 自我评估提升检索和生成质量

**包含**:
- `SELF_RAG_RETRIEVAL_PROMPT`: 检索相关性评估
- `SELF_RAG_ANSWER_QUALITY_PROMPT`: 答案质量评估

**检索评估**:
- `RELEVANT`: 高度相关
- `PARTIALLY_RELEVANT`: 部分相关
- `IRRELEVANT`: 不相关

**答案评估**:
- **Groundedness**: FULLY_GROUNDED / PARTIALLY_GROUNDED / NOT_GROUNDED
- **Utility**: HIGH / MEDIUM / LOW

---

### 7. manager.py - 统一管理器

**功能**: 统一管理所有提示词，提供便捷接口

**核心类**: `PromptManager`

**主要方法**:
- `get_router_prompts()`: 获取路由提示词
- `get_intent_prompts()`: 获取意图分类提示词
- `get_synthesis_prompts()`: 获取合成提示词
- `get_review_prompts()`: 获取质检提示词
- `get_react_prompts()`: 获取ReAct提示词
- `format_router_prompt(...)`: 格式化路由提示词
- `format_synthesis_prompt(...)`: 格式化合成提示词
- ... 更多格式化方法

---

## 🚀 快速开始

### 方式1: 使用管理器（推荐）

```python
from app.prompts import get_prompt_manager

# 获取管理器实例
pm = get_prompt_manager()

# 获取并格式化提示词
system_prompt, user_template = pm.get_router_prompts()
user_prompt = pm.format_router_prompt(
    question="什么是零信任架构？",
    previous_agent_class="general",
    language="zh"
)

# 调用LLM
response = model.invoke([
    ("system", system_prompt),
    ("human", user_prompt)
])
```

### 方式2: 直接导入（便捷函数）

```python
from app.prompts import (
    get_router_system_prompt,
    get_synthesis_system_prompt,
    get_react_system_prompt,
    get_intent_system_prompt,
    get_review_system_prompt,
)

# 直接获取系统提示词
router_prompt = get_router_system_prompt()
synthesis_prompt = get_synthesis_system_prompt()
```

### 方式3: 直接导入常量

```python
from app.prompts.router_prompts import ROUTER_SYSTEM_PROMPT
from app.prompts.synthesis_prompts import SYNTHESIS_SYSTEM_PROMPT
from app.prompts.react_prompts import REACT_SYSTEM_PROMPT

# 直接使用常量
system_prompt = ROUTER_SYSTEM_PROMPT
```

---

## 📝 使用示例

### 完整端到端流程

```python
from app.prompts import get_prompt_manager
from app.core.models import get_chat_model

# 初始化
pm = get_prompt_manager()
model = get_chat_model()

# 1. 意图分类
intent_sys, _ = pm.get_intent_prompts()
intent_user = pm.format_intent_prompt("什么是Compliance Layer？")
intent_result = model.invoke([("system", intent_sys), ("human", intent_user)])
# 结果: agent_class = "cybersecurity"

# 2. 路由决策
router_sys, _ = pm.get_router_prompts()
router_user = pm.format_router_prompt(
    question="什么是Compliance Layer？",
    previous_agent_class="cybersecurity",
    language="zh"
)
route_result = model.invoke([("system", router_sys), ("human", router_user)])
# 结果: route = "vector", skill = "answer_with_citations"

# 3. 检索（略）
vector_context = "[从文档库检索到的内容]"

# 4. 合成答案
synth_sys, _ = pm.get_synthesis_prompts()
synth_user = pm.format_synthesis_prompt(
    question="什么是Compliance Layer？",
    skill_name="answer_with_citations",
    language="zh",
    vector_context=vector_context
)
final_answer = model.invoke([("system", synth_sys), ("human", synth_user)])

# 5. 质量评估
review_sys, _ = pm.get_review_prompts()
review_user = pm.format_review_prompt(
    question="什么是Compliance Layer？",
    current_answer=final_answer.content,
    vector_context=vector_context
)
quality_check = model.invoke([("system", review_sys), ("human", review_user)])
```

---

## 🔄 迁移现有代码

### Router Agent

```python
# 旧代码 (app/agents/router_agent.py)
ROUTER_PROMPT = """You are a route planner..."""

# 新代码 - 方式1（推荐）
from app.prompts import get_router_system_prompt
ROUTER_PROMPT = get_router_system_prompt()

# 新代码 - 方式2
from app.prompts.router_prompts import ROUTER_SYSTEM_PROMPT
ROUTER_PROMPT = ROUTER_SYSTEM_PROMPT
```

### Synthesis Agent

```python
# 旧代码 (app/agents/synthesis_agent.py)
ANSWER_PROMPT = """你是企业知识库客服型回答 Agent..."""

# 新代码
from app.prompts import get_synthesis_system_prompt
ANSWER_PROMPT = get_synthesis_system_prompt()
```

### Intent Classifier

```python
# 旧代码 (app/services/llm_intent_classifier.py)
INTENT_CLASSIFICATION_PROMPT = """你是一个智能意图分类器..."""

# 新代码
from app.prompts import get_intent_system_prompt
INTENT_CLASSIFICATION_PROMPT = get_intent_system_prompt()
```

### ReAct Agent

```python
# 旧代码 (app/agents/react_agent.py)
REACT_SYSTEM_PROMPT = """你是一个使用ReAct模式..."""

# 新代码
from app.prompts import get_react_system_prompt
REACT_SYSTEM_PROMPT = get_react_system_prompt()
```

---

## 🎨 设计原则

### 1. 模块化
- 每个文件专注一个功能模块
- 职责单一，易于维护
- 独立测试和更新

### 2. 专业性
- 准确的技术术语
- 详细的领域知识
- 企业级标准

### 3. 完整性
- 覆盖所有业务场景
- 处理边界情况
- 详细的使用说明

### 4. 安全性
- 数据隔离规则
- 安全边界明确
- 防止信息泄露

### 5. 多语言
- 中英文双语支持
- 100%语言一致性
- 禁止语言混用

---

## 🧪 测试

```python
def test_prompt_manager():
    """测试提示词管理器"""
    from app.prompts import get_prompt_manager
    
    pm = get_prompt_manager()
    
    # 测试获取提示词
    sys_prompt, user_tpl = pm.get_router_prompts()
    assert len(sys_prompt) > 1000, "系统提示词应该足够详细"
    
    # 测试格式化
    user_prompt = pm.format_router_prompt(
        question="测试问题",
        previous_agent_class="general",
        language="zh"
    )
    assert "测试问题" in user_prompt
    assert "general" in user_prompt

def test_synthesis_prompt():
    """测试合成提示词"""
    from app.prompts import get_prompt_manager
    
    pm = get_prompt_manager()
    
    user_prompt = pm.format_synthesis_prompt(
        question="什么是XSS？",
        skill_name="cyber_attack_analysis",
        language="zh",
        vector_context="XSS是跨站脚本攻击..."
    )
    
    assert "[Language: zh]" in user_prompt
    assert "什么是XSS？" in user_prompt
    assert "cyber_attack_analysis" in user_prompt
```

---

## 📚 相关文档

- **完整报告**：历史版本报告未纳入当前公开文档。
- **使用指南**：请以本目录中的提示词实现和测试为准。
- **原始提示词**: 各个agent模块中的旧提示词定义

---

## 🔧 扩展指南

### 添加新的提示词模块

1. 创建新文件 `app/prompts/your_module_prompts.py`
2. 定义提示词常量
3. 在 `manager.py` 中添加管理方法
4. 在 `__init__.py` 中导出

示例：

```python
# app/prompts/your_module_prompts.py
"""你的模块提示词"""

YOUR_SYSTEM_PROMPT = """..."""
YOUR_USER_PROMPT_TEMPLATE = """..."""
```

```python
# app/prompts/manager.py
class PromptManager:
    def get_your_module_prompts(self) -> Tuple[str, str]:
        return (YOUR_SYSTEM_PROMPT, YOUR_USER_PROMPT_TEMPLATE)
    
    def format_your_module_prompt(self, **kwargs) -> str:
        return YOUR_USER_PROMPT_TEMPLATE.format(**kwargs)
```

### 自定义管理器

```python
from app.prompts.manager import PromptManager

class CustomPromptManager(PromptManager):
    """自定义提示词管理器"""
    
    def get_router_prompts(self):
        sys, user = super().get_router_prompts()
        # 自定义修改
        custom_sys = sys + "\n\n自定义规则..."
        return custom_sys, user
```

---

## ❓ 常见问题

### Q1: 为什么要分成多个文件？
**A**: 模块化设计便于维护和扩展。每个文件职责单一，修改一个模块不会影响其他模块。

### Q2: 如何选择使用方式？
**A**: 
- 需要格式化 → 使用 `PromptManager`
- 只需要系统提示词 → 使用便捷函数 `get_xxx_system_prompt()`
- 简单直接 → 直接导入常量

### Q3: 提示词太长会影响性能吗？
**A**: 现代LLM对提示词长度不敏感。优化后的提示词带来的准确性提升远大于轻微的token成本增加。

### Q4: 可以修改提示词吗？
**A**: 可以。直接编辑对应的 `.py` 文件，或者继承 `PromptManager` 类自定义。

---

**版本**: v2.0  
**最后更新**: 2026-06-23  
**维护者**: Project Team
