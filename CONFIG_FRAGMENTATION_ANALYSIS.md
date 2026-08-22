# 配置文件碎片化分析

## 发现的问题

### 6个配置文件，职责重叠！

| 文件 | 行数 | 用途 | 问题 |
|------|------|------|------|
| `rag/config.py` | 260 | RAG配置常量 | 最大，包含大量常量 |
| `shared/config.py` | 168 | 通用配置常量 | 与 unified_config 重复 |
| `shared/unified_config.py` | 163 | Pydantic配置模型 | 与 config.py 重叠 |
| `shared/quality_config.py` | 161 | 质量评估配置 | 应在 validation/ |
| `router/config.py` | 68 | Router配置 | 与 shared/config 重复 |
| `router/hybrid_config.py` | 57 | 混合模式配置 | 应合并到 router/config |

**总计**: 877 行配置代码分散在 6 个文件中！

## 重复内容示例

### 1. VALID_ROUTES 重复定义
```python
# shared/config.py
VALID_ROUTES: Final[frozenset[str]] = frozenset({"vector", "graph", "web", "react"})

# 其他文件可能也定义了相同常量
```

### 2. 配置方式不统一
- `shared/config.py` - 使用 Final 常量
- `shared/unified_config.py` - 使用 Pydantic BaseModel
- 两种方式并存，导致混乱

### 3. 质量配置错放
- `shared/quality_config.py` 应该在 `validation/` 模块
- `shared/quality_models.py` 应该在 `validation/` 模块

## 导入引用分析

9 处导入来自 3 个不同的配置文件：
- `from app.agents.shared.config import`
- `from app.agents.shared.unified_config import`
- `from app.agents.shared.quality_config import`

这说明配置管理**不统一**！

## 建议的统一方案

### 目标结构
```
app/agents/
├── shared/
│   └── config.py              # 统一配置 (合并3个)
├── rag/
│   └── config.py              # RAG专属配置
├── router/
│   └── config.py              # Router专属配置 (合并hybrid_config)
└── validation/
    └── config.py              # 质量配置 (从shared迁移)
```

### 优先级
1. **高优先级**: 合并 `shared/` 中的 3 个配置文件
2. **中优先级**: 合并 `router/hybrid_config.py` → `router/config.py`
3. **低优先级**: 迁移质量配置到 `validation/`

## 预期效果
- 6 个配置文件 → **4 个**
- 配置方式统一（统一使用 Pydantic 或 常量）
- 导入路径清晰
- 减少配置查找时间
