# 第三批修复 - 快速实施指南

**版本**: v0.6.2.4  
**预计工作量**: 2周  
**状态**: 📋 实施指南  

---

## 🚀 快速开始

本指南提供**可直接使用的代码片段**，帮助开发团队快速实施第三批改进。

---

## ⭐ 问题12: Credit余额提示（优先级最高）

**工作量**: 1天  
**影响**: 所有用户  

### 步骤1: 添加响应中间件

在 `app/api/transport/middleware.py` 的 `request_timing_middleware` 函数中添加：

```python
async def request_timing_middleware(request: Request, call_next):
    # ... 现有代码 ...
    
    try:
        response = await call_next(request)
        status_code = response.status_code
        
        # 添加Credit余额头部
        if hasattr(request.state, 'user') and request.state.user:
            user = request.state.user
            credit_balance = user.get('credit_balance', 0)
            
            # 添加HTTP头部
            response.headers["X-Credit-Remaining"] = str(credit_balance)
            
            # 添加警告标记
            if credit_balance < 10:
                response.headers["X-Credit-Warning"] = "low"
            elif credit_balance < 5:
                response.headers["X-Credit-Warning"] = "critical"
            else:
                response.headers["X-Credit-Warning"] = "ok"
        
        # ... 现有的其他头部 ...
        return response
```

### 步骤2: 在查询响应中添加credit信息

修改 `app/api/schemas/http.py`:

```python
class QueryResponse(BaseModel):
    answer: str
    route: str
    citations: list[Citation] = Field(default_factory=list)
    # ... 现有字段 ...
    
    # 新增字段
    credit_info: dict[str, Any] | None = Field(
        default=None,
        description="Credit余额信息"
    )

# 新增模型
class CreditInfo(BaseModel):
    remaining: int = Field(..., description="剩余credit数量")
    total: int = Field(..., description="总credit数量")
    cost_per_query: int = Field(default=1, description="每次查询消耗")
    warning_level: str = Field(default="ok", description="警告级别: ok, low, critical")
```

### 步骤3: 在查询时填充credit信息

修改 `app/api/query/response.py` 或相应的响应构建函数：

```python
def prepare_query_response(result, user):
    credit_balance = user.get('credit_balance', 0)
    
    # 确定警告级别
    if credit_balance < 5:
        warning_level = "critical"
    elif credit_balance < 10:
        warning_level = "low"
    else:
        warning_level = "ok"
    
    return QueryResponse(
        answer=result.answer,
        route=result.route,
        # ... 其他字段 ...
        credit_info={
            "remaining": credit_balance,
            "total": user.get('total_credits', 100),  # 需要添加此字段
            "cost_per_query": 1,
            "warning_level": warning_level,
        }
    )
```

### 步骤4: 前端集成

```typescript
// API响应处理
const response = await fetch('/api/query', {
  method: 'POST',
  body: JSON.stringify({ question }),
  headers: { 'Content-Type': 'application/json' }
});

// 从头部读取credit信息
const creditRemaining = parseInt(response.headers.get('X-Credit-Remaining') || '0');
const creditWarning = response.headers.get('X-Credit-Warning') || 'ok';

// 更新全局状态
setCreditBalance(creditRemaining);

// 显示警告
if (creditWarning === 'critical') {
  showBanner({
    type: 'error',
    message: `剩余${creditRemaining}次查询，即将用完！`,
    action: { text: '充值', onClick: () => router.push('/recharge') }
  });
} else if (creditWarning === 'low') {
  showBanner({
    type: 'warning',
    message: `剩余${creditRemaining}次查询`,
    action: { text: '充值', onClick: () => router.push('/recharge') }
  });
}

// 在输入框下方显示
<QueryInput>
  <textarea placeholder="输入你的问题..." />
  <div className="credit-hint">
    本次查询将消耗1个credit，剩余{creditRemaining}次
  </div>
</QueryInput>
```

---

## ⭐ 问题7: Session软删除（优先级高）

**工作量**: 2天  
**影响**: 所有用户  

### 步骤1: 修改Session数据结构

在 `app/services/sessions/history.py` 中的Session JSON添加字段：

```python
# Session数据结构
{
    "session_id": "xxx",
    "title": "对话标题",
    "messages": [...],
    "created_at": "2026-08-21T10:00:00Z",
    "updated_at": "2026-08-21T10:30:00Z",
    
    # 新增字段
    "deleted_at": null,  # 删除时间，null表示未删除
    "deleted_by": null,  # 删除者user_id
    "auto_delete_at": null  # 自动永久删除时间
}
```

### 步骤2: 修改删除方法

在 `app/services/sessions/history.py` 的 `HistoryStore` 类中：

```python
class HistoryStore:
    # ... 现有代码 ...
    
    def soft_delete_session(
        self, 
        session_id: str, 
        deleted_by: str,
        auto_delete_after_days: int = 30
    ) -> dict | None:
        """
        软删除session（标记为已删除，可恢复）
        
        Args:
            session_id: Session ID
            deleted_by: 删除者的user_id
            auto_delete_after_days: 多少天后自动永久删除
            
        Returns:
            更新后的session，或None如果session不存在
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        from datetime import datetime, timedelta
        now = datetime.now().isoformat()
        auto_delete_at = (datetime.now() + timedelta(days=auto_delete_after_days)).isoformat()
        
        # 标记为已删除
        session["deleted_at"] = now
        session["deleted_by"] = deleted_by
        session["auto_delete_at"] = auto_delete_at
        
        # 保存
        self._save_session(session_id, session)
        return session
    
    def restore_session(self, session_id: str) -> dict | None:
        """恢复已删除的session"""
        session = self.get_session(session_id, include_deleted=True)
        if not session or not session.get("deleted_at"):
            return None
        
        # 清除删除标记
        session["deleted_at"] = None
        session["deleted_by"] = None
        session["auto_delete_at"] = None
        
        self._save_session(session_id, session)
        return session
    
    def list_deleted_sessions(self) -> list[dict]:
        """列出所有已删除的session"""
        all_sessions = self.list_sessions(include_deleted=True)
        return [s for s in all_sessions if s.get("deleted_at")]
    
    def permanent_delete_session(self, session_id: str) -> bool:
        """永久删除session（无法恢复）"""
        session_file = self._base_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
            return True
        return False
    
    def cleanup_expired_deleted_sessions(self) -> int:
        """清理过期的已删除session，返回清理数量"""
        from datetime import datetime
        now = datetime.now()
        deleted_sessions = self.list_deleted_sessions()
        
        count = 0
        for session in deleted_sessions:
            auto_delete_at = session.get("auto_delete_at")
            if auto_delete_at:
                delete_time = datetime.fromisoformat(auto_delete_at)
                if now > delete_time:
                    self.permanent_delete_session(session["session_id"])
                    count += 1
        
        return count
```

### 步骤3: 修改API端点

在 `app/api/routes/public/sessions.py` 中：

```python
@router.delete("/{session_id}")
def delete_session(
    session_id: str, 
    request: Request, 
    user: dict[str, Any] = Depends(_require_user),
    permanent: bool = Query(False, description="是否永久删除")
):
    """
    删除session
    
    参数:
    - permanent: False=软删除(可恢复)，True=永久删除(不可恢复)
    """
    session_id = _require_valid_session_id(session_id)
    _require_permission(user, "session:delete", request, "session", resource_id=session_id)
    
    store = _history_store_for_user(user)
    
    if permanent:
        # 永久删除
        ok = store.permanent_delete_session(session_id)
        _audit(
            request, 
            action="session.permanent_delete", 
            resource_type="session", 
            result="success", 
            user=user, 
            resource_id=session_id
        )
        return {
            "ok": ok,
            "session_id": session_id,
            "message": "已永久删除，无法恢复"
        }
    else:
        # 软删除
        session = store.soft_delete_session(
            session_id=session_id,
            deleted_by=user["user_id"],
            auto_delete_after_days=30
        )
        if not session:
            raise not_found("Session")
        
        _audit(
            request, 
            action="session.soft_delete", 
            resource_type="session", 
            result="success", 
            user=user, 
            resource_id=session_id
        )
        
        return {
            "ok": True,
            "session_id": session_id,
            "recoverable_until": session["auto_delete_at"],
            "message": "已删除，可在30天内从回收站恢复"
        }


@router.get("/trash", response_model=list[SessionSummary])
def list_trash(
    request: Request,
    user: dict[str, Any] = Depends(_require_user)
):
    """查看回收站中的session"""
    _require_permission(user, "session:list", request, "session")
    deleted_sessions = _history_store_for_user(user).list_deleted_sessions()
    return deleted_sessions


@router.post("/{session_id}/restore", response_model=SessionDetail)
def restore_session(
    session_id: str,
    request: Request,
    user: dict[str, Any] = Depends(_require_user)
):
    """从回收站恢复session"""
    session_id = _require_valid_session_id(session_id)
    _require_permission(user, "session:update", request, "session", resource_id=session_id)
    
    store = _history_store_for_user(user)
    session = store.restore_session(session_id)
    
    if not session:
        raise not_found("Session not found in trash")
    
    _audit(
        request,
        action="session.restore",
        resource_type="session",
        result="success",
        user=user,
        resource_id=session_id
    )
    
    return session
```

### 步骤4: 添加定时清理任务

创建或修改 `app/services/scheduler.py`:

```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

def cleanup_expired_sessions():
    """定时清理过期的已删除session"""
    from app.core.config import get_settings
    from app.services.sessions.history import HistoryStore
    from pathlib import Path
    
    settings = get_settings()
    sessions_path = Path(settings.sessions_path)
    
    # 遍历所有用户目录
    total_cleaned = 0
    for user_dir in sessions_path.iterdir():
        if user_dir.is_dir():
            store = HistoryStore(base_dir=user_dir)
            count = store.cleanup_expired_deleted_sessions()
            total_cleaned += count
    
    print(f"Cleaned {total_cleaned} expired deleted sessions")

# 每天凌晨3点执行
scheduler.add_job(cleanup_expired_sessions, 'cron', hour=3)
scheduler.start()
```

在 `app/api/application/lifespan.py` 中启动scheduler：

```python
from app.services.scheduler import scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    scheduler.start()
    
    yield
    
    # 关闭时
    scheduler.shutdown()
```

### 步骤5: 前端集成

```typescript
// 删除确认
async function deleteSession(sessionId: string) {
  const confirmed = await showConfirmDialog({
    title: '删除会话',
    message: '确定删除此会话吗？',
    detail: '删除后可在30天内从回收站恢复',
    confirmText: '删除',
    cancelText: '取消',
    type: 'warning'
  });
  
  if (confirmed) {
    await api.delete(`/sessions/${sessionId}`);
    showToast({ type: 'success', message: '已删除，可从回收站恢复' });
  }
}

// 回收站页面
function TrashPage() {
  const { data: deletedSessions } = useDeletedSessions();
  
  return (
    <div>
      <h1>回收站</h1>
      <p>回收站中的会话将在30天后自动删除</p>
      
      {deletedSessions.map(session => (
        <SessionCard
          key={session.session_id}
          session={session}
          actions={[
            {
              text: '恢复',
              onClick: () => restoreSession(session.session_id)
            },
            {
              text: '永久删除',
              onClick: () => permanentDelete(session.session_id),
              danger: true
            }
          ]}
        />
      ))}
    </div>
  );
}

async function restoreSession(sessionId: string) {
  await api.post(`/sessions/${sessionId}/restore`);
  showToast({ type: 'success', message: '已恢复' });
  router.push('/sessions');
}

async function permanentDelete(sessionId: string) {
  const confirmed = await showConfirmDialog({
    title: '永久删除',
    message: '确定永久删除吗？此操作无法撤销！',
    confirmText: '确定删除',
    cancelText: '取消',
    type: 'danger'
  });
  
  if (confirmed) {
    await api.delete(`/sessions/${sessionId}?permanent=true`);
    showToast({ type: 'success', message: '已永久删除' });
  }
}
```

---

## ⭐ 问题14: 文档列表分页（中等优先级）

**工作量**: 2天  
**影响**: 多文档用户  

### 完整实现代码

修改 `app/api/routes/public/documents.py`:

```python
from fastapi import Query

@router.get("/documents")
def list_documents(
    user: dict[str, Any] = Depends(_require_user),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    search: str | None = Query(None, description="搜索文件名"),
    type: str | None = Query(None, description="过滤文件类型：pdf, docx, txt等"),
    sort: str = Query("created_desc", description="排序: created_desc, name_asc, size_desc"),
):
    """
    列出文档，支持分页、搜索和过滤
    
    示例：
    - GET /documents?page=1&limit=20
    - GET /documents?search=报告&type=pdf
    - GET /documents?sort=name_asc
    """
    request = Request  # 从依赖中获取
    _require_permission(user, "document:list", request, "document")
    
    # 获取所有可见文档
    all_docs = _list_visible_documents_for_user(user)
    
    # 1. 搜索过滤
    if search:
        search_lower = search.lower()
        all_docs = [
            doc for doc in all_docs
            if search_lower in doc.get("filename", "").lower()
        ]
    
    # 2. 类型过滤
    if type:
        type_lower = type.lower()
        all_docs = [
            doc for doc in all_docs
            if doc.get("filename", "").lower().endswith(f".{type_lower}")
        ]
    
    # 3. 排序
    if sort == "created_desc":
        all_docs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    elif sort == "created_asc":
        all_docs.sort(key=lambda x: x.get("created_at", ""))
    elif sort == "name_asc":
        all_docs.sort(key=lambda x: x.get("filename", ""))
    elif sort == "name_desc":
        all_docs.sort(key=lambda x: x.get("filename", ""), reverse=True)
    elif sort == "size_desc":
        all_docs.sort(key=lambda x: x.get("size", 0), reverse=True)
    elif sort == "size_asc":
        all_docs.sort(key=lambda x: x.get("size", 0))
    
    # 4. 分页
    total = len(all_docs)
    start = (page - 1) * limit
    end = start + limit
    page_docs = all_docs[start:end]
    
    # 5. 合并状态信息
    result_docs = merge_visible_document_status(
        page_docs,
        user=user,
        visibility_applied=None
    )
    
    return {
        "items": result_docs,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit if limit > 0 else 0,
            "has_next": end < total,
            "has_prev": page > 1,
        },
        "filters": {
            "search": search,
            "type": type,
            "sort": sort,
        }
    }
```

### 前端集成

```typescript
function DocumentList() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [sortBy, setSortBy] = useState("created_desc");
  
  const { data, loading } = useDocuments({ 
    page, 
    search, 
    type: typeFilter === "all" ? undefined : typeFilter,
    sort: sortBy
  });
  
  return (
    <div className="document-list">
      {/* 搜索栏 */}
      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="搜索文档..."
      />
      
      {/* 过滤和排序 */}
      <div className="filters">
        <Select value={typeFilter} onChange={setTypeFilter}>
          <option value="all">全部类型</option>
          <option value="pdf">PDF</option>
          <option value="docx">Word</option>
          <option value="txt">文本</option>
          <option value="md">Markdown</option>
        </Select>
        
        <Select value={sortBy} onChange={setSortBy}>
          <option value="created_desc">最新上传</option>
          <option value="created_asc">最早上传</option>
          <option value="name_asc">名称 A-Z</option>
          <option value="name_desc">名称 Z-A</option>
          <option value="size_desc">大小降序</option>
          <option value="size_asc">大小升序</option>
        </Select>
      </div>
      
      {/* 文档网格 */}
      {loading ? (
        <LoadingSpinner />
      ) : (
        <>
          <DocumentGrid documents={data.items} />
          
          {/* 分页 */}
          <Pagination
            current={page}
            total={data.pagination.pages}
            onChange={setPage}
            showTotal={`共 ${data.pagination.total} 个文档`}
          />
        </>
      )}
    </div>
  );
}
```

---

## 📋 实施检查清单

### 问题12（1天）
- [ ] 修改middleware添加HTTP头部
- [ ] 修改QueryResponse模型
- [ ] 修改响应构建函数
- [ ] 前端实现余额显示
- [ ] 前端实现警告提示
- [ ] 测试各种余额场景

### 问题7（2天）
- [ ] 修改Session数据结构
- [ ] 实现软删除方法
- [ ] 实现恢复方法
- [ ] 实现回收站API
- [ ] 添加定时清理任务
- [ ] 前端实现回收站页面
- [ ] 测试删除和恢复流程

### 问题14（2天）
- [ ] 实现分页逻辑
- [ ] 实现搜索功能
- [ ] 实现类型过滤
- [ ] 实现多种排序
- [ ] 前端实现列表组件
- [ ] 前端实现过滤器
- [ ] 测试各种查询组合

---

## 🧪 测试脚本

### 测试Credit余额

```bash
# 创建低余额测试用户
# 查询并检查响应头
curl -i http://localhost:8000/api/query \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question":"test"}'
  
# 预期响应头:
# X-Credit-Remaining: 3
# X-Credit-Warning: critical
```

### 测试Session软删除

```bash
# 软删除
curl -X DELETE http://localhost:8000/api/sessions/test-session \
  -H "Authorization: Bearer $TOKEN"

# 预期响应:
# {
#   "ok": true,
#   "recoverable_until": "2026-09-20T...",
#   "message": "已删除，可在30天内从回收站恢复"
# }

# 查看回收站
curl http://localhost:8000/api/sessions/trash \
  -H "Authorization: Bearer $TOKEN"

# 恢复
curl -X POST http://localhost:8000/api/sessions/test-session/restore \
  -H "Authorization: Bearer $TOKEN"
```

### 测试文档分页

```bash
# 基本分页
curl "http://localhost:8000/api/documents?page=1&limit=10" \
  -H "Authorization: Bearer $TOKEN"

# 搜索
curl "http://localhost:8000/api/documents?search=report" \
  -H "Authorization: Bearer $TOKEN"

# 过滤
curl "http://localhost:8000/api/documents?type=pdf" \
  -H "Authorization: Bearer $TOKEN"

# 排序
curl "http://localhost:8000/api/documents?sort=name_asc" \
  -H "Authorization: Bearer $TOKEN"

# 组合查询
curl "http://localhost:8000/api/documents?page=2&limit=20&search=test&type=pdf&sort=created_desc" \
  -H "Authorization: Bearer $TOKEN"
```

---

## 📚 相关文档

- [第三批规划文档](./batch-3-usability-improvements-plan.md)
- [第一批实施参考](./batch-1-core-ux-fixes.md)
- [第二批实施参考](./batch-2-error-feedback-improvements.md)

---

**维护者**: 后端团队  
**创建日期**: 2026-08-21  
**状态**: 可直接使用

