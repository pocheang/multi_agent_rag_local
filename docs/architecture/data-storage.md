# 数据存储 (Data Storage)

本文档详细介绍 QueryMind（智询） 系统的数据存储架构，包括 ChromaDB、Neo4j 和 SQLite 的使用和管理。

## 目录

- [快速参考](#快速参考)
- [概述](#概述)
- [ChromaDB 向量存储](#chromadb-向量存储)
- [Neo4j 知识图谱](#neo4j-知识图谱)
- [SQLite 应用数据库](#sqlite-应用数据库)
- [Redis 缓存](#redis-缓存)
- [数据模型](#数据模型)
- [数据迁移](#数据迁移)
- [备份和恢复](#备份和恢复)
- [性能优化](#性能优化)

---

## 快速参考

### 数据库速查

| 数据库 | 用途 | 端口 | 连接 | 数据位置 |
|--------|------|------|------|---------|
| **ChromaDB** | 向量存储 | - | 本地客户端 | `data/chroma_db/` |
| **Neo4j** | 知识图谱 | 7474/7687 | Bolt | Docker 容器 |
| **SQLite** | 应用数据 | - | 文件 | `data/app.db` |
| **Redis** | 缓存 | 6379 | TCP | 内存 |

### ChromaDB 常用操作

```python
import chromadb

# 1. 创建客户端
client = chromadb.PersistentClient(path="./data/chroma_db")

# 2. 获取集合
collection = client.get_or_create_collection("local_rag_collection")

# 3. 插入文档
collection.add(
    documents=["文本内容"],
    metadatas=[{"source": "doc.pdf"}],
    embeddings=[[0.1, 0.2, ...]],
    ids=["doc_1"]
)

# 4. 查询
results = collection.query(
    query_embeddings=[[0.1, 0.2, ...]],
    n_results=10,
    where={"user_id": "user_1"}
)

# 5. 删除
collection.delete(ids=["doc_1"])
```

### Neo4j Cypher 速查

```cypher
-- 创建节点
CREATE (e:Entity {name: "RAG", type: "Concept"})

-- 创建关系
MATCH (a:Entity {name: "RAG"})
MATCH (b:Entity {name: "向量数据库"})
CREATE (a)-[:USES]->(b)

-- 查询节点
MATCH (e:Entity {name: "RAG"})
RETURN e

-- 查询邻居
MATCH (e:Entity {name: "RAG"})-[r]-(other)
RETURN type(r), other.name

-- 路径查询
MATCH path = (a:Entity {name: "RAG"})-[*1..3]-(b:Entity {name: "LLM"})
RETURN path
LIMIT 10

-- 删除节点
MATCH (e:Entity {name: "RAG"})
DELETE e

-- 删除关系
MATCH (a)-[r:USES]->(b)
DELETE r
```

### SQLite 常用操作

```python
import sqlite3

# 1. 连接数据库
conn = sqlite3.connect("data/app.db")
conn.row_factory = sqlite3.Row

# 2. 查询
cursor = conn.cursor()
cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
user = cursor.fetchone()

# 3. 插入
cursor.execute(
    "INSERT INTO users (username, email) VALUES (?, ?)",
    (username, email)
)
conn.commit()

# 4. 更新
cursor.execute(
    "UPDATE users SET last_login = ? WHERE id = ?",
    (datetime.now(), user_id)
)
conn.commit()

# 5. 删除
cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
conn.commit()

# 6. 关闭
conn.close()
```

### 数据库连接速查

**ChromaDB**:
```python
from app.retrievers.vector_store import get_vector_store

vector_store = get_vector_store()
```

**Neo4j**:
```python
from app.graph.neo4j_client import Neo4jClient

client = Neo4jClient(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)
```

**SQLite**:
```python
from app.api.dependencies import get_db_connection

with get_db_connection() as conn:
    cursor = conn.cursor()
    # 执行操作
```

**Redis**:
```python
import redis

redis_client = redis.from_url("redis://localhost:6379/0")
```

### 元数据过滤速查

**ChromaDB 过滤**:
```python
# 等于
where = {"user_id": "user_1"}

# 包含
where = {"source": {"$in": ["doc1.pdf", "doc2.pdf"]}}

# 不等于
where = {"user_id": {"$ne": "user_1"}}

# 大于/小于
where = {"page": {"$gt": 10, "$lte": 20}}

# 逻辑与
where = {
    "$and": [
        {"user_id": "user_1"},
        {"doc_type": "pdf"}
    ]
}

# 逻辑或
where = {
    "$or": [
        {"doc_type": "pdf"},
        {"doc_type": "docx"}
    ]
}
```

### 备份命令速查

```bash
# ChromaDB 备份
cp -r data/chroma_db data/backups/chroma_$(date +%Y%m%d)

# Neo4j 备份（导出）
docker exec neo4j neo4j-admin dump \
    --database=neo4j \
    --to=/backups/neo4j_backup.dump

# Neo4j 恢复（导入）
docker exec neo4j neo4j-admin load \
    --from=/backups/neo4j_backup.dump \
    --database=neo4j \
    --force

# SQLite 备份
sqlite3 data/app.db ".backup data/backups/app_$(date +%Y%m%d).db"

# SQLite 恢复
cp data/backups/app_20260619.db data/app.db
```

### 性能优化速查

**ChromaDB**:
- 批量插入（每批 100-500 个文档）
- 使用元数据过滤减少搜索范围
- 定期清理旧数据

**Neo4j**:
```cypher
-- 创建索引
CREATE INDEX entity_name_index FOR (e:Entity) ON (e.name)

-- 查看执行计划
EXPLAIN MATCH (e:Entity {name: "RAG"}) RETURN e
```

**SQLite**:
```sql
-- 创建索引
CREATE INDEX idx_users_username ON users(username);

-- 启用 WAL 模式（提高并发）
PRAGMA journal_mode=WAL;

-- 分析查询性能
EXPLAIN QUERY PLAN SELECT * FROM users WHERE username = 'alice';
```

### 常见问题速查

**Q: ChromaDB 数据丢失？**
- 检查 `CHROMA_PERSIST_DIR` 配置
- 确保目录有写权限
- 检查磁盘空间

**Q: Neo4j 连接失败？**
```bash
# 检查 Neo4j 状态
docker-compose ps neo4j

# 查看日志
docker-compose logs neo4j

# 重启 Neo4j
docker-compose restart neo4j
```

**Q: SQLite 数据库锁定？**
- 启用 WAL 模式：`PRAGMA journal_mode=WAL`
- 减少长事务
- 使用连接池

**Q: 如何清空所有数据？**
```bash
# ChromaDB
rm -rf data/chroma_db

# Neo4j
docker-compose down -v
docker-compose up -d neo4j

# SQLite
rm data/app.db
# 重新运行应用会自动创建
```

---

## 概述

系统采用**多数据库架构**，每种数据库负责特定类型的数据存储：

| 数据库 | 用途 | 存储内容 | 持久化 |
|-------|------|---------|--------|
| **ChromaDB** | 向量存储 | 文档嵌入向量、元数据 | 本地文件 |
| **Neo4j** | 知识图谱 | 实体、关系、属性 | Docker 容器 |
| **SQLite** | 应用数据 | 用户、会话、文档元数据 | 本地文件 |
| **Redis** | 缓存 | 检索结果、会话状态 | 内存+持久化 |

### 数据流

```
文档上传
    │
    ├─→ 文本提取 → 分块 → 嵌入 → ChromaDB (向量)
    ├─→ 实体抽取 → 关系抽取 → Neo4j (图)
    └─→ 元数据存储 → SQLite (表)

查询请求
    │
    ├─→ ChromaDB (向量检索)
    ├─→ Neo4j (图查询)
    └─→ Redis (缓存)
```

---

## ChromaDB 向量存储

### 简介

ChromaDB 是一个开源的向量数据库，专为 AI 应用设计，支持高效的相似度搜索。

### 配置

**配置文件** (`.env`):
```bash
CHROMA_COLLECTION=local_rag_collection
CHROMA_PERSIST_DIR=./data/chroma_db
```

**初始化**:
```python
import chromadb
from chromadb.config import Settings

# 创建客户端
chroma_client = chromadb.PersistentClient(
    path="./data/chroma_db",
    settings=Settings(
        anonymized_telemetry=False,
        allow_reset=True
    )
)

# 创建或获取集合
collection = chroma_client.get_or_create_collection(
    name="local_rag_collection",
    metadata={"hnsw:space": "cosine"}  # 使用余弦相似度
)
```

### 数据模型

**文档结构**:
```python
{
    "id": "doc_123_chunk_5",           # 唯一标识符
    "embedding": [0.1, 0.2, ...],      # 向量（1536 维）
    "document": "这是文档内容...",      # 文本内容
    "metadata": {
        "source": "report.pdf",         # 来源文件
        "page": 5,                      # 页码
        "chunk_index": 5,               # 块索引
        "user_id": "user_456",          # 用户 ID
        "timestamp": "2026-06-19T10:00:00",
        "doc_type": "pdf",
        "language": "zh"
    }
}
```

### 基本操作

#### 1. 插入文档

```python
def add_documents(
    texts: list[str],
    metadatas: list[dict],
    embeddings: list[list[float]],
    ids: list[str]
):
    """
    批量插入文档
    
    Args:
        texts: 文本内容列表
        metadatas: 元数据列表
        embeddings: 嵌入向量列表
        ids: 文档 ID 列表
    """
    collection.add(
        documents=texts,
        metadatas=metadatas,
        embeddings=embeddings,
        ids=ids
    )
```

**示例**:
```python
texts = ["什么是 RAG？", "RAG 系统的优势"]
metadatas = [
    {"source": "intro.txt", "user_id": "user_1"},
    {"source": "intro.txt", "user_id": "user_1"}
]
embeddings = embedding_model.embed_documents(texts)
ids = ["doc_1_chunk_0", "doc_1_chunk_1"]

add_documents(texts, metadatas, embeddings, ids)
```

#### 2. 查询文档

```python
def query_documents(
    query_text: str,
    n_results: int = 10,
    where: dict = None
) -> dict:
    """
    相似度搜索
    
    Args:
        query_text: 查询文本
        n_results: 返回数量
        where: 元数据过滤条件
    
    Returns:
        dict: 查询结果
    """
    query_embedding = embedding_model.embed_query(query_text)
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where,
        include=["documents", "metadatas", "distances"]
    )
    
    return results
```

**示例**:
```python
# 基本查询
results = query_documents("什么是 RAG？", n_results=5)

# 带过滤的查询
results = query_documents(
    "什么是 RAG？",
    n_results=5,
    where={"user_id": "user_1"}
)

# 多条件过滤
results = query_documents(
    "什么是 RAG？",
    n_results=5,
    where={
        "$and": [
            {"user_id": "user_1"},
            {"doc_type": "pdf"}
        ]
    }
)
```

#### 3. 更新文档

```python
def update_document(doc_id: str, metadata: dict):
    """
    更新文档元数据
    
    Args:
        doc_id: 文档 ID
        metadata: 新的元数据
    """
    collection.update(
        ids=[doc_id],
        metadatas=[metadata]
    )
```

#### 4. 删除文档

```python
def delete_documents(doc_ids: list[str] = None, where: dict = None):
    """
    删除文档
    
    Args:
        doc_ids: 文档 ID 列表
        where: 元数据过滤条件
    """
    if doc_ids:
        collection.delete(ids=doc_ids)
    elif where:
        collection.delete(where=where)
```

**示例**:
```python
# 按 ID 删除
delete_documents(doc_ids=["doc_1_chunk_0"])

# 按条件删除（删除某用户的所有文档）
delete_documents(where={"user_id": "user_1"})
```

### 高级功能

#### 元数据过滤操作符

```python
# 等于
where = {"user_id": "user_1"}

# 包含（in）
where = {"source": {"$in": ["doc1.pdf", "doc2.pdf"]}}

# 不等于
where = {"user_id": {"$ne": "user_1"}}

# 大于/小于
where = {"page": {"$gt": 10}}
where = {"page": {"$gte": 10, "$lte": 20}}

# 逻辑与
where = {
    "$and": [
        {"user_id": "user_1"},
        {"doc_type": "pdf"}
    ]
}

# 逻辑或
where = {
    "$or": [
        {"doc_type": "pdf"},
        {"doc_type": "docx"}
    ]
}
```

#### 批量操作优化

```python
def batch_add_documents(
    texts: list[str],
    metadatas: list[dict],
    batch_size: int = 100
):
    """
    批量插入文档（分批处理）
    
    Args:
        texts: 文本列表
        metadatas: 元数据列表
        batch_size: 批大小
    """
    embeddings = embedding_model.embed_documents(texts)
    
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i + batch_size]
        batch_metadatas = metadatas[i:i + batch_size]
        batch_embeddings = embeddings[i:i + batch_size]
        batch_ids = [f"doc_{i + j}" for j in range(len(batch_texts))]
        
        collection.add(
            documents=batch_texts,
            metadatas=batch_metadatas,
            embeddings=batch_embeddings,
            ids=batch_ids
        )
```

---

## Neo4j 知识图谱

### 简介

Neo4j 是一个高性能的图数据库，用于存储和查询实体关系。

### 配置

**Docker Compose** (`docker-compose.yml`):
```yaml
services:
  neo4j:
    image: neo4j:5.13
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    environment:
      - NEO4J_AUTH=neo4j/password
      - NEO4J_dbms_memory_heap_max__size=2G
    volumes:
      - neo4j_data:/data
```

**启动 Neo4j**:
```bash
docker-compose up -d neo4j
```

**连接配置** (`.env`):
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
```

### 数据模型

**节点标签**:
- `Entity`: 实体（人物、组织、概念等）
- `Document`: 文档

**关系类型**:
- `MENTIONS`: 文档提及实体
- `RELATED_TO`: 实体间关系
- `DEPENDS_ON`: 依赖关系
- `PART_OF`: 从属关系

**示例图结构**:
```
(Entity:Person {name: "张三"})
  -[:WORKS_AT {since: 2020}]->
(Entity:Company {name: "某公司"})

(Entity:Concept {name: "RAG"})
  -[:RELATED_TO {type: "uses"}]->
(Entity:Concept {name: "向量数据库"})
```

### 基本操作

#### 1. 创建节点

```python
from neo4j import GraphDatabase

class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def create_entity(self, name: str, entity_type: str, properties: dict = None):
        """
        创建实体节点
        
        Args:
            name: 实体名称
            entity_type: 实体类型
            properties: 其他属性
        """
        with self.driver.session() as session:
            query = """
            CREATE (e:Entity {name: $name, type: $entity_type})
            SET e += $properties
            RETURN e
            """
            result = session.run(
                query,
                name=name,
                entity_type=entity_type,
                properties=properties or {}
            )
            return result.single()
```

**示例**:
```python
client = Neo4jClient(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)

client.create_entity(
    name="RAG",
    entity_type="Concept",
    properties={"description": "检索增强生成"}
)
```

#### 2. 创建关系

```python
def create_relationship(
    self,
    from_entity: str,
    to_entity: str,
    relation_type: str,
    properties: dict = None
):
    """
    创建实体间关系
    
    Args:
        from_entity: 起始实体名称
        to_entity: 目标实体名称
        relation_type: 关系类型
        properties: 关系属性
    """
    with self.driver.session() as session:
        query = f"""
        MATCH (a:Entity {{name: $from_entity}})
        MATCH (b:Entity {{name: $to_entity}})
        CREATE (a)-[r:{relation_type}]->(b)
        SET r += $properties
        RETURN r
        """
        result = session.run(
            query,
            from_entity=from_entity,
            to_entity=to_entity,
            properties=properties or {}
        )
        return result.single()
```

**示例**:
```python
client.create_relationship(
    from_entity="RAG",
    to_entity="向量数据库",
    relation_type="USES",
    properties={"strength": 0.9}
)
```

#### 3. 查询实体

```python
def search_entities(self, keywords: list[str], limit: int = 10):
    """
    搜索实体
    
    Args:
        keywords: 关键词列表
        limit: 返回数量
    
    Returns:
        list[dict]: 实体列表
    """
    with self.driver.session() as session:
        query = """
        MATCH (e:Entity)
        WHERE ANY(keyword IN $keywords WHERE e.name CONTAINS keyword)
        RETURN e.name AS entity, e.type AS type
        LIMIT $limit
        """
        result = session.run(query, keywords=keywords, limit=limit)
        return [record.data() for record in result]
```

#### 4. 查询关系

```python
def entity_neighbors(self, entity_name: str, limit: int = 10):
    """
    查询实体的邻居节点
    
    Args:
        entity_name: 实体名称
        limit: 返回数量
    
    Returns:
        list[dict]: 关系列表
    """
    with self.driver.session() as session:
        query = """
        MATCH (e:Entity {name: $entity_name})-[r]-(other:Entity)
        RETURN type(r) AS relation, other.name AS other_entity
        LIMIT $limit
        """
        result = session.run(query, entity_name=entity_name, limit=limit)
        return [record.data() for record in result]
```

#### 5. 路径查询

```python
def find_path(
    self,
    from_entity: str,
    to_entity: str,
    max_depth: int = 3
):
    """
    查找两个实体间的路径
    
    Args:
        from_entity: 起始实体
        to_entity: 目标实体
        max_depth: 最大深度
    
    Returns:
        list[dict]: 路径列表
    """
    with self.driver.session() as session:
        query = f"""
        MATCH path = (a:Entity {{name: $from_entity}})
                    -[*1..{max_depth}]-
                    (b:Entity {{name: $to_entity}})
        RETURN path
        LIMIT 10
        """
        result = session.run(
            query,
            from_entity=from_entity,
            to_entity=to_entity
        )
        return [record.data() for record in result]
```

### 高级 Cypher 查询

#### 1. 聚合查询

```cypher
-- 统计每种实体类型的数量
MATCH (e:Entity)
RETURN e.type AS type, count(e) AS count
ORDER BY count DESC
```

#### 2. 子图查询

```cypher
-- 获取某实体的二度子图
MATCH (center:Entity {name: 'RAG'})
MATCH (center)-[r1]-(neighbor1)
OPTIONAL MATCH (neighbor1)-[r2]-(neighbor2)
WHERE neighbor2 <> center
RETURN center, r1, neighbor1, r2, neighbor2
```

#### 3. 推荐查询

```cypher
-- 基于共同邻居的实体推荐
MATCH (e1:Entity {name: 'RAG'})-[:RELATED_TO]-(common)-[:RELATED_TO]-(e2:Entity)
WHERE e1 <> e2
RETURN e2.name AS recommendation, count(common) AS score
ORDER BY score DESC
LIMIT 10
```

---

## SQLite 应用数据库

### 简介

SQLite 用于存储应用的结构化数据，如用户、会话、文档元数据等。

### 配置

**配置文件** (`.env`):
```bash
APP_DB_PATH=./data/app.db
```

### 数据模型

#### 1. 用户表 (users)

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user',  -- 'user' or 'admin'
    status VARCHAR(20) DEFAULT 'active',  -- 'active' or 'disabled'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
```

#### 2. 会话表 (sessions)

```sql
CREATE TABLE sessions (
    id VARCHAR(50) PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name VARCHAR(255),
    strategy VARCHAR(50) DEFAULT 'balanced',
    memory_context TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_sessions_user_id ON sessions(user_id);
```

#### 3. 文档表 (documents)

```sql
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    filename VARCHAR(255) NOT NULL,
    filepath VARCHAR(500) NOT NULL,
    file_size INTEGER,
    doc_type VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'processed', 'failed'
    chunks_count INTEGER DEFAULT 0,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_documents_user_id ON documents(user_id);
CREATE INDEX idx_documents_status ON documents(status);
```

#### 4. 审计日志表 (audit_logs)

```sql
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    details TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
```

### 基本操作

#### 1. 连接数据库

```python
import sqlite3
from contextlib import contextmanager

@contextmanager
def get_db_connection():
    """数据库连接上下文管理器"""
    conn = sqlite3.connect("./data/app.db")
    conn.row_factory = sqlite3.Row  # 返回字典格式
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

#### 2. CRUD 操作

```python
# 创建用户
def create_user(username: str, email: str, password_hash: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO users (username, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (username, email, password_hash)
        )
        return cursor.lastrowid

# 查询用户
def get_user_by_username(username: str):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

# 更新用户
def update_user_last_login(user_id: int):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users
            SET last_login = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (user_id,)
        )

# 删除用户
def delete_user(user_id: int):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
```

---

## Redis 缓存

### 配置

```bash
REDIS_URL=redis://localhost:6379/0
RETRIEVAL_CACHE_TTL_SECONDS=300
```

### 基本操作

```python
import redis
import json

# 连接 Redis
redis_client = redis.from_url("redis://localhost:6379/0")

# 设置缓存
def cache_set(key: str, value: any, ttl: int = 300):
    redis_client.setex(key, ttl, json.dumps(value))

# 获取缓存
def cache_get(key: str):
    cached = redis_client.get(key)
    return json.loads(cached) if cached else None

# 删除缓存
def cache_delete(key: str):
    redis_client.delete(key)
```

---

## 备份和恢复

### ChromaDB 备份

```bash
# 备份（复制目录）
cp -r data/chroma_db data/backups/chroma_db_$(date +%Y%m%d)
```

### Neo4j 备份

```bash
# 导出数据
docker exec neo4j neo4j-admin dump --database=neo4j --to=/backups/neo4j_backup.dump

# 恢复数据
docker exec neo4j neo4j-admin load --from=/backups/neo4j_backup.dump --database=neo4j --force
```

### SQLite 备份

```bash
# 备份
sqlite3 data/app.db ".backup data/backups/app_$(date +%Y%m%d).db"

# 恢复
cp data/backups/app_20260619.db data/app.db
```

---

## 性能优化

### ChromaDB 优化

1. **批量插入**: 使用 `collection.add()` 批量插入
2. **索引优化**: 适当的元数据过滤
3. **向量维度**: 权衡精度和性能

### Neo4j 优化

1. **创建索引**:
```cypher
CREATE INDEX entity_name_index FOR (e:Entity) ON (e.name)
```

2. **查询优化**: 使用 `EXPLAIN` 分析查询计划

### SQLite 优化

1. **创建索引**: 为常用查询字段创建索引
2. **使用事务**: 批量操作使用事务
3. **WAL 模式**: 提高并发性能
```sql
PRAGMA journal_mode=WAL;
```

---

## 下一步

了解数据存储后，建议继续阅读：

1. **[API 开发](../development/api-development.md)** - 学习如何使用数据存储
2. **[开发流程](../development/workflow.md)** - 了解开发规范

---

**更新日期**: 2026-06-19  
**文档版本**: 1.0
