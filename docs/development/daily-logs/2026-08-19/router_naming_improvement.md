# Router 重构命名改进方案

**当前状态**: 2026-08-19  
**问题**: `refactored_routing.py` 命名不够清晰

---

## 🎯 推荐方案

### 方案 A: 重命名为 `pipeline.py` (推荐)

**理由**:
- ✅ 语义清晰 - 描述了架构特征（流水线模式）
- ✅ 长期适用 - 不带临时性质
- ✅ 简洁明了 - 一看就懂

**实施**:
```bash
# 1. 重命名文件
git mv app/agents/router/refactored_routing.py \
       app/agents/router/pipeline.py

# 2. 更新导入
# adapter.py
from app.agents.router.pipeline import RoutingPipeline

# 3. 更新测试
git mv tests/agents/router/test_refactored_routing.py \
       tests/agents/router/test_pipeline.py
```

**最终结构**:
```
app/agents/router/
  ├── routing.py      # Legacy (待废弃)
  ├── pipeline.py     # 新架构 ⭐
  └── adapter.py      # 兼容层
```

---

### 方案 B: 重命名为 `components.py`

**理由**:
- ✅ 强调组件化
- ✅ 清晰的架构意图

**实施**: 同方案 A

---

### 方案 C: 创建子包 `v2`

**理由**:
- ✅ 版本清晰
- ✅ 易于扩展

**结构**:
```
app/agents/router/
  ├── routing.py          # v1 (legacy)
  ├── v2/
  │   ├── __init__.py     # 导出 RoutingPipeline
  │   ├── pipeline.py     # 流水线
  │   └── components.py   # 组件
  └── adapter.py
```

---

## 🚀 推荐执行方案

### 立即重命名 (推荐)

```bash
# 1. 重命名主文件
git mv app/agents/router/refactored_routing.py \
       app/agents/router/pipeline.py

# 2. 重命名测试
git mv tests/agents/router/test_refactored_routing.py \
       tests/agents/router/test_pipeline.py

# 3. 更新 adapter.py
# 修改导入: 
# from app.agents.router.refactored_routing import RoutingPipeline
# 改为:
# from app.agents.router.pipeline import RoutingPipeline

# 4. 更新文档中的引用
```

### 迁移时间表

**Phase 1: 重命名** (立即)
- 重命名文件
- 更新导入
- 更新文档

**Phase 2: 逐步迁移** (1-2周)
- 将 `RouterService` 切换到新架构
- 更新所有调用点
- 添加废弃警告到 `routing.py`

**Phase 3: 移除 Legacy** (1个月后)
- 删除 `routing.py`
- `pipeline.py` 成为唯一实现

---

## 📋 需要更新的文件

1. **代码文件**
   - app/agents/router/adapter.py
   - app/agents/router/service.py (如果使用了)

2. **测试文件**
   - tests/agents/router/test_pipeline.py (重命名)

3. **文档**
   - router_refactoring_report.md
   - phase2_plan.md
   - README_PHASE2.md

4. **演示脚本**
   - scripts/demo_router_refactoring.py (可保持原名)

---

## 💡 建议

**我的推荐**: 立即执行方案 A (重命名为 `pipeline.py`)

**理由**:
1. 简单直接
2. 语义清晰
3. 易于维护
4. 符合长期使用场景

**是否立即执行?**
- 如果您同意，我可以立即执行重命名
- 或者保持现状，等待进一步讨论

---

**当前状态**: 待决定  
**推荐行动**: 重命名为 `pipeline.py`
