# 检索系统 (Retrieval System)

本文档详细介绍 QueryMind（智询） 系统的混合检索架构、算法实现和优化策略。

## 目录

- [快速参考](#快速参考)
- [概述](#概述)
- [混合检索架构](#混合检索架构)
- [向量检索](#向量检索)
- [BM25 检索](#bm25-检索)
- [倒数排名融合 (RRF)](#倒数排名融合-rrf)
- [重排序系统](#重排序系统)
- [查询优化](#查询优化)
- [缓存策略](#缓存策略)
- [性能调优](#性能调优)

---

## 快速参考

### 检索配置速查

| 参数 | 默认值 | 说明 | 调优建议 |
|------|-------|------|---------|
| `TOP_K` | 4 | 最终返回数量 | 增大提高召回率 |
| `VECTOR_TOP_K` | 6 | 向量检索数量 | 通常设为 TOP_K * 2 |
| `BM25_TOP_K` | 6 | BM25 检索数量 | 与 VECTOR_TOP_K 相同 |
| `HYBRID_RRF_K` | 60 | RRF 融合常数 | 一般不需要调整 |
| `ENABLE_RERANKER` | true | 启用重排序 | 提高精度但增加延迟 |
| `RERANKER_TOP_N` | 5 | 重排序返回数量 | 不超过 TOP_K |
| `VECTOR_SIMILARITY_THRESHOLD` | 0.2 | 相似度阈值 | 提高过滤低质量结果 |

### 检索流程速查

```python
# 完整的混合检索流程
def hybrid_retrieve(query: str, top_k: int = 10) -> list[dict]:
    # 1. 查询预处理
    queries = preprocess_query(query)
    
    # 2. 并行检索
    vector_results = vector_search(queries, top_k=20)
    bm25_results = bm25_search(queries, top_k=20)
    
    # 3. RRF 融合
    fused = rrf_fusion(vector_results, bm25_results, k=60)
    
    # 4. 重排序
    if ENABLE_RERANKER:
        reranked = rerank(query, fused[:top_k*2], top_n=top_k)
    else:
        reranked = fused[:top_k]
    
    return reranked
```

### RRF 算法速查

```python
# 倒数排名融合 (Reciprocal Rank Fusion)
def rrf_score(rank: int, k: int = 60) -> float:
    """
    计算 RRF 分数
    rank: 文档排名 (1-based)
    k: 常数，通常取 60
    """
    return 1.0 / (k + rank)

# 示例
# 文档在向量检索中排名第1，BM25中排名第3
score = rrf_score(1, 60) + rrf_score(3, 60)  # 0.0164 + 0.0159 = 0.0323
```

### 常用操作速查

**向量检索**:
```python
from app.retrievers.vector_store import VectorStore

vector_store = VectorStore()
results = vector_store.search(
    query="什么是 RAG",
    top_k=10,
    filter={"user_id": "user_123"}
)
```

**BM25 检索**:
```python
from app.retrievers.bm25_retriever import BM25Retriever

bm25 = BM25Retriever.from_corpus(corpus)
results = bm25.search(
    query="RAG 系统",
    top_k=10
)
```

**重排序**:
```python
from app.retrievers.reranker import Reranker

reranker = Reranker()
reranked = reranker.rerank(
    query="什么是 RAG",
    candidates=candidates,
    top_n=5
)
```

### 性能调优速查

**提高召回率**:
- ✅ 增大 `TOP_K`、`VECTOR_TOP_K`、`BM25_TOP_K`
- ✅ 降低 `VECTOR_SIMILARITY_THRESHOLD`
- ✅ 启用查询扩展

**提高精确率**:
- ✅ 启用 `ENABLE_RERANKER`
- ✅ 提高 `VECTOR_SIMILARITY_THRESHOLD`
- ✅ 使用更好的嵌入模型

**提高速度**:
- ✅ 减小 `TOP_K`
- ✅ 禁用 `ENABLE_RERANKER`
- ✅ 启用缓存

### 检索策略对比

| 策略 | 优势 | 劣势 | 适用场景 |
|------|------|------|---------|
| **仅向量** | 语义理解好 | 对罕见词不敏感 | 自然语言问答 |
| **仅 BM25** | 精确匹配强 | 无语义理解 | 关键词搜索 |
| **混合 (RRF)** | 结合两者优势 | 计算开销稍大 | 通用场景（推荐） |
| **+重排序** | 精度最高 | 延迟较高 | 对精度要求高 |

### 常见问题速查

**Q: 检索结果太少？**
- 降低 `VECTOR_SIMILARITY_THRESHOLD`
- 增大 `TOP_K`
- 检查文档是否已索引

**Q: 检索结果不相关？**
- 启用 `ENABLE_RERANKER`
- 提高 `VECTOR_SIMILARITY_THRESHOLD`
- 检查嵌入模型是否合适

**Q: 检索速度慢？**
- 减小 `TOP_K`
- 禁用重排序
- 启用缓存

**Q: 中文检索效果差？**
- 启用 `BM25_USE_CHINESE_TOKENIZER=true`
- 使用中文友好的嵌入模型（如 bge-m3）
- 添加自定义词典

---

## 概述

系统采用**混合检索**策略，结合向量检索（语义搜索）和 BM25 检索（关键词匹配）的优势，通过倒数排名融合（RRF）和重排序提高检索质量。

### 检索管道

```
用户查询
    │
    ├─→ 查询预处理
    │     ├─ 语言检测
    │     ├─ 中文分词
    │     ├─ 查询重写
    │     └─ 查询扩展
    │
    ├─→ 并行检索
    │     ├─ 向量检索 (ChromaDB)
    │     │   └─→ 余弦相似度搜索
    │     │
    │     └─ BM25 检索 (rank-bm25)
    │           └─→ TF-IDF + BM25 算法
    │
    ├─→ 倒数排名融合 (RRF)
    │     └─→ 合并和去重
    │
    ├─→ 重排序 (可选)
    │     └─→ Cross-Encoder (bge-reranker-v2-m3)
    │
    └─→ 最终结果
```

### 核心优势

| 检索方式 | 优势 | 劣势 |
|---------|------|------|
| **向量检索** | 语义理解、跨语言、同义词 | 对罕见词不敏感 |
| **BM25 检索** | 精确匹配、罕见词、专有名词 | 无语义理解 |
| **混合检索** | 结合两者优势 | 计算开销稍大 |

---

## 混合检索架构

### 检索流程代码

```python
async def hybrid_retrieve(
    query: str,
    user_id: str,
    top_k: int = 10
) -> list[dict]:
    """
    混合检索主函数
    
    Args:
        query: 用户查询
        user_id: 用户 ID（用于过滤）
        top_k: 返回结果数量
    
    Returns:
        list[dict]: 检索到的文档列表
    """
    # 1. 查询预处理
    processed_queries = preprocess_query(query)
    
    # 2. 并行执行向量和 BM25 检索
    vector_results, bm25_results = await asyncio.gather(
        vector_search(processed_queries, user_id, top_k=20),
        bm25_search(processed_queries, user_id, top_k=20)
    )
    
    # 3. RRF 融合
    fused_results = reciprocal_rank_fusion(
        vector_results,
        bm25_results,
        k=60
    )
    
    # 4. 重排序（如果启用）
    if ENABLE_RERANKER:
        final_results = rerank(query, fused_results[:top_k * 2], top_n=top_k)
    else:
        final_results = fused_results[:top_k]
    
    return final_results
```

---

## 向量检索

### ChromaDB 配置

**存储位置**: `data/chroma_db/`

**集合配置**:
```python
collection = chroma_client.get_or_create_collection(
    name="local_rag_collection",
    metadata={"hnsw:space": "cosine"},  # 余弦相似度
    embedding_function=embedding_function
)
```

### 嵌入模型

| 提供商 | 模型 | 维度 | 说明 |
|-------|------|------|------|
| OpenAI | text-embedding-3-small | 1536 | 性价比高 |
| OpenAI | text-embedding-3-large | 3072 | 最高质量 |
| Ollama | nomic-embed-text | 768 | 本地部署 |
| Ollama | bge-m3 | 1024 | 中文友好 |

### 向量检索实现

```python
def vector_search(
    query: str,
    user_id: str,
    top_k: int = 10,
    similarity_threshold: float = 0.2
) -> list[dict]:
    """
    向量相似度搜索
    
    Args:
        query: 查询文本
        user_id: 用户 ID
        top_k: 返回数量
        similarity_threshold: 相似度阈值
    
    Returns:
        list[dict]: 检索结果
    """
    # 生成查询向量
    query_embedding = embedding_model.embed_query(query)
    
    # 构建元数据过滤
    where_filter = {"user_id": user_id}
    
    # 执行相似度搜索
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where_filter,
        include=["documents", "metadatas", "distances"]
    )
    
    # 转换为标准格式
    documents = []
    for i, doc in enumerate(results["documents"][0]):
        distance = results["distances"][0][i]
        similarity = 1 - distance  # 余弦距离转相似度
        
        if similarity >= similarity_threshold:
            documents.append({
                "text": doc,
                "metadata": results["metadatas"][0][i],
                "score": similarity,
                "source": "vector"
            })
    
    return documents
```

### 元数据过滤

支持的过滤条件：

```python
# 按用户过滤
where_filter = {"user_id": user_id}

# 按来源过滤
where_filter = {"source": {"$in": ["doc1.pdf", "doc2.pdf"]}}

# 按日期范围过滤
where_filter = {
    "timestamp": {"$gte": "2026-01-01", "$lte": "2026-12-31"}
}

# 组合条件
where_filter = {
    "$and": [
        {"user_id": user_id},
        {"source": {"$in": allowed_sources}}
    ]
}
```

---

## BM25 检索

### BM25 算法

BM25 (Best Matching 25) 是一种基于概率的排序函数，用于估计文档与查询的相关性。

**公式**:
```
BM25(D, Q) = Σ IDF(qi) * (f(qi, D) * (k1 + 1)) / (f(qi, D) + k1 * (1 - b + b * |D| / avgdl))

其中:
- IDF(qi): 逆文档频率
- f(qi, D): 词 qi 在文档 D 中的频率
- |D|: 文档长度
- avgdl: 平均文档长度
- k1: 词频饱和度参数 (通常 1.2-2.0)
- b: 长度归一化参数 (通常 0.75)
```

### BM25 实现

```python
from rank_bm25 import BM25Okapi
import jieba

class BM25Retriever:
    def __init__(self, corpus: list[dict]):
        """
        初始化 BM25 检索器
        
        Args:
            corpus: 文档语料库
        """
        self.corpus = corpus
        
        # 中文分词
        self.tokenized_corpus = [
            list(jieba.cut(doc["text"]))
            for doc in corpus
        ]
        
        # 初始化 BM25
        self.bm25 = BM25Okapi(
            self.tokenized_corpus,
            k1=1.5,  # 词频饱和度
            b=0.75   # 长度归一化
        )
    
    def search(
        self,
        query: str,
        user_id: str,
        top_k: int = 10
    ) -> list[dict]:
        """
        BM25 检索
        
        Args:
            query: 查询文本
            user_id: 用户 ID
            top_k: 返回数量
        
        Returns:
            list[dict]: 检索结果
        """
        # 查询分词
        tokenized_query = list(jieba.cut(query))
        
        # 计算 BM25 分数
        scores = self.bm25.get_scores(tokenized_query)
        
        # 获取 top-k 索引
        top_indices = scores.argsort()[-top_k:][::-1]
        
        # 过滤和构建结果
        results = []
        for idx in top_indices:
            doc = self.corpus[idx]
            
            # 用户过滤
            if doc.get("metadata", {}).get("user_id") != user_id:
                continue
            
            results.append({
                "text": doc["text"],
                "metadata": doc["metadata"],
                "score": float(scores[idx]),
                "source": "bm25"
            })
        
        return results[:top_k]
```

### 中文分词优化

```python
import jieba

# 加载自定义词典
jieba.load_userdict("custom_dict.txt")

# 添加停用词
stopwords = set(["的", "了", "在", "是", "我", "有", "和"])

def tokenize_chinese(text: str) -> list[str]:
    """
    中文分词，去除停用词
    
    Args:
        text: 输入文本
    
    Returns:
        list[str]: 分词结果
    """
    tokens = jieba.cut(text)
    return [t for t in tokens if t not in stopwords and t.strip()]
```

---

## 倒数排名融合 (RRF)

### RRF 算法

RRF 通过排名而非绝对分数融合多个检索器的结果，对不同分数尺度不敏感。

**公式**:
```
RRF_score(d) = Σ 1 / (k + rank_i(d))

其中:
- rank_i(d): 文档 d 在第 i 个检索器中的排名
- k: 常数，通常取 60
```

### RRF 实现

```python
def reciprocal_rank_fusion(
    vector_results: list[dict],
    bm25_results: list[dict],
    k: int = 60
) -> list[dict]:
    """
    倒数排名融合
    
    Args:
        vector_results: 向量检索结果
        bm25_results: BM25 检索结果
        k: RRF 常数
    
    Returns:
        list[dict]: 融合后的结果
    """
    from collections import defaultdict
    
    # 用于累积分数
    scores = defaultdict(float)
    doc_map = {}
    
    # 处理向量检索结果
    for rank, doc in enumerate(vector_results, start=1):
        doc_id = get_doc_id(doc)
        scores[doc_id] += 1.0 / (k + rank)
        if doc_id not in doc_map:
            doc_map[doc_id] = doc
    
    # 处理 BM25 检索结果
    for rank, doc in enumerate(bm25_results, start=1):
        doc_id = get_doc_id(doc)
        scores[doc_id] += 1.0 / (k + rank)
        if doc_id not in doc_map:
            doc_map[doc_id] = doc
    
    # 构建融合结果
    fused = []
    for doc_id, score in scores.items():
        doc = dict(doc_map[doc_id])
        doc["hybrid_score"] = score
        fused.append(doc)
    
    # 按 RRF 分数排序
    fused.sort(key=lambda x: x["hybrid_score"], reverse=True)
    
    return fused


def get_doc_id(doc: dict) -> str:
    """
    生成文档唯一 ID
    
    Args:
        doc: 文档字典
    
    Returns:
        str: 文档 ID
    """
    metadata = doc.get("metadata", {})
    source = metadata.get("source", "")
    chunk_idx = metadata.get("chunk_index", "")
    
    if source:
        return f"{source}_{chunk_idx}"
    
    # 回退到文本哈希
    text = doc.get("text", "")
    return f"text_{hash(text)}"
```

### RRF 参数调优

| 参数 k | 效果 | 适用场景 |
|-------|------|---------|
| **20-40** | 前排文档影响更大 | 高质量检索器 |
| **60** (默认) | 平衡 | 通用场景 |
| **80-100** | 后排文档也有机会 | 检索器质量参差 |

---

## 重排序系统

### Cross-Encoder 模型

**模型**: BAAI/bge-reranker-v2-m3

**工作原理**:
- 将查询和文档一起输入模型
- 输出相关性分数（0-1）
- 比向量检索更精确，但更慢

### 重排序实现

```python
from sentence_transformers import CrossEncoder

class Reranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        """
        初始化重排序器
        
        Args:
            model_name: Cross-Encoder 模型名称
        """
        self.model = CrossEncoder(
            model_name,
            trust_remote_code=True
        )
    
    def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_n: int = 5
    ) -> list[dict]:
        """
        重排序候选文档
        
        Args:
            query: 查询文本
            candidates: 候选文档列表
            top_n: 返回数量
        
        Returns:
            list[dict]: 重排序后的结果
        """
        if not candidates:
            return []
        
        # 构建查询-文档对
        pairs = [(query, doc["text"]) for doc in candidates]
        
        # 批量预测相关性分数
        scores = self.model.predict(pairs)
        
        # 添加重排序分数
        for doc, score in zip(candidates, scores):
            doc["rerank_score"] = float(score)
        
        # 按重排序分数排序
        reranked = sorted(
            candidates,
            key=lambda x: x["rerank_score"],
            reverse=True
        )
        
        return reranked[:top_n]
```

### 词法回退策略

当重排序模型不可用时，使用词法匹配作为回退：

```python
def lexical_fallback_rerank(
    query: str,
    candidates: list[dict],
    top_n: int = 5
) -> list[dict]:
    """
    词法匹配回退重排序
    
    Args:
        query: 查询文本
        candidates: 候选文档
        top_n: 返回数量
    
    Returns:
        list[dict]: 重排序结果
    """
    import re
    
    # 提取查询词
    query_tokens = set(re.findall(r'\w+', query.lower()))
    
    # 计算词法重叠分数
    for doc in candidates:
        text = doc["text"].lower()
        doc_tokens = set(re.findall(r'\w+', text))
        
        # 计算重叠率
        overlap = len(query_tokens & doc_tokens)
        total = len(query_tokens)
        
        overlap_score = overlap / total if total > 0 else 0
        
        # 结合混合分数
        hybrid_score = doc.get("hybrid_score", 0)
        doc["rerank_score"] = 0.7 * hybrid_score + 0.3 * overlap_score
    
    # 排序
    reranked = sorted(
        candidates,
        key=lambda x: x["rerank_score"],
        reverse=True
    )
    
    return reranked[:top_n]
```

---

## 查询优化

### 查询重写

**目的**: 扩展查询以提高召回率

**策略**:

1. **同义词扩展**:
```python
synonyms = {
    "RAG": ["检索增强生成", "Retrieval Augmented Generation"],
    "LLM": ["大语言模型", "Large Language Model"]
}

def expand_with_synonyms(query: str) -> list[str]:
    queries = [query]
    for term, syns in synonyms.items():
        if term in query:
            for syn in syns:
                queries.append(query.replace(term, syn))
    return queries
```

2. **查询分解**:
```python
def decompose_query(query: str) -> list[str]:
    """
    将复杂查询分解为多个子查询
    
    示例:
    "RAG 的优势和劣势" 
    → ["RAG 的优势", "RAG 的劣势"]
    """
    # 使用 LLM 进行智能分解
    prompt = f"将以下查询分解为多个子查询：{query}"
    subqueries = llm.generate(prompt)
    return subqueries
```

3. **查询去重**:
```python
def deduplicate_queries(queries: list[str]) -> list[str]:
    """
    去除重复或高度相似的查询
    
    Args:
        queries: 查询列表
    
    Returns:
        list[str]: 去重后的查询
    """
    unique_queries = []
    seen_embeddings = []
    
    for query in queries:
        # 生成嵌入
        emb = embedding_model.embed_query(query)
        
        # 检查相似度
        is_duplicate = False
        for seen_emb in seen_embeddings:
            similarity = cosine_similarity(emb, seen_emb)
            if similarity > 0.95:  # 高度相似
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_queries.append(query)
            seen_embeddings.append(emb)
    
    return unique_queries
```

---

## 缓存策略

### 多层缓存

```python
from functools import lru_cache
from redis import Redis

# 内存缓存（LRU）
@lru_cache(maxsize=256)
def cached_embedding(text: str) -> list[float]:
    return embedding_model.embed_query(text)

# Redis 缓存
redis_client = Redis.from_url("redis://localhost:6379")

def cached_retrieve(query: str, user_id: str, ttl: int = 300):
    """
    带 Redis 缓存的检索
    
    Args:
        query: 查询文本
        user_id: 用户 ID
        ttl: 缓存时间（秒）
    
    Returns:
        list[dict]: 检索结果
    """
    cache_key = f"retrieve:{user_id}:{hash(query)}"
    
    # 尝试从缓存获取
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # 执行检索
    results = hybrid_retrieve(query, user_id)
    
    # 存入缓存
    redis_client.setex(
        cache_key,
        ttl,
        json.dumps(results)
    )
    
    return results
```

### 自适应 TTL

```python
def adaptive_ttl(query: str, tier: str) -> int:
    """
    根据查询复杂度和层级决定缓存时间
    
    Args:
        query: 查询文本
        tier: fast | balanced | deep
    
    Returns:
        int: TTL（秒）
    """
    ttl_map = {
        "fast": 300,      # 简单查询，缓存 5 分钟
        "balanced": 120,  # 平衡查询，缓存 2 分钟
        "deep": 60        # 复杂查询，缓存 1 分钟
    }
    return ttl_map.get(tier, 120)
```

---

## 性能调优

### 检索参数调优

| 参数 | 默认值 | 说明 | 调优建议 |
|------|-------|------|---------|
| `VECTOR_TOP_K` | 10 | 向量检索数量 | 增大可提高召回率，但变慢 |
| `BM25_TOP_K` | 10 | BM25 检索数量 | 与 VECTOR_TOP_K 保持一致 |
| `RERANKER_TOP_N` | 5 | 重排序返回数量 | 不超过 VECTOR_TOP_K |
| `VECTOR_SIMILARITY_THRESHOLD` | 0.2 | 向量相似度阈值 | 提高可过滤低质量结果 |
| `HYBRID_RRF_K` | 60 | RRF 常数 | 通常不需要调整 |

### 分层检索策略

```python
tier_configs = {
    "fast": {
        "vector_top_k": 5,
        "bm25_top_k": 5,
        "enable_reranker": False,
        "enable_query_rewrite": False
    },
    "balanced": {
        "vector_top_k": 10,
        "bm25_top_k": 10,
        "enable_reranker": True,
        "reranker_top_n": 5
    },
    "deep": {
        "vector_top_k": 20,
        "bm25_top_k": 20,
        "enable_reranker": True,
        "reranker_top_n": 10,
        "enable_query_rewrite": True
    }
}
```

### 批处理优化

```python
async def batch_retrieve(
    queries: list[str],
    user_id: str,
    batch_size: int = 10
) -> list[list[dict]]:
    """
    批量检索，提高吞吐量
    
    Args:
        queries: 查询列表
        user_id: 用户 ID
        batch_size: 批大小
    
    Returns:
        list[list[dict]]: 每个查询的结果
    """
    results = []
    
    for i in range(0, len(queries), batch_size):
        batch = queries[i:i + batch_size]
        
        # 并行处理批次
        batch_results = await asyncio.gather(*[
            hybrid_retrieve(q, user_id)
            for q in batch
        ])
        
        results.extend(batch_results)
    
    return results
```

---

## 评估指标

### 检索质量指标

```python
def evaluate_retrieval(
    predictions: list[list[str]],
    ground_truth: list[list[str]]
) -> dict:
    """
    评估检索质量
    
    Args:
        predictions: 预测结果
        ground_truth: 真实标注
    
    Returns:
        dict: 评估指标
    """
    precisions = []
    recalls = []
    
    for pred, truth in zip(predictions, ground_truth):
        pred_set = set(pred)
        truth_set = set(truth)
        
        # 计算精确率和召回率
        tp = len(pred_set & truth_set)
        precision = tp / len(pred_set) if pred_set else 0
        recall = tp / len(truth_set) if truth_set else 0
        
        precisions.append(precision)
        recalls.append(recall)
    
    # 计算平均值
    avg_precision = sum(precisions) / len(precisions)
    avg_recall = sum(recalls) / len(recalls)
    f1 = 2 * (avg_precision * avg_recall) / (avg_precision + avg_recall) if (avg_precision + avg_recall) > 0 else 0
    
    return {
        "precision": avg_precision,
        "recall": avg_recall,
        "f1": f1
    }
```

---

## 最佳实践

1. **平衡召回率和精确率**: 调整 `top_k` 和相似度阈值
2. **使用分层策略**: 简单查询用快速模式，复杂查询用深度模式
3. **启用缓存**: 减少重复计算
4. **监控性能**: 追踪检索延迟和质量指标
5. **定期更新索引**: 保持数据新鲜度
6. **A/B 测试**: 对比不同检索配置的效果

---

## 下一步

了解检索系统后，建议继续阅读：

1. **[数据存储](./DATA_STORAGE.md)** - ChromaDB、Neo4j 使用详解
2. **[API 开发](./API_DEVELOPMENT.md)** - 如何集成检索系统
3. **[性能优化](../../PERFORMANCE_OPTIMIZATION.md)** - 全面的性能调优

---

**更新日期**: 2026-06-19  
**文档版本**: 1.0
