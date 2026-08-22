# 增强Router实现 - 动态轮次澄清系统

**日期**: 2026-08-17  
**功能**: 动态2-10轮澄清系统  
**状态**: ✅ 实现完成

---

## 📖 快速导航

| 文档 | 说明 | 大小 |
|------|------|------|
| [QUICK_REFERENCE.md](./QUICK_REFERENCE.md) | 📌 快速参考卡片 | 5分钟阅读 |
| [implementation.md](./implementation.md) | 📘 完整实现方案 | 30分钟阅读 |
| [dynamic-rounds.md](./dynamic-rounds.md) | 📗 动态轮次详解 | 15分钟阅读 |
| [decisions.md](./decisions.md) | 📙 技术决策记录 | 10分钟阅读 |
| [IMPLEMENTATION_COMPLETE.md](./IMPLEMENTATION_COMPLETE.md) | 📕 完成总结 | 10分钟阅读 |

---

## 🎯 核心改进

从**固定5轮**升级为**动态2-10轮**，根据意图复杂度自适应调整：

```
简单查询    → 2轮  (价格多少？)
文档查找    → 3轮  (查找文档)
文档对比    → 5轮  (对比产品)
RAG设计    → 7轮  (设计RAG系统)
系统架构    → 8轮  (设计微服务)
复杂分析    → 10轮 (多维分析)
```

---

## 🚀 快速开始

### 1. 后端测试

```bash
# 运行单元测试
conda activate rag-local
pytest tests/agents/router/test_enhanced_simple.py -v

# 运行动态轮次测试
pytest tests/agents/router/test_dynamic_rounds.py -v

# 运行验证脚本
python scripts/test_clarification_flow.py
```

### 2. 前端集成

```tsx
import { ClarificationPrompt } from '@/pages/chat/components/ClarificationPrompt';

// 使用组件
<ClarificationPrompt
  question={clarificationQuestion}
  context={clarificationContext}
  onAnswer={(field, answer) => handleAnswer(field, answer)}
  onSkip={() => handleSkip()}
/>
```

### 3. API调用

```bash
# 检查是否需要澄清
curl -X POST http://localhost:8000/api/v1/clarification/check \
  -H "Content-Type: application/json" \
  -d '{
    "question": "帮我设计一个RAG系统",
    "session_id": "test_session"
  }'

# 响应示例
{
  "action": "NEED_CLARIFICATION",
  "clarification": {
    "question": "这个 RAG 主要用于什么场景？",
    "options": ["企业知识库", "客服问答", "代码知识库", "数据分析"],
    "allow_custom_input": true,
    "field_name": "scenario"
  },
  "context": {
    "clarification_round": 0,
    "max_rounds": 7,
    "intent": "rag_design"
  }
}
```

---

## 📁 文件结构

```
multi_agent_rag_local_v4/
├── app/
│   ├── domain/
│   │   └── contracts.py                    ✅ 数据结构定义
│   ├── agents/
│   │   └── router/
│   │       └── enhanced_service.py         ✅ 核心服务 (411行)
│   ├── services/
│   │   └── sessions/
│   │       └── history.py                  ✅ 会话管理
│   └── api/
│       └── routes/
│           └── public/
│               └── clarification.py        ✅ API路由 (223行)
├── frontend/
│   └── src/
│       ├── types/
│       │   └── api.ts                      ✅ TypeScript类型
│       ├── pages/
│       │   └── chat/
│       │       └── components/
│       │           └── ClarificationPrompt.tsx ✅ UI组件 (142行)
│       └── styles/
│           └── components/
│               └── clarification-prompt.css ✅ 样式
├── tests/
│   └── agents/
│       └── router/
│           ├── test_enhanced_simple.py     ✅ 单元测试
│           └── test_dynamic_rounds.py      ✅ 动态轮次测试 (283行)
├── scripts/
│   └── test_clarification_flow.py          ✅ 验证脚本 (238行)
└── docs/
    └── development/
        └── daily-logs/
            └── 2026-08-17/
                ├── README.md               📖 本文档
                ├── QUICK_REFERENCE.md      📌 快速参考
                ├── implementation.md       📘 完整方案
                ├── dynamic-rounds.md       📗 动态轮次
                ├── decisions.md            📙 技术决策
                └── IMPLEMENTATION_COMPLETE.md 📕 完成总结
```

---

## 💻 代码示例

### 获取动态轮次

```python
from app.agents.router.enhanced_service import EnhancedRouterService

service = EnhancedRouterService()

# 简单查询 → 2轮
max_rounds = service._get_max_rounds_for_intent("simple_query")
print(f"Simple query max rounds: {max_rounds}")  # 2

# RAG设计 → 7轮
max_rounds = service._get_max_rounds_for_intent("rag_design")
print(f"RAG design max rounds: {max_rounds}")  # 7

# 未知意图 → 5轮（默认）
max_rounds = service._get_max_rounds_for_intent("unknown")
print(f"Unknown intent max rounds: {max_rounds}")  # 5
```

### 执行增强路由

```python
from app.orchestration.request import OrchestrationRequest, RequestScope
from app.domain.contracts import ClarificationContext

# 创建请求
request = OrchestrationRequest(
    question="帮我设计一个RAG系统",
    session_id="test_session",
    use_reasoning=False,
    source_scope=RequestScope(),
)

# 执行路由
context = ClarificationContext()
decision = await service.route(request, context)

print(f"Action: {decision.action}")              # NEED_CLARIFICATION
print(f"Intent: {decision.context.intent}")      # rag_design
print(f"Max Rounds: {decision.context.max_rounds}") # 7

if decision.clarification:
    print(f"Question: {decision.clarification.question}")
    print(f"Options: {decision.clarification.options}")
```

---

## 🧪 测试覆盖

### 单元测试 (test_enhanced_simple.py)
- ✅ `test_get_max_rounds_for_intent` - 轮次获取逻辑
- ✅ `test_is_simple_query` - 简单查询判断
- ✅ `test_check_missing_info` - 信息完整性检查
- ✅ `test_extract_info_from_history_patterns` - 历史信息提取
- ✅ `test_select_next_question_priority` - 问题选择优先级

**结果**: 5/5 通过 ✅

### 动态轮次测试 (test_dynamic_rounds.py)
- ✅ 配置验证 (3 tests)
- ✅ 轮次分配 (7 tests)
- ✅ 意图变更 (2 tests)
- ✅ 轮次限制 (2 tests)
- ✅ 利用率测试 (2 tests)
- ✅ 默认值 (2 tests)
- ✅ 指标验证 (2 tests)

**总计**: 20+ 测试用例

### 验证脚本 (test_clarification_flow.py)
- ✅ 简单查询场景
- ✅ RAG设计场景
- ✅ 文档对比场景
- ✅ 意图变更场景
- ✅ 轮次强制场景
- ✅ 多轮交互场景

**总计**: 6 个场景

---

## 📊 性能指标

### 目标指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 意图识别准确率 | >90% | 正确识别用户意图类型 |
| 轮次利用率 | 50-80% | 实际使用轮次 / 最大轮次 |
| 最大轮次达到率 | <10% | 达到max_rounds限制的查询占比 |
| 简单问题加速 | +50% | 相比固定5轮的效率提升 |
| 复杂问题完整性 | +40% | 信息收集完整度提升 |

### 监控查询

```sql
-- 各意图的平均轮次
SELECT 
    intent,
    AVG(clarification_round) as avg_rounds,
    MAX(max_rounds) as max_allowed,
    COUNT(*) as total_queries
FROM clarification_logs
GROUP BY intent
ORDER BY avg_rounds DESC;

-- 轮次达到率
SELECT 
    COUNT(CASE WHEN clarification_round >= max_rounds THEN 1 END) * 100.0 / COUNT(*) as reached_max_pct
FROM clarification_logs;
```

---

## 🔧 配置管理

### 添加新意图

```python
# 1. 在 INTENT_COMPLEXITY 中定义轮次
INTENT_COMPLEXITY["new_intent"] = 6

# 2. 在 INTENT_REQUIRED_INFO 中定义详细配置
INTENT_REQUIRED_INFO["new_intent"] = {
    "max_rounds": 6,
    "fields": ["field1", "field2"],
    "questions": {
        "field1": ClarificationQuestion(
            question="问题1？",
            options=["选项1", "选项2"],
            allow_custom_input=True,
            field_name="field1"
        ),
        "field2": ClarificationQuestion(
            question="问题2？",
            options=["选项A", "选项B"],
            allow_custom_input=True,
            field_name="field2"
        ),
    }
}
```

### 调整现有轮次

```python
# 方法1: 修改 INTENT_COMPLEXITY
INTENT_COMPLEXITY["rag_design"] = 8  # 从7改为8

# 方法2: 修改 INTENT_REQUIRED_INFO（优先级更高）
INTENT_REQUIRED_INFO["rag_design"]["max_rounds"] = 8
```

---

## 🐛 故障排查

### 问题1: 轮次始终为5
**原因**: 意图识别失败，使用了默认值  
**解决**: 检查 `_identify_intent()` 方法的关键词匹配

### 问题2: 意图改变后轮次未更新
**原因**: 代码逻辑问题  
**检查**: 
```python
if not clarification_context.intent or clarification_context.intent != intent:
    clarification_context.max_rounds = self._get_max_rounds_for_intent(intent)
```

### 问题3: 超过最大轮次后仍在澄清
**原因**: 轮次检查失败  
**检查**:
```python
if clarification_context.clarification_round >= clarification_context.max_rounds:
    return CONTINUE
```

---

## 📚 相关资源

### 内部文档
- [QUICK_REFERENCE.md](./QUICK_REFERENCE.md) - 快速参考卡片
- [implementation.md](./implementation.md) - 完整实现方案
- [dynamic-rounds.md](./dynamic-rounds.md) - 动态轮次机制详解
- [decisions.md](./decisions.md) - 技术决策记录

### 代码文件
- `app/agents/router/enhanced_service.py` - 核心实现
- `app/domain/contracts.py` - 数据结构
- `app/api/routes/public/clarification.py` - API路由
- `frontend/src/pages/chat/components/ClarificationPrompt.tsx` - UI组件

### 测试文件
- `tests/agents/router/test_enhanced_simple.py` - 单元测试
- `tests/agents/router/test_dynamic_rounds.py` - 动态轮次测试
- `scripts/test_clarification_flow.py` - 验证脚本

---

## 🎓 学习路径

### 新手入门 (30分钟)
1. 阅读 [QUICK_REFERENCE.md](./QUICK_REFERENCE.md) (5分钟)
2. 运行 `python scripts/test_clarification_flow.py` (10分钟)
3. 查看代码示例 (15分钟)

### 开发者深入 (2小时)
1. 阅读 [implementation.md](./implementation.md) (30分钟)
2. 阅读 [dynamic-rounds.md](./dynamic-rounds.md) (20分钟)
3. 阅读核心代码 `enhanced_service.py` (40分钟)
4. 运行完整测试套件 (30分钟)

### 架构师视角 (3小时)
1. 阅读 [decisions.md](./decisions.md) (20分钟)
2. 阅读所有文档 (90分钟)
3. 代码审查 (60分钟)
4. 测试验证 (30分钟)

---

## 📞 支持

**问题反馈**: 请在项目中创建 Issue  
**文档维护**: 请及时更新本目录下的文档  
**测试报告**: 运行测试后请记录结果

---

## 📝 更新日志

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-08-17 | v1.0 | 初始实现完成 |
| 2026-08-17 | v1.1 | 添加完整测试套件 |
| 2026-08-17 | v1.2 | 文档补充完善 |

---

**最后更新**: 2026-08-17 17:45  
**维护者**: AI Development Team  
**状态**: ✅ 生产就绪
