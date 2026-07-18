# 代码规范 (Code Standards)

本文档定义 QueryMind（智询） 项目的编码标准、最佳实践和代码风格指南。

## 目录

- [快速检查清单](#快速检查清单)
- [Python 代码规范](#python-代码规范)
- [TypeScript 代码规范](#typescript-代码规范)
- [命名规范](#命名规范)
- [文档字符串规范](#文档字符串规范)
- [注释规范](#注释规范)
- [错误处理](#错误处理)
- [性能最佳实践](#性能最佳实践)
- [安全编码](#安全编码)

---

## 快速检查清单

### 提交前检查

**Python 代码**:
```bash
# 1. 格式化代码
ruff format app/ tests/

# 2. 检查代码风格
ruff check app/ tests/

# 3. 自动修复问题
ruff check app/ tests/ --fix

# 4. 类型检查（可选）
mypy app/

# 5. 运行测试
pytest -v
```

**TypeScript 代码**:
```bash
cd frontend

# 1. 格式化代码
npm run format

# 2. 检查代码风格
npm run lint

# 3. 自动修复
npm run lint:fix

# 4. 类型检查
npm run type-check

# 5. 运行测试
npm run test
```

### 代码质量检查清单

**基本检查**:
- [ ] 代码格式化（运行格式化工具）
- [ ] 无 linter 错误
- [ ] 所有测试通过
- [ ] 无类型错误

**代码质量**:
- [ ] 函数长度 < 50 行
- [ ] 类职责单一
- [ ] 变量命名清晰
- [ ] 无重复代码
- [ ] 无硬编码的魔法数字

**文档**:
- [ ] 所有公共函数有文档字符串
- [ ] 复杂逻辑有注释
- [ ] API 文档已更新
- [ ] README 已更新（如需要）

**测试**:
- [ ] 新功能有单元测试
- [ ] 测试覆盖率 > 80%
- [ ] 边界条件已测试
- [ ] 错误处理已测试

**安全**:
- [ ] 输入验证
- [ ] 无 SQL 注入风险
- [ ] 无硬编码的密钥
- [ ] 敏感数据已加密

### 命名速查表

| 类型 | Python | TypeScript | 示例 |
|------|--------|------------|------|
| **文件** | `snake_case.py` | `camelCase.ts`<br>`PascalCase.tsx` | `user_service.py`<br>`apiClient.ts`<br>`UserProfile.tsx` |
| **类** | `PascalCase` | `PascalCase` | `UserRepository`<br>`QueryService` |
| **函数** | `snake_case` | `camelCase` | `get_user()`<br>`fetchData()` |
| **变量** | `snake_case` | `camelCase` | `user_count`<br>`isActive` |
| **常量** | `UPPER_SNAKE_CASE` | `UPPER_SNAKE_CASE` | `MAX_RETRY`<br>`API_BASE_URL` |
| **私有** | `_leading_underscore` | `#private` | `_cache`<br>`#apiKey` |

### 常见错误和修正

**❌ 错误示例** → **✅ 正确示例**

**1. 缺少类型提示**:
```python
# ❌ 错误
def search(query, top_k=10):
    pass

# ✅ 正确
def search(query: str, top_k: int = 10) -> list[dict]:
    pass
```

**2. 过长的函数**:
```python
# ❌ 错误 - 100+ 行的函数
def process_everything(data):
    # 验证、解析、处理、存储...
    pass

# ✅ 正确 - 拆分为小函数
def validate_data(data): pass
def parse_data(data): pass
def process_data(data): pass
def save_data(data): pass
```

**3. 不清晰的命名**:
```python
# ❌ 错误
def f(x, y):
    return x + y

# ✅ 正确
def calculate_total_price(base_price: float, tax: float) -> float:
    return base_price + tax
```

**4. 捕获所有异常**:
```python
# ❌ 错误
try:
    result = risky_operation()
except Exception:
    pass  # 吞掉异常

# ✅ 正确
try:
    result = risky_operation()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
    raise
except ConnectionError as e:
    logger.error(f"Connection failed: {e}")
    return default_value
```

**5. 无文档字符串**:
```python
# ❌ 错误
def search_documents(query, top_k):
    pass

# ✅ 正确
def search_documents(query: str, top_k: int = 10) -> list[dict]:
    """
    搜索文档。

    Args:
        query: 搜索查询字符串
        top_k: 返回的文档数量

    Returns:
        list[dict]: 文档列表
    """
    pass
```

### Ruff 配置速查

```toml
# pyproject.toml
[tool.ruff]
line-length = 120
target-version = "py311"

[tool.ruff.lint]
select = [
  "E",   # pycodestyle errors
  "F",   # pyflakes
  "W",   # warnings
  "I",   # isort
  "B",   # bugbear
  "UP",  # pyupgrade
]

ignore = [
  "E501",  # line too long
]
```

### 常用装饰器

```python
from functools import lru_cache, wraps
from typing import TypeVar, Callable

# 缓存
@lru_cache(maxsize=128)
def expensive_function(arg: str) -> str:
    return compute(arg)

# 计时器
def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        print(f"{func.__name__}: {time.time() - start:.2f}s")
        return result
    return wrapper

# 重试
def retry(max_attempts: int = 3):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    logger.warning(f"Retry {attempt + 1}/{max_attempts}")
        return wrapper
    return decorator
```

---

## Python 代码规范

### 基础规范

本项目的 Python 代码遵循 [PEP 8](https://peps.python.org/pep-0008/) 和 [PEP 257](https://peps.python.org/pep-0257/) 规范。PEP 8 定义了 Python 代码的格式规范，包括缩进、命名、空格等，而 PEP 257 则规定了文档字符串的编写标准。

遵循这些规范的好处包括：
1. **可读性提升** - 统一的代码风格让团队成员更容易理解彼此的代码
2. **减少认知负担** - 不需要在阅读代码时适应不同的风格
3. **工具支持** - 大多数 IDE 和代码检查工具都基于这些规范
4. **社区标准** - 符合 Python 社区的通用实践

### 代码格式化

代码格式化是保持代码风格一致的基础。本项目使用 Ruff 作为格式化和检查工具，它比传统的 Black + Flake8 组合更快，同时功能更强大。

**为什么选择 Ruff**：
- **速度快** - 使用 Rust 编写，比 Python 工具快 10-100 倍
- **功能全面** - 集成了格式化、linting、导入排序等功能
- **兼容性好** - 与现有工具（Black、isort）兼容
- **配置简单** - 单一配置文件管理所有规则

**工具**: Ruff (格式化器 + Linter)

**配置** (`pyproject.toml`):
```toml
[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
select = [
  "E",   # pycodestyle errors
  "F",   # pyflakes
  "W",   # pycodestyle warnings
  "I",   # isort
  "B",   # flake8-bugbear
  "UP",  # pyupgrade
]
ignore = [
  "E501",  # line too long (handled by formatter)
  "B008",  # function calls in argument defaults
]
```

**运行格式化**:
```bash
# 格式化代码
ruff format app/ tests/

# 检查代码
ruff check app/ tests/

# 自动修复
ruff check app/ tests/ --fix
```

### 行长度

- **最大行长度**: 120 字符
- **文档字符串**: 72 字符
- **注释**: 72 字符

```python
# ✅ 好的
def process_query(query: str, user_id: str, top_k: int = 10) -> list[dict]:
    return retriever.search(query, user_id, top_k)

# ❌ 不好的 - 超过 120 字符
def process_query_with_very_long_parameter_list(query: str, user_id: str, top_k: int, enable_reranker: bool, similarity_threshold: float) -> list[dict]:
    pass
```

### 导入规范

**顺序**:
1. 标准库
2. 第三方库
3. 本地模块

```python
# ✅ 好的
import os
import sys
from pathlib import Path

from fastapi import FastAPI, Depends
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.auth import get_current_user
```

**避免**:
```python
# ❌ 不好的
from app.services.auth import *  # 避免 import *
import app.core.config as cfg     # 避免缩写
```

### 类型提示

类型提示（Type Hints）是 Python 3.5 引入的特性，它允许我们在代码中标注变量、参数和返回值的类型。虽然 Python 是动态类型语言，但类型提示提供了静态类型检查的好处，在不牺牲灵活性的前提下提升了代码质量。

**为什么使用类型提示**：
1. **早期发现错误** - 在编写代码时就能发现类型错误，而不是在运行时
2. **更好的 IDE 支持** - 自动补全、重构工具能提供更准确的建议
3. **文档作用** - 类型提示本身就是代码的文档，说明了函数的输入输出
4. **团队协作** - 让其他开发者更容易理解代码的预期用法
5. **重构信心** - 修改代码时，类型检查能确保没有破坏接口契约

**Python 3.11+ 的新语法**：
从 Python 3.10 开始，可以使用 `|` 运算符表示联合类型（Union），使代码更简洁。例如 `str | None` 替代 `Optional[str]`，`list[str]` 替代 `List[str]`。

**强制使用类型提示**（Python 3.11+）:

```python
# ✅ 好的
def search_documents(
    query: str,
    user_id: str,
    top_k: int = 10,
    filters: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    """搜索文档"""
    pass

# ✅ 使用新语法
def process_results(results: list[dict]) -> dict[str, Any]:
    pass

# ❌ 不好的 - 缺少类型提示
def search_documents(query, user_id, top_k=10):
    pass
```

**泛型类型**:
```python
from typing import Any, TypeVar, Generic

T = TypeVar('T')

class Repository(Generic[T]):
    def get(self, id: int) -> T | None:
        pass
    
    def list(self) -> list[T]:
        pass
```

### 函数和方法

函数是代码复用和抽象的基本单元。保持函数简短和专注是编写可维护代码的关键原则。

**为什么限制函数长度**：
- **单一职责** - 短函数通常只做一件事，更容易理解和测试
- **减少bug** - 复杂度低，出错的可能性也低
- **易于重用** - 小函数更容易在不同场景中复用
- **便于测试** - 测试用例更简单，边界条件更少
- **提高可读性** - 读者可以快速理解函数的作用

**如何拆分长函数**：
1. **提取子功能** - 将独立的逻辑块提取为独立函数
2. **使用辅助函数** - 将验证、转换等辅助逻辑分离
3. **引入中间层** - 对于复杂流程，引入协调函数
4. **使用组合** - 将多个小函数组合实现复杂功能

**函数长度**: 不超过 50 行（建议 20 行以内）

```python
# ✅ 好的 - 单一职责
def validate_query(query: str) -> bool:
    """验证查询是否有效"""
    if not query or not query.strip():
        return False
    if len(query) > 1000:
        return False
    return True

def sanitize_query(query: str) -> str:
    """清理查询字符串"""
    return query.strip().lower()

def process_query(query: str) -> str:
    """处理查询"""
    if not validate_query(query):
        raise ValueError("Invalid query")
    return sanitize_query(query)
```

**避免过长函数**:
```python
# ❌ 不好的 - 函数太长，职责不清
def process_user_request(request_data):
    # 100+ 行代码...
    # 验证、解析、处理、存储、返回
    pass
```

### 类设计

类是面向对象编程的核心，良好的类设计能让代码更易维护和扩展。SOLID 原则是面向对象设计的五个基本原则，它们共同构成了高质量代码的基础。

**SOLID 原则简介**：
1. **S - 单一职责原则（Single Responsibility）**：一个类应该只有一个引起它变化的原因。换句话说，每个类只负责一个功能领域。
2. **O - 开闭原则（Open/Closed）**：类应该对扩展开放，对修改关闭。通过继承和接口实现新功能，而不是修改现有代码。
3. **L - 里氏替换原则（Liskov Substitution）**：子类应该能够替换父类而不影响程序的正确性。
4. **I - 接口隔离原则（Interface Segregation）**：不应该强迫客户端依赖它们不使用的接口。
5. **D - 依赖倒置原则（Dependency Inversion）**：高层模块不应该依赖低层模块，两者都应该依赖抽象。

**为什么遵循 SOLID**：
- **降低耦合** - 类之间的依赖关系更清晰，修改一个类不会影响其他类
- **提高内聚** - 相关的功能集中在一起，不相关的功能分离
- **易于测试** - 职责单一的类更容易编写单元测试
- **便于扩展** - 添加新功能时不需要修改现有代码
- **代码复用** - 小而专注的类更容易在不同场景中复用

**遵循 SOLID 原则**:

```python
# ✅ 好的 - 单一职责
class UserRepository:
    """负责用户数据访问"""
    def get_user(self, user_id: int) -> User | None:
        pass
    
    def create_user(self, user_data: dict) -> User:
        pass

class UserService:
    """负责用户业务逻辑"""
    def __init__(self, repository: UserRepository):
        self.repository = repository
    
    def register_user(self, username: str, password: str) -> User:
        # 业务逻辑
        pass
```

**数据类**:
```python
from dataclasses import dataclass
from datetime import datetime

# ✅ 使用 dataclass
@dataclass
class Document:
    id: str
    content: str
    source: str
    created_at: datetime
    metadata: dict[str, Any] | None = None
```

### 异常处理

```python
# ✅ 好的 - 具体的异常
try:
    result = vector_store.search(query)
except ConnectionError as e:
    logger.error(f"Failed to connect to vector store: {e}")
    raise
except ValueError as e:
    logger.warning(f"Invalid query: {e}")
    return []

# ❌ 不好的 - 捕获所有异常
try:
    result = vector_store.search(query)
except Exception:
    pass  # 吞掉异常
```

**自定义异常**:
```python
# app/core/exceptions.py
class RAGException(Exception):
    """RAG 系统基础异常"""
    pass

class RetrievalError(RAGException):
    """检索错误"""
    pass

class AuthenticationError(RAGException):
    """认证错误"""
    pass
```

### 上下文管理器

```python
# ✅ 好的 - 使用上下文管理器
from contextlib import contextmanager

@contextmanager
def database_connection():
    conn = create_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# 使用
with database_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
```

### 装饰器

```python
# ✅ 好的 - 使用 functools.wraps
from functools import wraps
import time

def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} took {end - start:.2f}s")
        return result
    return wrapper

@timer
def slow_function():
    time.sleep(1)
```

---

## TypeScript 代码规范

### 基础规范

遵循 [TypeScript 官方风格指南](https://www.typescriptlang.org/docs/handbook/declaration-files/do-s-and-don-ts.html)。

### 代码格式化

**工具**: ESLint + Prettier

**配置** (`frontend/.eslintrc.json`):
```json
{
  "extends": [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
    "plugin:react-hooks/recommended"
  ],
  "rules": {
    "semi": ["error", "always"],
    "quotes": ["error", "double"],
    "@typescript-eslint/no-unused-vars": "error"
  }
}
```

**Prettier 配置** (`frontend/.prettierrc`):
```json
{
  "semi": true,
  "trailingComma": "es5",
  "singleQuote": false,
  "printWidth": 100,
  "tabWidth": 2
}
```

### 类型定义

**使用 interface 和 type**:

```typescript
// ✅ 好的 - 使用 interface 定义对象结构
interface User {
  id: string;
  username: string;
  email: string;
  role: "user" | "admin";
}

// ✅ 使用 type 定义联合类型
type QueryStatus = "pending" | "success" | "error";

type ApiResponse<T> = {
  data: T;
  status: number;
  message: string;
};
```

**避免 any**:
```typescript
// ❌ 不好的
function processData(data: any): any {
  return data;
}

// ✅ 好的
function processData<T>(data: T): T {
  return data;
}
```

### React 组件

**函数组件**:
```typescript
// ✅ 好的 - 使用 FC 类型
import React, { FC, useState } from "react";

interface ChatMessageProps {
  content: string;
  sender: "user" | "assistant";
  timestamp: Date;
}

export const ChatMessage: FC<ChatMessageProps> = ({ content, sender, timestamp }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className={`message message-${sender}`}>
      <p>{content}</p>
      <span>{timestamp.toLocaleString()}</span>
    </div>
  );
};
```

**Hooks**:
```typescript
// ✅ 好的 - 自定义 Hook
import { useState, useEffect } from "react";

interface UseQueryResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}

export function useQuery<T>(url: string): UseQueryResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    fetch(url)
      .then((res) => res.json())
      .then(setData)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [url]);

  return { data, loading, error };
}
```

### API 调用

```typescript
// ✅ 好的 - 类型安全的 API 客户端
import axios, { AxiosResponse } from "axios";

interface QueryRequest {
  question: string;
  sessionId: string;
}

interface QueryResponse {
  answer: string;
  sources: string[];
  confidence: number;
}

class ApiClient {
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  async query(request: QueryRequest): Promise<QueryResponse> {
    const response: AxiosResponse<QueryResponse> = await axios.post(
      `${this.baseURL}/api/query`,
      request
    );
    return response.data;
  }
}
```

---

## 命名规范

### Python 命名

| 类型 | 规范 | 示例 |
|------|------|------|
| **模块** | `snake_case` | `user_service.py` |
| **类** | `PascalCase` | `UserRepository` |
| **函数/方法** | `snake_case` | `get_user_by_id()` |
| **变量** | `snake_case` | `user_count` |
| **常量** | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| **私有成员** | `_leading_underscore` | `_internal_cache` |

```python
# ✅ 好的
class VectorRetriever:
    MAX_RESULTS = 100
    
    def __init__(self):
        self._cache = {}
    
    def search_documents(self, query: str) -> list[dict]:
        pass
    
    def _build_query(self, query: str) -> str:
        pass
```

### TypeScript 命名

| 类型 | 规范 | 示例 |
|------|------|------|
| **文件** | `PascalCase.tsx` (组件)<br>`camelCase.ts` (工具) | `ChatMessage.tsx`<br>`apiClient.ts` |
| **组件** | `PascalCase` | `UserProfile` |
| **函数** | `camelCase` | `fetchUserData()` |
| **变量** | `camelCase` | `userId` |
| **常量** | `UPPER_SNAKE_CASE` | `API_BASE_URL` |
| **Interface/Type** | `PascalCase` | `UserData` |

```typescript
// ✅ 好的
const API_BASE_URL = "http://localhost:8000";

interface UserProfile {
  userId: string;
  displayName: string;
}

function fetchUserProfile(userId: string): Promise<UserProfile> {
  return fetch(`${API_BASE_URL}/users/${userId}`).then((r) => r.json());
}
```

### 命名最佳实践

**清晰胜过简洁**:
```python
# ✅ 好的
retrieved_documents = retriever.search(query)
user_session_count = len(sessions)

# ❌ 不好的
docs = ret.search(q)
n = len(s)
```

**布尔值命名**:
```python
# ✅ 好的
is_authenticated = check_auth(token)
has_permission = user.role == "admin"
should_retry = error_count < MAX_RETRIES

# ❌ 不好的
authenticated = check_auth(token)
permission = user.role == "admin"
```

**避免魔法数字**:
```python
# ✅ 好的
MAX_RETRY_COUNT = 3
DEFAULT_TIMEOUT = 30

if retry_count > MAX_RETRY_COUNT:
    raise TimeoutError()

# ❌ 不好的
if retry_count > 3:
    raise TimeoutError()
```

---

## 文档字符串规范

### Python Docstring

**使用 Google 风格**:

```python
def search_documents(
    query: str,
    user_id: str,
    top_k: int = 10,
    filters: dict[str, str] | None = None
) -> list[dict]:
    """
    搜索用户的文档。

    执行混合检索（向量 + BM25），并返回最相关的文档。

    Args:
        query: 搜索查询字符串
        user_id: 用户 ID，用于过滤文档
        top_k: 返回的文档数量，默认 10
        filters: 可选的元数据过滤条件

    Returns:
        list[dict]: 文档列表，每个文档包含 text、metadata、score

    Raises:
        ValueError: 如果 query 为空或 top_k <= 0
        ConnectionError: 如果无法连接到向量数据库

    Example:
        >>> results = search_documents("什么是 RAG", "user_123", top_k=5)
        >>> len(results)
        5
    """
    if not query:
        raise ValueError("Query cannot be empty")
    
    # 实现...
```

**类的 Docstring**:
```python
class VectorRetriever:
    """
    向量检索器，用于语义搜索。

    使用 ChromaDB 进行向量存储和检索，支持余弦相似度搜索
    和元数据过滤。

    Attributes:
        collection_name: ChromaDB 集合名称
        embedding_model: 用于生成嵌入的模型
        _client: ChromaDB 客户端实例

    Example:
        >>> retriever = VectorRetriever("my_collection")
        >>> results = retriever.search("machine learning", top_k=5)
    """
    
    def __init__(self, collection_name: str):
        """
        初始化向量检索器。

        Args:
            collection_name: ChromaDB 集合名称
        """
        self.collection_name = collection_name
```

### TypeScript JSDoc

```typescript
/**
 * 搜索文档
 *
 * 执行混合检索并返回最相关的文档。
 *
 * @param query - 搜索查询字符串
 * @param topK - 返回的文档数量
 * @returns Promise 包含文档列表
 * @throws {Error} 如果查询为空
 *
 * @example
 * ```typescript
 * const results = await searchDocuments("machine learning", 5);
 * console.log(results.length); // 5
 * ```
 */
async function searchDocuments(query: string, topK: number): Promise<Document[]> {
  if (!query) {
    throw new Error("Query cannot be empty");
  }
  // 实现...
}
```

---

## 注释规范

### 何时添加注释

**需要注释**:
- 复杂的算法逻辑
- 非显而易见的优化
- 已知的限制或 TODO
- 引用外部资源

```python
# ✅ 好的 - 解释为什么
# 使用 RRF (Reciprocal Rank Fusion) 算法融合向量和 BM25 结果
# k=60 是经过实验验证的最优参数
rrf_score = 1.0 / (60 + rank)

# TODO: 考虑使用 LambdaMART 替代 RRF 以提高精度
# See: https://github.com/project/issues/123
```

**不需要注释**:
```python
# ❌ 不好的 - 显而易见
# 增加计数器
count += 1

# ❌ 不好的 - 重复代码
# 获取用户名
username = user.get_username()
```

### 注释风格

```python
# 单行注释使用 #

"""
多行注释使用三引号
通常用于模块级文档
"""

# TODO: 待办事项
# FIXME: 需要修复的问题
# NOTE: 重要说明
# HACK: 临时解决方案
# XXX: 警告或注意事项
```

---

## 错误处理

异常处理是编写健壮代码的关键。好的异常处理能够让程序在遇到错误时优雅地降级，而不是直接崩溃。

**异常处理的重要性**：
1. **提高可靠性** - 程序能够从错误中恢复，而不是直接终止
2. **便于调试** - 清晰的错误信息帮助快速定位问题
3. **用户体验** - 向用户提供友好的错误提示，而不是技术性的堆栈跟踪
4. **分离关注点** - 业务逻辑和错误处理逻辑分离，代码更清晰

**异常处理原则**：
- **捕获具体异常** - 避免使用 `except Exception`，这会捕获所有异常，包括你不想捕获的（如 KeyboardInterrupt）
- **不要吞掉异常** - 捕获后应该记录日志或重新抛出，除非你确定要忽略这个错误
- **及早失败** - 在问题发生的地方抛出异常，而不是让错误悄悄传播
- **使用上下文** - 异常消息应该包含足够的上下文信息，帮助定位问题

**为什么避免捕获所有异常**：
使用 `except Exception` 会捕获所有异常，包括程序错误（如 NameError、TypeError）和系统信号（如 KeyboardInterrupt）。这可能导致：
- 掩盖真正的 bug
- 无法通过 Ctrl+C 中断程序
- 调试困难，因为错误被静默处理

### 异常层次

```python
# app/core/exceptions.py

class RAGException(Exception):
    """基础异常"""
    pass

class ValidationError(RAGException):
    """验证错误"""
    pass

class RetrievalError(RAGException):
    """检索错误"""
    pass

class AuthenticationError(RAGException):
    """认证错误"""
    pass
```

### 错误处理最佳实践

```python
# ✅ 好的 - 具体的异常处理
try:
    result = vector_store.search(query)
except ConnectionError as e:
    logger.error(f"Vector store connection failed: {e}")
    # 降级到 BM25
    result = bm25_retriever.search(query)
except ValueError as e:
    logger.warning(f"Invalid query: {e}")
    raise ValidationError(f"Query validation failed: {e}") from e

# ✅ 好的 - 使用 finally 清理资源
file = None
try:
    file = open("data.txt")
    process(file)
except IOError as e:
    logger.error(f"File operation failed: {e}")
finally:
    if file:
        file.close()
```

---

## 性能最佳实践

性能优化应该基于实际的性能测量，而不是猜测。过早优化是万恶之源，但了解常见的性能模式可以帮助你在设计阶段就避免明显的性能问题。

**性能优化的原则**：
1. **先测量再优化** - 使用性能分析工具找到真正的瓶颈
2. **关注热点代码** - 优化执行频率高的代码路径
3. **权衡复杂度** - 优化不应该牺牲代码可读性和维护性
4. **考虑实际场景** - 优化应该针对实际的使用模式

### 1. 使用生成器

生成器（Generator）是 Python 中实现惰性求值的方式。它们不会一次性将所有数据加载到内存，而是按需产生数据。这对于处理大文件或大数据集特别有用。

**为什么使用生成器**：
- **内存高效** - 一次只处理一个元素，不需要在内存中保存所有数据
- **延迟计算** - 只在需要时才计算下一个元素
- **可组合** - 多个生成器可以串联处理数据流
- **无限序列** - 可以表示无限序列（如斐波那契数列）

**适用场景**：
- 读取大文件（逐行处理）
- 处理数据库查询结果
- 生成序列数据
- 流式处理管道

```python
# ✅ 好的 - 内存高效
def process_large_file(filename: str):
    with open(filename) as f:
        for line in f:  # 生成器
            yield process_line(line)

# ❌ 不好的 - 内存占用大
def process_large_file(filename: str):
    with open(filename) as f:
        lines = f.readlines()  # 一次性读入内存
        return [process_line(line) for line in lines]
```

### 2. 缓存

缓存是提高性能最有效的方法之一。通过缓存昂贵计算的结果，可以避免重复计算。Python 的 `functools.lru_cache` 提供了简单易用的内存缓存。

**LRU (Least Recently Used) 缓存原理**：
- **固定大小** - 缓存有最大容量限制（maxsize）
- **自动淘汰** - 当缓存满时，删除最久未使用的条目
- **O(1) 访问** - 使用哈希表实现，查找速度快

**何时使用缓存**：
- 计算开销大（如复杂数学运算、API 调用）
- 相同输入会重复出现
- 函数是纯函数（相同输入总是产生相同输出）
- 输入参数是可哈希的（hashable）

**注意事项**：
- 不要缓存有副作用的函数
- 注意内存占用（设置合理的 maxsize）
- 对于可变参数（如 list、dict），需要转换为不可变类型

```python
from functools import lru_cache

# ✅ 好的 - 缓存昂贵计算
@lru_cache(maxsize=128)
def compute_embedding(text: str) -> list[float]:
    return embedding_model.embed(text)
```

### 3. 批处理

批处理是将多个小操作合并为一个大操作的技术。这可以显著减少网络往返次数、数据库连接开销和函数调用开销。

**批处理的优势**：
- **减少开销** - 减少网络请求、数据库连接等固定开销
- **提高吞吐量** - 一次处理多个项目，提高整体效率
- **更好的资源利用** - 批量操作可以更好地利用缓存和并行处理

**何时使用批处理**：
- 数据库插入/更新操作
- API 调用（如批量嵌入生成）
- 文件 I/O 操作
- 网络请求

**最佳实践**：
- 选择合适的批大小（太小效率低，太大可能超时或占用过多内存）
- 处理部分失败（某些项目失败不应该影响其他项目）
- 考虑事务（数据库批处理可能需要事务支持）

```python
# ✅ 好的 - 批量操作
def batch_insert_documents(documents: list[dict], batch_size: int = 100):
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        collection.add(batch)

# ❌ 不好的 - 逐个插入
for doc in documents:
    collection.add(doc)
```

---

## 安全编码

安全是软件开发的重要方面。虽然不能完全杜绝安全漏洞，但遵循安全编码实践可以大大减少风险。

**安全编码的核心原则**：
1. **永远不要信任用户输入** - 所有外部输入都应该验证和清理
2. **最小权限原则** - 只授予必要的权限
3. **深度防御** - 多层安全措施，不依赖单一防线
4. **及时更新** - 定期更新依赖包，修复已知漏洞
5. **敏感数据保护** - 加密存储和传输敏感信息

### 1. 输入验证

输入验证是防御的第一道防线。所有来自外部的数据（用户输入、API 调用、文件上传等）都应该被视为不可信的。

**为什么需要输入验证**：
- **防止注入攻击** - SQL 注入、命令注入、XSS 等
- **数据完整性** - 确保数据符合预期格式
- **业务逻辑保护** - 防止非法的业务操作
- **资源保护** - 防止恶意输入消耗过多资源

**验证策略**：
- **白名单优于黑名单** - 明确允许什么，而不是禁止什么
- **类型检查** - 使用 Pydantic 等工具进行严格的类型验证
- **范围限制** - 限制数值范围、字符串长度等
- **格式验证** - 使用正则表达式验证邮箱、URL 等格式

Pydantic 的 `Field` 函数提供了丰富的验证选项：
- `min_length`/`max_length` - 限制字符串或列表长度
- `ge`/`le` - 限制数值范围（大于等于/小于等于）
- `regex` - 正则表达式验证
- 自定义验证器可以实现更复杂的验证逻辑

```python
# ✅ 好的
from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=10, ge=1, le=100)
```

### 2. SQL 注入防护

SQL 注入是最常见也是最危险的 Web 应用漏洞之一。攻击者可以通过注入恶意 SQL 代码来访问、修改或删除数据库数据。

**SQL 注入的危害**：
- **数据泄露** - 窃取敏感数据（用户信息、密码等）
- **数据篡改** - 修改或删除数据
- **权限提升** - 获取管理员权限
- **服务器控制** - 在某些情况下可以执行系统命令

**防护方法**：
1. **使用参数化查询** - 永远不要拼接 SQL 字符串
2. **使用 ORM** - ORM（如 SQLAlchemy）会自动处理参数化
3. **输入验证** - 限制输入的字符和长度
4. **最小权限** - 数据库用户只有必要的权限

**参数化查询的工作原理**：
参数化查询将 SQL 语句和数据分开处理。数据库先编译 SQL 语句结构，然后再填充参数值。这样即使参数中包含特殊字符，也不会被解释为 SQL 代码。

字符串拼接（危险）：
```python
# ❌ 永远不要这样做
query = f"SELECT * FROM users WHERE username = '{username}'"
# 如果 username = "admin' OR '1'='1"
# 查询变成: SELECT * FROM users WHERE username = 'admin' OR '1'='1'
# 这会返回所有用户！
```

参数化查询（安全）：
```python
# ✅ 正确的做法
cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
# 数据库会将 username 作为字符串字面值处理，不会解释其中的 SQL 代码
```

```python
# ✅ 好的 - 使用参数化查询
cursor.execute("SELECT * FROM users WHERE username = ?", (username,))

# ❌ 不好的 - 字符串拼接
cursor.execute(f"SELECT * FROM users WHERE username = '{username}'")
```

### 3. 密钥管理

密钥（API 密钥、数据库密码、加密密钥等）是系统安全的关键。泄露的密钥可能导致严重的安全事故。

**密钥管理的重要性**：
- **访问控制** - 密钥控制对系统和数据的访问
- **审计追踪** - 泄露的密钥难以追踪来源
- **合规要求** - 许多法规要求安全地管理密钥
- **最小影响** - 正确的密钥管理可以限制泄露的影响范围

**密钥管理最佳实践**：
1. **永远不要硬编码** - 不要在代码中直接写入密钥
2. **使用环境变量** - 从环境变量或配置文件读取
3. **不要提交到版本控制** - 使用 .gitignore 排除包含密钥的文件
4. **使用密钥管理服务** - 在生产环境使用专门的密钥管理系统（如 AWS Secrets Manager、Azure Key Vault）
5. **定期轮换** - 定期更换密钥，限制泄露窗口
6. **最小权限** - 每个密钥只授予必要的权限
7. **加密存储** - 如果必须存储密钥，使用加密

**环境变量的优势**：
- 与代码分离，不会被误提交到版本控制
- 易于在不同环境中使用不同的密钥
- 可以通过部署系统安全地注入
- 不会出现在日志或错误消息中（如果正确处理）

**注意事项**：
- 环境变量在某些情况下仍可能被访问（如进程列表）
- 生产环境应使用更安全的密钥管理方案
- 开发环境可以使用 .env 文件（确保在 .gitignore 中）

```python
# ✅ 好的 - 从环境变量读取
import os
API_KEY = os.getenv("OPENAI_API_KEY")

# ❌ 不好的 - 硬编码
API_KEY = "sk-1234567890abcdef"
```

---

## 代码审查清单

使用此清单审查代码：

- [ ] 代码风格符合规范（运行 ruff/eslint）
- [ ] 所有函数有类型提示和文档字符串
- [ ] 没有明显的性能问题
- [ ] 错误处理得当
- [ ] 没有安全漏洞
- [ ] 测试覆盖充分
- [ ] 命名清晰易懂
- [ ] 没有重复代码
- [ ] 注释充分且有意义

---

## 下一步

了解代码规范后，建议继续阅读：

1. **[测试指南](testing.md)** - 测试框架和测试策略
2. **[API 开发](api-development.md)** - FastAPI 开发最佳实践
3. **[开发流程](workflow.md)** - Git 工作流程

---

**更新日期**: 2026-06-19  
**文档版本**: 1.0
