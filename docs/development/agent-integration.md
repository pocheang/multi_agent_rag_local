# Agent集成指南 (Agent Integration Guide)

**版本**: v1.0  
**更新日期**: 2026-06-23

本指南展示如何在Agent中使用智能切片和检索功能。

---

## 📚 目录

1. [快速开始](#1-快速开始)
2. [类型过滤检索](#2-类型过滤检索)
3. [元数据增强检索](#3-元数据增强检索)
4. [Router Agent集成](#4-router-agent集成)
5. [实战示例](#5-实战示例)

---

## 1. 快速开始

### 基础检索

```python
from app.retrievers.vector_store import VectorStore

def basic_search(query: str, k: int = 5):
    """基础向量检索"""
    vector_store = VectorStore()
    results = vector_store.similarity_search(query=query, k=k)
    return results
```

### 带类型过滤的检索

```python
def search_with_type(query: str, chunk_type: str, k: int = 5):
    """带类型过滤的检索"""
    vector_store = VectorStore()
    
    results = vector_store.similarity_search(
        query=query,
        k=k,
        filter={"chunk_type": chunk_type}
    )
    
    return results
```

---

## 2. 类型过滤检索

### 2.1 单类型过滤

#### 搜索定义

```python
def search_definitions(query: str, k: int = 5):
    """
    搜索定义类内容
    
    适用场景：
    - "什么是X"类查询
    - 术语解释
    - 概念说明
    """
    vector_store = VectorStore()
    
    results = vector_store.similarity_search(
        query=query,
        k=k,
        filter={"chunk_type": "definition"}
    )
    
    return results

# 使用示例
results = search_definitions("什么是MFA认证")
```

#### 搜索步骤/流程

```python
def search_procedures(query: str, k: int = 5):
    """
    搜索步骤类内容
    
    适用场景：
    - "如何做X"类查询
    - 操作指南
    - 配置步骤
    """
    vector_store = VectorStore()
    
    results = vector_store.similarity_search(
        query=query,
        k=k,
        filter={"chunk_type": "procedure"}
    )
    
    return results

# 使用示例
results = search_procedures("如何配置OAuth")
```

#### 搜索代码示例

```python
def search_code_examples(query: str, k: int = 5):
    """
    搜索代码块
    
    适用场景：
    - 代码示例查找
    - API使用示例
    - 配置文件模板
    """
    vector_store = VectorStore()
    
    results = vector_store.similarity_search(
        query=query,
        k=k,
        filter={"chunk_type": "code"}
    )
    
    return results

# 使用示例
results = search_code_examples("Python API调用示例")
```

#### 搜索表格数据

```python
def search_tables(query: str, k: int = 5):
    """
    搜索表格内容
    
    适用场景：
    - 数据查询
    - 配置参数表
    - 对比信息
    """
    vector_store = VectorStore()
    
    results = vector_store.similarity_search(
        query=query,
        k=k,
        filter={"chunk_type": "table"}
    )
    
    return results

# 使用示例
results = search_tables("API端点列表")
```

### 2.2 多类型过滤

```python
def search_structured_content(query: str, k: int = 5):
    """
    搜索结构化内容（列表、表格、代码）
    """
    vector_store = VectorStore()
    
    results = vector_store.similarity_search(
        query=query,
        k=k,
        filter={"chunk_type": {"$in": ["list", "table", "code"]}}
    )
    
    return results

def search_instructional_content(query: str, k: int = 5):
    """
    搜索教学类内容（定义、步骤、列表）
    """
    vector_store = VectorStore()
    
    results = vector_store.similarity_search(
        query=query,
        k=k,
        filter={"chunk_type": {"$in": ["definition", "procedure", "list"]}}
    )
    
    return results
```

---

## 3. 元数据增强检索

### 3.1 重要性过滤

```python
def search_important_content(query: str, min_importance: float = 0.7, k: int = 5):
    """
    搜索高重要性内容
    
    Args:
        query: 查询文本
        min_importance: 最小重要性得分 (0.0-1.0)
        k: 返回结果数量
    """
    vector_store = VectorStore()
    
    results = vector_store.similarity_search(
        query=query,
        k=k,
        filter={"importance_score": {"$gte": min_importance}}
    )
    
    return results
```

### 3.2 组合过滤

```python
def search_important_definitions(query: str, k: int = 5):
    """
    搜索重要的定义类内容
    """
    vector_store = VectorStore()
    
    results = vector_store.similarity_search(
        query=query,
        k=k,
        filter={
            "chunk_type": "definition",
            "importance_score": {"$gte": 0.6}
        }
    )
    
    return results

def search_technical_procedures(query: str, k: int = 5):
    """
    搜索技术类的操作步骤
    """
    vector_store = VectorStore()
    
    results = vector_store.similarity_search(
        query=query,
        k=k,
        filter={
            "chunk_type": {"$in": ["procedure", "list"]},
            "agent_class": "technical",
            "importance_score": {"$gte": 0.5}
        }
    )
    
    return results
```

### 3.3 位置过滤

```python
def search_document_starts(query: str, k: int = 5):
    """
    搜索文档开头的内容（通常包含摘要、概述）
    """
    vector_store = VectorStore()
    
    results = vector_store.similarity_search(
        query=query,
        k=k,
        filter={"position": "start"}
    )
    
    return results
```

---

## 4. Router Agent集成

### 4.1 智能路由 + 类型过滤

```python
from app.agents.router_agent import decide_route

def enhanced_route_and_search(question: str, k: int = 5):
    """
    路由决策 + 智能类型过滤
    """
    # 路由决策
    route_decision = decide_route(question)
    route = route_decision.get("route", "vector_rag")
    
    # 根据问题推断chunk类型
    chunk_type_filter = infer_chunk_type(question)
    
    # 执行检索
    vector_store = VectorStore()
    
    filter_dict = {}
    if chunk_type_filter:
        if isinstance(chunk_type_filter, list):
            filter_dict["chunk_type"] = {"$in": chunk_type_filter}
        else:
            filter_dict["chunk_type"] = chunk_type_filter
    
    results = vector_store.similarity_search(
        query=question,
        k=k,
        filter=filter_dict if filter_dict else None
    )
    
    return {
        "route": route,
        "chunk_type": chunk_type_filter,
        "results": results
    }

def infer_chunk_type(question: str) -> str | list[str] | None:
    """
    从问题推断合适的chunk类型
    """
    question_lower = question.lower()
    
    # 定义类查询
    if any(keyword in question_lower for keyword in ["什么是", "定义", "是指", "含义"]):
        return "definition"
    
    # 步骤类查询
    if any(keyword in question_lower for keyword in ["如何", "怎么", "步骤", "方法"]):
        return ["procedure", "list"]
    
    # 代码类查询
    if any(keyword in question_lower for keyword in ["代码", "示例", "example", "code"]):
        return "code"
    
    # 配置类查询
    if any(keyword in question_lower for keyword in ["配置", "参数", "设置"]):
        return ["table", "list"]
    
    # 默认不过滤
    return None
```

### 4.2 在现有Agent中集成

#### VectorRAGAgent集成

```python
# 在 app/agents/vector_rag_agent.py 中

class VectorRAGAgent:
    def search_with_type_inference(self, question: str, k: int = 5):
        """带类型推断的检索"""
        
        # 推断类型
        chunk_type = self._infer_chunk_type(question)
        
        # 构建过滤器
        filter_dict = {}
        if chunk_type:
            if isinstance(chunk_type, list):
                filter_dict["chunk_type"] = {"$in": chunk_type}
            else:
                filter_dict["chunk_type"] = chunk_type
        
        # 检索
        results = self.vector_store.similarity_search(
            query=question,
            k=k,
            filter=filter_dict if filter_dict else None
        )
        
        return results
    
    def _infer_chunk_type(self, question: str) -> str | list[str] | None:
        """类型推断逻辑"""
        # 同上面的 infer_chunk_type 函数
        pass
```

---

## 5. 实战示例

### 示例1: 技术文档Agent

```python
class TechnicalDocAgent:
    """技术文档专用Agent"""
    
    def __init__(self):
        self.vector_store = VectorStore()
    
    def answer_definition_question(self, question: str):
        """回答定义类问题"""
        # 搜索定义
        definitions = self.vector_store.similarity_search(
            query=question,
            k=3,
            filter={"chunk_type": "definition", "agent_class": "technical"}
        )
        
        if not definitions:
            return "未找到相关定义"
        
        # 构建答案
        answer = f"根据文档，{definitions[0].page_content}"
        return answer
    
    def answer_howto_question(self, question: str):
        """回答操作类问题"""
        # 搜索步骤
        procedures = self.vector_store.similarity_search(
            query=question,
            k=5,
            filter={
                "chunk_type": {"$in": ["procedure", "list", "code"]},
                "agent_class": "technical"
            }
        )
        
        if not procedures:
            return "未找到相关操作步骤"
        
        # 构建答案
        answer = "操作步骤如下：\n\n"
        for i, proc in enumerate(procedures[:3], 1):
            answer += f"{i}. {proc.page_content}\n\n"
        
        return answer
    
    def get_code_example(self, query: str):
        """获取代码示例"""
        examples = self.vector_store.similarity_search(
            query=query,
            k=3,
            filter={"chunk_type": "code", "agent_class": "technical"}
        )
        
        if not examples:
            return "未找到相关代码示例"
        
        return examples[0].page_content
```

### 示例2: 业务知识Agent

```python
class BusinessKnowledgeAgent:
    """业务知识专用Agent"""
    
    def __init__(self):
        self.vector_store = VectorStore()
    
    def search_policies(self, question: str):
        """搜索政策类内容"""
        results = self.vector_store.similarity_search(
            query=question,
            k=5,
            filter={
                "chunk_type": {"$in": ["definition", "list", "table"]},
                "agent_class": "business",
                "importance_score": {"$gte": 0.6}
            }
        )
        
        return results
    
    def search_procedures(self, question: str):
        """搜索流程类内容"""
        results = self.vector_store.similarity_search(
            query=question,
            k=5,
            filter={
                "chunk_type": {"$in": ["procedure", "list"]},
                "agent_class": "business"
            }
        )
        
        return results
```

### 示例3: 智能FAQ Agent

```python
class SmartFAQAgent:
    """智能FAQ Agent"""
    
    def __init__(self):
        self.vector_store = VectorStore()
    
    def answer(self, question: str):
        """智能回答问题"""
        # 分析问题类型
        question_type = self._analyze_question_type(question)
        
        # 根据类型选择检索策略
        if question_type == "definition":
            results = self._search_definitions(question)
        elif question_type == "howto":
            results = self._search_procedures(question)
        elif question_type == "example":
            results = self._search_examples(question)
        else:
            results = self._search_general(question)
        
        # 生成答案
        answer = self._generate_answer(question, results)
        
        return answer
    
    def _analyze_question_type(self, question: str) -> str:
        """分析问题类型"""
        q = question.lower()
        
        if any(k in q for k in ["什么是", "定义", "含义"]):
            return "definition"
        elif any(k in q for k in ["如何", "怎么", "步骤"]):
            return "howto"
        elif any(k in q for k in ["示例", "例子", "example"]):
            return "example"
        else:
            return "general"
    
    def _search_definitions(self, question: str):
        return self.vector_store.similarity_search(
            query=question,
            k=3,
            filter={"chunk_type": "definition"}
        )
    
    def _search_procedures(self, question: str):
        return self.vector_store.similarity_search(
            query=question,
            k=5,
            filter={"chunk_type": {"$in": ["procedure", "list"]}}
        )
    
    def _search_examples(self, question: str):
        return self.vector_store.similarity_search(
            query=question,
            k=3,
            filter={"chunk_type": {"$in": ["code", "quote"]}}
        )
    
    def _search_general(self, question: str):
        return self.vector_store.similarity_search(
            query=question,
            k=5
        )
    
    def _generate_answer(self, question: str, results: list) -> str:
        """生成答案"""
        if not results:
            return "抱歉，我没有找到相关信息。"
        
        # 简单拼接（实际应用中应该用LLM生成）
        answer = "根据文档：\n\n"
        for i, doc in enumerate(results[:3], 1):
            answer += f"{i}. {doc.page_content[:200]}...\n\n"
        
        return answer
```

---

## 📊 性能优化建议

### 1. 减少不必要的检索

```python
# ❌ 不好：每次都检索全部
def search(question):
    return vector_store.similarity_search(question, k=20)

# ✅ 好：使用类型过滤减少范围
def search(question):
    chunk_type = infer_type(question)
    return vector_store.similarity_search(
        question, 
        k=10, 
        filter={"chunk_type": chunk_type}
    )
```

### 2. 利用缓存

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_search(question: str, chunk_type: str | None = None):
    """带缓存的检索"""
    filter_dict = {"chunk_type": chunk_type} if chunk_type else None
    return vector_store.similarity_search(
        query=question,
        k=5,
        filter=filter_dict
    )
```

### 3. 批量处理

```python
def batch_search(questions: list[str], chunk_type: str | None = None):
    """批量检索"""
    results = []
    
    filter_dict = {"chunk_type": chunk_type} if chunk_type else None
    
    for question in questions:
        result = vector_store.similarity_search(
            query=question,
            k=5,
            filter=filter_dict
        )
        results.append(result)
    
    return results
```

---

## 🔗 相关资源

- [功能使用指南](../features/README.md)
- [切片优化指南](../features/README.md)
- [API文档](../reference/README.md)

---

**维护者**: QueryMind Team  
**更新日期**: 2026-06-23
