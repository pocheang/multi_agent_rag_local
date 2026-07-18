# Web Research Agent Documentation

## Overview

Web Research Agent是多智能体RAG系统的外部知识获取器，负责从互联网搜索信息以补充本地知识库。

**文件位置**: `app/agents/web_research_agent.py`

**核心功能**: 互联网搜索 + 来源质量过滤 + 结果整合

---

## Table of Contents

1. [核心功能](#核心功能)
2. [架构设计](#架构设计)
3. [可信度评分机制](#可信度评分机制)
4. [API接口](#api接口)
5. [配置参数](#配置参数)
6. [工作流程](#工作流程)
7. [与其他Agent集成](#与其他agent集成)
8. [使用场景](#使用场景)
9. [安全特性](#安全特性)
10. [性能优化](#性能优化)
11. [故障处理](#故障处理)
12. [最佳实践](#最佳实践)

---

## 核心功能

### 1. 互联网搜索
- 当本地知识库（Vector RAG/Graph RAG）检索结果不足时触发
- 搜索最新信息、新闻、实时数据
- 验证和补充本地知识

### 2. 来源质量过滤
- 基于域名的可信度评分系统
- 支持白名单模式（严格域名过滤）
- 自动过滤低质量来源

### 3. 结果整合
- 提取网页标题、URL、摘要内容
- 生成格式化的上下文字符串
- 提供引用信息供Synthesis Agent使用

---

## 架构设计

### 系统位置

```
User Query
    ↓
[Router Agent] → 路由决策
    ↓
[Vector RAG] → 本地文档检索
    ↓
[Graph RAG] → 知识图谱查询
    ↓
[Web Research Agent] → 互联网搜索（fallback）
    ↓
[Synthesis Agent] → 答案综合
```

### 依赖关系

```python
Web Research Agent
    ↓ 调用
app/tools/web_search.py (search_web函数)
    ↓ 使用
外部搜索API（DuckDuckGo/Google/Bing等）
```

### 核心模块

1. **`run_web_research(question: str)`**: 主函数
2. **`_source_score(url: str, allowlist: list[str])`**: 可信度评分
3. **`_parse_allowlist(raw: str)`**: 白名单解析

---

## 可信度评分机制

Web Research Agent使用两种评分模式来确保搜索结果的质量。

### 模式1: 白名单模式（Whitelist Mode）

**触发条件**: 配置了 `WEB_DOMAIN_ALLOWLIST` 环境变量

**评分规则**:
- ✅ 在白名单中的域名: **1.0分** (通过)
- ❌ 不在白名单的域名: **0.0分** (拒绝)

**配置示例**:
```bash
WEB_DOMAIN_ALLOWLIST="github.com,stackoverflow.com,owasp.org"
```

**适用场景**:
- 企业内部部署，只信任特定网站
- 高安全要求的场景
- 需要严格控制信息来源

### 模式2: TLD评分模式（Trust Level Domain Scoring）

**触发条件**: 未配置 `WEB_DOMAIN_ALLOWLIST`

**评分规则**:

| 域名类型 | 评分 | 说明 | 示例 |
|---------|------|------|------|
| `.gov`, `.edu` | 0.9 | 政府/教育机构（最高信任） | `cisa.gov`, `mit.edu` |
| 可信技术域名 | 0.8 | 知名技术/安全网站 | `github.com`, `owasp.org` |
| `.org` | 0.7 | 非营利组织（中等信任） | `mozilla.org`, `w3.org` |
| 其他域名 | 0.4 | 通用域名（低信任） | `example.com` |

**内置可信域名列表**:
```python
trusted_domains = {
    # 代码托管
    "github.com",
    
    # 技术社区
    "stackoverflow.com",
    
    # 科技公司
    "microsoft.com", "apple.com",
    
    # 标准组织
    "mozilla.org", "w3.org", "ietf.org",
    
    # 安全组织
    "owasp.org", "cve.org", "nvd.nist.gov",
    "cisa.gov", "cert.org"
}
```

**默认阈值**: `min_score = 0.6`
- 只接受评分 ≥ 0.6 的来源
- 可通过 `WEB_MIN_SOURCE_SCORE` 环境变量调整

### 评分函数实现

```python
def _source_score(url: str, allowlist: list[str]) -> float:
    """Calculate source score for a URL."""
    host = (urlparse(str(url or "")).hostname or "").lower()
    if not host:
        return 0.0

    # 白名单模式：严格匹配
    if allowlist:
        if any(host == d or host.endswith(f".{d}") for d in allowlist):
            return 1.0
        return 0.0

    # TLD评分模式
    if host.endswith(".gov") or host.endswith(".edu"):
        return 0.9
    if host.endswith(".org"):
        return 0.7
    if host in trusted_domains or any(host.endswith(f".{d}") for d in trusted_domains):
        return 0.8
    return 0.4
```

---

## API接口

### 主函数: `run_web_research()`

```python
def run_web_research(question: str) -> dict:
    """
    执行网络搜索并返回过滤后的结果。
    
    Args:
        question (str): 用户查询问题
        
    Returns:
        dict: 包含上下文、引用、使用状态的字典
    """
```

### 输入参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `question` | str | ✅ | 用户的查询问题 |

### 返回结果

```python
{
    "context": str,           # 格式化的搜索结果上下文
    "citations": list[dict],  # 引用列表
    "used": bool,             # 是否成功检索到结果
    "error": str              # 错误信息（可选）
}
```

### 返回结果详细说明

#### 1. `context` (str)
格式化的搜索结果字符串，供Synthesis Agent使用：

```
[WEB] Understanding RAG Systems
URL: https://github.com/example/rag-tutorial
Retrieval-Augmented Generation (RAG) combines retrieval and generation...

[WEB] OWASP Top 10 Security Risks
URL: https://owasp.org/www-project-top-ten/
The OWASP Top 10 is a standard awareness document for developers...
```

#### 2. `citations` (list[dict])
引用信息列表，每项包含：

```python
{
    "source": str,        # URL或标题
    "content": str,       # 摘要内容
    "metadata": {
        "title": str,           # 网页标题
        "source_score": float   # 可信度评分 (0.0-1.0)
    }
}
```

#### 3. `used` (bool)
- `True`: 成功检索到至少1条符合质量标准的结果
- `False`: 没有找到符合标准的结果，或搜索失败

#### 4. `error` (str, optional)
错误信息，仅在搜索失败时返回：
```python
"error": "web_search_error:ConnectionError"
```

### 调用示例

```python
from app.agents.web_research_agent import run_web_research

# 基本调用
result = run_web_research("What is RAG in AI?")

# 检查结果
if result["used"]:
    print(f"找到 {len(result['citations'])} 条网络结果")
    print(result["context"])
else:
    print("网络搜索未返回有效结果")
    if "error" in result:
        print(f"错误: {result['error']}")
```

---

## 配置参数

### 环境变量配置

在 `.env` 文件中配置：

```bash
# Web搜索域名白名单（逗号分隔）
# 如果设置，则只接受白名单中的域名
WEB_DOMAIN_ALLOWLIST="github.com,stackoverflow.com,owasp.org,microsoft.com"

# 最低可信度评分阈值（仅在未设置白名单时生效）
# 范围: 0.0-1.0，默认: 0.6
WEB_MIN_SOURCE_SCORE=0.6

# 搜索引擎配置（在 app/tools/web_search.py 中配置）
SEARCH_ENGINE="duckduckgo"  # 或 "google", "bing"
```

### 配置模式对比

| 配置场景 | WEB_DOMAIN_ALLOWLIST | WEB_MIN_SOURCE_SCORE | 过滤行为 |
|---------|---------------------|---------------------|---------|
| 严格白名单模式 | ✅ 已设置 | ❌ 忽略 | 只接受白名单域名 (score=1.0) |
| TLD评分模式 | ❌ 未设置 | ✅ 0.6 | 接受score≥0.6的域名 |
| 宽松模式 | ❌ 未设置 | ✅ 0.4 | 接受大部分域名 (除非score<0.4) |
| 极严格模式 | ❌ 未设置 | ✅ 0.8 | 只接受高可信度域名 (.gov, .edu, trusted) |

### 推荐配置

#### 企业/生产环境（高安全性）
```bash
WEB_DOMAIN_ALLOWLIST="github.com,stackoverflow.com,microsoft.com,owasp.org,cve.org,nvd.nist.gov"
```

#### 研究/开发环境（平衡模式）
```bash
# 不设置白名单，使用默认TLD评分
WEB_MIN_SOURCE_SCORE=0.6
```

#### 探索/测试环境（宽松模式）
```bash
WEB_MIN_SOURCE_SCORE=0.4
```

### 动态配置

配置会在运行时从 `get_settings()` 加载：

```python
settings = get_settings()
allowlist = _parse_allowlist(getattr(settings, "web_domain_allowlist", ""))
min_score = float(getattr(settings, "web_min_source_score", 0.6) or 0.6)
```

---

## 工作流程

### 完整执行流程

```
1. 接收查询问题
   ↓
2. 加载配置（白名单、阈值）
   ↓
3. 调用 search_web(question, max_results=5)
   ↓
4. 遍历搜索结果
   ├─ 提取: title, href, body
   ├─ 计算可信度评分 _source_score()
   ├─ 过滤: score < min_score 的结果
   └─ 保留: 符合标准的结果
   ↓
5. 格式化保留的结果
   ├─ 生成 context 字符串
   └─ 构建 citations 列表
   ↓
6. 返回结果
   ├─ used=True (有结果)
   └─ used=False (无结果或错误)
```

### 详细步骤说明

#### Step 1: 配置加载
```python
settings = get_settings()
allowlist = _parse_allowlist(getattr(settings, "web_domain_allowlist", ""))

# 根据是否有白名单决定评分模式
if allowlist:
    min_score = 0.5  # 白名单模式：只接受score=1.0的域名
else:
    min_score = float(getattr(settings, "web_min_source_score", 0.6) or 0.6)
```

#### Step 2: 执行搜索
```python
try:
    results = search_web(question, max_results=5)
except Exception as e:
    logger.exception(f"Web search failed for question: {question}")
    return {
        "context": "",
        "citations": [],
        "used": False,
        "error": f"web_search_error:{type(e).__name__}"
    }
```

#### Step 3: 结果过滤和格式化
```python
lines = []
citations = []
for item in results:
    title = item.get("title", "")
    href = item.get("href", "")
    body = item.get("body", "")
    
    # 计算可信度评分
    score = _source_score(href, allowlist=allowlist)
    
    # 过滤低质量来源
    if score < min_score:
        continue
    
    # 格式化上下文
    lines.append(f"[WEB] {title}\nURL: {href}\n{body}")
    
    # 构建引用
    citations.append({
        "source": href or title,
        "content": body,
        "metadata": {"title": title, "source_score": score}
    })
```

#### Step 4: 返回结果
```python
return {
    "context": "\n\n".join(lines),
    "citations": citations,
    "used": bool(citations)
}
```

### 时序图

```
User/Agent                  Web Research Agent           search_web()        External API
    |                              |                           |                    |
    |---run_web_research()-------->|                           |                    |
    |                              |---加载配置---------------->|                    |
    |                              |                           |                    |
    |                              |---search_web()----------->|                    |
    |                              |                           |---HTTP Request---->|
    |                              |                           |<---Response--------|
    |                              |<---results----------------|                    |
    |                              |                           |                    |
    |                              |---遍历结果---------------->|                    |
    |                              |---计算score--------------->|                    |
    |                              |---过滤+格式化------------->|                    |
    |                              |                           |                    |
    |<---返回结果------------------|                           |                    |
    |    {context, citations}      |                           |                    |
```

---

## 与其他Agent集成

### 在LangGraph工作流中的位置

```python
# app/graph/workflow.py

START
  ↓
router_node          # Router Agent 决定路由
  ↓
vector_node          # Vector RAG 本地检索
  ↓
vector_decider       # 决定是否继续
  ↓
graph_node           # Graph RAG 图谱查询
  ↓
graph_decider        # 决定是否需要Web搜索
  ↓ (need_web=True)
web_node             # Web Research Agent ← 这里
  ↓
synthesis_node       # Synthesis Agent 综合答案
  ↓
END
```

### 触发条件

Web Research Agent在以下情况被调用：

#### 1. Graph Decider触发（自动模式）
```python
def graph_decider(state: GraphState) -> str:
    """Decide next step after graph RAG."""
    graph_result = state.get("graph_result", {})
    
    # 图谱查询失败 → 触发Web搜索
    if not graph_result or not graph_result.get("context"):
        return "web"
    
    # 图谱信号分数低 → 触发Web搜索
    if graph_result.get("graph_signal_score", 0.0) < 0.3:
        return "web"
    
    # 其他情况 → 跳过Web，直接合成答案
    return "synthesis"
```

#### 2. ReAct Agent工具调用（主动模式）
```python
# ReAct Agent在推理过程中主动调用
tools = [
    {
        "name": "vector_search",
        "description": "Search local documents"
    },
    {
        "name": "graph_query",
        "description": "Query knowledge graph"
    },
    {
        "name": "web_search",              # ← Web Research工具
        "description": "Search the internet for latest information"
    }
]

# ReAct决定调用web_search工具
action = "web_search"
result = run_web_research(question)
```

#### 3. API参数显式启用（用户控制）
```python
# POST /api/v1/query
{
    "question": "最新的AI新闻",
    "use_web_fallback": true    # ← 强制启用Web搜索
}
```

### 与Synthesis Agent集成

Web Research结果会传递给Synthesis Agent进行最终答案生成：

```python
# app/agents/synthesis_agent.py

def synthesize_answer(
    question: str,
    vector_context: str = "",
    graph_context: str = "",
    web_context: str = "",        # ← Web搜索结果
    ...
) -> dict:
    # 综合多个来源生成答案
    all_context = []
    
    if vector_context:
        all_context.append(f"[LOCAL DOCS]\n{vector_context}")
    
    if graph_context:
        all_context.append(f"[KNOWLEDGE GRAPH]\n{graph_context}")
    
    if web_context:
        all_context.append(f"[WEB SEARCH]\n{web_context}")
    
    combined_context = "\n\n---\n\n".join(all_context)
    
    # 生成答案时明确标注来源
    prompt = f"""
    Based on the following sources, answer the question.
    
    Context:
    {combined_context}
    
    Question: {question}
    
    Instructions:
    - Cite sources using [source_type:id] format
    - For web sources, use [web:url] format
    - Prefer local sources over web sources when both available
    """
```

### 结果合并策略

```python
# 优先级: Local > Graph > Web
priority_order = ["vector", "graph", "web"]

# 1. 如果本地文档充足，Web结果作为补充验证
if len(vector_citations) >= 5:
    use_web_as_supplementary = True

# 2. 如果本地+图谱都不足，Web结果为主要来源
elif len(vector_citations) + len(graph_citations) < 3:
    use_web_as_primary = True

# 3. 对于时效性查询，Web结果优先
if is_time_sensitive_query(question):
    prioritize_web = True
```

### 调用示例

```python
# 完整工作流调用
from app.agents.vector_rag_agent import run_vector_rag
from app.agents.graph_rag_agent import run_graph_rag
from app.agents.web_research_agent import run_web_research
from app.agents.synthesis_agent import synthesize_answer

question = "What are the latest security vulnerabilities in Log4j?"

# Step 1: 本地文档检索
vector_result = run_vector_rag(question, agent_class="cybersecurity")

# Step 2: 图谱查询
graph_result = run_graph_rag(
    question, 
    retrieved_docs=vector_result.get("citations", [])
)

# Step 3: Web搜索（补充最新信息）
web_result = run_web_research(question)

# Step 4: 综合答案
answer = synthesize_answer(
    question=question,
    vector_context=vector_result.get("context", ""),
    graph_context=graph_result.get("context", ""),
    web_context=web_result.get("context", ""),
    skill_name="cyber_attack_analysis"
)

print(answer["answer"])
```

---

## 使用场景

### ✅ 适合使用Web Research Agent的场景

#### 1. 时效性查询
**特征**: 查询涉及"最新"、"今天"、"当前"等时间性词汇

**示例**:
- "2026年最新的AI模型有哪些？"
- "今天的股市行情如何？"
- "当前Log4j漏洞的修复进展"
- "最近发布的网络安全漏洞"

**原因**: 本地知识库可能过时，Web搜索提供最新信息

#### 2. 本地知识不足
**特征**: Vector RAG和Graph RAG返回结果少或质量低

**示例**:
- 查询本地没有的专业领域知识
- 新兴技术话题（如新发布的框架）
- 冷门主题查询

**触发条件**:
```python
if len(vector_citations) < 3 and graph_signal_score < 0.3:
    trigger_web_search = True
```

#### 3. 事实验证
**特征**: 需要交叉验证本地信息的准确性

**示例**:
- "验证某个技术细节的准确性"
- "检查统计数据的最新版本"
- "确认某个漏洞的CVE编号"

**用法**: Web结果作为补充验证源

#### 4. 新闻和事件查询
**特征**: 查询实时事件、新闻、公告

**示例**:
- "OpenAI最近有什么重大发布？"
- "GitHub昨天的服务中断情况"
- "某公司最新的安全公告"

#### 5. 探索性研究
**特征**: 开放式探索，需要广泛来源

**示例**:
- "当前业界对某技术的看法"
- "某话题的最新研究进展"
- "不同来源对某问题的分析"

### ❌ 不适合使用Web Research Agent的场景

#### 1. 内部/专有知识
**原因**: 互联网上不存在，徒劳无功且可能泄露查询意图

**示例**:
- 公司内部文档查询
- 专有代码库问题
- 企业内部流程

**建议**: 禁用Web搜索或使用白名单限制

#### 2. 本地知识充足
**原因**: 浪费资源和时间，本地结果已足够

**触发条件**:
```python
if len(vector_citations) >= 5 and vector_quality_score > 0.8:
    skip_web_search = True
```

#### 3. 隐私敏感查询
**原因**: 查询可能包含敏感信息，不应发送到外部

**示例**:
- 包含个人信息的查询
- 涉及机密项目的问题
- 包含认证凭据的查询

**防护**: 实施查询内容过滤

#### 4. 离线环境
**原因**: 无法访问互联网

**示例**:
- 内网隔离环境
- 高安全性环境
- 飞机/船舶等离线场景

#### 5. 历史性查询
**原因**: 查询的是历史事实，不需要最新信息

**示例**:
- "二战的起始时间"
- "Python 2.7的发布日期"
- "TCP/IP协议的工作原理"

### 场景决策树

```
用户查询
    ↓
是否包含时间性词汇？
    ├─ 是 → 使用Web Search ✅
    └─ 否
        ↓
本地检索结果是否充足？
    ├─ 是（≥5条，质量>0.8）→ 跳过Web Search ❌
    └─ 否
        ↓
是否涉及隐私/专有信息？
    ├─ 是 → 跳过Web Search ❌
    └─ 否
        ↓
是否需要最新信息验证？
    ├─ 是 → 使用Web Search ✅
    └─ 否 → 可选使用Web Search ⚠️
```

---

## 安全特性

### 1. 域名过滤（Domain Filtering）

**目的**: 防止访问恶意或不可信网站

**实现**:
```python
def _source_score(url: str, allowlist: list[str]) -> float:
    """评估URL可信度，低于阈值的自动过滤"""
    host = (urlparse(str(url or "")).hostname or "").lower()
    if not host:
        return 0.0
    
    # 白名单模式：严格控制
    if allowlist:
        return 1.0 if host in allowlist else 0.0
    
    # TLD评分模式：基于域名类型评估
    return calculate_trust_score(host)
```

**防护等级**:
- **Level 1**: 白名单模式（最严格）
- **Level 2**: TLD评分 + 高阈值（0.8+）
- **Level 3**: TLD评分 + 默认阈值（0.6）
- **Level 4**: TLD评分 + 低阈值（0.4）

### 2. 结果数量限制（Rate Limiting）

**目的**: 防止信息过载和资源滥用

**实现**:
```python
results = search_web(question, max_results=5)  # 硬限制5条
```

**效果**:
- 控制API调用成本
- 减少处理时间
- 聚焦高质量结果

### 3. 错误隔离（Error Isolation）

**目的**: Web搜索失败不影响整体流程

**实现**:
```python
try:
    results = search_web(question, max_results=5)
except Exception as e:
    logger.exception(f"Web search failed for question: {question}")
    return {
        "context": "",
        "citations": [],
        "used": False,
        "error": f"web_search_error:{type(e).__name__}"
    }
```

**优势**:
- 搜索失败时系统继续运行
- 错误被记录但不抛出
- 降级到本地结果

### 4. 查询内容脱敏（Query Sanitization）

**推荐实现**（当前未实现，建议添加）:

```python
def _sanitize_query(question: str) -> str:
    """Remove sensitive information from query before web search."""
    import re
    
    # 移除常见敏感模式
    patterns = [
        r'\b\d{3}-\d{2}-\d{4}\b',        # SSN
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
        r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',  # IP地址
        r'password\s*[=:]\s*\S+',        # 密码
        r'token\s*[=:]\s*\S+',           # Token
    ]
    
    sanitized = question
    for pattern in patterns:
        sanitized = re.sub(pattern, '[REDACTED]', sanitized, flags=re.IGNORECASE)
    
    return sanitized
```

### 5. 可信度透明（Trust Transparency）

**目的**: 让用户了解信息来源的可信度

**实现**:
```python
citations.append({
    "source": href,
    "content": body,
    "metadata": {
        "title": title,
        "source_score": score  # ← 可信度评分透明化
    }
})
```

**用户体验**:
- Synthesis Agent在答案中可标注来源可信度
- 用户可根据评分判断信息可靠性
- 便于审计和问题追溯

### 6. 日志和审计（Logging & Auditing）

**实现**:
```python
logger = logging.getLogger(__name__)

# 搜索失败记录
logger.exception(f"Web search failed for question: {question}")

# 建议添加：搜索成功记录
logger.info(f"Web search returned {len(citations)} results for: {question[:50]}...")

# 建议添加：过滤统计
logger.debug(f"Filtered {filtered_count} low-quality sources (score < {min_score})")
```

**审计能力**:
- 追踪所有Web搜索请求
- 记录过滤决策
- 监控异常模式

### 7. 超时保护（Timeout Protection）

**推荐实现**（在 `search_web()` 中）:

```python
import requests

def search_web(query: str, max_results: int = 5, timeout: int = 10):
    """Execute web search with timeout protection."""
    try:
        response = requests.get(
            search_url,
            params={"q": query},
            timeout=timeout  # ← 10秒超时
        )
        # ...
    except requests.Timeout:
        logger.warning(f"Web search timeout for query: {query}")
        return []
```

### 安全配置建议

#### 高安全环境
```bash
# 严格白名单
WEB_DOMAIN_ALLOWLIST="github.com,owasp.org,nvd.nist.gov,cisa.gov"

# 禁用通用搜索，只允许技术/安全网站
WEB_MIN_SOURCE_SCORE=1.0
```

#### 平衡环境
```bash
# 使用TLD评分
# WEB_DOMAIN_ALLOWLIST=  # 留空

# 只接受可信来源
WEB_MIN_SOURCE_SCORE=0.7
```

#### 开放环境
```bash
# 接受大部分来源
WEB_MIN_SOURCE_SCORE=0.4
```

---

## 性能优化

### 1. 搜索结果限制

**当前实现**:
```python
results = search_web(question, max_results=5)
```

**优化考虑**:
- ✅ 限制为5条减少API调用时间
- ✅ 减少后续过滤和格式化开销
- ⚠️ 可能错过高质量结果（如果前5条都被过滤）

**改进建议**:
```python
# 动态调整：先获取更多，再过滤
initial_results = search_web(question, max_results=10)
filtered = [r for r in initial_results if _source_score(r["href"]) >= min_score]
top_5 = filtered[:5]  # 只保留前5条高质量结果
```

### 2. 缓存机制

**推荐实现**（当前未实现）:

```python
from functools import lru_cache
from hashlib import md5

# 简单缓存（内存）
@lru_cache(maxsize=128)
def run_web_research_cached(question: str) -> dict:
    """Cached version of web research."""
    return run_web_research(question)

# 持久化缓存（Redis/文件）
def run_web_research_with_cache(question: str, cache_ttl: int = 3600):
    """Web research with persistent cache."""
    cache_key = f"web_search:{md5(question.encode()).hexdigest()}"
    
    # 尝试从缓存读取
    cached = cache.get(cache_key)
    if cached:
        logger.info(f"Cache hit for web search: {question[:50]}...")
        return cached
    
    # 执行搜索
    result = run_web_research(question)
    
    # 存入缓存
    if result["used"]:
        cache.set(cache_key, result, ttl=cache_ttl)
    
    return result
```

**缓存策略**:
- **TTL**: 1小时（时效性查询）到24小时（通用查询）
- **缓存键**: 查询问题的hash
- **缓存条件**: 只缓存成功的搜索（`used=True`）

### 3. 并行搜索

**场景**: 当需要多个独立查询时

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def run_parallel_web_research(questions: list[str]) -> list[dict]:
    """Execute multiple web searches in parallel."""
    results = []
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_question = {
            executor.submit(run_web_research, q): q 
            for q in questions
        }
        
        for future in as_completed(future_to_question):
            question = future_to_question[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Parallel search failed for {question}: {e}")
                results.append({"context": "", "citations": [], "used": False})
    
    return results
```

### 4. 懒加载配置

**当前实现已优化**:
```python
def run_web_research(question: str) -> dict:
    settings = get_settings()  # 每次调用时加载
    allowlist = _parse_allowlist(...)
```

**优势**: 支持运行时配置更新，无需重启服务

### 5. 早期退出（Early Exit）

**优化URL解析**:
```python
def _source_score(url: str, allowlist: list[str]) -> float:
    host = (urlparse(str(url or "")).hostname or "").lower()
    if not host:
        return 0.0  # ← 早期退出：无效URL直接返回
    
    if allowlist:
        # ← 早期退出：白名单模式快速判断
        if any(host == d or host.endswith(f".{d}") for d in allowlist):
            return 1.0
        return 0.0
```

### 6. 批量处理优化

**当前实现**:
```python
lines = []
citations = []
for item in results:  # 逐条处理
    title = item.get("title", "")
    href = item.get("href", "")
    body = item.get("body", "")
    score = _source_score(href, allowlist=allowlist)
    if score < min_score:
        continue
    # ...
```

**性能分析**:
- ✅ 串行处理，逻辑简单
- ✅ 结果数量少（≤5），性能已足够
- ⚠️ 如果扩展到大量结果，考虑向量化操作

### 性能指标

**典型执行时间**:
```
search_web():           1-3秒  (外部API调用)
_source_score():        <1毫秒 (URL解析)
结果格式化:              <10毫秒 (5条结果)
总计:                   1-3秒
```

**瓶颈分析**:
- 🔴 主要瓶颈：外部搜索API响应时间（1-3秒）
- 🟡 次要因素：网络延迟（0.1-0.5秒）
- 🟢 内部处理：可忽略（<50毫秒）

**优化优先级**:
1. ⭐⭐⭐ 实施缓存（减少90%重复请求）
2. ⭐⭐ 添加超时控制（防止长时间阻塞）
3. ⭐ 并行查询（适用于多查询场景）

---

## 故障处理

### 1. 常见错误类型

#### 错误1: 搜索API失败
**现象**:
```python
{
    "context": "",
    "citations": [],
    "used": False,
    "error": "web_search_error:ConnectionError"
}
```

**可能原因**:
- 网络连接问题
- 搜索API不可用
- API配额耗尽
- 防火墙阻止

**解决方案**:
```python
# 1. 检查网络连接
curl -I https://duckduckgo.com

# 2. 检查代理设置
echo $HTTP_PROXY
echo $HTTPS_PROXY

# 3. 检查搜索引擎配置
grep SEARCH_ENGINE .env

# 4. 查看详细日志
tail -f logs/app.log | grep "web_search"
```

#### 错误2: 所有结果被过滤
**现象**:
```python
{
    "context": "",
    "citations": [],
    "used": False  # 无错误，但无结果
}
```

**可能原因**:
- 白名单配置过严
- 阈值设置过高
- 搜索返回的都是低质量来源

**诊断**:
```python
# 添加调试日志
logger.debug(f"Search returned {len(results)} raw results")
for item in results:
    score = _source_score(item.get("href", ""), allowlist)
    logger.debug(f"URL: {item.get('href')} | Score: {score} | Threshold: {min_score}")
```

**解决方案**:
```bash
# 临时降低阈值
WEB_MIN_SOURCE_SCORE=0.4

# 或清空白名单（使用TLD评分）
WEB_DOMAIN_ALLOWLIST=
```

#### 错误3: 超时
**现象**: 请求长时间无响应

**解决方案**:
```python
# 在 search_web() 中添加超时
def search_web(query: str, max_results: int = 5):
    try:
        response = requests.get(
            url,
            params={"q": query},
            timeout=10  # ← 添加超时
        )
    except requests.Timeout:
        logger.warning(f"Search timeout for: {query}")
        return []
```

#### 错误4: 无效URL
**现象**: `source_score = 0.0` for all results

**诊断**:
```python
# 检查URL解析
from urllib.parse import urlparse
test_url = "https://example.com/page"
parsed = urlparse(test_url)
print(f"Hostname: {parsed.hostname}")
```

### 2. 降级策略

#### 策略1: 跳过Web搜索
```python
def safe_run_web_research(question: str) -> dict:
    """Web research with graceful degradation."""
    try:
        result = run_web_research(question)
        if not result["used"]:
            logger.info("Web search returned no results, skipping")
        return result
    except Exception as e:
        logger.error(f"Web search failed, continuing without it: {e}")
        return {"context": "", "citations": [], "used": False}
```

#### 策略2: Fallback到备用搜索引擎
```python
def run_web_research_with_fallback(question: str) -> dict:
    """Try multiple search engines in sequence."""
    engines = ["duckduckgo", "google", "bing"]
    
    for engine in engines:
        try:
            results = search_web(question, engine=engine, max_results=5)
            if results:
                return process_results(results)
        except Exception as e:
            logger.warning(f"{engine} search failed: {e}")
            continue
    
    # 所有引擎都失败
    return {"context": "", "citations": [], "used": False, "error": "all_engines_failed"}
```

### 3. 监控和告警

**关键指标**:
```python
# 1. 成功率
web_search_success_rate = successful_searches / total_searches

# 2. 平均响应时间
avg_response_time = sum(search_times) / len(search_times)

# 3. 过滤率
filter_rate = filtered_results / total_results

# 4. 错误类型分布
error_distribution = Counter([e["error"] for e in errors])
```

**告警阈值**:
- 🔴 成功率 < 50%: 严重告警
- 🟡 响应时间 > 5秒: 警告
- 🟡 过滤率 > 80%: 配置问题警告

### 4. 调试技巧

#### 启用详细日志
```python
import logging
logging.getLogger("app.agents.web_research_agent").setLevel(logging.DEBUG)
```

#### 手动测试
```python
from app.agents.web_research_agent import run_web_research

# 测试基本功能
result = run_web_research("What is RAG?")
print(f"Used: {result['used']}")
print(f"Citations: {len(result['citations'])}")
print(result["context"][:200])

# 测试白名单
import os
os.environ["WEB_DOMAIN_ALLOWLIST"] = "github.com"
result = run_web_research("GitHub best practices")
```

#### 查看原始搜索结果
```python
from app.tools.web_search import search_web

raw_results = search_web("test query", max_results=5)
for i, item in enumerate(raw_results):
    print(f"{i+1}. {item.get('title')}")
    print(f"   URL: {item.get('href')}")
    print(f"   Body: {item.get('body', '')[:100]}...")
```

---

## 最佳实践

### 1. 配置管理

#### ✅ 推荐做法
```bash
# 生产环境：使用白名单
WEB_DOMAIN_ALLOWLIST="github.com,stackoverflow.com,owasp.org,nvd.nist.gov"

# 开发环境：使用TLD评分
WEB_MIN_SOURCE_SCORE=0.6

# 按环境分离配置
# .env.production
WEB_DOMAIN_ALLOWLIST="trusted1.com,trusted2.com"

# .env.development
WEB_MIN_SOURCE_SCORE=0.4
```

#### ❌ 避免做法
```bash
# 不要过度宽松（安全风险）
WEB_MIN_SOURCE_SCORE=0.0

# 不要完全关闭过滤
# WEB_DOMAIN_ALLOWLIST=  # 空但存在 → 阻止所有
# 应该不设置该变量
```

### 2. 集成使用

#### ✅ 推荐做法
```python
# 1. 先尝试本地，后尝试Web
vector_result = run_vector_rag(question)
if len(vector_result["citations"]) < 3:
    web_result = run_web_research(question)

# 2. 时效性查询优先Web
if is_time_sensitive(question):
    web_result = run_web_research(question)
    vector_result = run_vector_rag(question)  # 补充

# 3. 错误处理
try:
    web_result = run_web_research(question)
except Exception as e:
    logger.error(f"Web search failed: {e}")
    web_result = {"context": "", "citations": [], "used": False}
```

#### ❌ 避免做法
```python
# 不要盲目依赖Web搜索
web_result = run_web_research(question)
# 应该先检查本地

# 不要忽略错误
web_result = run_web_research(question)
# 应该 try-except

# 不要对所有查询都使用Web
for q in all_queries:
    web_result = run_web_research(q)  # 浪费资源
```

### 3. 结果处理

#### ✅ 推荐做法
```python
# 1. 检查是否使用
if web_result["used"]:
    web_context = web_result["context"]
else:
    web_context = ""

# 2. 标注来源可信度
for citation in web_result["citations"]:
    score = citation["metadata"]["source_score"]
    if score < 0.6:
        logger.warning(f"Low trust source: {citation['source']}")

# 3. 合并多源结果时明确优先级
contexts = []
if vector_context:
    contexts.append(("LOCAL", vector_context, 1.0))
if web_context:
    contexts.append(("WEB", web_context, 0.7))  # 权重低于本地
```

### 4. 性能优化

#### ✅ 推荐做法
```python
# 1. 使用缓存
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_web_search(question: str):
    return run_web_research(question)

# 2. 设置超时
result = run_web_research_with_timeout(question, timeout=10)

# 3. 并行处理独立查询
results = run_parallel_web_research([q1, q2, q3])
```

### 5. 安全实践

#### ✅ 推荐做法
```python
# 1. 查询脱敏
sanitized_query = remove_sensitive_info(question)
web_result = run_web_research(sanitized_query)

# 2. 结果验证
for citation in web_result["citations"]:
    if not is_safe_url(citation["source"]):
        logger.warning(f"Unsafe URL detected: {citation['source']}")

# 3. 日志审计
logger.info(f"Web search: query='{question[:50]}', results={len(citations)}, sources={[c['source'] for c in citations]}")
```

### 6. 监控和维护

#### ✅ 推荐做法
```python
# 1. 记录关键指标
metrics.record("web_search.latency", elapsed_time)
metrics.record("web_search.success", int(result["used"]))
metrics.record("web_search.citations", len(result["citations"]))

# 2. 定期审查过滤规则
# 每月检查：
# - 白名单是否需要更新
# - 阈值是否合理
# - 过滤率是否过高

# 3. A/B测试不同配置
if experiment_group == "A":
    min_score = 0.6
else:
    min_score = 0.7
```

### 7. 文档和注释

#### ✅ 推荐做法
```python
def run_web_research(question: str) -> dict:
    """
    Execute web search with quality filtering.
    
    Args:
        question: User query (should be sanitized for sensitive info)
        
    Returns:
        dict with keys:
        - context: Formatted search results
        - citations: List of source citations with trust scores
        - used: True if results found, False otherwise
        - error: Error message if search failed (optional)
        
    Example:
        >>> result = run_web_research("What is RAG?")
        >>> if result["used"]:
        ...     print(f"Found {len(result['citations'])} sources")
    """
```

---

## 总结

Web Research Agent是多智能体RAG系统的重要补充组件，提供以下核心价值：

✅ **时效性**: 获取最新信息和实时数据  
✅ **完整性**: 补充本地知识库的不足  
✅ **验证性**: 交叉验证本地信息的准确性  
✅ **安全性**: 可信度评分和域名过滤确保结果质量  
✅ **灵活性**: 支持白名单和TLD两种评分模式  

**关键记忆点**:
- 🔍 外部搜索 + 质量过滤 = 可信补充
- 🛡️ 安全第一：白名单/TLD双模式
- ⚡ 性能优化：缓存 + 超时 + 限流
- 🔧 容错设计：错误隔离 + 降级策略

**文档版本**: v1.0  
**最后更新**: 2026-06-30

