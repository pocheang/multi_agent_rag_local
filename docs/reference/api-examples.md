# 📡 API 使用示例

> QueryMind REST API 完整使用示例和代码片段

---

## 📋 目录

- [快速开始](#快速开始)
- [认证](#认证)
- [查询接口](#查询接口)
- [文档管理](#文档管理)
- [用户管理](#用户管理)
- [会话管理](#会话管理)
- [Python客户端](#python客户端)
- [JavaScript客户端](#javascript客户端)
- [错误处理](#错误处理)

---

## 快速开始

### 基础配置

```bash
# API基础URL
API_BASE_URL=http://localhost:8000

# 认证令牌
AUTH_TOKEN=your_jwt_token_here
```

### 健康检查

```bash
curl http://localhost:8000/health
```

**响应**:
```json
{
  "status": "healthy",
  "timestamp": "2026-06-23T10:00:00Z"
}
```

---

## 认证

### 注册用户

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "email": "john@example.com",
    "password": "SecurePass123!",
    "full_name": "John Doe"
  }'
```

**响应**:
```json
{
  "user_id": 1,
  "username": "john_doe",
  "email": "john@example.com",
  "role": "viewer",
  "created_at": "2026-06-23T10:00:00Z"
}
```

### 登录

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "password": "SecurePass123!"
  }'
```

**响应**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": 1,
    "username": "john_doe",
    "role": "viewer"
  }
}
```

### 刷新令牌

```bash
curl -X POST http://localhost:8000/api/auth/refresh \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

---

## 查询接口

### 简单查询

```bash
curl -X POST http://localhost:8000/api/chat/query \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "什么是RAG？"
  }'
```

**响应**:
```json
{
  "query": "什么是RAG？",
  "answer": "RAG（Retrieval-Augmented Generation）是检索增强生成技术...",
  "sources": [
    {
      "document_id": "doc_123",
      "title": "RAG技术介绍",
      "content": "...",
      "score": 0.92,
      "metadata": {}
    }
  ],
  "session_id": "sess_abc123",
  "agent_trace": [],
  "response_time": 2.5
}
```

### 带上下文的多轮对话

```bash
curl -X POST http://localhost:8000/api/chat/query \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "它有什么优势？",
    "session_id": "sess_abc123",
    "history": [
      {
        "role": "user",
        "content": "什么是RAG？"
      },
      {
        "role": "assistant",
        "content": "RAG是检索增强生成技术..."
      }
    ]
  }'
```

### 流式查询

```bash
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "详细解释RAG的工作原理",
    "stream": true
  }'
```

**流式响应**:
```
data: {"type": "start", "session_id": "sess_abc123"}
data: {"type": "token", "content": "RAG"}
data: {"type": "token", "content": "的"}
data: {"type": "token", "content": "工作"}
data: {"type": "source", "source": {...}}
data: {"type": "end"}
```

### 指定模型查询

```bash
curl -X POST http://localhost:8000/api/chat/query \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "生成一段Python代码",
    "model": "gpt-5.3-codex",
    "temperature": 0.2,
    "max_tokens": 1000
  }'
```

---

## 文档管理

### 上传文档

```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -F "file=@/path/to/document.pdf" \
  -F "metadata={\"title\":\"技术文档\",\"tags\":[\"技术\",\"教程\"]}"
```

**响应**:
```json
{
  "document_id": "doc_123",
  "filename": "document.pdf",
  "status": "processing",
  "uploaded_at": "2026-06-23T10:00:00Z"
}
```

### 批量上传

```bash
curl -X POST http://localhost:8000/api/documents/batch-upload \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.pdf" \
  -F "files=@doc3.pdf"
```

### 查询文档状态

```bash
curl -X GET http://localhost:8000/api/documents/doc_123 \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

**响应**:
```json
{
  "document_id": "doc_123",
  "filename": "document.pdf",
  "status": "completed",
  "chunks_count": 45,
  "uploaded_at": "2026-06-23T10:00:00Z",
  "processed_at": "2026-06-23T10:02:30Z",
  "metadata": {
    "title": "技术文档",
    "tags": ["技术", "教程"]
  }
}
```

### 列出所有文档

```bash
curl -X GET "http://localhost:8000/api/documents?page=1&size=20&sort=created_at" \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

**响应**:
```json
{
  "items": [
    {
      "document_id": "doc_123",
      "filename": "document.pdf",
      "status": "completed",
      "uploaded_at": "2026-06-23T10:00:00Z"
    }
  ],
  "total": 100,
  "page": 1,
  "size": 20,
  "pages": 5
}
```

### 删除文档

```bash
curl -X DELETE http://localhost:8000/api/documents/doc_123 \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

### 搜索文档

```bash
curl -X POST http://localhost:8000/api/documents/search \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "人工智能",
    "filters": {
      "tags": ["技术"],
      "date_from": "2026-01-01"
    },
    "limit": 10
  }'
```

---

## 用户管理

### 获取当前用户信息

```bash
curl -X GET http://localhost:8000/api/users/me \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

### 更新用户资料

```bash
curl -X PUT http://localhost:8000/api/users/me \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "John Smith",
    "email": "john.smith@example.com"
  }'
```

### 修改密码

```bash
curl -X POST http://localhost:8000/api/users/change-password \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "old_password": "OldPass123!",
    "new_password": "NewPass456!"
  }'
```

---

## 会话管理

### 创建新会话

```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "技术讨论",
    "metadata": {}
  }'
```

### 获取会话历史

```bash
curl -X GET http://localhost:8000/api/sessions/sess_abc123/history \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

**响应**:
```json
{
  "session_id": "sess_abc123",
  "messages": [
    {
      "role": "user",
      "content": "什么是RAG？",
      "timestamp": "2026-06-23T10:00:00Z"
    },
    {
      "role": "assistant",
      "content": "RAG是...",
      "timestamp": "2026-06-23T10:00:02Z",
      "sources": [...]
    }
  ]
}
```

### 删除会话

```bash
curl -X DELETE http://localhost:8000/api/sessions/sess_abc123 \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

---

## Python客户端

### 安装

```bash
pip install requests
```

### 完整客户端类

```python
import requests
from typing import List, Dict, Optional, Generator
import json

class QueryMindClient:
    def __init__(self, base_url: str = "http://localhost:8000", token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.session_id = None
        
    @property
    def headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
    
    def login(self, username: str, password: str) -> Dict:
        """登录并获取token"""
        response = requests.post(
            f"{self.base_url}/api/auth/login",
            json={"username": username, "password": password}
        )
        response.raise_for_status()
        data = response.json()
        self.token = data["access_token"]
        return data
    
    def query(self, 
              query: str, 
              session_id: Optional[str] = None,
              history: Optional[List[Dict]] = None,
              model: Optional[str] = None) -> Dict:
        """发送查询"""
        payload = {"query": query}
        if session_id:
            payload["session_id"] = session_id
        if history:
            payload["history"] = history
        if model:
            payload["model"] = model
            
        response = requests.post(
            f"{self.base_url}/api/chat/query",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        result = response.json()
        
        # 保存session_id
        if "session_id" in result:
            self.session_id = result["session_id"]
            
        return result
    
    def stream_query(self, query: str) -> Generator[Dict, None, None]:
        """流式查询"""
        response = requests.post(
            f"{self.base_url}/api/chat/stream",
            headers=self.headers,
            json={"query": query, "stream": True},
            stream=True
        )
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data = json.loads(line_str[6:])
                    yield data
    
    def upload_document(self, file_path: str, metadata: Optional[Dict] = None) -> Dict:
        """上传文档"""
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {}
            if metadata:
                data['metadata'] = json.dumps(metadata)
            
            headers = {"Authorization": f"Bearer {self.token}"}
            response = requests.post(
                f"{self.base_url}/api/documents/upload",
                headers=headers,
                files=files,
                data=data
            )
        response.raise_for_status()
        return response.json()
    
    def list_documents(self, page: int = 1, size: int = 20) -> Dict:
        """列出文档"""
        response = requests.get(
            f"{self.base_url}/api/documents",
            headers=self.headers,
            params={"page": page, "size": size}
        )
        response.raise_for_status()
        return response.json()
    
    def delete_document(self, document_id: str) -> None:
        """删除文档"""
        response = requests.delete(
            f"{self.base_url}/api/documents/{document_id}",
            headers=self.headers
        )
        response.raise_for_status()

# 使用示例
if __name__ == "__main__":
    # 初始化客户端
    client = QueryMindClient()
    
    # 登录
    client.login("john_doe", "SecurePass123!")
    
    # 简单查询
    result = client.query("什么是RAG？")
    print(result["answer"])
    
    # 多轮对话
    result2 = client.query(
        "它有什么优势？",
        session_id=client.session_id
    )
    print(result2["answer"])
    
    # 流式查询
    print("\n流式响应：")
    for chunk in client.stream_query("详细解释RAG"):
        if chunk["type"] == "token":
            print(chunk["content"], end='', flush=True)
    
    # 上传文档
    doc = client.upload_document(
        "document.pdf",
        metadata={"title": "技术文档", "tags": ["技术"]}
    )
    print(f"\n文档已上传: {doc['document_id']}")
    
    # 列出文档
    docs = client.list_documents()
    print(f"共有 {docs['total']} 个文档")
```

### 异步客户端（使用aiohttp）

```python
import aiohttp
import asyncio
from typing import Dict, Optional

class AsyncQueryMindClient:
    def __init__(self, base_url: str = "http://localhost:8000", token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.token = token
    
    @property
    def headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
    
    async def query(self, query: str) -> Dict:
        """异步查询"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/chat/query",
                headers=self.headers,
                json={"query": query}
            ) as response:
                return await response.json()
    
    async def batch_query(self, queries: List[str]) -> List[Dict]:
        """批量异步查询"""
        tasks = [self.query(q) for q in queries]
        return await asyncio.gather(*tasks)

# 使用示例
async def main():
    client = AsyncQueryMindClient(token="your_token")
    
    # 单个查询
    result = await client.query("什么是RAG？")
    print(result["answer"])
    
    # 批量查询
    queries = [
        "什么是RAG？",
        "什么是向量数据库？",
        "什么是LLM？"
    ]
    results = await client.batch_query(queries)
    for r in results:
        print(r["answer"])

if __name__ == "__main__":
    asyncio.run(main())
```

---

## JavaScript客户端

### 基础客户端

```javascript
class QueryMindClient {
  constructor(baseURL = 'http://localhost:8000', token = null) {
    this.baseURL = baseURL;
    this.token = token;
    this.sessionId = null;
  }

  get headers() {
    const headers = { 'Content-Type': 'application/json' };
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    return headers;
  }

  async login(username, password) {
    const response = await fetch(`${this.baseURL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await response.json();
    this.token = data.access_token;
    return data;
  }

  async query(query, options = {}) {
    const payload = {
      query,
      session_id: options.sessionId || this.sessionId,
      history: options.history,
      model: options.model
    };

    const response = await fetch(`${this.baseURL}/api/chat/query`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify(payload)
    });

    const result = await response.json();
    if (result.session_id) {
      this.sessionId = result.session_id;
    }
    return result;
  }

  async *streamQuery(query) {
    const response = await fetch(`${this.baseURL}/api/chat/stream`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({ query, stream: true })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          yield JSON.parse(line.slice(6));
        }
      }
    }
  }

  async uploadDocument(file, metadata = {}) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('metadata', JSON.stringify(metadata));

    const headers = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(`${this.baseURL}/api/documents/upload`, {
      method: 'POST',
      headers,
      body: formData
    });

    return await response.json();
  }
}

// 使用示例
(async () => {
  const client = new QueryMindClient();
  
  // 登录
  await client.login('john_doe', 'SecurePass123!');
  
  // 查询
  const result = await client.query('什么是RAG？');
  console.log(result.answer);
  
  // 流式查询
  for await (const chunk of client.streamQuery('详细解释RAG')) {
    if (chunk.type === 'token') {
      process.stdout.write(chunk.content);
    }
  }
})();
```

### TypeScript 类型定义

```typescript
interface QueryResponse {
  query: string;
  answer: string;
  sources: Source[];
  session_id: string;
  agent_trace: AgentTrace[];
  response_time: number;
}

interface Source {
  document_id: string;
  title: string;
  content: string;
  score: number;
  metadata: Record<string, any>;
}

interface AgentTrace {
  agent: string;
  action: string;
  input: string;
  output: string;
  timestamp: string;
}
```

---

## 错误处理

### 常见错误码

| 状态码 | 错误类型 | 说明 |
|--------|---------|------|
| 400 | Bad Request | 请求参数错误 |
| 401 | Unauthorized | 未认证或token过期 |
| 403 | Forbidden | 权限不足 |
| 404 | Not Found | 资源不存在 |
| 429 | Too Many Requests | 请求过于频繁 |
| 500 | Internal Server Error | 服务器内部错误 |

### 错误响应格式

```json
{
  "error": {
    "code": "INVALID_QUERY",
    "message": "查询不能为空",
    "details": {
      "field": "query",
      "constraint": "required"
    }
  }
}
```

### Python错误处理示例

```python
import requests
from requests.exceptions import HTTPError, ConnectionError, Timeout

def safe_query(client, query):
    try:
        result = client.query(query)
        return result
    except HTTPError as e:
        if e.response.status_code == 401:
            # token过期，重新登录
            client.login(username, password)
            return client.query(query)
        elif e.response.status_code == 429:
            # 请求过于频繁，等待后重试
            time.sleep(5)
            return client.query(query)
        else:
            print(f"HTTP错误: {e.response.status_code}")
            print(e.response.json())
    except ConnectionError:
        print("连接失败，请检查服务是否运行")
    except Timeout:
        print("请求超时")
    except Exception as e:
        print(f"未知错误: {str(e)}")
    return None
```

---

## 🔗 相关文档

- [API开发指南](../zh-CN/README.md)
- [认证和权限](../../SECURITY.md)
- [性能优化](../operations/performance.md)
- [FAQ](faq.md)

---

<div align="center">

**完整API文档**: http://localhost:8000/docs 📚

[返回主页](./README.md)

</div>
