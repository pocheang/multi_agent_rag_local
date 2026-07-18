# ⚡ 性能优化指南

> QueryMind 生产环境性能调优和最佳实践

---

## 📋 目录

- [系统架构优化](#系统架构优化)
- [数据库优化](#数据库优化)
- [模型配置优化](#模型配置优化)
- [检索性能优化](#检索性能优化)
- [缓存策略](#缓存策略)
- [并发和负载](#并发和负载)
- [监控和诊断](#监控和诊断)

---

## 系统架构优化

### 推荐生产架构

```
Internet
    │
┌───▼────────────┐
│  Load Balancer  │  Nginx/HAProxy
│   (SSL/TLS)     │
└───┬────────────┘
    │
┌───▼────────────┐
│  Frontend x3   │  React静态文件
└───┬────────────┘
    │
┌───▼────────────┐
│  API Gateway   │  FastAPI x4
└───┬────────────┘
    │
    ├──────┬──────────┬────────┐
    │      │          │        │
┌───▼──┐ ┌─▼──┐  ┌───▼───┐ ┌─▼────┐
│Chroma│ │Neo4j│  │Postgres│Redis│
└──────┘ └────┘  └───────┘ └─────┘
```

### 硬件配置建议

**小规模（<100用户）**:
- CPU: 8核心
- 内存: 16 GB
- 硬盘: 100 GB SSD
- 网络: 100 Mbps

**中规模（100-500用户）**:
- CPU: 16核心
- 内存: 32 GB
- 硬盘: 500 GB NVMe SSD
- 网络: 1 Gbps

**大规模（>500用户）**:
- CPU: 32核心+
- 内存: 64 GB+
- 硬盘: 1 TB+ NVMe SSD
- 网络: 10 Gbps

---

## 数据库优化

### PostgreSQL 优化

**配置文件 (postgresql.conf)**:

```ini
# 内存配置（基于32GB内存）
shared_buffers = 8GB              # 25% 物理内存
effective_cache_size = 24GB       # 75% 物理内存
work_mem = 64MB                   # 单个操作内存
maintenance_work_mem = 2GB        # 维护操作内存

# 连接配置
max_connections = 200             # 最大连接数

# 写入优化
wal_buffers = 16MB
checkpoint_completion_target = 0.9
max_wal_size = 4GB
min_wal_size = 1GB

# 查询优化
random_page_cost = 1.1            # SSD优化
effective_io_concurrency = 200    # SSD并发

# 日志配置
log_min_duration_statement = 1000  # 记录慢查询(>1s)
```

**连接池配置**:

```python
# app/core/config.py
DATABASE_POOL_SIZE = 20           # 连接池大小
DATABASE_MAX_OVERFLOW = 40        # 最大溢出连接
DATABASE_POOL_TIMEOUT = 30        # 连接超时(秒)
DATABASE_POOL_RECYCLE = 3600      # 连接回收时间(秒)
```

**索引优化**:

```sql
-- 用户查询索引
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);

-- 文档查询索引
CREATE INDEX idx_documents_user_id ON documents(user_id);
CREATE INDEX idx_documents_created_at ON documents(created_at DESC);

-- 会话查询索引
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_created_at ON sessions(created_at DESC);

-- 分析表统计信息
ANALYZE;
```

### ChromaDB 优化

**配置优化**:

```python
# app/services/chroma_service.py
import chromadb
from chromadb.config import Settings

client = chromadb.Client(Settings(
    chroma_db_impl="duckdb+parquet",
    persist_directory="./data/chroma",
    anonymized_telemetry=False,
    allow_reset=True
))

# 批量插入优化
BATCH_SIZE = 100  # 每批100条记录
```

**向量索引优化**:

```python
# 使用HNSW索引（更快）
collection = client.get_or_create_collection(
    name="documents",
    metadata={
        "hnsw:space": "cosine",
        "hnsw:construction_ef": 200,  # 构建时精度
        "hnsw:search_ef": 100,        # 搜索时精度
        "hnsw:M": 16                  # 连接数
    }
)
```

### Neo4j 优化（可选）

**配置文件 (neo4j.conf)**:

```properties
# 内存配置
dbms.memory.heap.initial_size=4G
dbms.memory.heap.max_size=4G
dbms.memory.pagecache.size=8G

# 查询优化
dbms.query_cache_size=1000
cypher.min_replan_interval=10s
```

---

## 模型配置优化

### 选择合适的模型

**场景化选择**:

```bash
# 高性能生产环境
OPENAI_CHAT_MODEL=gpt-5.5
ANTHROPIC_CHAT_MODEL=claude-opus-4-8

# 平衡性能和成本
OPENAI_CHAT_MODEL=gpt-4-turbo
OLLAMA_CHAT_MODEL=qwen3:14b

# 低成本高吞吐
MODEL_BACKEND=ollama
OLLAMA_CHAT_MODEL=qwen3:7b
```

### 并发请求优化

```python
# app/core/config.py

# LLM并发配置
LLM_MAX_CONCURRENT_REQUESTS = 10   # 同时最多10个LLM请求
LLM_REQUEST_TIMEOUT = 60           # 单个请求超时(秒)
LLM_RETRY_MAX_ATTEMPTS = 3         # 失败重试次数
LLM_RETRY_DELAY = 1                # 重试延迟(秒)
```

### 响应流式传输

```python
# 启用流式响应，降低首字节时间
STREAM_RESPONSE = True
STREAM_CHUNK_SIZE = 64  # 每次发送64字节
```

---

## 检索性能优化

### 检索参数调优

**高精度场景**:

```bash
# .env
TOP_K=5
MAX_CONTEXT_CHUNKS=8
VECTOR_TOP_K=10
BM25_TOP_K=10
ENABLE_RERANKER=true
RERANKER_TOP_N=5
VECTOR_SIMILARITY_THRESHOLD=0.25
```

**高性能场景**:

```bash
# .env
TOP_K=3
MAX_CONTEXT_CHUNKS=4
VECTOR_TOP_K=6
BM25_TOP_K=6
ENABLE_RERANKER=false  # 禁用重排序
VECTOR_SIMILARITY_THRESHOLD=0.20
```

### 混合检索权重调优

```bash
# 向量检索权重（语义理解）
HYBRID_VECTOR_WEIGHT=0.7

# BM25权重（关键词匹配）
HYBRID_BM25_WEIGHT=0.3

# RRF融合参数
HYBRID_RRF_K=60
```

**调优建议**:
- 中文查询：增加BM25权重至0.4-0.5
- 英文查询：保持向量权重0.7+
- 专有名词多：增加BM25权重

### 文档分块优化

```bash
# 父文档分块（用于检索）
PARENT_CHUNK_SIZE=1500
PARENT_CHUNK_OVERLAP=200

# 子文档分块（用于上下文）
CHILD_CHUNK_SIZE=600
CHILD_CHUNK_OVERLAP=120
```

**优化原则**:
- 技术文档：较小分块（500-800）
- 长篇文章：较大分块（1200-1500）
- 重叠建议：15-20%分块大小

---

## 缓存策略

### Redis 缓存配置

**安装和配置**:

```bash
# 安装Redis
sudo apt install redis-server

# 配置
sudo vim /etc/redis/redis.conf

# 内存限制
maxmemory 4gb
maxmemory-policy allkeys-lru  # LRU淘汰策略

# 持久化
save 900 1
save 300 10
save 60 10000
```

**应用配置**:

```bash
# .env
REDIS_URL=redis://localhost:6379/0
CACHE_ENABLED=true
CACHE_TTL=3600              # 缓存1小时
QUERY_CACHE_TTL=1800        # 查询缓存30分钟
EMBEDDING_CACHE_TTL=86400   # Embedding缓存24小时
```

### 多层缓存架构

```python
# 三级缓存
# L1: 进程内存缓存（最快）
# L2: Redis缓存（快）
# L3: 数据库（慢）

from functools import lru_cache

# L1缓存示例
@lru_cache(maxsize=1000)
def get_embedding_cached(text: str):
    # 先查Redis(L2)，再查数据库(L3)
    return get_embedding(text)
```

### 缓存预热

```python
# scripts/warmup_cache.py
import requests

# 常见查询预热
common_queries = [
    "什么是RAG？",
    "如何使用QueryMind？",
    "支持哪些模型？"
]

for query in common_queries:
    requests.post("http://localhost:8000/api/chat/query", 
                  json={"query": query})
```

---

## 并发和负载

### Uvicorn Worker 配置

```bash
# 计算Worker数量
# 公式: (CPU核心数 * 2) + 1

# 16核服务器
uvicorn app.api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 33 \
  --worker-class uvicorn.workers.UvicornWorker \
  --limit-concurrency 2000 \
  --backlog 4096 \
  --timeout-keep-alive 5
```

### Nginx 负载均衡

```nginx
upstream querymind_backend {
    least_conn;  # 最少连接算法
    
    server 127.0.0.1:8000 weight=1 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8001 weight=1 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8002 weight=1 max_fails=3 fail_timeout=30s;
    
    keepalive 32;
}

server {
    listen 80;
    server_name querymind.example.com;
    
    location /api {
        proxy_pass http://querymind_backend;
        proxy_http_version 1.1;
        
        # 连接复用
        proxy_set_header Connection "";
        
        # 超时配置
        proxy_connect_timeout 10s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # 缓冲配置
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }
}
```

### 限流配置

```python
# app/api/middleware/rate_limit.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute", "1000/hour"]
)

# 针对不同端点的限流
@app.post("/api/chat/query")
@limiter.limit("30/minute")  # 查询接口更严格
async def chat_query():
    pass

@app.get("/api/documents")
@limiter.limit("100/minute")  # 文档接口较宽松
async def list_documents():
    pass
```

---

## 监控和诊断

### Prometheus + Grafana

**安装Prometheus**:

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'querymind'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

**应用埋点**:

```python
# app/api/main.py
from prometheus_client import Counter, Histogram, Gauge

# 请求计数
request_count = Counter('querymind_requests_total', 'Total requests')

# 响应时间
response_time = Histogram('querymind_response_seconds', 'Response time')

# 当前连接数
active_connections = Gauge('querymind_active_connections', 'Active connections')
```

### 日志监控

```python
# app/core/logging_config.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)

# 慢查询日志
if response_time > 3.0:
    logger.warning(f"Slow query: {query} took {response_time}s")
```

### 性能分析

```bash
# 使用cProfile分析
python -m cProfile -o profile.stats app/api/main.py

# 可视化分析
pip install snakeviz
snakeviz profile.stats

# 内存分析
pip install memory_profiler
python -m memory_profiler app/api/main.py
```

---

## 性能基准测试

### 压力测试

```bash
# 使用Apache Bench
ab -n 1000 -c 100 -p query.json -T application/json \
   http://localhost:8000/api/chat/query

# 使用Locust
pip install locust
locust -f tests/load/locustfile.py --host http://localhost:8000
```

### 目标性能指标

| 指标 | 目标值 | 优秀值 |
|------|--------|--------|
| **响应时间(P50)** | < 2s | < 1s |
| **响应时间(P95)** | < 5s | < 3s |
| **吞吐量** | > 50 req/s | > 100 req/s |
| **错误率** | < 1% | < 0.1% |
| **可用性** | > 99% | > 99.9% |

---

## 快速优化清单

### 立即可做的优化

- [ ] 启用Redis缓存
- [ ] 调整检索参数（减少TOP_K）
- [ ] 使用更快的模型（本地Ollama）
- [ ] 启用流式响应
- [ ] 配置数据库连接池
- [ ] 添加Nginx反向代理
- [ ] 启用Gzip压缩

### 进阶优化

- [ ] 配置负载均衡
- [ ] 优化数据库索引
- [ ] 实现多级缓存
- [ ] 配置CDN加速静态资源
- [ ] 实现查询结果缓存
- [ ] 优化向量索引参数
- [ ] 配置自动扩缩容

---

## 🔗 相关文档

- [部署指南](deployment.md)
- [配置指南](../zh-CN/README.md)
- [故障排查](../zh-CN/README.md)
- [FAQ](../reference/faq.md)

---

<div align="center">

**持续优化，追求极致性能** ⚡

[返回主页](./README.md)

</div>
