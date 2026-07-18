# Backend Best Practices - Post v0.4.6 Fixes

## Rate Limiting

### ✅ Do: Use Atomic Operations
```python
from app.services.rate_limiter import SlidingWindowLimiter

limiter = SlidingWindowLimiter(max_attempts=10, window_seconds=60)

# GOOD: Atomic check and record
if limiter.try_acquire(user_key):
    # Proceed with operation
    pass
else:
    raise RateLimitedError("Too many attempts")
```

### ❌ Don't: Separate Check and Record
```python
# BAD: Race condition between check and record
if not limiter.is_limited(user_key):
    limiter.record(user_key)
    # Another thread could record between check and this point
```

---

## Bulkhead Pattern

### ✅ Do: Use Context Manager
```python
from app.services.bulkhead import bulkhead

# GOOD: Automatic cleanup
with bulkhead("llm"):
    result = call_llm_api()
```

### ❌ Don't: Manual Acquire/Release
```python
# BAD: Risk of forgetting to release
sem = _semaphore("llm")
acquired = sem.acquire()
try:
    result = call_llm_api()
finally:
    if acquired:  # Easy to forget this check
        sem.release()
```

---

## Redis Operations

### ✅ Do: Handle Failures Gracefully
```python
try:
    client.incr(key)
except (ValueError, TypeError, OSError) as e:
    logger.warning(f"Redis operation failed: {e}")
    # Fall back to in-memory or skip
    return fallback_operation()
```

### ✅ Do: Use Connection Pooling
```python
# GOOD: Connection pool configured automatically
import redis
client = redis.from_url(
    url,
    max_connections=50,  # Reuse connections
    health_check_interval=30
)
```

### ❌ Don't: Create Connections Without Cleanup
```python
# BAD: Connection leak
client = redis.Redis(host=host, port=port)
# Never closed!
```

---

## Context Variables vs Module Patching

### ✅ Do: Use Context Variables for Thread-Local State
```python
from contextvars import ContextVar

_REQUEST_USER: ContextVar[dict] = ContextVar("request_user", default=None)

def set_request_user(user: dict):
    token = _REQUEST_USER.set(user)
    return token

def get_request_user() -> dict | None:
    return _REQUEST_USER.get()
```

### ❌ Don't: Patch Module Attributes
```python
# BAD: Not thread-safe
import some_module
original = some_module.function
some_module.function = my_function  # Other threads see this!
try:
    result = some_module.do_work()
finally:
    some_module.function = original
```

---

## Double-Checked Locking

### ✅ Do: Simple Lock or Cache
```python
from functools import lru_cache

# GOOD: Thread-safe caching
@lru_cache(maxsize=1)
def get_singleton():
    return ExpensiveObject()
```

### ✅ Do: Always Lock if State is Mutable
```python
# GOOD: Simple and correct
with self._lock:
    if self._instance is None:
        self._instance = create_instance()
    return self._instance
```

### ❌ Don't: Double-Checked Lock in Python
```python
# BAD: Not safe without memory barriers
if self._instance is None:  # First check (unlocked)
    with self._lock:
        if self._instance is None:  # Second check (locked)
            self._instance = create_instance()  # Could be reordered!
return self._instance  # Might see partial initialization
```

---

## Database Connection Management

### ✅ Do: Use Context Managers
```python
def query_database():
    with self._connect() as conn:
        cursor = conn.execute("SELECT * FROM users")
        return cursor.fetchall()
    # Connection automatically closed
```

### ✅ Do: Validate Configuration
```python
def _connect(self):
    timeout = float(getattr(settings, "timeout", 10))
    # GOOD: Validate before use
    if not (0 < timeout < 3600):
        timeout = 10.0
    return sqlite3.connect(self.db_path, timeout=timeout)
```

### ❌ Don't: Create Connections Without Pooling
```python
# BAD: New connection every time
def query():
    conn = sqlite3.connect(db_path)  # No reuse!
    # ...
```

---

## Request Timeout Handling

### ✅ Do: Check Deadline Before Long Operations
```python
from app.services.request_context import deadline_exceeded, remaining_seconds

def long_operation():
    for batch in batches:
        if deadline_exceeded():
            raise TimeoutError("Request deadline exceeded")
        process_batch(batch)
```

### ✅ Do: Use Remaining Time for Nested Calls
```python
remaining = remaining_seconds()
if remaining is not None and remaining > 0:
    result = api_call(timeout=remaining - 0.5)  # Leave margin
```

---

## Memory Management

### ✅ Do: Use Bounded Collections
```python
from collections import deque

# GOOD: Automatically drops old entries
metrics = deque(maxlen=1000)
```

### ✅ Do: Make Limits Configurable
```python
import os

MAX_ITEMS = int(os.getenv("CACHE_MAX_ITEMS", "1000"))
cache = deque(maxlen=MAX_ITEMS)
```

### ❌ Don't: Unbounded Growth
```python
# BAD: Grows forever
metrics = []  # No limit!
metrics.append(new_metric)
```

---

## Error Handling

### ✅ Do: Specific Exception Types
```python
from app.services.quota_guard import QuotaExceededError

try:
    quota_guard.enforce_query_quota(user)
except QuotaExceededError as e:
    # Handle specifically
    return rate_limited_response(str(e))
```

### ✅ Do: Log with Context
```python
try:
    operation()
except Exception as e:
    logger.error(
        "operation_failed user_id=%s error=%s",
        user_id,
        str(e),
        exc_info=True  # Include traceback
    )
```

### ❌ Don't: Swallow Exceptions Silently
```python
# BAD: Silent failure
try:
    critical_operation()
except Exception:
    pass  # What happened?!
```

---

## Atomic Operations

### ✅ Do: Combine Related State Changes
```python
# GOOD: Atomic check and update
with self._lock:
    if self._counter < self._limit:
        self._counter += 1
        return True
    return False
```

### ❌ Don't: Split Check and Act
```python
# BAD: TOCTOU (Time-Of-Check-Time-Of-Use)
if self._counter < self._limit:  # Check
    # Race window here!
    self._counter += 1  # Act
```

---

## Configuration Validation

### ✅ Do: Validate Early with Defaults
```python
def __init__(self, config: dict):
    self.timeout = max(1, min(int(config.get("timeout", 30)), 300))
    self.max_retries = max(0, min(int(config.get("retries", 3)), 10))
```

### ✅ Do: Type Coercion with Error Handling
```python
try:
    value = int(config_value)
except (ValueError, TypeError):
    logger.warning(f"Invalid config value: {config_value}, using default")
    value = DEFAULT_VALUE
```

---

## Testing Concurrency Issues

### ✅ Do: Use Thread Pools for Race Condition Tests
```python
import threading

def test_concurrent_rate_limit():
    limiter = SlidingWindowLimiter(max_attempts=10, window_seconds=60)
    success_count = [0]
    lock = threading.Lock()

    def worker():
        if limiter.try_acquire("test"):
            with lock:
                success_count[0] += 1

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert success_count[0] == 10  # Exactly limit, not more
```

---

## Monitoring & Observability

### ✅ Do: Add Metrics for Critical Paths
```python
from app.services.runtime_metrics import RuntimeMetrics

metrics = RuntimeMetrics()

def critical_operation():
    try:
        result = operation()
        metrics.inc("operation_success_total")
        return result
    except Exception as e:
        metrics.inc("operation_error_total")
        raise
```

### ✅ Do: Log State Transitions
```python
logger.info(
    "rate_limit_enforced user_id=%s attempts=%d window=%d",
    user_id,
    current_attempts,
    window_seconds
)
```

---

## Summary Checklist

- [ ] Use `try_acquire()` for rate limiting
- [ ] Always use context managers for bulkhead
- [ ] Handle Redis failures with fallbacks
- [ ] Use context variables, not module patching
- [ ] Avoid double-checked locking
- [ ] Use connection pooling for databases
- [ ] Check deadlines in long operations
- [ ] Bound all collections
- [ ] Log errors with context
- [ ] Make critical operations atomic
- [ ] Validate all configuration
- [ ] Test concurrency scenarios
- [ ] Add metrics and logging

---

**Remember**: 
- **Atomicity**: Combine related state changes
- **Cleanup**: Use context managers
- **Validation**: Trust nothing from config
- **Observability**: Log, metric, trace
- **Testing**: Simulate real concurrency
