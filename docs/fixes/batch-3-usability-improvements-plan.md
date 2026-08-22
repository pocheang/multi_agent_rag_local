# 第三批修复 - 可用性改进规划

**修复批次**: Batch 3 - 可用性细节优化  
**版本**: v0.6.2.4（规划中）  
**状态**: 📋 规划阶段  
**预计工作量**: 2周  
**最后更新**: 2026-08-21

---

## 📋 规划概览

第三批聚焦于**可用性细节优化**，解决用户在日常使用中遇到的小痛点。虽然单个问题影响不如前两批严重，但积累起来对用户体验有显著影响。

### 优先级矩阵

```
影响范围  │  简单  │  中等  │  复杂
─────────┼───────┼───────┼──────
所有用户  │ 问题12│   -   │ 问题6
─────────┼───────┼───────┼──────
常见场景  │ 问题14│ 问题13│   -
─────────┼───────┼───────┼──────
特定场景  │ 问题15│ 问题7 │   -
```

**建议顺序**: 12 → 7 → 14 → 15 → 13 → 6

---

## 🎯 包含的问题

### ⭐ 高优先级（建议优先实施）

#### 问题12: Credit余额无提示
**影响**: 所有用户  
**复杂度**: ⭐ 简单  
**工作量**: 1天

**当前问题**:
- 用户发送查询时才知道credit不足
- 输入的问题可能丢失
- 不知道还能查询几次

**解决方案**:
```python
# 1. 在每个API响应中添加HTTP头部
response.headers["X-Credit-Remaining"] = str(user["credit_balance"])
response.headers["X-Credit-Warning"] = "low" if balance < 10 else "ok"

# 2. 在查询响应中包含余额信息
{
  "answer": "...",
  "credit_info": {
    "remaining": 5,
    "total": 100,
    "warning_threshold": 10,
    "cost_per_query": 1
  }
}
```

**前端实现**:
```typescript
// 显示余额提示
if (creditRemaining < 10) {
  showBanner({
    type: 'warning',
    message: `剩余${creditRemaining}次查询，充值>`,
    persistent: true
  });
}

// 输入框下方显示
<div>本次查询将消耗1个credit，剩余{creditRemaining}次</div>
```

**预期效果**:
- ✅ 用户提前知道余额
- ✅ 可以决定是否发送查询
- ✅ 减少"余额不足"的挫败感

---

#### 问题7: Session删除无法恢复
**影响**: 误删用户  
**复杂度**: ⭐⭐ 中等  
**工作量**: 2天

**当前问题**:
- 用户误删重要对话
- 无法恢复，数据永久丢失
- 企业用户需要历史记录作为工作证明

**解决方案**: 软删除 + 回收站

**实现方案**:

1. **数据库schema变更**:
```python
# session数据添加字段
{
  "session_id": "xxx",
  "messages": [...],
  "deleted_at": null,  # 新增：删除时间
  "deleted_by": null,  # 新增：删除人
  "auto_delete_at": null  # 新增：自动删除时间
}
```

2. **API变更**:
```python
# 现有DELETE保持不变，但改为软删除
@router.delete("/{session_id}")
def delete_session(session_id, user):
    store.soft_delete_session(
        session_id=session_id,
        deleted_by=user["user_id"],
        auto_delete_after_days=30  # 30天后自动永久删除
    )
    return {
        "ok": True,
        "session_id": session_id,
        "recoverable_until": "2026-09-20",
        "message": "已删除，可在30天内从回收站恢复"
    }

# 新增：查看回收站
@router.get("/trash")
def list_trash(user):
    return store.list_deleted_sessions(user["user_id"])

# 新增：恢复session
@router.post("/{session_id}/restore")
def restore_session(session_id, user):
    store.restore_session(session_id)
    return {"ok": True, "session_id": session_id}

# 新增：永久删除
@router.delete("/{session_id}/permanent")
def permanent_delete(session_id, user):
    store.permanent_delete_session(session_id)
    return {"ok": True, "message": "已永久删除，无法恢复"}
```

3. **后台任务**:
```python
# 定时清理过期的软删除session
@scheduler.scheduled_job('cron', hour=3)
def cleanup_expired_deleted_sessions():
    store.permanent_delete_expired(days=30)
```

**前端实现**:
```typescript
// 删除确认对话框
showConfirmDialog({
  title: '删除会话',
  message: '确定删除此会话吗？',
  detail: '删除后可在30天内从回收站恢复',
  confirmText: '删除',
  cancelText: '取消'
});

// 回收站页面
<RecycleBin>
  <EmptyState icon="🗑️">
    <p>回收站中的会话将在30天后自动删除</p>
    <Button onClick={viewTrash}>查看回收站</Button>
  </EmptyState>
</RecycleBin>
```

**预期效果**:
- ✅ 误删可以恢复
- ✅ 30天缓冲期
- ✅ 自动清理过期数据

---

### ⭐ 中优先级（建议后续实施）

#### 问题14: 文档列表无搜索和分页
**影响**: 多文档用户  
**复杂度**: ⭐⭐ 中等  
**工作量**: 2天

**当前问题**:
```python
@router.get("/documents")
def list_documents(user):
    # 返回全部文档，可能上百个
    return merge_visible_document_status(all_docs, ...)
```

**解决方案**:

```python
@router.get("/documents")
def list_documents(
    user: dict,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    type: str | None = Query(None),  # pdf, docx, txt
    sort: str = Query("created_desc"),  # created_desc, name_asc, size_desc
):
    """
    列出文档，支持分页、搜索和过滤
    
    查询参数:
    - page: 页码（从1开始）
    - limit: 每页数量（1-100）
    - search: 搜索文件名
    - type: 过滤文件类型
    - sort: 排序方式
    """
    
    # 获取所有可见文档
    all_docs = _list_visible_documents_for_user(user)
    
    # 搜索过滤
    if search:
        search_lower = search.lower()
        all_docs = [
            doc for doc in all_docs
            if search_lower in doc["filename"].lower()
        ]
    
    # 类型过滤
    if type:
        all_docs = [
            doc for doc in all_docs
            if doc["filename"].lower().endswith(f".{type}")
        ]
    
    # 排序
    sort_key, sort_order = sort.split("_")
    reverse = (sort_order == "desc")
    
    if sort_key == "created":
        all_docs.sort(key=lambda x: x.get("created_at", ""), reverse=reverse)
    elif sort_key == "name":
        all_docs.sort(key=lambda x: x["filename"], reverse=reverse)
    elif sort_key == "size":
        all_docs.sort(key=lambda x: x.get("size", 0), reverse=reverse)
    
    # 分页
    total = len(all_docs)
    start = (page - 1) * limit
    end = start + limit
    page_docs = all_docs[start:end]
    
    return {
        "items": merge_visible_document_status(page_docs, ...),
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit,
            "has_next": end < total,
            "has_prev": page > 1,
        }
    }
```

**前端实现**:
```typescript
function DocumentList() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  
  const { data, loading } = useDocuments({ page, search, type: typeFilter });
  
  return (
    <div>
      <SearchBar 
        value={search}
        onChange={setSearch}
        placeholder="搜索文档..."
      />
      
      <FilterBar>
        <Select value={typeFilter} onChange={setTypeFilter}>
          <option value="all">全部</option>
          <option value="pdf">PDF</option>
          <option value="docx">Word</option>
          <option value="txt">文本</option>
        </Select>
      </FilterBar>
      
      <DocumentGrid documents={data.items} />
      
      <Pagination
        current={page}
        total={data.pagination.pages}
        onChange={setPage}
      />
    </div>
  );
}
```

**预期效果**:
- ✅ 列表加载快
- ✅ 可以搜索文档
- ✅ 按类型过滤
- ✅ 多种排序方式

---

#### 问题15: Session列表性能问题
**影响**: 重度用户  
**复杂度**: ⭐⭐ 中等  
**工作量**: 2天

**解决方案**: 类似问题14，实现分页和虚拟滚动

```python
@router.get("/sessions")
def list_sessions(
    user: dict,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    include_pinned: bool = Query(True),
    recent: str | None = Query(None),  # 7d, 30d, 90d
):
    """
    列出会话，支持分页
    
    查询参数:
    - page: 页码
    - limit: 每页数量
    - include_pinned: 是否包含置顶会话
    - recent: 时间范围过滤
    """
    store = _history_store_for_user(user)
    
    # 获取全部session
    all_sessions = store.list_sessions()
    
    # 时间过滤
    if recent:
        days = int(recent.rstrip('d'))
        cutoff = datetime.now() - timedelta(days=days)
        all_sessions = [
            s for s in all_sessions
            if datetime.fromisoformat(s["updated_at"]) > cutoff
        ]
    
    # 分离置顶和普通
    pinned = [s for s in all_sessions if s.get("pinned")]
    regular = [s for s in all_sessions if not s.get("pinned")]
    
    # 分页（只对非置顶分页）
    total = len(regular)
    start = (page - 1) * limit
    end = start + limit
    page_regular = regular[start:end]
    
    # 第一页包含置顶
    items = (pinned + page_regular) if page == 1 and include_pinned else page_regular
    
    return {
        "items": items,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit,
        },
        "pinned_count": len(pinned),
    }
```

**前端虚拟滚动**:
```typescript
import { useVirtualizer } from '@tanstack/react-virtual';

function SessionList() {
  const parentRef = useRef();
  const { data } = useSessions({ page: 1, limit: 1000 });
  
  const virtualizer = useVirtualizer({
    count: data.items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 80, // 每个session高度
  });
  
  return (
    <div ref={parentRef} style={{ height: '600px', overflow: 'auto' }}>
      <div style={{ height: virtualizer.getTotalSize() }}>
        {virtualizer.getVirtualItems().map(virtualRow => (
          <SessionCard
            key={data.items[virtualRow.index].session_id}
            session={data.items[virtualRow.index]}
            style={{
              position: 'absolute',
              top: virtualRow.start,
              height: virtualRow.size,
            }}
          />
        ))}
      </div>
    </div>
  );
}
```

**预期效果**:
- ✅ 支持上千个session
- ✅ 滚动流畅
- ✅ 内存占用低

---

### ⏸️ 低优先级（建议延后）

#### 问题13: 查询无进度反馈
**影响**: 长查询场景  
**复杂度**: ⭐⭐⭐ 中高  
**工作量**: 2天

**问题**: 非流式查询时，用户只看到loading，不知道进度

**解决方案**: 建议优先推广使用流式API

**替代方案**:
1. **简单方案**: 在前端显示预估时间
   ```typescript
   // 基于历史平均时间预估
   const estimatedTime = getAverageQueryTime(queryType);
   showProgress(`预计需要 ${estimatedTime} 秒...`);
   ```

2. **完整方案**: 实现轮询进度端点（类似问题2的status端点）
   ```python
   @router.get("/query/progress/{request_id}")
   def get_query_progress(request_id):
       return {
           "status": "processing",
           "current_stage": "retrieve",  # route, retrieve, synthesize
           "progress_percent": 60,
           "estimated_remaining_seconds": 5
       }
   ```

**为什么延后**:
- 用户已经可以使用流式API（有实时进度）
- 实现成本较高
- 影响范围有限（大部分查询<5秒）

---

#### 问题6: 查询超时优雅降级
**影响**: 复杂查询  
**复杂度**: ⭐⭐⭐⭐ 高  
**工作量**: 3天

**问题**: 查询超时后用户什么都看不到

**为什么最后实施**:
1. **架构复杂度高**: 需要修改编排引擎核心
2. **影响范围大**: 涉及多个服务的协调
3. **测试成本高**: 需要大量边界测试
4. **可以规避**: 大部分查询都在超时内完成

**建议方案**（当确实需要时）:

```python
# 在编排引擎中保存中间结果
class OrchestrationEngine:
    async def execute(self, request):
        partial_result = {
            "completed_stages": [],
            "route": None,
            "evidence": None,
            "answer": None,
        }
        
        try:
            # Stage 1: Route
            route = await run_with_timeout("route", ...)
            partial_result["route"] = route
            partial_result["completed_stages"].append("route")
            
            # Stage 2: Retrieve
            evidence = await run_with_timeout("retrieve", ...)
            partial_result["evidence"] = evidence
            partial_result["completed_stages"].append("retrieve")
            
            # Stage 3: Synthesize
            answer = await run_with_timeout("synthesize", ...)
            partial_result["answer"] = answer
            
            return FinalAnswer(...)
            
        except TimeoutError:
            # 返回部分结果
            return PartialAnswer(
                status="timeout",
                completed_stages=partial_result["completed_stages"],
                partial_data=partial_result,
                message="查询超时，但已完成部分工作",
                suggestion="请简化问题或稍后重试"
            )
```

**预计工作量**: 3天（设计1天 + 实现1天 + 测试1天）

---

## 📊 实施建议

### 阶段1（1周）- 快速改进
1. ✅ **问题12**: Credit余额提示（1天）
2. ✅ **问题7**: Session软删除（2天）
3. ✅ **问题14**: 文档列表分页（2天）

### 阶段2（1周）- 性能优化
4. ✅ **问题15**: Session列表分页（2天）
5. ⏸️ **问题13**: 查询进度（可选，2天）

### 阶段3（未来）- 架构优化
6. ⏸️ **问题6**: 超时降级（需要时，3天）

---

## 💰 成本收益分析

### 投入
- **阶段1**: 5个工作日
- **阶段2**: 5个工作日
- **总计**: 10个工作日（2周）

### 回报
- **Credit提示**: 减少"余额不足"工单 50%（约5个/月）
- **Session恢复**: 减少"误删恢复"工单 80%（约4个/月）
- **列表性能**: 改善重度用户体验，减少投诉 30%
- **总计**: 预计减少10-15个工单/月

### ROI
- **首月**: 75% (10小时节省 / 80小时投入)
- **年度**: 900% (120小时节省 / 80小时投入)

---

## 🧪 测试策略

### 问题12测试
```bash
# 测试Credit余额在响应中
curl -i http://localhost:8000/api/query ...
# 检查 X-Credit-Remaining 头部

# 测试余额不足
# 创建credit=0的测试用户
# 预期：提前看到余额为0的提示
```

### 问题7测试
```bash
# 测试软删除
DELETE /api/sessions/{id}
# 预期：返回 recoverable_until 字段

# 测试回收站
GET /api/sessions/trash
# 预期：返回已删除的session

# 测试恢复
POST /api/sessions/{id}/restore
# 预期：session恢复到列表

# 测试自动清理
# 模拟31天后
# 预期：session永久删除
```

### 问题14/15测试
```bash
# 测试分页
GET /api/documents?page=1&limit=20
# 预期：返回20个文档 + pagination信息

# 测试搜索
GET /api/documents?search=report
# 预期：只返回包含"report"的文档

# 测试过滤
GET /api/documents?type=pdf
# 预期：只返回PDF文档
```

---

## 📝 后续优化建议

### 短期（1个月）
1. 监控Credit余额警告的触发率
2. 统计Session恢复的使用率
3. 收集用户对分页的反馈

### 中期（3个月）
4. 考虑实现问题13（查询进度）
5. 评估问题6（超时降级）的必要性
6. 基于数据优化分页大小和缓存策略

### 长期（6个月）
7. 建立用户行为分析系统
8. 基于分析结果持续优化
9. 探索更高级的UX改进

---

## 🎯 成功指标

### 定量指标
- [ ] Credit相关工单 ↓ 50%
- [ ] Session恢复使用率 > 10%
- [ ] 文档/Session列表加载时间 < 500ms
- [ ] 重度用户投诉 ↓ 30%

### 定性指标
- [ ] 用户反馈"体验更流畅"
- [ ] 支持团队反馈"工单减少"
- [ ] 产品经理认可改进效果

---

**文档版本**: 1.0  
**维护者**: 后端团队  
**最后更新**: 2026-08-21  
**下次审核**: 实施前

