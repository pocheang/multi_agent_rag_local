# 澄清功能修复 - 2026-08-18

## 问题

路由智能体的多轮澄清功能不工作 - 用户回答第一个澄清问题后，系统没有继续提出后续问题。

## 根本原因

**存储路径不匹配**：`/api/v1/clarification/check` 端点使用匿名存储 (`sessions/anonymous/`)，而用户实际会话在认证用户目录 (`sessions/user_{id}/`)，导致澄清上下文丢失。

## 修复

修改 `app/api/routes/public/clarification.py`：

1. 添加认证依赖：`user: dict[str, Any] = Depends(_require_user)`
2. 使用用户存储：`history_store = _history_store_for_user(user)`
3. 移除匿名存储逻辑

## 验证

✅ 后端逻辑测试通过（3轮澄清正常工作）  
✅ 会话存储测试通过（上下文正确保存和恢复）  
✅ 集成检查通过（16/16 项全部通过）

## 测试方法

```bash
# 启动后端
uvicorn app.api.main:app --reload --port 8000

# 启动前端
cd frontend && npm run dev
```

测试问题："我想设计一个RAG系统"

预期行为：
1. 系统问："这个 RAG 主要用于什么场景？"
2. 用户回答："企业知识库"
3. 系统问："数据来源是什么类型？"
4. 用户回答："PDF文档"
5. 系统问："预计的数据规模大概有多大？"
6. ... 继续直到收集完所有信息

## 相关文件

- `app/api/routes/public/clarification.py` - 已修复
- `app/agents/router/enhanced_service.py` - 澄清逻辑（无需修改）
- `frontend/src/pages/ChatPage.tsx` - 前端集成（无需修改）
