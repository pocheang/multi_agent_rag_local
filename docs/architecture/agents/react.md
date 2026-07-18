# ReAct Agent 使用指南

## 概述

ReAct (Reasoning + Acting) Agent 是一个智能协调器，它通过迭代的思考-行动-观察循环来回答复杂查询。

## 何时使用ReAct

### ✅ 适合使用ReAct的场景

1. **多步推理查询**
   ```
   "比较APT28和APT29的攻击手法，找出共同点，并推荐相应的防御策略"
   ```

2. **需要多个信息源的查询**
   ```
   "查找公司的财务政策，检查是否符合最新法规，并生成合规报告"
   ```

3. **探索性查询**
   ```
   "调查X漏洞的影响范围，找出受影响的系统，评估风险等级"
   ```

4. **序列化决策查询**
   ```
   "先找到所有使用OpenSSL的系统，然后检查版本，最后列出需要更新的系统"
   ```

### ❌ 不适合使用ReAct的场景

1. **简单事实查询** - 使用传统vector路由更快
   ```
   "什么是防火墙？"
   ```

2. **单一文档查询** - 不需要多步推理
   ```
   "财务报销流程是什么？"
   ```

## 使用方法

### 方法1：通过API调用

```python
from app.graph.workflow import run_query

# 方式A：让router自动决定是否使用ReAct
result = run_query(
    question="比较APT28和APT29的攻击手法并推荐防御策略",
    use_reasoning=True,  # 启用推理模型
)

# 方式B：强制使用ReAct路由
from app.agents.router_agent import decide_route

decision = decide_route(question, use_reasoning=True)
if decision.route == "react":
    result = run_query(question=question)
```

### 方法2：直接调用ReAct Agent

```python
from app.agents.react_agent import run_react_agent

result = run_react_agent(
    question="你的复杂查询",
    memory_context="",
    allowed_sources=None,
    retrieval_strategy="hybrid",
    use_reasoning=True,      # 使用推理模型
    max_iterations=5,        # 最多5轮迭代
)

print(result["answer"])
print(f"使用了 {result['iterations_used']} 轮迭代")
print(f"ReAct历史: {result['react_history']}")
```

## ReAct工作流程

```
用户查询: "比较APT28和APT29的攻击手法"
    ↓
┌───────────────────────────────────────────────────┐
│ 第1轮: Thought → Action → Observation             │
├───────────────────────────────────────────────────┤
│ 思考: "需要先了解APT28的攻击手法"                  │
│ 行动: vector_search("APT28攻击手法")              │
│ 观察: "找到5条结果，主要包括鱼叉式钓鱼、漏洞利用" │
└───────────────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────────────┐
│ 第2轮: Thought → Action → Observation             │
├───────────────────────────────────────────────────┤
│ 思考: "现在需要了解APT29的攻击手法"                │
│ 行动: vector_search("APT29攻击手法")              │
│ 观察: "找到4条结果，包括供应链攻击、凭证窃取"      │
└───────────────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────────────┐
│ 第3轮: Thought → Action → Observation             │
├───────────────────────────────────────────────────┤
│ 思考: "查询它们之间的关系"                         │
│ 行动: graph_query("APT28 APT29关系")              │
│ 观察: "找到2个实体，1个关系：都使用类似TTP"        │
└───────────────────────────────────────────────────┘
    ↓
┌───────────────────────────────────────────────────┐
│ 第4轮: Thought → Action                            │
├───────────────────────────────────────────────────┤
│ 思考: "信息足够了，可以生成对比分析"               │
│ 行动: finish                                       │
└───────────────────────────────────────────────────┘
    ↓
综合答案生成
```

## 可用工具

ReAct Agent可以调用以下工具：

1. **vector_search**: 搜索本地文档库
   - 适合：查找具体信息、政策文档、技术细节
   - 输入：搜索查询字符串
   - 输出：检索结果摘要

2. **graph_query**: 查询知识图谱
   - 适合：实体关系、依赖关系、网络拓扑
   - 输入：实体或关系查询
   - 输出：实体和关系统计

3. **web_search**: 搜索互联网
   - 适合：最新信息、新闻、公开资料
   - 输入：网络搜索查询
   - 输出：网络结果摘要

4. **finish**: 结束迭代，生成最终答案
   - 当收集到足够信息时使用

## 返回结果结构

```python
{
    "answer": "最终答案文本",
    "detected_language": "zh",
    "react_history": [
        {
            "iteration": 1,
            "thought": {
                "thought": "需要搜索APT28",
                "action": "vector_search",
                "action_input": "APT28",
                "reasoning": "本地文档应该有相关信息"
            },
            "observation": {
                "tool": "vector_search",
                "result": "找到5条结果",
                "metadata": {"retrieved_count": 5}
            }
        },
        # ... 更多迭代
    ],
    "iterations_used": 3,
    "contexts": {
        "vector": "累积的向量检索上下文...",
        "graph": "累积的图谱查询上下文...",
        "web": "累积的网络搜索上下文..."
    }
}
```

## 配置参数

### max_iterations
- 默认值: 5
- 说明: 最大迭代次数，防止无限循环
- 建议: 简单查询3轮，复杂查询5-7轮

### use_reasoning
- 默认值: False
- 说明: 是否使用推理模型进行思考
- 建议: 复杂查询启用，简单查询关闭

### retrieval_strategy
- 可选值: "hybrid", "dense", "bm25", "rerank"
- 说明: vector_search工具使用的检索策略
- 建议: 默认使用"hybrid"

## 性能考虑

### 延迟
- 每轮迭代包含：1次LLM调用（思考）+ 1次工具执行
- 典型3轮迭代耗时：3-10秒
- 建议：只在必要时使用ReAct

### Token消耗
- 每轮迭代消耗：思考prompt + 工具结果 + 历史上下文
- 5轮迭代约消耗：2000-5000 tokens
- 建议：设置合理的max_iterations

### 并发
- ReAct内部工具调用是串行的
- 建议：对于独立查询使用传统并行路由

## 故障处理

### 工具失败
如果工具执行失败，ReAct会：
1. 记录错误到observation
2. 继续下一轮迭代
3. 可以选择尝试其他工具

### 超时处理
- 支持deadline检查
- 超时时立即返回部分结果

### 无限循环保护
- max_iterations强制限制
- 重复查询检测（TODO）

## 调试技巧

### 查看思考过程
```python
result = run_react_agent(question="...")
for step in result["react_history"]:
    print(f"第{step['iteration']}轮:")
    print(f"  思考: {step['thought']['thought']}")
    print(f"  行动: {step['thought']['action']}")
    print(f"  观察: {step['observation']['result']}")
```

### 启用详细日志
```python
import logging
logging.getLogger("app.agents.react_agent").setLevel(logging.DEBUG)
```

## 最佳实践

1. **清晰的查询**: ReAct依赖LLM理解查询意图，清晰的问题表述很重要

2. **合理的迭代限制**: 根据查询复杂度设置max_iterations

3. **监控token使用**: 复杂查询可能消耗大量tokens

4. **缓存优化**: 相似查询可以复用部分结果（TODO）

5. **fallback机制**: 对于关键查询，设置ReAct失败后的fallback路由

## 示例查询

### 示例1：对比分析
```python
result = run_react_agent(
    question="对比分析APT28和APT29的攻击手法，找出共同点和差异",
    use_reasoning=True,
)
# ReAct会：
# 1. 搜索APT28信息
# 2. 搜索APT29信息  
# 3. 查询图谱关系
# 4. 综合生成对比报告
```

### 示例2：多步调查
```python
result = run_react_agent(
    question="调查Log4j漏洞的影响范围，列出受影响系统，并推荐修复方案",
    use_reasoning=True,
    max_iterations=7,
)
# ReAct会：
# 1. 搜索Log4j漏洞详情
# 2. 查询受影响的系统清单
# 3. 查询图谱中的依赖关系
# 4. 搜索最新修复方案
# 5. 综合生成报告
```

## 与传统路由的对比

| 维度 | 传统路由 | ReAct路由 |
|------|---------|----------|
| 决策时机 | 一次性预先决策 | 动态多次决策 |
| 工具调用 | 固定顺序 | 根据结果调整 |
| 适用场景 | 简单直接查询 | 复杂多步查询 |
| 延迟 | 低（1-3秒） | 中（3-10秒） |
| Token消耗 | 低（500-1000） | 高（2000-5000） |
| 可解释性 | 低 | 高（有思考过程） |

## 未来改进

- [ ] 重复查询检测和去重
- [ ] 工具调用结果缓存
- [ ] 并行工具执行优化
- [ ] 自适应max_iterations
- [ ] 更丰富的工具集
- [ ] 思考过程的可视化展示
