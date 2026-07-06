# API 开发 (API Development)

本文档介绍如何使用 FastAPI 开发 QueryMind（智询） 系统的 REST API。

## 目录

- [快速参考](#快速参考)
- [FastAPI 基础](#fastapi-基础)
- [路由开发](#路由开发)
- [依赖注入](#依赖注入)
- [请求验证](#请求验证)
- [响应处理](#响应处理)
- [错误处理](#错误处理)
- [认证和授权](#认证和授权)
- [API 文档](#api-文档)
- [测试 API](#测试-api)

---

## 快速参考

### API 路由清单

| 路由组 | 前缀 | 说明 | 示例 |
|--------|------|------|------|
| **认证** | `/api/auth` | 用户认证和授权 | `POST /api/auth/login` |
| **查询** | `/api/query` | RAG 查询 | `POST /api/query` |
| **会话** | `/api/sessions` | 会话管理 | `GET /api/sessions` |
| **文档** | `/api/documents` | 文档管理 | `POST /api/documents/upload` |
| **用户** | `/api/users` | 用户管理 | `GET /api/users/profile` |
| **管理** | `/api/admin` | 管理员操作 | `GET /api/admin/users` |

### 常用 HTTP 方法

| 方法 | 用途 | 幂等性 | 示例 |
|------|------|-------|------|
| `GET` | 获取资源 | ✅ | `GET /api/users/123` |
| `POST` | 创建资源 | ❌ | `POST /api/users` |
| `PUT` | 更新资源（完整） | ✅ | `PUT /api/users/123` |
| `PATCH` | 更新资源（部分） | ❌ | `PATCH /api/users/123` |
| `DELETE` | 删除资源 | ✅ | `DELETE /api/users/123` |

### 常用状态码

| 状态码 | 说明 | 使用场景 |
|--------|------|---------|
| `200` | OK | 成功（GET、PUT、PATCH） |
| `201` | Created | 创建成功（POST） |
| `204` | No Content | 删除成功（DELETE） |
| `400` | Bad Request | 请求参数错误 |
| `401` | Unauthorized | 未认证 |
| `403` | Forbidden | 无权限 |
| `404` | Not Found | 资源不存在 |
| `409` | Conflict | 资源冲突 |
| `422` | Unprocessable Entity | 验证失败 |
| `429` | Too Many Requests | 限流 |
| `500` | Internal Server Error | 服务器错误 |

### 快速开发模板

**创建新路由模块**:
```python
# app/api/routes/items.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/items", tags=["items"])

class Item(BaseModel):
    name: str
    description: str | None = None
    price: float

@router.get("/")
async def list_items():
    return [{"name": "item1"}, {"name": "item2"}]

@router.get("/{item_id}")
async def get_item(item_id: int):
    return {"id": item_id, "name": "item"}

@router.post("/", status_code=201)
async def create_item(item: Item):
    return {"id": 123, **item.dict()}

@router.put("/{item_id}")
async def update_item(item_id: int, item: Item):
    return {"id": item_id, **item.dict()}

@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: int):
    return None
```

**注册路由**:
```python
# app/api/main.py
from app.api.routes import items

app.include_router(items.router, prefix="/api")
```

### Pydantic 模型速查

```python
from pydantic import BaseModel, Field, validator
from typing import Literal

class QueryRequest(BaseModel):
    # 必需字段
    question: str = Field(..., min_length=1, max_length=1000)
    
    # 可选字段（有默认值）
    top_k: int = Field(default=10, ge=1, le=100)
    
    # 枚举类型
    strategy: Literal["fast", "balanced", "deep"] = "balanced"
    
    # 自定义验证
    @validator("question")
    def validate_question(cls, v):
        if not v.strip():
            raise ValueError("Question cannot be empty")
        return v.strip()
```

### 依赖注入速查

```python
from fastapi import Depends
from typing import Annotated

# 简单依赖
def get_db():
    db = DatabaseConnection()
    try:
        yield db
    finally:
        db.close()

# 使用依赖
@router.get("/items")
async def list_items(db = Depends(get_db)):
    return db.query("SELECT * FROM items")

# 使用 Annotated 简化
Database = Annotated[DatabaseConnection, Depends(get_db)]

@router.get("/items")
async def list_items(db: Database):
    return db.query("SELECT * FROM items")
```

### 错误处理速查

```python
from fastapi import HTTPException

# 抛出标准错误
raise HTTPException(status_code=404, detail="Item not found")

# 自定义错误响应
from fastapi.responses import JSONResponse

return JSONResponse(
    status_code=400,
    content={
        "error": "validation_error",
        "message": "Invalid input",
        "details": {"field": "email", "issue": "invalid format"}
    }
)
```

### 认证速查

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    token = credentials.credentials
    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

# 使用
CurrentUser = Annotated[dict, Depends(get_current_user)]

@router.get("/profile")
async def get_profile(user: CurrentUser):
    return user
```

---

## FastAPI 基础

FastAPI 是一个现代化的 Python Web 框架，专为构建高性能 API 而设计。它基于标准的 Python 类型提示，能够自动生成 API 文档、进行请求验证，并支持异步编程。

**为什么选择 FastAPI**：
1. **高性能** - 性能可与 Node.js 和 Go 媲美，得益于 Starlette 和 Pydantic
2. **开发效率** - 自动文档生成、请求验证减少了大量样板代码
3. **类型安全** - 基于 Python 类型提示，IDE 能提供更好的支持
4. **异步支持** - 原生支持 async/await，适合 I/O 密集型应用
5. **标准兼容** - 基于 OpenAPI 和 JSON Schema 标准
6. **易于学习** - API 设计直观，文档完善

**FastAPI 的核心特性**：
- **自动文档** - 访问 `/docs` 可查看交互式 API 文档（Swagger UI）
- **数据验证** - 使用 Pydantic 模型自动验证请求数据
- **依赖注入** - 优雅的依赖管理系统
- **异步优先** - 默认支持异步处理，也兼容同步代码
- **WebSocket 支持** - 内置 WebSocket 支持，适合实时应用

### 项目结构

API 代码组织遵循清晰的分层架构，每个模块职责明确：

**目录职责说明**：
- **main.py** - 应用入口，负责创建 FastAPI 实例、配置中间件、注册路由
- **dependencies.py** - 依赖注入定义，如数据库连接、当前用户获取等
- **middleware.py** - 中间件配置，处理跨域、日志、错误捕获等横切关注点
- **routes/** - 路由模块，按功能分组（认证、查询、文档等），每个文件负责一组相关的 API 端点

这种结构的优势：
- **关注点分离** - 不同类型的代码放在不同的文件中
- **易于导航** - 按功能分组，容易找到相关代码
- **模块化** - 每个路由模块可以独立测试和维护
- **可扩展** - 添加新功能时只需增加新的路由文件

```
app/api/
├── main.py              # FastAPI 应用入口
├── dependencies.py      # 共享依赖
├── middleware.py        # 中间件
└── routes/             # 路由模块
    ├── auth.py         # 认证路由
    ├── query.py        # 查询路由
    ├── sessions.py     # 会话路由
    └── documents.py    # 文档路由
```

### 应用初始化

**app/api/main.py**:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, query, sessions, documents
from app.core.config import get_settings

settings = get_settings()

# 创建 FastAPI 应用
app = FastAPI(
    title="QueryMind（智询） API",
    version="0.4.4",
    description="Enterprise RAG system with multi-agent orchestration",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(query.router, prefix="/api/query", tags=["query"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])

# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.4.4"}
```

---

## 路由开发

### 基本路由

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/users", tags=["users"])

# 响应模型
class User(BaseModel):
    id: int
    username: str
    email: str

# GET 请求
@router.get("/", response_model=list[User])
async def list_users():
    """获取用户列表"""
    users = [
        User(id=1, username="alice", email="alice@example.com"),
        User(id=2, username="bob", email="bob@example.com")
    ]
    return users

# GET 请求（带路径参数）
@router.get("/{user_id}", response_model=User)
async def get_user(user_id: int):
    """获取单个用户"""
    if user_id == 1:
        return User(id=1, username="alice", email="alice@example.com")
    raise HTTPException(status_code=404, detail="User not found")

# POST 请求
class CreateUserRequest(BaseModel):
    username: str
    email: str
    password: str

@router.post("/", response_model=User, status_code=201)
async def create_user(request: CreateUserRequest):
    """创建用户"""
    # 创建用户逻辑
    new_user = User(id=3, username=request.username, email=request.email)
    return new_user

# PUT 请求
class UpdateUserRequest(BaseModel):
    email: str | None = None

@router.put("/{user_id}", response_model=User)
async def update_user(user_id: int, request: UpdateUserRequest):
    """更新用户"""
    # 更新逻辑
    return User(id=user_id, username="alice", email=request.email or "alice@example.com")

# DELETE 请求
@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: int):
    """删除用户"""
    # 删除逻辑
    return None
```

---

## 依赖注入

依赖注入是 FastAPI 的核心特性之一，它提供了一种优雅的方式来管理函数之间的依赖关系。通过依赖注入，我们可以复用代码、管理资源生命周期，并轻松地进行测试。

**依赖注入的优势**：
1. **代码复用** - 相同的依赖逻辑可以在多个路由中共享
2. **关注点分离** - 将资源管理（如数据库连接）从业务逻辑中分离
3. **易于测试** - 可以轻松地用测试替身（mock）替换真实的依赖
4. **自动文档** - FastAPI 会在 API 文档中显示依赖的参数
5. **资源管理** - 使用 yield 可以自动清理资源（如关闭数据库连接）

**依赖注入的工作原理**：
FastAPI 在调用路由函数之前，会先执行所有的依赖函数。依赖可以是简单的函数，也可以是返回值的生成器（用于资源管理）。依赖之间还可以相互依赖，形成依赖链。

### 基本依赖

最简单的依赖是一个返回值的函数。FastAPI 会自动调用这个函数，并将返回值作为参数传递给路由函数。

**使用场景**：
- 获取配置对象
- 创建数据库连接
- 初始化服务实例
- 执行权限检查

**生成器依赖（使用 yield）**：
当依赖使用 `yield` 时，FastAPI 会在请求处理前执行 yield 之前的代码，在请求处理后执行 yield 之后的代码。这对于需要清理资源的场景特别有用，如数据库连接、文件句柄等。

```python
from fastapi import Depends
from app.core.config import Settings, get_settings

# 简单依赖
def get_db():
    db = DatabaseConnection()
    try:
        yield db
    finally:
        db.close()

@router.get("/items")
async def list_items(db = Depends(get_db)):
    return db.query("SELECT * FROM items")
```

### 依赖链

依赖可以依赖其他依赖，形成依赖链。这样可以构建复杂的依赖关系，同时保持代码的清晰性。

**依赖链的优势**：
- **逐层抽象** - 每一层只关心直接依赖，不需要了解整个依赖树
- **灵活组合** - 可以在不同的路由中组合不同的依赖
- **便于替换** - 修改某一层依赖不会影响其他层
- **测试友好** - 可以在不同层次进行 mock

```python
# 获取配置
def get_settings() -> Settings:
    return Settings()

# 获取数据库（依赖配置）
def get_db(settings: Settings = Depends(get_settings)):
    return Database(settings.db_url)

# 获取仓储（依赖数据库）
def get_user_repository(db = Depends(get_db)):
    return UserRepository(db)

# 路由使用
@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    repo: UserRepository = Depends(get_user_repository)
):
    return repo.get(user_id)
```

### 认证依赖

```python
from fastapi import HTTPException, Header
from typing import Annotated

# 验证令牌
async def verify_token(authorization: str = Header(...)):
    """验证 JWT 令牌"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = authorization[7:]
    user = decode_jwt(token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return user

# 使用依赖
@router.get("/protected")
async def protected_route(user: dict = Depends(verify_token)):
    return {"message": f"Hello, {user['username']}"}

# 使用 Annotated 简化
CurrentUser = Annotated[dict, Depends(verify_token)]

@router.get("/profile")
async def get_profile(user: CurrentUser):
    return user
```

### 权限依赖

```python
from functools import wraps

def require_permission(permission: str):
    """检查权限的依赖工厂"""
    async def permission_checker(user: CurrentUser):
        if not has_permission(user, permission):
            raise HTTPException(status_code=403, detail="Permission denied")
        return user
    return permission_checker

# 使用
@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    user: dict = Depends(require_permission("users:delete"))
):
    # 删除用户
    pass
```

---

## 请求验证

FastAPI 使用 Pydantic 模型进行请求数据的自动验证。这不仅减少了手动验证代码，还提供了自动的错误消息和 API 文档。

**为什么使用 Pydantic 进行验证**：
1. **声明式** - 通过类型和字段配置声明验证规则，而不是编写验证代码
2. **自动验证** - FastAPI 在调用路由函数前自动执行验证
3. **友好错误** - 验证失败时自动返回详细的错误信息（HTTP 422）
4. **类型安全** - 验证后的数据保证类型正确，IDE 能提供准确的补全
5. **文档生成** - 验证规则自动出现在 API 文档中

**Pydantic 的验证能力**：
- 类型验证（int、str、bool、list、dict 等）
- 范围约束（最小值、最大值、长度等）
- 正则表达式匹配
- 枚举值（Literal 类型）
- 自定义验证器
- 嵌套模型

### Pydantic 模型

Pydantic 模型定义了请求数据的结构和验证规则。每个字段可以有类型、默认值、描述和验证约束。

**Field 参数说明**：
- `...` - 表示必需字段（无默认值）
- `default` - 提供默认值
- `min_length`/`max_length` - 字符串或列表的长度约束
- `ge`/`gt`/`le`/`lt` - 数字的大小约束（大于等于、大于、小于等于、小于）
- `regex` - 正则表达式匹配
- `description` - 字段说明，会出现在 API 文档中

**自定义验证器**：
使用 `@validator` 装饰器可以添加自定义验证逻辑。验证器接收字段值作为参数，可以修改值或抛出 `ValueError` 来拒绝无效数据。

```python
from pydantic import BaseModel, Field, validator
from typing import Literal

class QueryRequest(BaseModel):
    """查询请求模型"""
    
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="用户问题"
    )
    
    session_id: str = Field(
        ...,
        regex=r"^[a-zA-Z0-9_-]+$",
        description="会话 ID"
    )
    
    top_k: int = Field(
        default=10,
        ge=1,
        le=100,
        description="返回结果数量"
    )
    
    strategy: Literal["fast", "balanced", "deep"] = Field(
        default="balanced",
        description="检索策略"
    )
    
    @validator("question")
    def validate_question(cls, v):
        """验证问题不为空"""
        if not v.strip():
            raise ValueError("Question cannot be empty")
        return v.strip()
    
    class Config:
        schema_extra = {
            "example": {
                "question": "什么是 RAG？",
                "session_id": "session_123",
                "top_k": 10,
                "strategy": "balanced"
            }
        }
```

### 查询参数验证

```python
from fastapi import Query

@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, max_length=100),
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(10, ge=1, le=100),
    sort: Literal["relevance", "date"] = Query("relevance")
):
    """搜索端点"""
    return {
        "query": q,
        "page": page,
        "page_size": page_size,
        "sort": sort
    }
```

### 文件上传

```python
from fastapi import File, UploadFile

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(..., description="上传的文件")
):
    """上传文件"""
    
    # 验证文件类型
    allowed_types = ["application/pdf", "text/plain"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}"
        )
    
    # 验证文件大小
    MAX_SIZE = 10 * 1024 * 1024  # 10MB
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File too large"
        )
    
    # 保存文件
    file_path = f"uploads/{file.filename}"
    with open(file_path, "wb") as f:
        f.write(contents)
    
    return {"filename": file.filename, "size": len(contents)}

# 多文件上传
@router.post("/upload-multiple")
async def upload_multiple_files(
    files: list[UploadFile] = File(..., description="多个文件")
):
    """上传多个文件"""
    results = []
    for file in files:
        contents = await file.read()
        results.append({
            "filename": file.filename,
            "size": len(contents)
        })
    return results
```

---

## 响应处理

FastAPI 提供了多种方式来自定义 HTTP 响应。了解这些方式可以帮助你更好地控制 API 的行为。

**响应类型**：
1. **JSON 响应** - 最常见，FastAPI 会自动将 Python 对象序列化为 JSON
2. **流式响应** - 用于大文件或实时数据流
3. **自定义响应** - 完全控制响应头、状态码和内容

**为什么需要不同的响应类型**：
- **JSON** - 适合结构化数据，易于前端解析
- **流式** - 适合大文件下载或服务端推送事件（SSE），避免内存占用过大
- **自定义** - 需要特殊的响应头（如 CORS、缓存控制）或非标准状态码

### 基本响应

FastAPI 默认返回 JSON 响应。你只需返回 Python 对象（dict、list、Pydantic 模型等），FastAPI 会自动处理序列化。

**状态码的选择**：
- **200 OK** - 成功的 GET、PUT、PATCH 请求
- **201 Created** - 成功创建资源（POST）
- **204 No Content** - 成功但无返回内容（DELETE）
- **400 Bad Request** - 客户端请求错误
- **401 Unauthorized** - 未认证
- **403 Forbidden** - 已认证但无权限
- **404 Not Found** - 资源不存在
- **422 Unprocessable Entity** - 请求格式正确但语义错误（Pydantic 验证失败）
- **500 Internal Server Error** - 服务器错误

### 流式响应

流式响应允许服务器逐步发送数据，而不是等待所有数据准备好再发送。这对于大文件、实时数据或长时间运行的操作特别有用。

**流式响应的优势**：
1. **低延迟** - 用户立即看到响应，而不是等待所有处理完成
2. **低内存** - 不需要在内存中保存完整的响应数据
3. **实时体验** - 适合聊天、日志流等实时应用
4. **容错性** - 即使部分数据失败，已发送的数据仍然可用

**使用场景**：
- 大文件下载
- 实时日志输出
- LLM 流式生成（逐字输出）
- 服务端推送事件（Server-Sent Events）

### SSE（Server-Sent Events）

SSE 是一种服务器向客户端推送事件的技术，基于 HTTP。与 WebSocket 相比，SSE 更简单，但只支持服务器到客户端的单向通信。

**SSE 的特点**：
- **基于 HTTP** - 不需要特殊协议，易于部署
- **自动重连** - 浏览器会自动重连断开的连接
- **事件 ID** - 支持事件 ID，重连后可以续传
- **单向通信** - 只支持服务器推送，客户端通过普通 HTTP 请求发送数据

**SSE 消息格式**：
```
event: message_type
data: {"key": "value"}

```
每个消息以空行结束。`event` 字段是可选的事件类型，`data` 字段是实际数据。

```python
@router.post("/query/stream")
async def query_stream(request: QueryRequest):
    """流式查询"""
    
    async def event_generator():
        # 发送开始事件
        yield encode_sse("start", {"session_id": request.session_id})
        
        # 执行查询并流式返回
        async for chunk in run_query_stream(request.question):
            yield encode_sse("chunk", {"text": chunk})
        
        # 发送完成事件
        yield encode_sse("done", {"status": "completed"})
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )

def encode_sse(event: str, data: dict) -> str:
    """编码 SSE 消息"""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
```

---

## 错误处理

### 自定义异常

```python
from fastapi import HTTPException

class NotFoundException(HTTPException):
    """资源不存在异常"""
    def __init__(self, resource: str, id: str):
        super().__init__(
            status_code=404,
            detail=f"{resource} with id {id} not found"
        )

class ValidationException(HTTPException):
    """验证异常"""
    def __init__(self, message: str):
        super().__init__(
            status_code=400,
            detail=message
        )

# 使用
@router.get("/users/{user_id}")
async def get_user(user_id: int):
    user = db.get_user(user_id)
    if not user:
        raise NotFoundException("User", str(user_id))
    return user
```

### 全局异常处理器

```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """处理 ValueError"""
    return JSONResponse(
        status_code=400,
        content={
            "error": "validation_error",
            "message": str(exc)
        }
    )

@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    """处理所有未捕获的异常"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred"
        }
    )
```

### 错误响应工具

```python
# app/api/utils/error_responses.py

def bad_request(message: str, details: dict = None):
    """400 错误响应"""
    return JSONResponse(
        status_code=400,
        content={
            "error": "bad_request",
            "message": message,
            "details": details
        }
    )

def unauthorized(message: str = "Unauthorized"):
    """401 错误响应"""
    return JSONResponse(
        status_code=401,
        content={
            "error": "unauthorized",
            "message": message
        }
    )

def forbidden(message: str = "Forbidden"):
    """403 错误响应"""
    return JSONResponse(
        status_code=403,
        content={
            "error": "forbidden",
            "message": message
        }
    )

def not_found(resource: str, id: str):
    """404 错误响应"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "message": f"{resource} not found",
            "resource_id": id
        }
    )

def rate_limited(retry_after: int = None):
    """429 错误响应"""
    headers = {}
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests"
        },
        headers=headers
    )
```

---

## 认证和授权

认证和授权是 API 安全的基础。认证解决"你是谁"的问题，授权解决"你能做什么"的问题。

**认证 vs 授权**：
- **认证（Authentication）** - 验证用户身份，确认"你是谁"
- **授权（Authorization）** - 验证用户权限，确认"你能做什么"

**为什么需要认证和授权**：
1. **保护资源** - 防止未授权访问敏感数据和操作
2. **用户隔离** - 确保用户只能访问自己的数据
3. **审计追踪** - 记录谁在什么时候做了什么
4. **合规要求** - 满足数据保护法规的要求

### JWT 认证

JWT（JSON Web Token）是一种无状态的认证方式，非常适合 RESTful API。

**JWT 的结构**：
JWT 由三部分组成，用点（.）分隔：
1. **Header** - 令牌类型和签名算法
2. **Payload** - 用户信息和元数据（claims）
3. **Signature** - 签名，用于验证令牌未被篡改

**JWT 的优势**：
- **无状态** - 服务器不需要存储 session，易于水平扩展
- **跨域友好** - 可以在不同的域之间传递
- **自包含** - 令牌本身包含用户信息，减少数据库查询
- **标准化** - 广泛支持，有成熟的库

**JWT 的注意事项**：
- **不要存储敏感信息** - Payload 是 Base64 编码的，任何人都可以解码
- **设置过期时间** - 防止令牌被无限期使用
- **使用 HTTPS** - 防止令牌在传输中被窃取
- **考虑刷新机制** - 长期令牌风险大，应使用短期令牌+刷新令牌机制

**令牌过期策略**：
- **短期访问令牌** - 15-60 分钟，用于日常操作
- **长期刷新令牌** - 7-30 天，仅用于获取新的访问令牌
- **记住我** - 可以延长刷新令牌的有效期

```python
from datetime import datetime, timedelta
import jwt
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"

security = HTTPBearer()

def create_token(user_id: str, expires_in: int = 24) -> str:
    """创建 JWT 令牌"""
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=expires_in)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    """解码 JWT 令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """获取当前用户"""
    token = credentials.credentials
    payload = decode_token(token)
    
    user = db.get_user(payload["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

# 使用
@router.get("/profile")
async def get_profile(user: dict = Depends(get_current_user)):
    return user
```

### 登录端点

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
async def login(request: LoginRequest):
    """用户登录"""
    
    # 查找用户
    user = db.get_user_by_username(request.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # 验证密码
    if not pwd_context.verify(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # 创建令牌
    token = create_token(user["id"])
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"]
        }
    }
```

### 基于角色的访问控制

RBAC（Role-Based Access Control）是最常见的授权模型。用户被分配角色（如 user、admin），每个角色有不同的权限。

**RBAC 的优势**：
- **简单易懂** - 概念直观，易于实现和管理
- **灵活性** - 可以定义多种角色，满足不同需求
- **可扩展** - 添加新角色不影响现有系统
- **审计友好** - 易于追踪谁有什么权限

**角色设计原则**：
1. **最小权限** - 角色只包含必要的权限
2. **职责分离** - 不同职责使用不同角色
3. **明确命名** - 角色名称应清晰反映其职责
4. **避免角色爆炸** - 不要为每个小权限创建一个角色

**常见角色示例**：
- **user** - 普通用户，可以查询、上传文档、管理自己的会话
- **admin** - 管理员，可以管理所有用户、查看系统指标、修改配置
- **readonly** - 只读用户，可以查询但不能修改数据
- **power_user** - 高级用户，有额外的配额或功能

**权限检查时机**：
- **路由级别** - 在路由函数执行前检查（通过依赖）
- **数据级别** - 在访问数据时检查（如只能访问自己的文档）
- **功能级别** - 在执行特定操作前检查（如删除用户）

```python
def require_role(role: str):
    """要求特定角色"""
    async def role_checker(user: dict = Depends(get_current_user)):
        if user.get("role") != role:
            raise HTTPException(
                status_code=403,
                detail=f"Requires {role} role"
            )
        return user
    return role_checker

# 仅管理员
@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: dict = Depends(require_role("admin"))
):
    # 删除用户
    pass
```

---

## API 文档

### OpenAPI 配置

```python
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="QueryMind（智询） API",
        version="0.4.4",
        description="Enterprise RAG system with multi-agent orchestration",
        routes=app.routes,
    )
    
    # 添加安全方案
    openapi_schema["components"]["securitySchemes"] = {
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

### 路由文档

```python
@router.post(
    "/query",
    response_model=QueryResponse,
    summary="执行查询",
    description="执行多智能体 RAG 查询，返回答案和引用",
    response_description="查询结果，包含答案、来源和元数据",
    tags=["query"],
    status_code=200
)
async def query(request: QueryRequest):
    """
    执行 RAG 查询。
    
    ## 参数
    - **question**: 用户问题（必需）
    - **session_id**: 会话 ID（必需）
    - **top_k**: 返回结果数量（可选，默认 10）
    - **strategy**: 检索策略（可选，默认 balanced）
    
    ## 返回
    - **answer**: 生成的答案
    - **sources**: 引用来源列表
    - **metadata**: 查询元数据
    
    ## 示例
    ```json
    {
        "question": "什么是 RAG？",
        "session_id": "session_123",
        "top_k": 10,
        "strategy": "balanced"
    }
    ```
    """
    # 实现...
    pass
```

---

## 测试 API

### 单元测试

```python
from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)

def test_health_check():
    """测试健康检查"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_create_user():
    """测试创建用户"""
    response = client.post(
        "/api/users",
        json={
            "username": "test_user",
            "email": "test@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "test_user"

def test_unauthorized_access():
    """测试未授权访问"""
    response = client.get("/api/profile")
    assert response.status_code == 401
```

### 集成测试

```python
import pytest

@pytest.fixture
def auth_token():
    """获取认证令牌"""
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"}
    )
    return response.json()["access_token"]

def test_protected_endpoint(auth_token):
    """测试受保护的端点"""
    response = client.get(
        "/api/profile",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
```

---

## 最佳实践

1. **使用 Pydantic 模型**: 始终定义请求和响应模型
2. **依赖注入**: 使用依赖注入管理共享资源
3. **错误处理**: 提供清晰的错误消息
4. **文档化**: 为所有端点添加文档字符串
5. **测试**: 编写单元测试和集成测试
6. **安全**: 验证输入、使用 HTTPS、保护敏感端点
7. **性能**: 使用异步编程、添加缓存
8. **版本控制**: 使用 API 版本（如 /v1/、/v2/）

---

## 下一步

了解 API 开发后，建议继续阅读：

1. **[前端开发](./FRONTEND_DEVELOPMENT.md)** - React 集成
2. **[测试指南](./TESTING_GUIDE.md)** - API 测试策略
3. **[本地部署](./LOCAL_DEPLOYMENT.md)** - 生产环境部署

---

**更新日期**: 2026-06-19  
**文档版本**: 1.0
