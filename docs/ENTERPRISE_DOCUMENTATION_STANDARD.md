# 企业级文档组织标准

**版本**: 1.0  
**生效日期**: 2026-04-27  
**维护者**: Bronit Team

## 文档分类体系

### 1. 核心运营文档 (Core Operations)
位置: 项目根目录 + `docs/`

**必须保持最新的文档**：
- `README.md` - 产品概览和快速开始
- `CHANGELOG.md` - 版本历史和发布说明
- `CLAUDE.md` - 开发指南和架构
- `docs/README.md` - 文档导航中心
- `docs/production_readiness_checklist.md` - 生产部署检查清单
- `docs/DOCUMENTATION_STANDARD.md` - 文档标准和规范
- `docs/DOCUMENTATION_MAINTENANCE.md` - 文档维护流程
- `docs/API_SETTINGS_GUIDE.md` - API 和配置指南
- `docs/PERFORMANCE_OPTIMIZATION.md` - 性能优化指南
- `docs/runtime_speed_profiles.md` - 运行时速度配置

### 2. 历史文档 (Historical Records)
位置: `docs/archive/`

**用途**: 审计、追溯、里程碑记录  
**更新规则**: 不更新，仅保留原始记录  
**访问频率**: 低（仅在需要历史背景时）

**包含内容**:
- 版本发布记录 (Release notes)
- 重构完成报告 (Refactoring reports)
- 修复日志 (Fix logs)
- 深度审查报告 (Code review reports)
- 阶段性完成报告 (Phase completion reports)

### 3. 项目文档 (Project Documentation)
位置: `docs/project/`

**用途**: 项目特定的指南和规范  
**更新规则**: 按需更新，保持与代码同步  
**访问频率**: 中等（开发和运维参考）

**包含内容**:
- 架构设计文档
- 模块说明文档
- 集成指南
- 故障排查指南
- 最佳实践

### 4. 设计文档 (Design Specifications)
位置: `docs/design/`

**用途**: 功能设计和技术规范  
**更新规则**: 功能完成后冻结，新功能创建新文档  
**访问频率**: 中等（设计参考和验证）

**包含内容**:
- 功能设计规范
- UX 设计文档
- 技术规范
- API 设计文档

### 5. 运维文档 (Operations)
位置: `docs/operations/`

**用途**: 部署、监控、故障处理  
**更新规则**: 按需更新，保持最新  
**访问频率**: 高（日常运维）

**包含内容**:
- 部署指南
- 监控和告警配置
- 故障排查手册
- 备份和恢复流程
- 性能调优指南

### 6. 开发文档 (Development)
位置: `docs/development/`

**用途**: 开发工作流和贡献指南  
**更新规则**: 按需更新  
**访问频率**: 中等（新开发者和贡献者）

**包含内容**:
- 开发环境设置
- 代码贡献指南
- 测试指南
- 构建和发布流程
- 依赖管理

## 文档生命周期

### 创建阶段
1. 确定文档类型和位置
2. 遵循文档标准格式
3. 添加元数据（版本、日期、作者）
4. 在相关索引中注册

### 维护阶段
1. 定期审查（根据类型）
2. 与代码变更同步更新
3. 记录更新历史
4. 保持链接有效性

### 归档阶段
1. 标记为历史文档
2. 移至 `docs/archive/`
3. 保留原始内容不修改
4. 更新索引和交叉引用

### 删除阶段
1. 确认文档已过时且无审计价值
2. 获得团队确认
3. 删除前备份
4. 更新所有引用

## 文档命名规范

### 核心文档
- `README.md` - 项目入口
- `CHANGELOG.md` - 版本历史
- `CLAUDE.md` - 开发指南

### 功能文档
- `{feature}_guide.md` - 功能指南
- `{feature}_design.md` - 功能设计
- `{feature}_troubleshooting.md` - 故障排查

### 历史文档
- `{date}_{description}.md` - 带日期的历史记录
- `v{version}_{description}.md` - 版本相关的历史记录

### 避免的命名
- ❌ 临时文件名 (temp, tmp, test)
- ❌ 个人名字 (john_notes, mary_findings)
- ❌ 模糊的名字 (stuff, things, misc)
- ❌ 重复的名字 (summary, summary2, summary_final)

## 文档质量标准

### 必须包含
- [ ] 清晰的标题和目的
- [ ] 最后更新日期
- [ ] 适用的版本范围
- [ ] 目标受众
- [ ] 目录（如果超过 5 个部分）

### 应该包含
- [ ] 快速参考/TL;DR
- [ ] 示例或代码片段
- [ ] 常见问题解答
- [ ] 相关文档链接
- [ ] 维护者或所有者

### 避免
- ❌ 过时的信息
- ❌ 重复的内容
- ❌ 个人观点
- ❌ 未验证的声明
- ❌ 死链接

## 文档索引和导航

### 主索引
- `README.md` - 项目入口
- `docs/README.md` - 文档导航中心
- `docs/ARCHIVE_REFERENCE.md` - 历史文档索引
- `ROOT_ARCHIVE_REFERENCE.md` - 根目录文档索引

### 分类索引
- `docs/project/INDEX.md` - 项目文档索引
- `docs/design/INDEX.md` - 设计文档索引
- `docs/operations/INDEX.md` - 运维文档索引
- `docs/development/INDEX.md` - 开发文档索引

## 审查和更新计划

### 每周
- 检查新增文档是否遵循标准
- 验证链接有效性

### 每月
- 审查核心文档的准确性
- 更新版本相关的文档

### 每季度
- 全面审查所有活跃文档
- 识别需要归档的文档
- 更新文档索引

### 每年
- 完整的文档审计
- 清理过时的历史文档
- 更新文档标准

## 工具和流程

### 文档验证
```bash
# 检查 Markdown 语法
markdownlint docs/**/*.md

# 检查链接有效性
markdown-link-check docs/**/*.md

# 检查拼写
aspell check docs/**/*.md
```

### 文档生成
- 从代码注释生成 API 文档
- 从 CHANGELOG 生成发布说明
- 从设计文档生成实现清单

## 常见问题

**Q: 我应该在哪里放置新文档？**  
A: 根据文档类型选择相应的目录。如果不确定，先放在 `docs/project/`，然后在审查时重新分类。

**Q: 历史文档可以删除吗？**  
A: 一般不删除。如果确实需要删除，必须获得团队确认，并确保没有审计价值。

**Q: 如何处理过时的文档？**  
A: 标记为"已过时"，移至 `docs/archive/`，更新所有引用。

**Q: 文档应该多久更新一次？**  
A: 核心文档应与代码变更同步。其他文档根据类型定期审查。

---

**维护者**: Bronit Team  
**最后更新**: 2026-04-28  
**版本**: 1.0
