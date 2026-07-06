# 配置参考 (Configuration Reference)

本文档详细说明 QueryMind（智询） 系统的所有环境变量和配置选项。

## 目录

- [快速索引](#快速索引)
- [应用配置](#应用配置)
- [模型配置](#模型配置)
- [数据库配置](#数据库配置)
- [检索配置](#检索配置)
- [缓存和性能](#缓存和性能)
- [安全配置](#安全配置)
- [文档处理](#文档处理)
- [高级配置](#高级配置)

---

## 快速索引

### 按场景查找

**🚀 快速开始（最小配置）**:
- [MODEL_BACKEND](#model_backend) - 模型后端
- [NEO4J_PASSWORD](#neo4j_password) - Neo4j 密码

**🔑 OpenAI 配置**:
- [OPENAI_API_KEY](#openai_api_key)
- [OPENAI_CHAT_MODEL](#openai_chat_model)
- [OPENAI_EMBED_MODEL](#openai_embed_model)

**🦙 Ollama 配置**:
- [OLLAMA_BASE_URL](#ollama_base_url)
- [OLLAMA_CHAT_MODEL](#ollama_chat_model)
- [OLLAMA_EMBED_MODEL](#ollama_embed_model)

**🔍 检索优化**:
- [TOP_K](#top_k) - 返回结果数量
- [ENABLE_RERANKER](#enable_reranker) - 启用重排序
- [VECTOR_SIMILARITY_THRESHOLD](#vector_similarity_threshold) - 相似度阈值

**⚡ 性能调优**:
- [RETRIEVAL_CACHE_ENABLED](#retrieval_cache_enabled) - 启用缓存
- [QUERY_REQUEST_TIMEOUT_MS](#query_request_timeout_ms) - 查询超时
- [CIRCUIT_BREAKER_ENABLED](#circuit_breaker_enabled) - 熔断器

**🔒 安全配置**:
- [AUTH_TOKEN_TTL_HOURS](#auth_token_ttl_hours) - 令牌有效期
- [API_SETTINGS_ENCRYPTION_KEY](#api_settings_encryption_key) - 加密密钥
- [ADMIN_CREATE_APPROVAL_TOKEN_HASH](#admin_create_approval_token_hash) - 审批令牌

### 按字母排序

| A-D | E-N | O-S | T-Z |
|-----|-----|-----|-----|
| [ADMIN_CREATE_APPROVAL_TOKEN_HASH](#admin_create_approval_token_hash) | [ENABLE_RERANKER](#enable_reranker) | [OLLAMA_BASE_URL](#ollama_base_url) | [TOP_K](#top_k) |
| [ANTHROPIC_API_KEY](#anthropic_api_key) | [HYBRID_RRF_K](#hybrid_rrf_k) | [OPENAI_API_KEY](#openai_api_key) | [VECTOR_TOP_K](#vector_top_k) |
| [API_SETTINGS_ENCRYPTION_KEY](#api_settings_encryption_key) | [MODEL_BACKEND](#model_backend) | [QUERY_REQUEST_TIMEOUT_MS](#query_request_timeout_ms) | - |
| [AUTH_TOKEN_TTL_HOURS](#auth_token_ttl_hours) | [NEO4J_PASSWORD](#neo4j_password) | [REDIS_URL](#redis_url) | - |
| [BM25_TOP_K](#bm25_top_k) | [NEO4J_URI](#neo4j_uri) | [RERANKER_MODEL_NAME](#reranker_model_name) | - |
| [CHROMA_COLLECTION](#chroma_collection) | - | [RETRIEVAL_CACHE_ENABLED](#retrieval_cache_enabled) | - |

### 常用配置组合

**开发环境（最小配置）**:
```bash
MODEL_BACKEND=local
NEO4J_PASSWORD=dev-password
```

**开发环境（Ollama）**:
```bash
MODEL_BACKEND=ollama
OLLAMA_CHAT_MODEL=qwen2.5:7b-instruct
OLLAMA_EMBED_MODEL=nomic-embed-text
NEO4J_PASSWORD=dev-password
```

**生产环境（OpenAI）**:
```bash
APP_ENV=production
MODEL_BACKEND=openai
OPENAI_API_KEY=sk-xxx
OPENAI_CHAT_MODEL=gpt-4-turbo
OPENAI_EMBED_MODEL=text-embedding-3-small
NEO4J_URI=bolt://production-neo4j:7687
NEO4J_PASSWORD=strong-production-password
AUTH_TOKEN_TTL_HOURS=24
API_SETTINGS_ENCRYPTION_KEY=xxx
ADMIN_CREATE_APPROVAL_TOKEN_HASH=xxx
RETRIEVAL_CACHE_BACKEND=redis
REDIS_URL=redis://production-redis:6379/0
ENABLE_RERANKER=true
```

**高性能配置**:
```bash
RETRIEVAL_CACHE_ENABLED=true
RETRIEVAL_CACHE_BACKEND=redis
CIRCUIT_BREAKER_ENABLED=true
ENABLE_RERANKER=true
DYNAMIC_RETRIEVAL_ENABLED=true
TOP_K=10
VECTOR_TOP_K=20
BM25_TOP_K=20
```

---

## 应用配置

### APP_ENV

**说明**: 应用运行环境

**类型**: `string`  
**默认值**: `dev`  
**可选值**: `dev`, `staging`, `production`

```bash
APP_ENV=dev
```

**影响**:
- `dev`: 启用调试日志、详细错误信息
- `production`: 优化性能、最小化日志

---

## 模型配置

### 模型后端选择

#### MODEL_BACKEND

**说明**: 主要 LLM 后端提供商

**类型**: `string`  
**默认值**: `local`  
**可选值**: `local`, `ollama`, `openai`, `anthropic`, `deepseek`, `custom`

```bash
MODEL_BACKEND=openai
```

**说明**:
- `local`: 无需 API 密钥的本地模型（开发/测试）
- `ollama`: 本地部署的 Ollama 模型
- `openai`: OpenAI API
- `anthropic`: Anthropic Claude API
- `deepseek`: DeepSeek API
- `custom`: 自定义 OpenAI 兼容端点

#### REASONING_MODEL_BACKEND

**说明**: 推理模型后端（用于复杂推理任务）

**类型**: `string`  
**默认值**: `""`（使用 MODEL_BACKEND）  
**可选值**: 与 MODEL_BACKEND 相同

```bash
REASONING_MODEL_BACKEND=anthropic
```

---

### Ollama 配置

#### OLLAMA_BASE_URL

**说明**: Ollama 服务器地址

**类型**: `string`  
**默认值**: `http://localhost:11434`

```bash
OLLAMA_BASE_URL=http://localhost:11434
```

#### OLLAMA_CHAT_MODEL

**说明**: Ollama 聊天模型名称

**类型**: `string`  
**默认值**: `qwen2.5:7b-instruct`

```bash
OLLAMA_CHAT_MODEL=qwen2.5:7b-instruct
```

**推荐模型**:
- `qwen2.5:7b-instruct` - 中英文通用（推荐）
- `llama3.2:3b` - 轻量级英文模型
- `mistral:7b` - 英文模型

#### OLLAMA_EMBED_MODEL

**说明**: Ollama 嵌入模型

**类型**: `string`  
**默认值**: `nomic-embed-text`

```bash
OLLAMA_EMBED_MODEL=nomic-embed-text
```

**推荐模型**:
- `nomic-embed-text` - 8192 上下文（推荐）
- `bge-m3` - 中文友好
- `all-minilm` - 轻量级

#### OLLAMA_REASONING_MODEL

**说明**: Ollama 推理模型

**类型**: `string`  
**默认值**: `""`

```bash
OLLAMA_REASONING_MODEL=qwen2.5:14b-instruct
```

---

### OpenAI 配置

#### OPENAI_API_KEY

**说明**: OpenAI API 密钥

**类型**: `string`  
**默认值**: `""`  
**必需**: 当 MODEL_BACKEND=openai 时

```bash
OPENAI_API_KEY=sk-your-api-key-here
```

**获取**: https://platform.openai.com/api-keys

#### OPENAI_BASE_URL

**说明**: OpenAI API 基础 URL（用于自定义端点）

**类型**: `string`  
**默认值**: `""`（使用官方 API）

```bash
# 官方 API（默认）
OPENAI_BASE_URL=

# Azure OpenAI
OPENAI_BASE_URL=https://your-resource.openai.azure.com/

# 自定义端点
OPENAI_BASE_URL=https://api.custom.com/v1
```

#### OPENAI_CHAT_MODEL

**说明**: OpenAI 聊天模型

**类型**: `string`  
**默认值**: `gpt-5.4-codex`

```bash
OPENAI_CHAT_MODEL=gpt-4-turbo
```

**推荐模型**:
- `gpt-4-turbo` - 最强性能
- `gpt-4o` - 平衡性价比
- `gpt-3.5-turbo` - 经济实惠

#### OPENAI_EMBED_MODEL

**说明**: OpenAI 嵌入模型

**类型**: `string`  
**默认值**: `text-embedding-3-small`

```bash
OPENAI_EMBED_MODEL=text-embedding-3-small
```

**可选值**:
- `text-embedding-3-small` - 1536 维（推荐）
- `text-embedding-3-large` - 3072 维（最高质量）

#### OPENAI_REASONING_MODEL

**说明**: OpenAI 推理模型

**类型**: `string`  
**默认值**: `gpt-5.4-codex`

```bash
OPENAI_REASONING_MODEL=o1-preview
```

---

### Anthropic 配置

#### ANTHROPIC_API_KEY

**说明**: Anthropic API 密钥

**类型**: `string`  
**默认值**: `""`  
**必需**: 当 MODEL_BACKEND=anthropic 时

```bash
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
```

**获取**: https://console.anthropic.com/

#### ANTHROPIC_CHAT_MODEL

**说明**: Anthropic 聊天模型

**类型**: `string`  
**默认值**: `claude-sonnet-4-6`

```bash
ANTHROPIC_CHAT_MODEL=claude-3-5-sonnet-20241022
```

**推荐模型**:
- `claude-3-5-sonnet-20241022` - 最新 Sonnet（推荐）
- `claude-3-opus-20240229` - 最强性能
- `claude-3-haiku-20240307` - 快速响应

#### ANTHROPIC_REASONING_MODEL

**说明**: Anthropic 推理模型

**类型**: `string`  
**默认值**: `claude-sonnet-4-6`

```bash
ANTHROPIC_REASONING_MODEL=claude-3-opus-20240229
```

---

## 数据库配置

### Neo4j 配置

#### NEO4J_URI

**说明**: Neo4j 数据库连接 URI

**类型**: `string`  
**默认值**: `bolt://localhost:7687`

```bash
NEO4J_URI=bolt://localhost:7687
```

#### NEO4J_USERNAME

**说明**: Neo4j 用户名

**类型**: `string`  
**默认值**: `neo4j`

```bash
NEO4J_USERNAME=neo4j
```

#### NEO4J_PASSWORD

**说明**: Neo4j 密码

**类型**: `string`  
**默认值**: `change-me-use-a-long-random-password`  
**必需**: 是

```bash
NEO4J_PASSWORD=your-secure-password-here
```

**安全建议**:
- 使用至少 16 字符的强密码
- 包含大小写字母、数字和特殊字符
- 定期更换密码

---

### ChromaDB 配置

#### CHROMA_COLLECTION

**说明**: ChromaDB 集合名称

**类型**: `string`  
**默认值**: `local_rag_collection`

```bash
CHROMA_COLLECTION=local_rag_collection
```

#### CHROMA_PERSIST_DIR

**说明**: ChromaDB 持久化目录

**类型**: `string`  
**默认值**: `./data/chroma`

```bash
CHROMA_PERSIST_DIR=./data/chroma
```

---

### SQLite 配置

#### APP_DB_PATH

**说明**: SQLite 数据库文件路径

**类型**: `string`  
**默认值**: `./data/app.db`

```bash
APP_DB_PATH=./data/app.db
```

---

### Redis 配置

#### REDIS_URL

**说明**: Redis 连接 URL

**类型**: `string`  
**默认值**: `redis://localhost:6379/0`

```bash
REDIS_URL=redis://localhost:6379/0
```

**格式**: `redis://[username:password@]host:port/db`

---

## 检索配置

### 基础检索参数

#### TOP_K

**说明**: 最终返回的文档数量

**类型**: `int`  
**默认值**: `4`  
**范围**: `1-100`

```bash
TOP_K=10
```

#### VECTOR_TOP_K

**说明**: 向量检索返回数量

**类型**: `int`  
**默认值**: `6`  
**范围**: `1-100`

```bash
VECTOR_TOP_K=10
```

#### BM25_TOP_K

**说明**: BM25 检索返回数量

**类型**: `int`  
**默认值**: `6`  
**范围**: `1-100`

```bash
BM25_TOP_K=10
```

**建议**: 保持 VECTOR_TOP_K 和 BM25_TOP_K 相等

---

### 混合检索参数

#### HYBRID_RRF_K

**说明**: RRF (Reciprocal Rank Fusion) 常数

**类型**: `int`  
**默认值**: `60`  
**范围**: `1-200`

```bash
HYBRID_RRF_K=60
```

**说明**: 较小的值使前排文档影响更大

#### HYBRID_VECTOR_WEIGHT

**说明**: 向量检索权重

**类型**: `float`  
**默认值**: `0.95`  
**范围**: `0.0-1.0`

```bash
HYBRID_VECTOR_WEIGHT=0.95
```

#### HYBRID_BM25_WEIGHT

**说明**: BM25 检索权重

**类型**: `float`  
**默认值**: `0.05`  
**范围**: `0.0-1.0`

```bash
HYBRID_BM25_WEIGHT=0.05
```

**注意**: VECTOR_WEIGHT + BM25_WEIGHT 应等于 1.0

---

### 相似度阈值

#### VECTOR_SIMILARITY_THRESHOLD

**说明**: 向量相似度阈值

**类型**: `float`  
**默认值**: `0.2`  
**范围**: `0.0-1.0`

```bash
VECTOR_SIMILARITY_THRESHOLD=0.3
```

**说明**: 低于此阈值的文档会被过滤

#### VECTOR_SIMILARITY_RELAXED_THRESHOLD

**说明**: 宽松相似度阈值（降级场景）

**类型**: `float`  
**默认值**: `0.05`  
**范围**: `0.0-1.0`

```bash
VECTOR_SIMILARITY_RELAXED_THRESHOLD=0.1
```

---

### 重排序配置

#### ENABLE_RERANKER

**说明**: 是否启用重排序

**类型**: `bool`  
**默认值**: `true`

```bash
ENABLE_RERANKER=true
```

#### RERANKER_MODEL_NAME

**说明**: 重排序模型名称

**类型**: `string`  
**默认值**: `BAAI/bge-reranker-v2-m3`

```bash
RERANKER_MODEL_NAME=BAAI/bge-reranker-v2-m3
```

**可选模型**:
- `BAAI/bge-reranker-v2-m3` - 多语言（推荐）
- `BAAI/bge-reranker-large` - 英文
- `jinaai/jina-reranker-v1-base-en` - 轻量级

#### RERANKER_TOP_N

**说明**: 重排序后返回的文档数量

**类型**: `int`  
**默认值**: `5`  
**范围**: `1-50`

```bash
RERANKER_TOP_N=5
```

---

### 查询优化

#### QUERY_REWRITE_ENABLED

**说明**: 是否启用查询重写

**类型**: `bool`  
**默认值**: `true`

```bash
QUERY_REWRITE_ENABLED=true
```

#### QUERY_REWRITE_WITH_LLM

**说明**: 是否使用 LLM 进行查询重写

**类型**: `bool`  
**默认值**: `false`

```bash
QUERY_REWRITE_WITH_LLM=false
```

**注意**: 启用会增加延迟和成本

#### QUERY_DECOMPOSE_ENABLED

**说明**: 是否启用查询分解

**类型**: `bool`  
**默认值**: `true`

```bash
QUERY_DECOMPOSE_ENABLED=true
```

#### QUERY_REWRITE_MAX_VARIANTS

**说明**: 查询重写最大变体数

**类型**: `int`  
**默认值**: `6`  
**范围**: `1-20`

```bash
QUERY_REWRITE_MAX_VARIANTS=6
```

---

### BM25 配置

#### BM25_USE_CHINESE_TOKENIZER

**说明**: 是否使用中文分词器（jieba）

**类型**: `bool`  
**默认值**: `true`

```bash
BM25_USE_CHINESE_TOKENIZER=true
```

---

### 动态检索

#### DYNAMIC_RETRIEVAL_ENABLED

**说明**: 是否启用动态检索参数调整

**类型**: `bool`  
**默认值**: `true`

```bash
DYNAMIC_RETRIEVAL_ENABLED=true
```

#### DYNAMIC_VECTOR_TOP_K_CAP

**说明**: 动态向量检索上限

**类型**: `int`  
**默认值**: `16`

```bash
DYNAMIC_VECTOR_TOP_K_CAP=20
```

#### DYNAMIC_BM25_TOP_K_CAP

**说明**: 动态 BM25 检索上限

**类型**: `int`  
**默认值**: `16`

```bash
DYNAMIC_BM25_TOP_K_CAP=20
```

#### DYNAMIC_RERANKER_TOP_N_CAP

**说明**: 动态重排序上限

**类型**: `int`  
**默认值**: `10`

```bash
DYNAMIC_RERANKER_TOP_N_CAP=15
```

---

## 缓存和性能

### 检索缓存

#### RETRIEVAL_CACHE_ENABLED

**说明**: 是否启用检索缓存

**类型**: `bool`  
**默认值**: `true`

```bash
RETRIEVAL_CACHE_ENABLED=true
```

#### RETRIEVAL_CACHE_TTL_SECONDS

**说明**: 缓存 TTL（秒）

**类型**: `int`  
**默认值**: `45`  
**范围**: `10-3600`

```bash
RETRIEVAL_CACHE_TTL_SECONDS=300
```

#### RETRIEVAL_CACHE_MAX_ITEMS

**说明**: 最大缓存项数

**类型**: `int`  
**默认值**: `256`

```bash
RETRIEVAL_CACHE_MAX_ITEMS=512
```

#### RETRIEVAL_CACHE_BACKEND

**说明**: 缓存后端

**类型**: `string`  
**默认值**: `auto`  
**可选值**: `auto`, `memory`, `redis`, `off`

```bash
RETRIEVAL_CACHE_BACKEND=redis
```

**说明**:
- `auto`: 自动选择（Redis 可用则用 Redis）
- `memory`: 内存缓存（单机）
- `redis`: Redis 缓存（分布式）
- `off`: 禁用缓存

---

### 自适应缓存 TTL

#### CACHE_TTL_FAST_TIER

**说明**: 快速层缓存 TTL（秒）

**类型**: `int`  
**默认值**: `300`

```bash
CACHE_TTL_FAST_TIER=300
```

#### CACHE_TTL_BALANCED_TIER

**说明**: 平衡层缓存 TTL（秒）

**类型**: `int`  
**默认值**: `120`

```bash
CACHE_TTL_BALANCED_TIER=120
```

#### CACHE_TTL_DEEP_TIER

**说明**: 深度层缓存 TTL（秒）

**类型**: `int`  
**默认值**: `60`

```bash
CACHE_TTL_DEEP_TIER=60
```

#### CACHE_TTL_USER_QUERY

**说明**: 用户查询缓存 TTL（秒）

**类型**: `int`  
**默认值**: `180`

```bash
CACHE_TTL_USER_QUERY=180
```

---

### 熔断器

#### CIRCUIT_BREAKER_ENABLED

**说明**: 是否启用熔断器

**类型**: `bool`  
**默认值**: `true`

```bash
CIRCUIT_BREAKER_ENABLED=true
```

#### CIRCUIT_BREAKER_FAIL_THRESHOLD

**说明**: 触发熔断的失败次数

**类型**: `int`  
**默认值**: `3`  
**范围**: `1-10`

```bash
CIRCUIT_BREAKER_FAIL_THRESHOLD=5
```

#### CIRCUIT_BREAKER_COOLDOWN_SECONDS

**说明**: 熔断冷却时间（秒）

**类型**: `int`  
**默认值**: `30`  
**范围**: `10-300`

```bash
CIRCUIT_BREAKER_COOLDOWN_SECONDS=60
```

---

### 超时配置

#### QUERY_REQUEST_TIMEOUT_MS

**说明**: 查询请求超时（毫秒）

**类型**: `int`  
**默认值**: `60000`  
**范围**: `1000-300000`

```bash
QUERY_REQUEST_TIMEOUT_MS=30000
```

#### STREAM_HEARTBEAT_SECONDS

**说明**: 流式响应心跳间隔（秒）

**类型**: `int`  
**默认值**: `6`  
**范围**: `1-60`

```bash
STREAM_HEARTBEAT_SECONDS=10
```

---

## 安全配置

### 认证配置

#### AUTH_TOKEN_TTL_HOURS

**说明**: JWT 令牌有效期（小时）

**类型**: `int`  
**默认值**: `24`  
**范围**: `1-720`

```bash
AUTH_TOKEN_TTL_HOURS=24
```

#### AUTH_LOGIN_MAX_FAILURES

**说明**: 登录最大失败次数

**类型**: `int`  
**默认值**: `8`

```bash
AUTH_LOGIN_MAX_FAILURES=5
```

#### AUTH_LOGIN_WINDOW_SECONDS

**说明**: 登录限流窗口（秒）

**类型**: `int`  
**默认值**: `300`

```bash
AUTH_LOGIN_WINDOW_SECONDS=300
```

---

### 管理员配置

#### ADMIN_CREATE_APPROVAL_TOKEN

**说明**: 管理员创建审批令牌（明文）

**类型**: `string`  
**默认值**: `""`

```bash
ADMIN_CREATE_APPROVAL_TOKEN=your-secret-approval-token
```

**警告**: 生产环境使用 ADMIN_CREATE_APPROVAL_TOKEN_HASH

#### ADMIN_CREATE_APPROVAL_TOKEN_HASH

**说明**: 管理员创建审批令牌（SHA256 哈希）

**类型**: `string`  
**默认值**: `""`

```bash
ADMIN_CREATE_APPROVAL_TOKEN_HASH=abc123...
```

**生成方法**:
```bash
echo -n "your-token" | sha256sum
```

---

### API 密钥安全

#### API_SETTINGS_ENCRYPTION_KEY

**说明**: API 设置加密密钥

**类型**: `string`  
**默认值**: `""`  
**必需**: 是

```bash
API_SETTINGS_ENCRYPTION_KEY=your-32-byte-encryption-key
```

**生成方法**:
```python
import secrets
print(secrets.token_urlsafe(32))
```

---

### 网络安全

#### API_BASE_URL_ALLOWLIST

**说明**: 允许的 API 基础 URL 列表（逗号分隔）

**类型**: `string`  
**默认值**: `""`

```bash
API_BASE_URL_ALLOWLIST=https://api.openai.com,https://api.anthropic.com
```

#### API_BASE_URL_ALLOW_PRIVATE

**说明**: 是否允许私有 IP

**类型**: `bool`  
**默认值**: `false`

```bash
API_BASE_URL_ALLOW_PRIVATE=false
```

#### API_BASE_URL_DNS_CHECK

**说明**: 是否进行 DNS 检查

**类型**: `bool`  
**默认值**: `true`

```bash
API_BASE_URL_DNS_CHECK=true
```

---

### 出站数据脱敏

#### OUTBOUND_LLM_REDACTION_ENABLED

**说明**: 是否对发送到 LLM 的数据脱敏

**类型**: `bool`  
**默认值**: `true`

```bash
OUTBOUND_LLM_REDACTION_ENABLED=true
```

#### OUTBOUND_EMBEDDING_REDACTION_ENABLED

**说明**: 是否对嵌入数据脱敏

**类型**: `bool`  
**默认值**: `true`

```bash
OUTBOUND_EMBEDDING_REDACTION_ENABLED=true
```

---

## 文档处理

### 文件上传

#### UPLOAD_MAX_FILES

**说明**: 单次上传最大文件数

**类型**: `int`  
**默认值**: `20`

```bash
UPLOAD_MAX_FILES=10
```

#### UPLOAD_MAX_FILE_BYTES

**说明**: 单个文件最大字节数

**类型**: `int`  
**默认值**: `20971520`（20MB）

```bash
UPLOAD_MAX_FILE_BYTES=52428800  # 50MB
```

#### UPLOAD_MAX_TOTAL_BYTES

**说明**: 总上传最大字节数

**类型**: `int`  
**默认值**: `104857600`（100MB）

```bash
UPLOAD_MAX_TOTAL_BYTES=209715200  # 200MB
```

---

### OCR 配置

#### TESSERACT_CMD

**说明**: Tesseract 可执行文件路径

**类型**: `string`  
**默认值**: `""`（自动检测）

```bash
# Linux/macOS
TESSERACT_CMD=/usr/bin/tesseract

# Windows
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

#### TESSERACT_LANG

**说明**: Tesseract 语言

**类型**: `string`  
**默认值**: `chi_sim+eng`

```bash
TESSERACT_LANG=chi_sim+eng
```

**常用值**:
- `eng` - 英文
- `chi_sim` - 简体中文
- `chi_tra` - 繁体中文
- `chi_sim+eng` - 中英文

#### OCR_PREPROCESS_ENABLED

**说明**: 是否启用图像预处理

**类型**: `bool`  
**默认值**: `true`

```bash
OCR_PREPROCESS_ENABLED=true
```

---

### PDF 处理

#### PDF_CACHE_TTL_DAYS

**说明**: PDF 缓存有效期（天）

**类型**: `int`  
**默认值**: `30`

```bash
PDF_CACHE_TTL_DAYS=30
```

#### PDF_STREAMING_CHUNK_SIZE

**说明**: 流式处理每批页数

**类型**: `int`  
**默认值**: `10`

```bash
PDF_STREAMING_CHUNK_SIZE=10
```

#### PDF_BATCH_CHART_SIZE

**说明**: 批量图表提取每批数量

**类型**: `int`  
**默认值**: `5`

```bash
PDF_BATCH_CHART_SIZE=5
```

---

## 高级配置

### 检索配置文件

#### RETRIEVAL_PROFILE

**说明**: 检索配置文件

**类型**: `string`  
**默认值**: `advanced`  
**可选值**: `baseline`, `advanced`, `safe`

```bash
RETRIEVAL_PROFILE=advanced
```

**说明**:
- `baseline`: 基础配置（快速）
- `advanced`: 高级配置（精确）
- `safe`: 安全配置（保守）

---

### 图处理

#### GRAPH_EXTRACTION_MODE

**说明**: 图提取模式

**类型**: `string`  
**默认值**: `llm`  
**可选值**: `llm`, `rule`

```bash
GRAPH_EXTRACTION_MODE=llm
```

#### GRAPH_RAG_ENHANCED

**说明**: 是否启用增强图 RAG

**类型**: `bool`  
**默认值**: `false`

```bash
GRAPH_RAG_ENHANCED=true
```

---

### 监控和追踪

#### OTEL_TRACING_ENABLED

**说明**: 是否启用 OpenTelemetry 追踪

**类型**: `bool`  
**默认值**: `true`

```bash
OTEL_TRACING_ENABLED=true
```

#### PDF_ENABLE_METRICS

**说明**: 是否启用 PDF 处理指标

**类型**: `bool`  
**默认值**: `true`

```bash
PDF_ENABLE_METRICS=true
```

---

### SLO 目标

#### SLO_P95_LATENCY_MS_THRESHOLD

**说明**: P95 延迟目标（毫秒）

**类型**: `int`  
**默认值**: `3000`

```bash
SLO_P95_LATENCY_MS_THRESHOLD=2000
```

#### SLO_ERROR_RATE_PERCENT_THRESHOLD

**说明**: 错误率目标（百分比）

**类型**: `float`  
**默认值**: `5.0`

```bash
SLO_ERROR_RATE_PERCENT_THRESHOLD=3.0
```

---

## 配置模板

### 最小配置（本地开发）

```bash
# .env.minimal
MODEL_BACKEND=local
NEO4J_PASSWORD=your-password
```

### 生产配置（OpenAI）

```bash
# .env.production
APP_ENV=production
MODEL_BACKEND=openai
OPENAI_API_KEY=sk-your-key
OPENAI_CHAT_MODEL=gpt-4-turbo
OPENAI_EMBED_MODEL=text-embedding-3-small

NEO4J_URI=bolt://neo4j.example.com:7687
NEO4J_PASSWORD=your-secure-password

AUTH_TOKEN_TTL_HOURS=24
API_SETTINGS_ENCRYPTION_KEY=your-encryption-key
ADMIN_CREATE_APPROVAL_TOKEN_HASH=your-token-hash

RETRIEVAL_CACHE_BACKEND=redis
REDIS_URL=redis://redis.example.com:6379/0

ENABLE_RERANKER=true
TOP_K=10
```

---

## 故障排查

### 配置验证

```python
# scripts/validate_config.py
import os
from app.core.config import get_settings

settings = get_settings()
print(f"Model Backend: {settings.model_backend}")
print(f"Neo4j URI: {settings.neo4j_uri}")
```

### 常见问题

**问题**: 环境变量未生效

**解决**:
```bash
# 1. 检查 .env 文件是否存在
ls -la .env

# 2. 检查环境变量是否加载
python -c "from app.core.config import get_settings; print(get_settings().model_backend)"
```

---

## 下一步

了解配置后，建议继续阅读：

1. **[API 开发](./API_DEVELOPMENT.md)** - 学习如何使用配置
2. **[本地部署](./LOCAL_DEPLOYMENT.md)** - 生产环境配置

---

**更新日期**: 2026-06-19  
**文档版本**: 1.0
