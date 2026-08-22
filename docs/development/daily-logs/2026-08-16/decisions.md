# 技术决策 - 2026-08-16

**日期**: 2026-08-16
**记录人**: pocheang
**状态**: 已确认

---

## 决策1：使用 PATCH 方法更新会话属性

### 背景
需要实现会话的重命名和置顶功能。可以选择为每个操作创建独立端点，或使用一个统一的更新端点。

### 考虑的方案

#### 方案A：独立端点
```
PUT /sessions/{id}/title
PUT /sessions/{id}/pin
DELETE /sessions/{id}/pin
```

**优点**:
- API 语义明确，每个端点职责单一
- 更符合 RESTful 资源操作风格
- 易于单独控制权限

**缺点**:
- 端点数量多，维护成本高
- 无法原子性地同时更新多个属性
- 客户端需要发起多个请求

**成本**: 需要实现3个端点，代码量较大

---

#### 方案B：统一 PATCH 端点（选择）
```
PATCH /sessions/{id}
Body: { "title": "...", "pinned": true }
```

**优点**:
- 单一端点，灵活支持部分更新
- 可以同时更新多个属性（原子操作）
- 符合 HTTP PATCH 语义（部分更新）
- 易于扩展新属性（如标签、颜色等）

**缺点**:
- 需要在后端验证每个字段
- 权限控制粒度较粗（统一为 session:update）

**成本**: 实现成本低，维护简单

---

### 最终决策

**选择方案**: B - 统一 PATCH 端点

**决策理由**: 
1. **可扩展性**：未来添加新属性（如标签、颜色、分组）时无需新增端点
2. **原子性**：可以在一次请求中同时更新多个属性，保证数据一致性
3. **标准化**：PATCH 是 HTTP 标准的部分更新方法，符合 RESTful 最佳实践
4. **简化前端**：前端只需调用一个 API，传入需要更新的字段即可

**权衡分析**:
- 我们接受了：权限控制粒度较粗（所有更新操作共享 `session:update` 权限）
- 我们避免了：端点膨胀和维护成本

### 实施计划
1. ✅ 在 `sessions.py` 添加 PATCH 端点
2. ✅ 实现字段级别的验证逻辑
3. ✅ 支持部分更新（只传入需要修改的字段）
4. ✅ 添加审计日志记录每个字段的变更

### 影响范围
- **影响的模块**: API 路由、数据存储层、前端 API 服务
- **需要修改的文件**: 
  - `app/api/routes/public/sessions.py`
  - `app/services/sessions/history.py`
  - `frontend/src/services/api/chat.ts`

---

## 决策2：置顶会话的排序策略

### 背景
置顶会话应该显示在列表顶部，但多个置顶会话之间如何排序？

### 考虑的方案

#### 方案A：置顶会话按创建时间排序
**优点**: 逻辑简单
**缺点**: 最近使用的会话可能在底部

---

#### 方案B：置顶会话按更新时间排序（选择）
**优点**: 
- 最近活跃的会话在最上面
- 符合用户使用习惯
- 与非置顶会话排序逻辑一致

**缺点**: 需要在每次消息发送时更新 updated_at

---

#### 方案C：置顶会话手动排序（拖拽）
**优点**: 用户完全控制顺序
**缺点**: 需要额外的 `pin_order` 字段和拖拽实现

---

### 最终决策

**选择方案**: B - 按更新时间排序（当前实现）+ C（预留扩展）

**决策理由**:
- 当前实现方案B，逻辑简单且符合直觉
- 前端已集成 `react-beautiful-dnd`，为将来实现拖拽排序预留空间
- 可以在未来添加 `pin_order` 字段实现手动排序，不影响现有功能

**排序规则**:
```
1. 置顶会话 (pinned=true) 按 updated_at 降序
2. 非置顶会话 (pinned=false) 按 updated_at 降序
```

### 实施计划
1. ✅ 前端按 pinned 字段分组显示
2. ✅ 每组内按 updated_at 排序
3. ⏸️ 预留拖拽排序功能（未来实现）

---

## 决策3：数据存储格式（JSON vs SQLite）

### 背景
当前系统支持两种存储后端：JSON 文件和 SQLite。新增的 `pinned` 字段如何存储？

### 考虑的方案

#### 方案A：仅支持 JSON 文件
**优点**: 实现简单，无需数据库迁移
**缺点**: SQLite 用户无法使用新功能

---

#### 方案B：同时支持两种存储（选择）
**优点**: 向后兼容，所有用户都能使用
**缺点**: 需要维护两套代码

---

### 最终决策

**选择方案**: B - 同时支持，但优先实现 JSON

**决策理由**:
- 大部分用户使用 JSON 文件存储（默认配置）
- SQLite 支持可以通过数据库迁移脚本添加
- 代码抽象层已存在，添加 SQLite 支持成本不高

**实施计划**:
1. ✅ 实现 JSON 文件存储的 pinned 字段
2. ✅ 在 Schema 中添加默认值确保兼容性
3. ⏸️ 提供 SQLite 迁移脚本（文档已包含）
4. ⏸️ 在 `_init_sqlite()` 中添加 pinned 列支持

**SQLite 迁移脚本**（已在文档中提供）:
```sql
ALTER TABLE sessions ADD COLUMN pinned INTEGER DEFAULT 0;
CREATE INDEX idx_sessions_pinned ON sessions(namespace, pinned DESC, updated_at DESC);
```

### 影响范围
- **当前影响**: 仅 JSON 文件存储
- **未来影响**: SQLite 用户需要运行迁移脚本

---

## 决策4：Toast 通知 vs 全局消息提示

### 背景
用户执行重命名、置顶等操作后需要反馈。是使用 Toast 通知还是页面顶部的全局消息条？

### 考虑的方案

#### 方案A：Ant Design Message 组件
**优点**: 
- 已有依赖，无需额外安装
- 样式统一

**缺点**: 
- 自动消失时间不可定制
- 不支持动作按钮（撤销等）

---

#### 方案B：自定义 Toast 组件（选择）
**优点**:
- 完全控制样式和行为
- 支持堆叠显示多个通知
- 支持不同类型（success、error、info、warning）
- 可扩展撤销功能

**缺点**:
- 需要自己实现组件和样式

---

### 最终决策

**选择方案**: B - 自定义 Toast 组件

**决策理由**:
- 需要更灵活的控制（持续时间、位置、样式）
- 为将来的撤销功能预留空间
- 与整体UI风格更一致

**实施计划**:
1. ✅ 创建 ToastStack 组件
2. ✅ 在 Zustand store 中管理 toast 状态
3. ✅ 在 App.tsx 中全局挂载
4. ✅ 支持 4 种类型（success、error、info、warning）
5. ⏸️ 未来添加撤销功能

### 影响范围
- **新增组件**: ToastStack.tsx
- **状态管理**: useChatStore 添加 toasts 和相关方法
- **全局集成**: App.tsx

---

## 参考资料

- [RESTful API 设计最佳实践](https://restfulapi.net/)
- [HTTP PATCH Method - RFC 5789](https://tools.ietf.org/html/rfc5789)
- [React Beautiful DnD](https://github.com/atlassian/react-beautiful-dnd)
- [Toast UX 最佳实践](https://uxdesign.cc/toast-notification-best-practices-1e19ee84f4e3)
