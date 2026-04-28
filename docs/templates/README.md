# 文档模板索引 / Documentation Templates Index

**最后更新**: 2026-04-28  
**维护者**: Bronit Team

---

## 📋 概述

本目录包含项目版本发布时使用的标准文档模板。使用这些模板可以确保文档的一致性和完整性。

---

## 📝 可用模板

### 1. 版本完成报告模板
**文件**: [VERSION_COMPLETION_REPORT_TEMPLATE.md](VERSION_COMPLETION_REPORT_TEMPLATE.md)  
**用途**: 每个版本发布时创建版本完成报告  
**适用**: 所有版本类型

**使用方法**:
```bash
# 复制模板
cp docs/templates/VERSION_COMPLETION_REPORT_TEMPLATE.md V0.3.2_COMPLETION_REPORT.md

# 替换占位符
sed -i 's/{VERSION}/0.3.2/g' V0.3.2_COMPLETION_REPORT.md
sed -i 's/YYYY-MM-DD/2026-04-28/g' V0.3.2_COMPLETION_REPORT.md

# 编辑并填写内容
```

---

### 2. 架构重构报告模板
**文件**: [REFACTORING_REPORT_TEMPLATE.md](REFACTORING_REPORT_TEMPLATE.md)  
**用途**: 架构版本发布时创建重构报告  
**适用**: 架构版本（Architecture Release）

**使用方法**:
```bash
# 复制模板
cp docs/templates/REFACTORING_REPORT_TEMPLATE.md docs/archive/V0.3.2_REFACTORING.md

# 替换占位符并编辑
```

**包含章节**:
- 重构目标和背景
- 重构前后架构对比
- 模块划分和依赖关系
- 重构过程和成果
- 性能改进数据
- 迁移指南

---

### 3. 功能设计文档模板
**文件**: [FEATURE_DESIGN_TEMPLATE.md](FEATURE_DESIGN_TEMPLATE.md)  
**用途**: 功能版本发布前创建设计文档  
**适用**: 功能版本（Feature Release）

**使用方法**:
```bash
# 复制模板
cp docs/templates/FEATURE_DESIGN_TEMPLATE.md docs/design/specs/2026-04-28-new-feature-design.md

# 编辑并填写设计内容
```

**包含章节**:
- 功能背景和目标
- 需求分析（功能需求和非功能需求）
- 技术设计（架构、组件、数据模型）
- API 设计
- 实现计划
- 测试策略
- 性能和安全考虑

---

### 4. 修复总结报告模板
**文件**: [FIXES_REPORT_TEMPLATE.md](FIXES_REPORT_TEMPLATE.md)  
**用途**: 修复版本发布时创建修复报告  
**适用**: 修复版本（Patch Release）

**使用方法**:
```bash
# 复制模板
cp docs/templates/FIXES_REPORT_TEMPLATE.md docs/archive/V0.3.2_FIXES.md

# 替换占位符并编辑
```

**包含章节**:
- 修复统计（按优先级和类型）
- 详细修复说明（P0/P1/P2/P3）
- 性能改进数据
- 测试结果
- 向后兼容性分析
- 根本原因分析

---

## 🔧 模板使用指南

### 基本步骤

1. **选择合适的模板**
   - 根据版本类型选择对应的模板
   - 每个版本至少需要版本完成报告模板

2. **复制模板**
   - 复制到正确的位置
   - 使用规范的命名格式

3. **替换占位符**
   - `{VERSION}` → 实际版本号（如 0.3.2）
   - `YYYY-MM-DD` → 实际日期
   - `[占位符]` → 实际内容

4. **填写内容**
   - 按照模板章节逐一填写
   - 删除不适用的章节
   - 保持格式一致

5. **审查和验证**
   - 使用检查清单验证完整性
   - 确保所有必需章节已填写
   - 验证数据准确性

---

## 📊 模板对应关系

| 版本类型 | 必需模板 | 可选模板 |
|---------|---------|---------|
| 🎉 首次发布 | 版本完成报告 | - |
| ⚡ 功能版本 | 版本完成报告 | 功能设计文档 |
| 🔧 修复版本 | 版本完成报告 | 修复总结报告 |
| 🏗️ 架构版本 | 版本完成报告 | 架构重构报告 |
| 📚 文档版本 | 版本完成报告 | - |
| 🔒 安全版本 | 版本完成报告 | 修复总结报告 |

---

## 🎯 模板最佳实践

### 内容填写
1. **准确性**: 确保所有数据和信息准确
2. **完整性**: 填写所有必需章节
3. **清晰性**: 使用清晰简洁的语言
4. **具体性**: 提供具体的数据和示例

### 格式规范
1. **标题层级**: 使用标准的 Markdown 标题层级
2. **代码块**: 使用正确的语言标识
3. **表格**: 保持表格格式整齐
4. **列表**: 使用一致的列表格式

### 版本控制
1. **及时提交**: 完成后及时提交到 Git
2. **清晰消息**: 使用清晰的提交消息
3. **标签关联**: 与版本标签关联

---

## 🔄 模板维护

### 更新频率
- **定期审查**: 每季度审查模板
- **反馈驱动**: 根据使用反馈更新
- **版本同步**: 与项目版本保持同步

### 改进建议
如果您有模板改进建议：
1. 在 GitHub 上创建 Issue
2. 描述改进建议和理由
3. 提供示例（如适用）
4. 提交 Pull Request

---

## 📚 相关文档

- [VERSION_DOCUMENTATION_STANDARD.md](../VERSION_DOCUMENTATION_STANDARD.md) - 版本文档标准
- [VERSION_DOCUMENTATION_GUIDE.md](../VERSION_DOCUMENTATION_GUIDE.md) - 版本文档管理指南
- [VERSION_DOCUMENTATION_CHECKLIST.md](../VERSION_DOCUMENTATION_CHECKLIST.md) - 版本文档检查清单

---

## 📝 模板历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| v1.0 | 2026-04-28 | 初始版本，创建4个标准模板 |

---

**维护者**: Bronit Team  
**最后更新**: 2026-04-28
