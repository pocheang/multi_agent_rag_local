# 从标准logging迁移到Structlog
# Migration Guide: Standard Logging to Structlog

本文档描述如何将现有代码从Python标准logging迁移到结构化日志（structlog）。

This document describes how to migrate existing code from Python's standard logging to structured logging (structlog).

---

## 为什么要迁移？ / Why Migrate?

### 问题 / Problems with Standard Logging

1. **日志难以解析** - 文本格式不便于机器处理
2. **缺乏结构化** - 无法按字段查询和过滤
3. **上下文传递困难** - 需要手动在每条日志中添加request_id等
4. **性能开销** - 字符串格式化在高频日志中成为瓶颈

### Structlog的优势 / Benefits of Structlog

1. ✅ **JSON格式** - 可直接导入ELK/Loki等日志系统
2. ✅ **自动上下文** - request_id/user_id自动附加到所有日志
3. ✅ **类型安全** - 键值对而非字符串插值
4. ✅ **性能优化** - 延迟序列化，仅在需要时格式化

---

## 安装依赖 / Install Dependencies

```bash
# 添加到requirements.txt
echo "structlog>=23.1.0" >> requirements.txt

# 安装
pip install structlog
```

---

## 迁移步骤 / Migration Steps

### Step 1: 初始化Structlog

在应用启动时配置structlog（通常在`app/main.py`）：

```python
# app/main.py
from app.core.logging_config import configure_structured_logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时配置
    configure_structured_logging(
        log_level="INFO",
        json_output=True,  # 生产环境使用JSON
        include_timestamp=True,
    )
    
    logger = structlog.get_logger(__name__)
    logger.info("application_started", version="0.6.1")
    
    yield
    
    logger.info("application_shutdown")
```

---

### Step 2: 逐模块迁移

#### 旧代码 / Old Code (Standard Logging)

```python
import logging

logger = logging.getLogger(__name__)

class EnhancedRouterAgent:
    def process(self, query: str, user_id: str):
        logger.info(f"Processing query for user {user_id}: {query[:50]}")
        
        try:
            result = self._route(query)
            logger.info(f"Query routed to {result['route']} (confidence: {result['confidence']:.2f})")
            return result
        except Exception as e:
            logger.error(f"Routing failed: {e}", exc_info=True)
            raise
```

#### 新代码 / New Code (Structlog)

```python
from app.core.logging_config import get_logger

logger = get_logger(__name__)

class EnhancedRouterAgent:
    def process(self, query: str, user_id: str):
        logger.info(
            "processing_query",
            user_id=user_id,
            query_preview=query[:50],
            agent="EnhancedRouterAgent"
        )
        
        try:
            result = self._route(query)
            logger.info(
                "query_routed",
                route=result["route"],
                confidence=result["confidence"],
                user_id=user_id
            )
            return result
        except Exception as e:
            logger.exception(
                "routing_failed",
                user_id=user_id,
                error_type=type(e).__name__
            )
            raise
```

**关键变化：**
- ❌ 不再使用f-string格式化
- ✅ 使用事件名称 + 键值对
- ✅ 使用`logger.exception()`自动捕获堆栈跟踪

---

### Step 3: 使用上下文绑定

#### 在API路由中绑定请求上下文

```python
# app/api/routes/query.py
from app.core.logging_config import get_logger, bind_context, clear_context
import uuid

logger = get_logger(__name__)

@router.post("/query")
async def query(request: QueryRequest):
    # 生成请求ID并绑定到日志上下文
    request_id = str(uuid.uuid4())
    bind_context(
        request_id=request_id,
        user_id=request.user_id,
        endpoint="/query"
    )
    
    try:
        logger.info("query_received", query=request.query)
        
        # 后续所有日志都会自动包含request_id和user_id
        result = await process_query(request.query)
        
        logger.info("query_completed", duration_ms=result.duration)
        return result
        
    finally:
        # 清理上下文
        clear_context()
```

**输出示例（JSON）：**
```json
{
  "event": "query_received",
  "query": "What is Docker?",
  "request_id": "req_abc123",
  "user_id": "user_456",
  "endpoint": "/query",
  "timestamp": "2026-07-06T10:30:45.123Z",
  "level": "info",
  "logger": "app.api.routes.query"
}
```

---

### Step 4: 使用上下文管理器

对于临时上下文（如Agent执行），使用`LogContext`：

```python
from app.core.logging_config import get_logger, LogContext

logger = get_logger(__name__)

class VectorRAGAgent:
    def retrieve(self, query: str, execution_id: str):
        with LogContext(execution_id=execution_id, agent="VectorRAGAgent"):
            logger.info("retrieval_started", query_length=len(query))
            
            results = self._search(query)
            
            logger.info(
                "retrieval_completed",
                num_results=len(results),
                top_score=results[0].score if results else 0
            )
            
            return results
```

---

## 迁移模式 / Migration Patterns

### 模式1: 简单日志消息

```python
# ❌ 旧
logger.info("Query processed successfully")

# ✅ 新
logger.info("query_processed")
```

---

### 模式2: 带变量的日志

```python
# ❌ 旧
logger.info(f"Retrieved {count} documents in {duration}ms")

# ✅ 新
logger.info("documents_retrieved", count=count, duration_ms=duration)
```

---

### 模式3: 错误日志

```python
# ❌ 旧
logger.error(f"Failed to connect to Neo4j: {str(e)}")

# ✅ 新
logger.error("neo4j_connection_failed", error=str(e), error_type=type(e).__name__)
```

---

### 模式4: 异常日志

```python
# ❌ 旧
try:
    result = dangerous_operation()
except Exception as e:
    logger.error("Operation failed", exc_info=True)

# ✅ 新
try:
    result = dangerous_operation()
except Exception as e:
    logger.exception("operation_failed", operation="dangerous_operation")
```

---

### 模式5: 调试日志

```python
# ❌ 旧
logger.debug(f"Intermediate state: {state}")

# ✅ 新
logger.debug("intermediate_state", state=state)
```

---

## 命名规范 / Naming Conventions

### 事件名称 / Event Names

使用snake_case，动词+名词形式：

- ✅ `query_received`
- ✅ `document_ingested`
- ✅ `agent_execution_started`
- ❌ `received_query`（动词后置）
- ❌ `QueryReceived`（驼峰命名）

### 字段名称 / Field Names

- ✅ `user_id` - 标识符
- ✅ `duration_ms` - 带单位
- ✅ `error_type` - 描述性
- ❌ `uid` - 缩写不清晰
- ❌ `time` - 单位不明确

---

## 性能优化 / Performance Optimization

### 1. 延迟求值

```python
# ❌ 低效 - 即使不记录也会执行expensive_function
logger.debug("debug_info", data=expensive_function())

# ✅ 高效 - 使用lambda延迟求值
logger.debug("debug_info", data=lambda: expensive_function())
```

### 2. 条件日志

```python
# ❌ 低效
if logger.isEnabledFor(logging.DEBUG):
    logger.debug("detailed_info", data=compute_details())

# ✅ 高效 - structlog自动跳过禁用级别
logger.debug("detailed_info", data=compute_details())
```

---

## ELK集成示例 / ELK Integration Example

### Logstash配置

```ruby
# logstash.conf
input {
  file {
    path => "/var/log/rag-system/*.log"
    codec => json
  }
}

filter {
  # 添加地理位置（如果有IP）
  if [client_ip] {
    geoip {
      source => "client_ip"
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "rag-logs-%{+YYYY.MM.dd}"
  }
}
```

### Kibana查询示例

```
# 查找特定用户的错误
user_id:"user_123" AND level:"error"

# 查找慢查询（>2秒）
event:"query_completed" AND duration_ms:>2000

# 查找特定Agent的执行
agent:"EnhancedRouterAgent" AND event:"query_routed"
```

---

## 迁移检查清单 / Migration Checklist

- [ ] 在`app/main.py`中配置structlog
- [ ] 更新`app/agents/`中的所有Agent
- [ ] 更新`app/api/routes/`中的所有路由
- [ ] 在API中间件中添加request_id绑定
- [ ] 更新`app/services/`中的服务
- [ ] 删除旧的`QualityAgentLogger`（如果不再需要）
- [ ] 更新日志相关测试
- [ ] 配置日志聚合系统（ELK/Loki）
- [ ] 更新监控告警规则
- [ ] 团队培训 - 新的日志模式

---

## 常见问题 / FAQ

### Q: 是否需要一次性迁移所有文件？

A: 不需要。Structlog与标准logging兼容，可以逐步迁移。建议优先迁移高频调用的模块。

### Q: 如何处理第三方库的日志？

A: 第三方库的日志会继续使用标准logging，Structlog会捕获并转换它们的输出。

### Q: JSON格式对开发不友好怎么办？

A: 开发环境使用`json_output=False`，获得彩色的人类可读输出。

### Q: 如何在Jupyter Notebook中使用？

```python
from app.core.logging_config import configure_structured_logging, get_logger

configure_structured_logging(json_output=False)  # 人类可读
logger = get_logger("notebook")
logger.info("experiment_started", model="gpt-4", dataset="test_set")
```

---

## 验证迁移 / Verify Migration

### 测试日志输出

```python
from app.core.logging_config import configure_structured_logging, get_logger, bind_context

# 配置
configure_structured_logging(json_output=True)

# 测试
logger = get_logger("test")
bind_context(request_id="test_123", user_id="test_user")

logger.info("test_event", key1="value1", key2=42)
logger.error("test_error", error="Sample error")

# 预期输出（JSON格式）：
# {"event": "test_event", "key1": "value1", "key2": 42, "request_id": "test_123", ...}
```

---

## 相关资源 / Related Resources

- [Structlog文档](https://www.structlog.org/en/stable/)
- [ELK Stack配置](https://www.elastic.co/guide/en/logstash/current/index.html)
- [日志最佳实践](https://12factor.net/logs)
- [JSON日志格式](https://jsonlines.org/)
