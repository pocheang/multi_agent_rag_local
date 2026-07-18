# 配置参考

**Owner:** QueryMind maintainers  
**Status:** Active  
**Last verified:** 2026-07-17

本页提供当前配置的分类索引。变量名称和默认值以项目根目录 .env.example 与 app/core/config.py 为准；新增变量必须同时更新这两个来源和本页。

## 配置来源

- .env.example：可提交的配置模板
- .env：本地或部署环境实际配置，不提交
- configs/runtime-profiles/fast.env：低延迟
- configs/runtime-profiles/balanced.env：默认平衡
- configs/runtime-profiles/deep.env：高质量
- app/core/config.py：类型化读取、默认值和验证

## 运行环境与模型

| 变量 | 用途 |
| --- | --- |
| APP_ENV | dev、staging 或 production |
| MODEL_BACKEND | 当前聊天/嵌入模型后端 |
| REASONING_MODEL_BACKEND | 可选推理模型后端 |
| OPENAI_API_KEY | OpenAI 服务密钥 |
| OPENAI_BASE_URL | OpenAI 兼容端点 |
| OPENAI_CHAT_MODEL | OpenAI 聊天模型 |
| OPENAI_EMBED_MODEL | OpenAI 嵌入模型 |
| OLLAMA_BASE_URL | Ollama 地址 |
| OLLAMA_CHAT_MODEL | Ollama 聊天模型 |
| OLLAMA_EMBED_MODEL | Ollama 嵌入模型 |

## 检索与质量

| 变量 | 用途 |
| --- | --- |
| RETRIEVAL_PROFILE | baseline、advanced 或 safe |
| TOP_K | 返回结果数量 |
| VECTOR_TOP_K | 向量检索候选数量 |
| BM25_TOP_K | BM25 候选数量 |
| HYBRID_RRF_K | RRF 融合参数 |
| VECTOR_SIMILARITY_THRESHOLD | 向量检索阈值 |
| ENABLE_RERANKER | 是否启用重排序 |
| RERANKER_MODEL_NAME | 重排序模型 |
| RERANKER_TOP_N | 重排序候选上限 |
| QUERY_REWRITE_ENABLED | 是否启用查询改写 |
| QUERY_DECOMPOSE_ENABLED | 是否启用查询分解 |
| CONSISTENCY_GUARD_ENABLED | 是否启用一致性检查 |

## 数据与基础设施

| 变量 | 用途 |
| --- | --- |
| NEO4J_URI | Neo4j Bolt 地址 |
| NEO4J_USERNAME | Neo4j 用户名 |
| NEO4J_PASSWORD | Neo4j 密码 |
| REDIS_URL | Redis 地址 |
| CHROMA_COLLECTION | Chroma collection 名称 |
| CHROMA_PERSIST_DIR | Chroma 持久化目录 |
| DATA_DIR | 文档目录 |
| CORPUS_STORE_PATH | chunks 数据文件 |
| PARENT_STORE_PATH | parent 数据文件 |
| APP_DB_PATH | 应用数据库路径 |
| SESSIONS_DIR | 会话目录 |
| UPLOADS_DIR | 上传目录 |

## 安全与限制

| 变量 | 用途 |
| --- | --- |
| AUTH_TOKEN_TTL_HOURS | 登录令牌有效期 |
| ADMIN_CREATE_APPROVAL_TOKEN_HASH | 管理员创建审批令牌哈希 |
| API_SETTINGS_ENCRYPTION_KEY | API 设置加密密钥 |
| API_BASE_URL_ALLOWLIST | 出站 API 地址白名单 |
| API_BASE_URL_ALLOW_PRIVATE | 是否允许私有地址 |
| UPLOAD_MAX_FILES | 单次上传文件数 |
| UPLOAD_MAX_FILE_BYTES | 单文件大小上限 |
| UPLOAD_MAX_TOTAL_BYTES | 总上传大小上限 |

生产环境必须使用 Secret 管理注入密钥，不要在文档或仓库中放入真实值。

## Profile 使用

~~~powershell
Copy-Item .env.example .env
Get-Content configs/runtime-profiles/balanced.env | Add-Content .env
~~~

只选择一个 profile。fast、balanced、deep 的完整变量集合分别见对应文件；profile 中的值会覆盖前面重复变量。

## 变更要求

修改配置变量时必须同步：

1. app/core/config.py 的字段和默认值
2. .env.example
3. 本页分类和说明
4. 相关启动、部署或发布文档
5. 配置相关测试或验证命令

相关页面：[配置说明](../getting-started/configuration.md)、[Docker 部署](../operations/docker.md)。
