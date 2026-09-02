# Day 4 Plan - Session Management Enhancement

## 日期
2026-08-21

## 目标
增强会话管理功能，提供更好的用户体验和会话组织能力

## 背景

### 当前状态
- ✅ 基础会话管理已实现（创建、重命名、固定）
- ✅ 上下文追踪系统完成（Day 3）
- ⚠️ 缺少高级会话管理功能
- ⚠️ 缺少会话元数据和标签
- ⚠️ 缺少会话搜索和过滤

### Week 2 Phase 2 进度
- ✅ Day 2: Query Optimization (1,154 lines)
- ✅ Day 3: Context Management (1,367 lines, P0 fixed)
- 🎯 Day 4: Session Management Enhancement
- ⏳ Day 5: Multi-modal Support Improvements
- ⏳ Day 6-7: Performance Optimization

## 核心功能范围

### 1. Session Metadata System (2-3小时)
**目标**: 为会话添加丰富的元数据

**功能**:
- 会话标签系统 (tags)
- 会话分类 (category: work, personal, research, etc.)
- 会话描述 (description)
- 自动元数据提取（从对话内容）
- 元数据CRUD API

**数据模型**:
```python
@dataclass
class SessionMetadata:
    session_id: str
    tags: list[str]  # ["技术", "AI", "产品"]
    category: str | None  # "work" | "personal" | "research"
    description: str | None
    auto_tags: list[str]  # 自动提取的标签
    created_at: datetime
    updated_at: datetime
    query_count: int
    last_query_at: datetime | None
```

**实现**:
- `app/services/session_metadata.py` - 核心服务
- `app/api/routes/sessions/metadata.py` - API路由
- Database migration for metadata table

### 2. Session Search & Filter (1-2小时)
**目标**: 快速查找和过滤会话

**功能**:
- 按标签搜索
- 按分类过滤
- 按时间范围过滤
- 全文搜索（会话名称、描述）
- 复合过滤条件

**API接口**:
```python
GET /api/v1/sessions/search?
    q=<query>&
    tags=<tag1,tag2>&
    category=<category>&
    from=<date>&
    to=<date>&
    limit=<n>
```

### 3. Session Export & Import (1-2小时)
**目标**: 会话数据的导出和导入

**功能**:
- 导出单个会话为JSON
- 导出多个会话为ZIP
- 导入会话（带冲突处理）
- 导出包含完整上下文和元数据

**格式**:
```json
{
  "session_id": "xxx",
  "metadata": {...},
  "messages": [...],
  "context": {...},
  "export_version": "1.0",
  "exported_at": "2026-08-21T10:00:00Z"
}
```

### 4. Session Templates (1小时)
**目标**: 预定义会话模板，快速开始

**功能**:
- 系统模板（技术研究、产品分析、代码审查）
- 用户自定义模板
- 模板包含初始消息和元数据
- 从现有会话创建模板

**模板示例**:
```python
TEMPLATES = {
    "technical_research": {
        "name": "技术研究",
        "category": "research",
        "tags": ["技术", "研究"],
        "initial_message": "请帮我研究...",
        "description": "用于技术主题的深度研究",
    }
}
```

### 5. Frontend Integration (2-3小时)
**目标**: 前端UI支持新功能

**组件**:
- SessionMetadataEditor - 元数据编辑器
- SessionSearch - 搜索界面
- SessionExport - 导出对话框
- SessionTemplates - 模板选择器
- TagInput - 标签输入组件

## 技术设计

### 数据库Schema
```sql
CREATE TABLE session_metadata (
    session_id TEXT PRIMARY KEY,
    tags JSON,
    category TEXT,
    description TEXT,
    auto_tags JSON,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    query_count INTEGER DEFAULT 0,
    last_query_at TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX idx_session_tags ON session_metadata USING GIN(tags);
CREATE INDEX idx_session_category ON session_metadata(category);
CREATE INDEX idx_session_updated ON session_metadata(updated_at DESC);
```

### API路由设计
```
POST   /api/v1/sessions/{id}/metadata       # 更新元数据
GET    /api/v1/sessions/{id}/metadata       # 获取元数据
GET    /api/v1/sessions/search              # 搜索会话
POST   /api/v1/sessions/{id}/export         # 导出会话
POST   /api/v1/sessions/import              # 导入会话
GET    /api/v1/sessions/templates           # 获取模板列表
POST   /api/v1/sessions/from-template       # 从模板创建
```

### 服务架构
```
SessionMetadataService
├─ create_metadata()
├─ update_metadata()
├─ extract_auto_tags()  # 使用LLM提取标签
└─ search_sessions()

SessionExportService
├─ export_session()
├─ export_multiple()
├─ import_session()
└─ validate_import()

SessionTemplateService
├─ list_templates()
├─ create_from_template()
└─ save_as_template()
```

## 自动标签提取

使用轻量级LLM（Claude Haiku）从对话内容提取标签：

```python
async def extract_auto_tags(
    session_id: str,
    messages: list[dict]
) -> list[str]:
    """
    从会话消息中提取标签
    
    使用最近5-10条消息
    提取3-5个关键标签
    """
    # 收集最近消息
    recent = messages[-10:]
    content = "\n".join([m["content"] for m in recent])
    
    # 使用Haiku提取
    prompt = f"""
    Analyze this conversation and extract 3-5 key tags.
    Tags should be:
    - Single words or short phrases (1-3 words)
    - In the same language as the conversation
    - Represent main topics discussed
    
    Conversation:
    {content[:1000]}
    
    Output format: tag1, tag2, tag3
    """
    
    response = await call_haiku(prompt)
    tags = [t.strip() for t in response.split(",")]
    return tags[:5]
```

## 实施计划

### Phase 1: 后端核心 (3-4小时)
**时间**: 09:00 - 13:00

1. **09:00 - 10:00**: SessionMetadata数据模型和服务
   - 数据模型定义
   - CRUD操作
   - 单元测试

2. **10:00 - 11:00**: 自动标签提取
   - LLM集成
   - 标签提取逻辑
   - 测试

3. **11:00 - 12:00**: 搜索和过滤
   - 搜索服务实现
   - 复合查询支持
   - 测试

4. **12:00 - 13:00**: 导出导入功能
   - JSON序列化
   - ZIP压缩
   - 导入验证

### Phase 2: API集成 (1-2小时)
**时间**: 14:00 - 16:00

5. **14:00 - 15:00**: REST API endpoints
   - 元数据API
   - 搜索API
   - 导出导入API

6. **15:00 - 16:00**: API测试
   - 集成测试
   - 端到端测试

### Phase 3: 前端实现 (2-3小时)
**时间**: 16:00 - 19:00

7. **16:00 - 17:30**: React组件
   - SessionMetadataEditor
   - SessionSearch
   - TagInput

8. **17:30 - 18:30**: 导出导入UI
   - SessionExport对话框
   - 进度显示
   - 错误处理

9. **18:30 - 19:00**: 集成测试和文档
   - 端到端测试
   - 用户文档
   - 完成报告

## 预期成果

### 代码交付
- `app/services/session_metadata.py` (~400 lines)
- `app/services/session_export.py` (~300 lines)
- `app/services/session_templates.py` (~200 lines)
- `app/api/routes/sessions/metadata.py` (~200 lines)
- `tests/services/test_session_metadata.py` (~300 lines)
- `tests/services/test_session_export.py` (~200 lines)
- `frontend/src/components/SessionMetadataEditor.tsx` (~200 lines)
- `frontend/src/components/SessionSearch.tsx` (~250 lines)
- `frontend/src/components/SessionExport.tsx` (~150 lines)
- **总计**: ~2,200 lines

### 功能验证
- [ ] 元数据CRUD正常工作
- [ ] 自动标签提取准确率>70%
- [ ] 搜索响应时间<200ms
- [ ] 导出导入完整无损
- [ ] 前端UI流畅易用

## 风险和注意事项

### 技术风险
1. **自动标签提取质量**
   - 缓解: 使用少样本提示词，结合用户反馈调整

2. **搜索性能**
   - 缓解: 添加数据库索引，使用分页

3. **导出文件大小**
   - 缓解: 压缩JSON，限制消息数量

### 兼容性
- 确保与现有会话API兼容
- 数据库迁移要支持回滚
- 旧会话要能正常使用

## 成功标准

1. **功能完整性**: 所有计划功能实现
2. **测试覆盖**: >80% 代码覆盖率
3. **性能**: 搜索<200ms, 导出<2s
4. **用户体验**: 前端交互流畅
5. **代码质量**: 通过代码审查标准

## 后续优化

Day 4完成后可考虑的增强：
- 会话分享功能
- 会话协作（多用户）
- 会话统计和分析
- 智能会话推荐
- 会话归档和清理

---

**预计时间**: 8-9小时
**优先级**: P1 (Week 2核心功能)
**依赖**: Day 2, Day 3完成
