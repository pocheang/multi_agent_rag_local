# 缓存系统安全审计报告

**日期**: 2026-08-20  
**审计范围**: QueryMind 项目所有缓存实现  
**审计人**: Claude Code

## 执行摘要

本次审计发现了 **9 个安全问题**，包括 3 个高危漏洞、4 个中危问题和 2 个低危问题。主要风险集中在缓存隔离、并发安全和资源耗尽防护方面。

---

## 🔴 高危问题 (Critical)

### 1. **用户缓存隔离不完整** - `query_result_cache.py`

**位置**: [app/services/runtime/query_result_cache.py:140-200](app/services/runtime/query_result_cache.py#L140-L200)

**问题描述**:
虽然代码在 `get()` 和 `set()` 方法中添加了 `user_id` 验证，但存在以下漏洞：

1. **验证逻辑可被绕过**: 
   - `get()` 方法中，`user_id` 是可选参数，如果调用时不传递，验证会被跳过
   - 攻击者可以通过不传递 `user_id` 参数来访问其他用户的缓存数据

2. **session_id 缓存没有验证**:
   ```python
   # Line 154-166: session 缓存路径没有用户验证
   if session_id:
       v = self._session_memory.get(f"session:{session_id}:{key}")
       if isinstance(v, dict):
           # 这里有验证，但如果 user_id=None，验证被跳过
           if user_id and v.get("user_id") != user_id:
               return None
           return v
   ```

3. **Redis 缓存键没有用户隔离**:
   ```python
   # Line 172: Redis key 格式: qcache:{key}
   raw = client.get(f"qcache:{key}")
   ```
   - 缓存键不包含 `user_id`，不同用户可能共享相同的查询缓存
   - `build_key()` 方法虽然包含 `user_id`，但如果两个用户的其他参数相同，可能产生哈希碰撞

**影响**:
- **数据泄露**: 用户 A 可能读取到用户 B 的查询结果
- **隐私侵犯**: 敏感查询内容可能被跨用户访问
- **合规风险**: 违反数据隔离要求

**修复建议**:
```python
def get(self, key: str, session_id: str | None = None, user_id: str | None = None) -> dict[str, Any] | None:
    # 1. 强制要求 user_id
    if not user_id:
        logger.warning("Cache get without user_id is not allowed")
        return None
    
    # 2. 将 user_id 包含在 Redis key 中
    redis_key = f"qcache:{user_id}:{key}"
    
    # 3. 所有缓存路径都验证用户归属
    ...
```

---

### 2. **并发竞态条件** - `query_result_cache.py`

**位置**: [app/services/runtime/query_result_cache.py:231-262](app/services/runtime/query_result_cache.py#L231-L262)

**问题描述**:
`mark_inflight()` 方法存在 **检查-使用 (TOCTOU) 竞态条件**：

```python
# Line 240-261
if key in self._inflight:
    return False  # 检查点 A
if backend == "redis":
    # ... Redis 操作
    locked = bool(client.set(..., nx=True, ...))  # 使用点 B
    if not locked:
        return False
    self._inflight_tokens[key] = token
self._inflight[key] = now  # 使用点 C
return True
```

**攻击场景**:
1. 线程 1 执行到检查点 A，发现 key 不存在
2. 线程 2 同时执行到检查点 A，也发现 key 不存在
3. 两个线程都认为可以标记为 inflight，导致重复请求

**影响**:
- 重复查询执行，浪费资源
- 缓存一致性问题
- 可能导致 DDoS 放大攻击

**修复建议**:
```python
def mark_inflight(self, key: str) -> bool:
    now = time.time()
    backend = self._effective_backend()
    
    with self._lock:  # 将整个检查-使用过程放在锁内
        # gc old inflight marks
        stale = [k for k, ts in self._inflight.items() if (now - ts) > self._ttl_seconds]
        for s in stale:
            self._inflight.pop(s, None)
            self._inflight_tokens.pop(s, None)
        
        if key in self._inflight:
            return False
        
        if backend == "redis":
            client = _get_redis_client()
            if client is not None:
                token = hashlib.sha256(f"{key}:{now}".encode()).hexdigest()
                try:
                    locked = bool(client.set(f"qinflight:{key}", token, nx=True, ex=max(1, int(self._ttl_seconds))))
                except Exception:
                    locked = False
                if not locked:
                    return False
                self._inflight_tokens[key] = token
        
        self._inflight[key] = now
        return True
```

---

### 3. **Redis 连接池耗尽** - `query_result_cache.py` & `caching.py`

**位置**: 
- [app/services/runtime/query_result_cache.py:38-50](app/services/runtime/query_result_cache.py#L38-L50)
- [app/retrievers/hybrid/caching.py:32-50](app/retrievers/hybrid/caching.py#L32-L50)

**问题描述**:

1. **`query_result_cache.py` 的连接池配置不完整**:
   ```python
   # Line 40-48: 添加了 max_connections=50，但缺少超时配置
   _REDIS_CLIENT = redis.from_url(
       str(getattr(settings, "redis_url", "")),
       decode_responses=True,
       socket_connect_timeout=0.2,  # 仅 0.2 秒，太短
       socket_timeout=0.2,  # 仅 0.2 秒，太短
       retry_on_timeout=False,  # 关闭重试
       max_connections=50,
       health_check_interval=30,
   )
   ```
   - 超时时间过短（200ms），在网络延迟或高负载时容易失败
   - `retry_on_timeout=False` 意味着瞬时网络抖动会导致缓存失效

2. **`caching.py` 的配置更好，但缺少文档**:
   ```python
   # Line 33-42: 配置合理
   _REDIS_CLIENT = redis.from_url(
       str(getattr(settings, "redis_url", "")),
       max_connections=50,
       socket_keepalive=True,
       socket_connect_timeout=5,  # 5秒，合理
       socket_timeout=5,  # 5秒，合理
       decode_responses=False,
       health_check_interval=30,
   )
   ```

3. **连接泄露风险**:
   - 两处代码都使用全局单例 `_REDIS_CLIENT`
   - 如果初始化失败后设置为 `None`，下次调用会重新创建连接
   - 但旧连接可能没有正确关闭，导致连接泄露

**影响**:
- Redis 连接池耗尽，导致所有缓存操作失败
- 应用性能下降或服务不可用
- 内存泄露

**修复建议**:

```python
def _get_redis_client():
    global _REDIS_CLIENT, _REDIS_UNAVAILABLE_UNTIL

    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT

    if _REDIS_UNAVAILABLE_UNTIL and time.monotonic() < _REDIS_UNAVAILABLE_UNTIL:
        return None

    with _REDIS_LOCK:
        if _REDIS_CLIENT is not None:
            return _REDIS_CLIENT

        if _REDIS_UNAVAILABLE_UNTIL and time.monotonic() < _REDIS_UNAVAILABLE_UNTIL:
            return None

        settings = get_settings()
        try:
            import redis

            # 关闭旧连接（如果存在）
            if _REDIS_CLIENT is not None:
                try:
                    _REDIS_CLIENT.close()
                except Exception as e:
                    logger.debug(f"Error closing old Redis connection: {e}")

            # 创建新连接，使用合理的超时配置
            _REDIS_CLIENT = redis.from_url(
                str(getattr(settings, "redis_url", "")),
                decode_responses=True,
                socket_connect_timeout=2.0,  # 增加到 2 秒
                socket_timeout=2.0,  # 增加到 2 秒
                retry_on_timeout=True,  # 启用重试
                retry_on_error=[redis.ConnectionError, redis.TimeoutError],
                max_connections=50,
                health_check_interval=30,
                socket_keepalive=True,  # 启用 keepalive
                socket_keepalive_options={
                    socket.TCP_KEEPIDLE: 60,
                    socket.TCP_KEEPINTVL: 10,
                    socket.TCP_KEEPCNT: 3,
                },
            )
            _REDIS_CLIENT.ping()
            _REDIS_UNAVAILABLE_UNTIL = 0.0
            return _REDIS_CLIENT

        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            # 确保清理
            if _REDIS_CLIENT is not None:
                try:
                    _REDIS_CLIENT.close()
                except Exception:
                    pass
                _REDIS_CLIENT = None

            _REDIS_UNAVAILABLE_UNTIL = time.monotonic() + _redis_retry_cooldown_seconds()
            return None
```

---

## 🟠 中危问题 (High)

### 4. **缓存键哈希碰撞风险** - `cache_manager.py`

**位置**: [app/services/caching/cache_manager.py:330-338](app/services/caching/cache_manager.py#L330-L338)

**问题描述**:
```python
def _generate_key(self, prefix: str, **kwargs) -> str:
    sorted_items = sorted(kwargs.items())
    key_str = f"{prefix}:" + ":".join(f"{k}={v}" for k, v in sorted_items)
    # 使用 MD5 哈希
    key_hash = hashlib.md5(key_str.encode()).hexdigest()
    return f"{prefix}:{key_hash}"
```

- **MD5 已不安全**: MD5 存在已知的碰撞攻击，攻击者可能构造不同的输入产生相同的哈希
- **缓存投毒**: 攻击者可以通过碰撞覆盖其他用户的缓存

**修复建议**:
```python
def _generate_key(self, prefix: str, **kwargs) -> str:
    sorted_items = sorted(kwargs.items())
    key_str = f"{prefix}:" + ":".join(f"{k}={v}" for k, v in sorted_items)
    # 使用 SHA-256 代替 MD5
    key_hash = hashlib.sha256(key_str.encode()).hexdigest()
    return f"{prefix}:{key_hash}"
```

---

### 5. **语义缓存内存泄露** - `semantic_cache.py`

**位置**: [app/services/caching/semantic_cache.py:102-110](app/services/caching/semantic_cache.py#L102-L110)

**问题描述**:
```python
async def set_with_embedding(self, query: str, query_embedding: np.ndarray, ...):
    # ...
    async with self._lock:
        self._embeddings_cache[query] = query_embedding
        
        # 仅使用 FIFO 清理
        if len(self._embeddings_cache) > self.max_candidates:
            oldest_query = next(iter(self._embeddings_cache))
            del self._embeddings_cache[oldest_query]
```

**问题**:
1. **embedding 向量占用大量内存**: 每个 numpy 数组可能占用数 KB
2. **FIFO 策略不合理**: 注释说"could use LRU"，但没有实现
3. **与 `cache_manager` 不同步**: embedding 缓存和实际结果缓存可能不一致

**影响**:
- 内存占用持续增长
- 语义搜索性能下降
- 可能导致 OOM

**修复建议**:
```python
class SemanticCache:
    def __init__(self, cache_manager: CacheManager, similarity_threshold: float = 0.95, max_candidates: int = 50):
        self.cache_manager = cache_manager
        self.similarity_threshold = similarity_threshold
        self.max_candidates = max_candidates
        # 改用 OrderedDict 实现 LRU
        self._embeddings_cache: OrderedDict[str, tuple[np.ndarray, float]] = OrderedDict()
        self._lock = asyncio.Lock()
    
    async def set_with_embedding(self, query: str, query_embedding: np.ndarray, ...):
        await self.cache_manager.set(prefix, result, l1_ttl=ttl, query=query)
        
        async with self._lock:
            # 存储 embedding 和时间戳
            self._embeddings_cache[query] = (query_embedding, time.time())
            self._embeddings_cache.move_to_end(query)
            
            # LRU 清理：移除最旧的
            while len(self._embeddings_cache) > self.max_candidates:
                self._embeddings_cache.popitem(last=False)
    
    async def get_similar(self, query: str, query_embedding: np.ndarray, prefix: str = "query") -> Optional[Any]:
        # ...
        async with self._lock:
            # 清理过期的 embeddings（与 cache_manager TTL 同步）
            now = time.time()
            expired = [q for q, (_, ts) in self._embeddings_cache.items() 
                      if now - ts > self.cache_manager.l1_cache.default_ttl]
            for q in expired:
                del self._embeddings_cache[q]
            
            # 语义搜索...
```

---

### 6. **TTLCache 时间复杂度问题** - `resilience.py`

**位置**: [app/services/runtime/resilience.py:111-176](app/services/runtime/resilience.py#L111-L176)

**问题描述**:
```python
def _evict(self) -> None:
    now = time.time()
    self._last_eviction = now
    
    # O(n) 扫描所有键
    stale_keys = [k for k, (exp, _v) in self._store.items() if exp <= now]
    for k in stale_keys:
        self._store.pop(k, None)
    
    # O(n) 限制大小
    while len(self._store) > self.max_items:
        self._store.popitem(last=False)
```

**问题**:
- 每次清理都是 O(n) 复杂度
- 虽然使用了 `_eviction_interval` 限流，但在高并发时仍然会阻塞
- `_evict()` 在持有锁的情况下执行，会阻塞所有读写操作

**影响**:
- 高负载下缓存性能下降
- 可能导致请求超时
- 锁竞争严重

**修复建议**:
```python
class TTLCache:
    def __init__(self, ttl_seconds: int, max_items: int):
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.max_items = max(1, int(max_items))
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.RLock()
        self._last_eviction = time.time()
        # 批量清理阈值
        self._eviction_batch_size = 100
        self._eviction_interval = max(1.0, float(ttl_seconds) / 10.0)
    
    def _evict(self) -> None:
        """增量清理，限制每次处理的数量"""
        now = time.time()
        self._last_eviction = now
        
        # 限制扫描数量，避免长时间持锁
        scanned = 0
        stale_keys = []
        
        for k, (exp, _v) in self._store.items():
            if scanned >= self._eviction_batch_size:
                break
            scanned += 1
            if exp <= now:
                stale_keys.append(k)
        
        # 批量删除
        for k in stale_keys:
            self._store.pop(k, None)
        
        # 限制大小（也限制批量）
        removed = 0
        while len(self._store) > self.max_items and removed < self._eviction_batch_size:
            self._store.popitem(last=False)
            removed += 1
```

---

### 7. **缓存键长度无限制** - `shared/cache.py`

**位置**: [app/agents/shared/cache.py:122-139](app/agents/shared/cache.py#L122-L139)

**问题描述**:
```python
def _make_cache_key(*args, **kwargs) -> str:
    key_parts = []
    for arg in args:
        if isinstance(arg, str):
            key_parts.append(arg[:100])  # 截断到 100 字符
        elif isinstance(arg, list | tuple):
            key_parts.append(str(sorted(arg))[:100])
        else:
            key_parts.append(str(arg)[:50])
    
    for k, v in sorted(kwargs.items()):
        if v is not None:
            key_parts.append(f"{k}={str(v)[:50]}")
    
    key_string = "|".join(key_parts)
    return hashlib.md5(key_string.encode("utf-8")).hexdigest()
```

**问题**:
1. **最终 key_string 长度仍然不受限**: 虽然单个部分被截断，但如果有很多 kwargs，总长度仍然可能很大
2. **使用 MD5**: 与问题 4 相同的哈希碰撞风险
3. **截断可能导致信息丢失**: `arg[:100]` 可能让不同的输入产生相同的缓存键

**修复建议**:
```python
def _make_cache_key(*args, **kwargs) -> str:
    """创建缓存键，限制总长度并使用安全哈希"""
    key_parts = []
    
    for arg in args:
        if isinstance(arg, str):
            key_parts.append(arg[:200])  # 增加截断长度
        elif isinstance(arg, (list, tuple)):
            # 对列表排序并限制元素数量
            sorted_arg = sorted(str(x) for x in arg)[:20]
            key_parts.append(",".join(sorted_arg)[:200])
        else:
            key_parts.append(str(arg)[:100])
    
    for k, v in sorted(kwargs.items()):
        if v is not None:
            key_parts.append(f"{k}={str(v)[:100]}")
    
    key_string = "|".join(key_parts)
    
    # 限制总长度，避免过大的键
    if len(key_string) > 1000:
        key_string = key_string[:1000] + f"_truncated_{len(key_string)}"
    
    # 使用 SHA-256 代替 MD5
    return hashlib.sha256(key_string.encode("utf-8")).hexdigest()
```

---

## 🟡 低危问题 (Medium)

### 8. **Redis 操作缺少错误边界** - `cache_manager.py`

**位置**: [app/services/caching/cache_manager.py:168-280](app/services/caching/cache_manager.py#L168-L280)

**问题描述**:
Redis 操作虽然有 try-except，但异常处理不够细致：

```python
async def get(self, key: str) -> Optional[Any]:
    try:
        raw = await client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.error(f"Error getting from Redis: {e}")
        return None
```

**问题**:
- 所有异常都被吞掉，包括严重的错误（如连接断开）
- 没有区分**瞬时错误**（可重试）和**永久错误**（需要降级）
- 没有监控和告警

**修复建议**:
```python
async def get(self, key: str) -> Optional[Any]:
    client = await self._get_client()
    if client is None:
        return None
    
    try:
        raw = await client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError) as e:
        # 数据损坏，删除该键
        logger.warning(f"Corrupted cache data for key {key}: {e}")
        try:
            await client.delete(key)
        except Exception:
            pass
        return None
    except (redis.ConnectionError, redis.TimeoutError) as e:
        # 瞬时错误，记录并返回
        logger.warning(f"Redis transient error: {e}")
        runtime_metrics.inc("redis_transient_error_total")
        return None
    except Exception as e:
        # 未知错误，记录并告警
        logger.error(f"Unexpected Redis error: {e}", exc_info=True)
        runtime_metrics.inc("redis_unknown_error_total")
        emit_alert("redis_unknown_error", {"key": key, "error": str(e)})
        return None
```

---

### 9. **缺少缓存预热和备份机制**

**位置**: 全局问题

**问题描述**:
当前系统缺少以下关键功能：

1. **缓存预热**: 应用重启后缓存全部失效，导致冷启动性能差
2. **缓存备份**: Redis 故障时无法恢复缓存数据
3. **缓存同步**: 多实例部署时，L1 缓存不一致

**影响**:
- 冷启动性能差
- Redis 故障影响面大
- 多实例部署时缓存效率低

**修复建议**:

1. **添加缓存预热**:
```python
# app/api/application/lifespan.py


async def warmup_cache():
    """预热高频查询缓存"""
    logger.info("Starting cache warmup...")

    # 从数据库加载常见查询
    popular_queries = await db.fetch_popular_queries(limit=100)

    for query in popular_queries:
        try:
            # 预执行查询，填充缓存
            await pipeline.execute(query)
        except Exception as e:
            logger.warning(f"Cache warmup failed for query: {e}")

    logger.info("Cache warmup completed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时预热
    await warmup_cache()
    yield
    # 关闭时...
```

2. **添加缓存备份**:
```python
# app/services/caching/backup.py


class CacheBackup:
    def __init__(self, cache_manager: CacheManager, backup_path: str):
        self.cache_manager = cache_manager
        self.backup_path = backup_path

    async def backup(self):
        """定期备份热点缓存"""
        stats = self.cache_manager.get_stats()
        hot_keys = self._get_hot_keys(stats)

        backup_data = {}
        for key in hot_keys:
            value = await self.cache_manager.l1_cache.get(key)
            if value is not None:
                backup_data[key] = value

        # 保存到磁盘
        with open(self.backup_path, "wb") as f:
            pickle.dump(backup_data, f)

    async def restore(self):
        """从备份恢复缓存"""
        if not os.path.exists(self.backup_path):
            return

        with open(self.backup_path, "rb") as f:
            backup_data = pickle.load(f)

        for key, value in backup_data.items():
            await self.cache_manager.l1_cache.set(key, value)
```

---

## 额外发现

### ✅ 做得好的地方

1. **多层缓存架构** (`cache_manager.py`):
   - L1 (内存) + L2 (Redis) 设计合理
   - 降级策略完善

2. **自适应 TTL** (`adaptive_cache.py`):
   - 根据查询复杂度调整缓存时长
   - 识别实时查询并跳过缓存

3. **circuit breaker 集成** (`resilience.py`):
   - 防止缓存故障雪崩
   - 自动降级和恢复

4. **并发安全** (大部分模块):
   - 使用了 `threading.Lock` 和 `asyncio.Lock`
   - OrderedDict 实现 LRU

---

## 修复优先级

| 优先级 | 问题 | 预计修复时间 | 风险等级 |
|--------|------|--------------|----------|
| P0 | #1 用户缓存隔离 | 4 小时 | 🔴 Critical |
| P0 | #2 并发竞态条件 | 2 小时 | 🔴 Critical |
| P0 | #3 Redis 连接池 | 3 小时 | 🔴 Critical |
| P1 | #4 哈希碰撞风险 | 1 小时 | 🟠 High |
| P1 | #5 内存泄露 | 3 小时 | 🟠 High |
| P1 | #6 TTLCache 性能 | 2 小时 | 🟠 High |
| P1 | #7 缓存键长度 | 1 小时 | 🟠 High |
| P2 | #8 错误边界 | 2 小时 | 🟡 Medium |
| P2 | #9 缓存预热 | 4 小时 | 🟡 Medium |

**总修复时间估算**: 约 22 小时（3 个工作日）

---

## 测试建议

修复后需要进行以下测试：

### 1. 安全测试
```python
# tests/security/test_cache_isolation.py


async def test_user_cache_isolation():
    """验证用户缓存隔离"""
    # 用户 A 查询
    result_a = await cache.get(key, user_id="user_a")
    await cache.set(key, {"data": "secret_a"}, user_id="user_a")

    # 用户 B 不应该访问到用户 A 的数据
    result_b = await cache.get(key, user_id="user_b")
    assert result_b is None

    # 无 user_id 不应该访问到任何数据
    result_none = await cache.get(key, user_id=None)
    assert result_none is None
```

### 2. 并发测试
```python
async def test_concurrent_inflight_marking():
    """验证并发场景下的 inflight 标记"""
    import asyncio

    results = await asyncio.gather(*[cache.mark_inflight(key) for _ in range(100)])

    # 只有一个请求应该成功
    assert sum(results) == 1
```

### 3. 性能测试
```bash
# 使用 locust 进行压力测试
locust -f tests/performance/cache_load_test.py --host=http://localhost:8000
```

### 4. 故障注入测试
```python
async def test_redis_failure_graceful_degradation():
    """验证 Redis 故障时的降级"""
    # 模拟 Redis 断开
    with mock.patch("redis.Redis.get", side_effect=redis.ConnectionError):
        # 应该降级到内存缓存
        result = await cache.get(key)
        assert result is not None  # 从 L1 获取
```

---

## 总结

QueryMind 的缓存系统架构设计合理，但在**安全性**和**并发安全**方面存在明显漏洞。建议：

1. **立即修复** 3 个高危问题（P0）
2. **本周内修复** 4 个中危问题（P1）
3. **下周修复** 2 个低危问题（P2）
4. **增加监控**: 缓存命中率、错误率、内存使用量
5. **增加文档**: 缓存策略说明、故障处理流程

修复后，系统的安全性和可靠性将大幅提升。
