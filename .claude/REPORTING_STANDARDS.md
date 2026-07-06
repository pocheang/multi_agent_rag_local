# 报告管理规范

> **创建日期**: 2026-07-06  
> **目的**: 统一报告格式，避免混乱，确保完整性  
> **状态**: 强制执行

---

## 🎯 核心原则

### 三大统一标准

1. **格式统一** - 所有报告必须使用指定模板
2. **位置统一** - 所有报告必须保存到正确目录
3. **流程统一** - 所有报告必须经过检查清单验证

---

## 📋 报告类型矩阵

### 强制报告（必须生成）

| 报告类型 | 何时生成 | 模板位置 | 保存位置 | 负责技能 |
|---------|---------|---------|---------|---------|
| **交接报告** | 任务完成/会话结束/交接时 | 内置格式 | `docs/archive/completion-reports/` | `reporting-handoff` |
| **版本完成报告** | 每个版本发布后 | `docs/templates/VERSION_COMPLETION_REPORT_TEMPLATE.md` | `docs/releases/` + `docs/archive/completion-reports/` | 手动 |
| **日志记录** | 每次重要决策/变更 | 无（追加到文件） | `docs/archive/decisions/` | 手动 |

### 可选报告（按需生成）

| 报告类型 | 何时生成 | 模板位置 | 保存位置 |
|---------|---------|---------|---------|
| **修复报告** | Patch版本发布时 | `docs/templates/FIXES_REPORT_TEMPLATE.md` | `docs/archive/fixes/` |
| **重构报告** | 架构重构完成时 | `docs/templates/REFACTORING_REPORT_TEMPLATE.md` | `docs/archive/refactoring/` |
| **性能报告** | 性能优化完成时 | 自定义 | `docs/archive/performance/` |
| **安全报告** | 安全审计完成时 | 自定义 | `docs/archive/security/` |

---

## 📝 统一报告模板

### 模板 1: 交接报告（强制）

**文件名格式**: `YYYY-MM-DD-task-name-handoff.md`

```markdown
# 交接报告 - [任务名称]

**日期**: YYYY-MM-DD  
**交接人**: [你的名字/AI]  
**接收人**: [接收人/团队/下一个会话]  
**任务ID**: [如有] #123  
**相关PR**: [如有] #456

---

## 📊 执行摘要

**任务目标**: [一句话描述任务]  
**完成状态**: ✅ 完成 / ⚠️ 部分完成 / ❌ 未完成  
**完成度**: XX%  
**耗时**: X小时/天

---

## ✅ 已完成任务

### 主要任务
- [x] 任务1 - 详细描述
  - 文件: `path/to/file.py`
  - 变更: 添加了X功能
  - 测试: ✅ 通过
  
- [x] 任务2 - 详细描述
  - 文件: `path/to/file.ts`
  - 变更: 修复了Y bug
  - 测试: ✅ 通过

### 次要任务
- [x] 文档更新
- [x] 测试编写
- [x] 代码审查

---

## 📋 待办事项

### 高优先级 (P0)
- [ ] **任务A** - 描述及原因
  - 预计时间: X小时
  - 依赖: 无/其他任务
  - 风险: 高/中/低

### 中优先级 (P1)
- [ ] **任务B** - 描述

### 低优先级 (P2)
- [ ] **任务C** - 描述

### 建议改进 (P3)
- [ ] 改进点1
- [ ] 改进点2

---

## 💡 技术决策

### 决策 1: [决策标题]
**问题**: 描述需要决策的问题  
**选项**:
- 选项A: 优点/缺点
- 选项B: 优点/缺点

**决定**: 选择了X  
**理由**: 详细解释为什么选择X  
**影响**: 对系统的影响  
**风险**: 潜在风险及缓解措施

### 决策 2: [决策标题]
[同上格式]

---

## 📁 文件变更清单

### 新增文件
- `path/to/new-file1.py` - 功能描述
- `path/to/new-file2.ts` - 功能描述

### 修改文件
- `path/to/modified-file1.py`
  - 变更: 添加了X方法
  - 行数: +50/-10
  - 影响: Y功能
  
- `path/to/modified-file2.ts`
  - 变更: 重构了Z组件
  - 行数: +30/-80
  - 影响: 性能提升20%

### 删除文件
- `path/to/deprecated-file.py` - 删除原因

---

## ⚠️ 已知问题

### 问题 1: [问题标题]
**描述**: 详细描述问题  
**影响**: 影响范围和严重程度  
**临时解决方案**: 当前的workaround  
**永久解决方案**: 计划的修复方案  
**优先级**: P0/P1/P2

### 问题 2: [问题标题]
[同上格式]

---

## 🔧 配置变更

### 环境变量
- 新增: `NEW_VAR=value` - 用途说明
- 修改: `OLD_VAR=new_value` - 变更原因
- 删除: `DEPRECATED_VAR` - 删除原因

### 配置文件
- `config/app.json` - 变更内容
- `.env.example` - 新增示例

---

## 📊 测试覆盖

### 新增测试
- `tests/test_feature_x.py` - 覆盖X功能
  - 测试用例: 10个
  - 覆盖率: 95%

### 测试结果
- ✅ 单元测试: 50/50 通过
- ✅ 集成测试: 15/15 通过
- ⚠️ E2E测试: 8/10 通过（2个失败原因已知）

---

## 🎯 下一步建议

### 立即执行
1. **建议1** - 详细描述和理由
2. **建议2** - 详细描述和理由

### 短期计划（1-2周）
- 建议3
- 建议4

### 长期考虑（1个月+）
- 建议5
- 建议6

---

## 📚 相关文档

- [设计文档](path/to/design.md)
- [API文档](path/to/api.md)
- [测试报告](path/to/test-report.md)

---

## 📞 联系信息

**有问题？联系**:
- 技术问题: [邮箱/Slack]
- 产品问题: [邮箱/Slack]

---

**报告生成**: YYYY-MM-DD HH:MM  
**最后更新**: YYYY-MM-DD HH:MM
```

---

### 模板 2: 版本完成报告（强制）

**文件名格式**: `RELEASE_NOTES_v0.X.Y.md`

**位置**: 
- `docs/releases/RELEASE_NOTES_v0.X.Y.md` (当前)
- `docs/archive/completion-reports/YYYY-MM-DD-v0.X.Y-summary.md` (归档)

```markdown
# v0.X.Y Release Notes

**Release Date**: YYYY-MM-DD  
**Release Type**: [Feature/Fix/Architecture/Security]  
**Git Tag**: `v0.X.Y`  
**Commits**: XX commits since v0.X.Y-1

---

## 🎯 Release Highlights

### 1. [主要功能1] ✅
- **描述**: 简要说明
- **影响**: 用户收益
- **技术亮点**: 关键技术点

### 2. [主要功能2] ✅
[同上]

### 3. [主要功能3] ✅
[同上]

---

## 📊 Statistics

| Metric | Count |
|--------|-------|
| **Total Commits** | XX |
| **Files Changed** | XX |
| **Lines Added** | +XXX |
| **Lines Removed** | -XXX |
| **Contributors** | X |
| **Issues Closed** | X |

### Commit Breakdown

- **Features**: X commits
- **Bug Fixes**: X commits
- **Documentation**: X commits
- **Performance**: X commits
- **Tests**: X commits

---

## 📦 Deliverables

### Code
✅ `path/to/major-file1.py` - 功能描述  
✅ `path/to/major-file2.ts` - 功能描述  
✅ New API endpoints: `/api/v1/...`

### Documentation
✅ [User Guide](link)  
✅ [API Reference](link)  
✅ [Migration Guide](link) (如果有破坏性变更)

### Tests
✅ Unit tests: XX new tests  
✅ Integration tests: XX new tests  
✅ E2E tests: XX new tests  
✅ Coverage: XX% (+/- X%)

### Infrastructure
✅ Database migrations: `migration_XXX.sql`  
✅ Config updates: `.env.example`  
✅ CI/CD updates: `.github/workflows/`

---

## 🚀 Upgrade Path

### From v0.X.Y-1 to v0.X.Y

```bash
# 1. Backup (if needed)
cp .env .env.backup

# 2. Pull latest changes
git fetch origin
git checkout v0.X.Y

# 3. Update dependencies
# Backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install

# 4. Run migrations (if needed)
python scripts/migrate.py

# 5. Update config
# Review .env.example for new variables

# 6. Restart services
# [具体重启命令]
```

### Breaking Changes ⚠️

如果有破坏性变更，详细列出：

- **变更1**: 描述
  - **迁移步骤**: 详细步骤
  - **影响范围**: 谁会受影响
  
- **变更2**: 描述
  [同上]

---

## ✅ Success Criteria Met

### Functionality
- ✅ 所有计划功能已实现
- ✅ 所有测试通过
- ✅ 无已知P0/P1 bug

### Performance
- ✅ P95延迟 < XXms (baseline: XXms)
- ✅ 内存使用 < XXX MB
- ✅ 吞吐量 > XXX req/s

### Quality
- ✅ 代码覆盖率 > XX%
- ✅ 代码审查完成
- ✅ 安全扫描通过
- ✅ 文档完整

---

## 🐛 Known Issues

### P2 Issues (非阻塞)
- **Issue #XXX**: 描述
  - Workaround: 临时解决方案
  - Fix ETA: v0.X.Y+1

---

## 🙏 Contributors

感谢以下贡献者:
- @contributor1 - 贡献内容
- @contributor2 - 贡献内容

---

## 📚 Full Changelog

查看完整变更: [CHANGELOG.md](../CHANGELOG.md#0XY)

---

## 📞 Support

遇到问题？
- 📖 [Documentation](link)
- 💬 [GitHub Issues](link)
- 📧 [Email](email)

---

**Release Manager**: [名字]  
**Approved By**: [审批人]  
**Released**: YYYY-MM-DD
```

---

## 🔄 强制报告流程

### 流程 1: 任务完成必须生成交接报告

```mermaid
任务开始
    ↓
实现代码
    ↓
验证完成
    ↓
【强制】调用 reporting-handoff 技能
    ↓
生成交接报告
    ↓
【检查清单】验证报告完整性
    ↓
保存到正确位置
    ↓
任务结束
```

**检查清单（交接报告）**:
- [ ] 使用了统一模板
- [ ] 包含所有必填章节
- [ ] 文件变更清单完整
- [ ] 已知问题已列出
- [ ] 技术决策已记录
- [ ] 待办事项已明确
- [ ] 下一步建议清晰
- [ ] 文件名符合规范：`YYYY-MM-DD-task-name-handoff.md`
- [ ] 保存到正确位置：`docs/archive/completion-reports/`
- [ ] 在索引中添加条目

---

### 流程 2: 版本发布必须生成版本报告

```mermaid
准备发布
    ↓
【强制】复制版本完成报告模板
    ↓
填写所有章节
    ↓
【检查清单】验证报告完整性
    ↓
保存到 docs/releases/
    ↓
更新 CHANGELOG.md
    ↓
创建Git标签
    ↓
发布到GitHub
    ↓
【强制】归档报告副本到 docs/archive/completion-reports/
    ↓
发布完成
```

**检查清单（版本报告）**:
- [ ] 使用了 `VERSION_COMPLETION_REPORT_TEMPLATE.md`
- [ ] Release Highlights 包含3-5个要点
- [ ] Statistics 数据完整准确
- [ ] Deliverables 列出所有交付物
- [ ] Upgrade Path 提供详细步骤
- [ ] Breaking Changes 已明确标注（如有）
- [ ] Success Criteria 全部验证
- [ ] Known Issues 已列出（如有）
- [ ] 文件名符合规范：`RELEASE_NOTES_v0.X.Y.md`
- [ ] 同时保存到 `docs/releases/` 和 `docs/archive/completion-reports/`
- [ ] 更新了 `CHANGELOG.md`
- [ ] 创建了Git标签

---

## 📂 统一目录结构

```
docs/
├── releases/                                 # 当前发布说明（不归档）
│   ├── RELEASE_NOTES_v0.6.0.md
│   └── RELEASE_NOTES_v0.6.1.md
│
├── archive/                                  # 历史归档
│   ├── completion-reports/                   # 所有完成报告
│   │   ├── 2026-06-17-v0.4.4-release-summary.md
│   │   ├── 2026-07-06-feature-x-handoff.md
│   │   └── 2026-07-06-bugfix-y-handoff.md
│   │
│   ├── fixes/                               # 修复记录
│   │   ├── 2026-06-03-security-fixes.md
│   │   └── 2026-07-01-performance-fixes.md
│   │
│   ├── refactoring/                         # 重构报告
│   │   └── 2026-05-20-architecture-refactor.md
│   │
│   ├── decisions/                           # 技术决策日志
│   │   ├── 2026-06-01-use-postgresql.md
│   │   └── 2026-06-15-adopt-typescript.md
│   │
│   ├── performance/                         # 性能报告
│   │   └── 2026-06-20-query-optimization.md
│   │
│   ├── security/                            # 安全审计
│   │   └── 2026-07-01-security-audit.md
│   │
│   └── INDEX.md                             # 归档索引
│
└── templates/                                # 报告模板
    ├── VERSION_COMPLETION_REPORT_TEMPLATE.md
    ├── FIXES_REPORT_TEMPLATE.md
    ├── REFACTORING_REPORT_TEMPLATE.md
    └── README.md
```

---

## 📋 报告完整性检查清单

### 通用检查（所有报告）

- [ ] **格式规范**
  - [ ] 使用Markdown格式
  - [ ] 标题层级正确（H1 → H2 → H3）
  - [ ] 代码块使用正确语言标识
  - [ ] 链接有效

- [ ] **内容完整**
  - [ ] 所有必填章节已填写
  - [ ] 没有留下 `[TODO]` 或 `[待填写]`
  - [ ] 日期格式统一：`YYYY-MM-DD`
  - [ ] 版本号格式统一：`v0.X.Y`

- [ ] **文件管理**
  - [ ] 文件名符合规范
  - [ ] 保存到正确目录
  - [ ] 索引已更新
  - [ ] Git提交消息清晰

### 交接报告特定检查

- [ ] **任务信息**
  - [ ] 任务目标明确
  - [ ] 完成状态准确
  - [ ] 完成度估计合理

- [ ] **技术决策**
  - [ ] 列出所有重要决策
  - [ ] 说明选择理由
  - [ ] 记录替代方案

- [ ] **文件变更**
  - [ ] 列出所有修改文件
  - [ ] 说明变更内容
  - [ ] 标注影响范围

- [ ] **待办事项**
  - [ ] 按优先级分类
  - [ ] 预估时间
  - [ ] 说明依赖关系

### 版本报告特定检查

- [ ] **统计数据**
  - [ ] Commit数量准确
  - [ ] 文件变更统计正确
  - [ ] 测试覆盖率数据真实

- [ ] **升级路径**
  - [ ] 步骤完整可执行
  - [ ] Breaking Changes 明确
  - [ ] 迁移脚本已测试

- [ ] **发布物**
  - [ ] 所有交付物已列出
  - [ ] 文档链接有效
  - [ ] 测试结果真实

---

## 🤖 自动化规则

### 规则 1: 技能必须生成报告

**触发条件**:
- 调用 `superpowers:finishing-a-development-branch`
- 调用 `reporting-handoff`
- 版本发布流程

**强制动作**:
1. 检查是否已有报告
2. 如果没有，强制生成
3. 验证报告完整性
4. 保存到正确位置

### 规则 2: 报告必须验证

**验证内容**:
- 使用了正确模板
- 所有必填章节已填写
- 文件名符合规范
- 保存位置正确
- 索引已更新

**验证失败处理**:
- 显示错误信息
- 列出缺失内容
- 要求补全后重试

### 规则 3: 定期归档检查

**频率**: 每周

**检查内容**:
- `docs/releases/` 中超过30天的报告
- 未归档的完成报告
- 索引更新情况

**自动动作**:
- 移动旧报告到 `archive/`
- 更新索引
- 生成归档报告

---

## 📊 报告质量标准

### 优秀报告标准

✅ **完整性** - 所有章节填写完整，无遗漏  
✅ **准确性** - 数据真实，信息准确  
✅ **清晰性** - 表达清楚，易于理解  
✅ **可操作** - 待办事项明确，步骤可执行  
✅ **可追溯** - 链接完整，便于查找  
✅ **及时性** - 任务完成后立即生成

### 不合格报告示例

❌ 缺少关键章节  
❌ 技术决策没有说明理由  
❌ 文件变更清单不完整  
❌ 待办事项没有优先级  
❌ 已知问题没有临时解决方案  
❌ 下一步建议不具体

---

## 🎯 实施步骤

### 第一阶段：立即执行（今天）

1. **创建目录结构**
```bash
mkdir -p docs/archive/{completion-reports,fixes,refactoring,decisions,performance,security}
touch docs/archive/INDEX.md
```

2. **整理现有报告**
```bash
# 移动所有完成报告到统一位置
mv docs/superpowers/plans/*-summary.md docs/archive/completion-reports/
mv docs/archive/summaries/*.md docs/archive/completion-reports/
```

3. **创建索引**
```bash
# 生成索引文件
ls -1 docs/archive/completion-reports/ > docs/archive/INDEX.md
```

### 第二阶段：规范化（本周）

1. **检查所有现有报告**
   - 使用完整性检查清单验证
   - 补全缺失章节
   - 统一格式

2. **更新模板**
   - 确保所有模板在 `docs/templates/`
   - 添加使用说明
   - 创建示例

### 第三阶段：自动化（下周）

1. **创建报告生成脚本**
2. **添加验证脚本**
3. **设置定期归档任务**

---

## 📞 强制执行

### 从现在开始

**所有任务完成后必须**:
1. 调用 `reporting-handoff` 技能
2. 使用统一交接报告模板
3. 通过完整性检查清单
4. 保存到正确位置
5. 更新索引

**所有版本发布前必须**:
1. 使用版本完成报告模板
2. 通过完整性检查清单
3. 保存到两个位置（releases + archive）
4. 更新 CHANGELOG.md
5. 创建Git标签

**违反规则的后果**:
- ⚠️ 报告被拒绝
- ⚠️ 任务状态设为"未完成"
- ⚠️ 版本发布被阻止

---

**此规范从 2026-07-06 起强制执行，无例外。**
