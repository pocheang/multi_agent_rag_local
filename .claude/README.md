# Claude Code 指南索引

> **创建日期**: 2026-07-06  
> **目的**: 快速导航到相关指南文档

---

## 📚 核心指南

### 1. [SKILLS_GUIDE.md](SKILLS_GUIDE.md) - 技能使用指南
**用途**: 避免技能选择混乱，提供清晰的决策树

**包含内容**:
- 📋 快速决策树 - 从用户请求到技能选择
- 🎯 核心规则 - 3大必须遵守的规则
- 📊 技能分类矩阵 - 47个技能的完整分类
- ⚠️ 常见冲突场景 - 4个典型混淆场景及解决方案
- 🎬 完整工作流示例 - 4个端到端示例
- 🚫 反模式 - 应该避免的错误模式

**何时查看**: 
- ✅ 不确定应该使用哪个技能
- ✅ 技能之间出现冲突
- ✅ 需要了解技能的正确使用顺序

---

### 2. [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) - 完整工作流指南
**用途**: 从开发到发布的完整流程指南

**包含内容**:
- 🔄 开发工作流 - 5个阶段的详细流程
- 📊 报告生成流程 - 4种报告类型及模板使用
- 📂 历史记录管理 - 文档归档规则和命名规范
- 🚀 GitHub发布流程 - 6步发布检查清单
- 🔗 技能与工作流映射 - 快速查找表

**何时查看**:
- ✅ 需要生成交接报告或版本报告
- ✅ 不知道文档应该放在哪里
- ✅ 准备发布到GitHub
- ✅ 需要归档历史记录
- ✅ 想了解完整的开发到发布流程

---

### 3. [REPORTING_STANDARDS.md](REPORTING_STANDARDS.md) - 报告管理规范 🔥 强制执行
**用途**: 统一报告格式，避免混乱，确保完整性

**包含内容**:
- 📋 报告类型矩阵 - 强制报告 vs 可选报告
- 📝 统一报告模板 - 交接报告、版本报告的完整模板
- 🔄 强制报告流程 - 带检查清单的标准流程
- 📂 统一目录结构 - 所有报告的保存位置
- 📊 报告质量标准 - 优秀报告的评判标准
- 🤖 自动化规则 - 强制验证和归档规则

**何时查看**:
- ✅ **必看** - 每次生成报告前
- ✅ 不确定报告格式是否正确
- ✅ 不知道报告应该保存在哪里
- ✅ 需要检查报告是否完整

**重要**: 此规范从 2026-07-06 起**强制执行**，所有报告必须遵守！

---

## 🎯 快速查找

### 按任务类型查找

| 任务 | 查看文档 | 章节 |
|------|---------|------|
| **选择技能** | [SKILLS_GUIDE.md](SKILLS_GUIDE.md) | 快速决策树 |
| **解决技能冲突** | [SKILLS_GUIDE.md](SKILLS_GUIDE.md) | 常见冲突场景 |
| **开发新功能** | [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) | 开发工作流 → 阶段1-3 |
| **验证代码** | [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) | 开发工作流 → 阶段3 |
| **代码审查** | [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) | 开发工作流 → 阶段4 |
| **生成报告** 🔥 | [REPORTING_STANDARDS.md](REPORTING_STANDARDS.md) | 统一报告模板 |
| **检查报告完整性** 🔥 | [REPORTING_STANDARDS.md](REPORTING_STANDARDS.md) | 完整性检查清单 |
| **归档文档** | [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) + [REPORTING_STANDARDS.md](REPORTING_STANDARDS.md) | 历史记录管理 + 统一目录结构 |
| **发布版本** | [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) | GitHub发布流程 |

### 按问题类型查找

| 问题 | 解决方案位置 |
|------|------------|
| "应该用哪个技能？" | [SKILLS_GUIDE.md](SKILLS_GUIDE.md) → 快速决策树 |
| "code-review和simplify有什么区别？" | [SKILLS_GUIDE.md](SKILLS_GUIDE.md) → 场景1 |
| "为什么必须用流程技能？" | [SKILLS_GUIDE.md](SKILLS_GUIDE.md) → 核心规则1 |
| "报告格式是什么？" 🔥 | [REPORTING_STANDARDS.md](REPORTING_STANDARDS.md) → 统一报告模板 |
| "报告应该放在哪里？" 🔥 | [REPORTING_STANDARDS.md](REPORTING_STANDARDS.md) → 统一目录结构 |
| "报告是否完整？" 🔥 | [REPORTING_STANDARDS.md](REPORTING_STANDARDS.md) → 完整性检查清单 |
| "如何发布到GitHub？" | [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) → GitHub发布流程 |
| "历史文档如何整理？" | [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) + [REPORTING_STANDARDS.md](REPORTING_STANDARDS.md) → 归档规则 |

---

## 📖 学习路径

### 新手路径

1. **第一步**: 阅读 [SKILLS_GUIDE.md](SKILLS_GUIDE.md) 的"快速决策树"
2. **第二步**: 查看"核心规则"理解3大原则
3. **第三步**: 浏览"完整工作流示例"了解实际应用
4. **第四步**: 阅读 [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) 的"开发工作流"

### 进阶路径

1. **技能精通**: 研究 [SKILLS_GUIDE.md](SKILLS_GUIDE.md) 的"技能分类矩阵"
2. **避免陷阱**: 熟记"反模式"和"常见冲突场景"
3. **流程规范**: 掌握 [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) 所有章节
4. **实践应用**: 在实际项目中应用完整工作流

---

## 🔄 文档更新记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.1 | 2026-07-06 | 新增报告管理规范（强制执行） |
| v1.0 | 2026-07-06 | 初始版本，创建两个核心指南 |

---

## 💡 使用建议

### 日常开发

**每次开始任务前**:
1. 查看 [SKILLS_GUIDE.md](SKILLS_GUIDE.md) 决策树确定技能
2. 按照流程技能 → 实现技能 → 验证技能的顺序工作

**完成任务后**:
1. 使用 [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) 生成报告
2. 按照归档规则整理文档

### 版本发布

1. 参考 [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) 的"GitHub发布流程"
2. 使用发布检查清单确保完整性
3. 按照文档分类规则准备公开文档

---

## 🆘 常见问题

**Q: 这两个文档有什么区别？**

A: 
- **SKILLS_GUIDE.md**: 专注于**技能本身** - 如何选择、何时使用、如何避免冲突
- **WORKFLOW_GUIDE.md**: 专注于**完整流程** - 从开发到发布的端到端过程

**Q: 应该先看哪个？**

A: 
- 如果你不确定用什么技能 → 先看 [SKILLS_GUIDE.md](SKILLS_GUIDE.md)
- 如果你需要了解完整流程 → 先看 [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md)

**Q: 这些指南会更新吗？**

A: 是的，当发现新的技能冲突、工作流优化或用户反馈时会更新。

---

## 📞 快速帮助

遇到问题？使用决策树：

```
我的问题是...
    │
    ├─ 关于技能选择/冲突？
    │   └─ 查看 SKILLS_GUIDE.md
    │
    ├─ 关于报告/归档/发布？
    │   └─ 查看 WORKFLOW_GUIDE.md
    │
    └─ 不确定问题类型？
        └─ 查看本索引的"按问题类型查找"表格
```

---

**维护者**: Claude Code  
**最后更新**: 2026-07-06
