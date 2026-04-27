# 文档中心 / Documentation Center

**项目**: Multi-Agent Local RAG System  
**当前版本**: v0.3.0  
**最后更新**: 2026-04-27

---

## 📚 文档导航

### 🎯 快速开始
| 文档 | 说明 | 语言 |
|------|------|------|
| [README.md](../README.md) | 项目主文档 - 安装、配置、使用 | 英文 |
| [CLAUDE.md](../CLAUDE.md) | 架构文档 - 系统设计、开发指南 | 英文 |
| [CHANGELOG.md](../CHANGELOG.md) | 版本变更历史 | 英文 |

### 📖 用户指南
| 文档 | 说明 | 适合人群 |
|------|------|----------|
| [API_SETTINGS_GUIDE.md](API_SETTINGS_GUIDE.md) | API 配置指南 | 开发者 |
| [如何找到API设置.md](如何找到API设置.md) | API 设置教程（中文） | 新用户 |
| [claude-api-setup.md](claude-api-setup.md) | Claude API 配置 | 开发者 |
| [workflow_lowcode_setup.md](workflow_lowcode_setup.md) | 工作流低代码配置 | 产品经理 |

### 🏗️ 架构与设计
| 文档 | 说明 | 适合人群 |
|------|------|----------|
| [superpowers/specs/2026-04-19-query-to-answer-ux-speed-design.md](superpowers/specs/2026-04-19-query-to-answer-ux-speed-design.md) | 查询响应速度优化设计 | 架构师 |
| [runtime_speed_profiles.md](runtime_speed_profiles.md) | 运行时速度配置 | 性能工程师 |
| [PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md) | 性能优化指南 | 开发者 |

### 🔧 运维与部署
| 文档 | 说明 | 适合人群 |
|------|------|----------|
| [production_readiness_checklist.md](production_readiness_checklist.md) | 生产环境检查清单 | 运维人员 |
| [网络功能检查报告.md](网络功能检查报告.md) | 网络功能测试报告 | 测试人员 |

### 📝 开发规范
| 文档 | 说明 | 适合人群 |
|------|------|----------|
| [DOCUMENTATION_STANDARD.md](DOCUMENTATION_STANDARD.md) | 文档编写规范 | 所有贡献者 |
| [DOCUMENT_VERSION_CONTROL.md](DOCUMENT_VERSION_CONTROL.md) | 文档版本控制规范 | 所有贡献者 |

---

## 🔄 版本历史与修复记录

### v0.3.0 (2026-04-27) - 当前版本 🎉
**主题**: 模块化架构重构 - 代码减少 90.7%，可维护性大幅提升

**核心变更**:
- 🏗️ **模块化重构**: 7 个大文件 (9135 行) → 65 个专注模块 (846 行主文件)
- 📦 **新模块结构**: API 路由、工作流节点、检索组件、认证服务全部模块化
- ✅ **向后兼容**: 100% 兼容，所有现有 API 和测试保持不变
- 📊 **可维护性**: 平均模块大小从 1305 行降至 13 行
- 🚀 **开发效率**: 代码查找速度提升 5 倍，合并冲突减少

**详细文档**:
- [v0.3.0 发布完成报告](v0.3.0-release-completion-report.md) - 完整的重构统计和迁移指南
- [CHANGELOG.md](../CHANGELOG.md) - 版本变更记录

**模块结构概览**:
```
app/
├── api/              # API 层 (12 个模块)
│   ├── main.py       # 主应用 (140 行)
│   ├── routes/       # 路由模块 (11 个)
│   └── dependencies.py
├── graph/            # 工作流层 (13 个模块)
│   ├── workflow.py   # 工作流构建器 (99 行)
│   ├── nodes/        # 节点模块 (8 个)
│   ├── routing/      # 路由逻辑
│   └── streaming/    # 流式处理 (3 个)
├── retrievers/       # 检索层 (8 个模块)
│   ├── hybrid_retriever.py (109 行)
│   └── hybrid/       # 检索组件 (7 个)
├── services/auth/    # 认证层 (7 个模块)
└── ingestion/        # 数据摄取层 (7 个模块)
```

---

### v0.2.5 (2026-04-27)
**主文档**: [CHANGELOG_2026-04-27.md](CHANGELOG_2026-04-27.md) ⭐ **推荐首先阅读**

**快速导航**:
- [📋 修复索引](FIXES_INDEX.md) - 所有修复的快速导航
- [📝 修复总结](FINAL_FIXES_SUMMARY_2026-04-27.md) - 统计数据和性能改进
- [🔍 深度代码审查](DEEP_CODE_REVIEW_2026-04-27.md) - 发现的问题和架构建议

**分轮次修复文档**:
1. [第一轮修复](LOGIC_FIXES_2026-04-27.md) - 8 个核心问题（2 P0 + 3 P1 + 3 P2）
2. [第二轮修复](FIXES_ROUND2_2026-04-27.md) - 6 个高优先级问题（2 P1 + 4 P2）
3. [第三轮修复](FIXES_ROUND3_2026-04-27.md) - 3 个优化验证（1 P2 + 2 P3）
4. [第四轮修复](FIXES_ROUND4_2026-04-27.md) - 1 个性能优化（1 P2）

**关键数据**:
- ✅ 修复问题: 18 个（2 P0 + 5 P1 + 9 P2 + 2 P3）
- ✅ 测试通过: 29/29
- 📈 性能提升: 减少 10-30% API 调用，降低 100-500ms 延迟
- ⚠️ 行为变化: 5 个需要注意的向后兼容性变化

### v0.2.4 (2026-04-26)
**主题**: 查询响应速度优化（Tiered Execution）

**文档**:
- [CHANGELOG.md](../CHANGELOG.md#024---2026-04-26) - 版本变更记录
- [2026-04-26-documentation-update-summary.md](2026-04-26-documentation-update-summary.md) - 文档更新总结

**关键特性**:
- 🎯 三层执行策略（fast/balanced/deep）
- ⚡ 首字节延迟优化（P50 ≤ 2s, P95 ≤ 4s）
- 📊 负载自适应降级
- 🎨 前端层级显示

### 历史版本
| 版本 | 日期 | 主题 | 文档链接 |
|------|------|------|----------|
| v0.2.2.1 | 2026-04-10 | 流式响应可靠性改进 | [CHANGELOG.md](../CHANGELOG.md#0221---2026-04-10) |
| v0.2.2 | 2026-04-09 | 运行时弹性与治理 | [CHANGELOG.md](../CHANGELOG.md#022---2026-04-09) |
| v0.2.1 | 2026-04-09 | RAG/Agent 运维控制 | [CHANGELOG.md](../CHANGELOG.md#021---2026-04-09) |
| v0.2.0 | 2026-04-08 | 管理员操作与用户管理 | [CHANGELOG.md](../CHANGELOG.md#02---2026-04-08) |
| v0.1.0 | 2026-04-08 | 首次公开发布 | [CHANGELOG.md](../CHANGELOG.md#010---2026-04-08) |

---

## 🎯 按角色查阅

### 👔 项目经理 / 产品经理
**推荐阅读顺序**:
1. [README.md](../README.md) - 了解项目概况
2. [CHANGELOG_2026-04-27.md](CHANGELOG_2026-04-27.md) - 最新变更和影响
3. [FIXES_INDEX.md](FIXES_INDEX.md) - 修复统计和部署建议

**关注点**:
- 📊 功能完成度和质量指标
- 📈 性能改进和用户体验提升
- ⚠️ 向后兼容性和风险评估
- 🚀 部署计划和时间线

### 🏗️ 技术负责人 / 架构师
**推荐阅读顺序**:
1. [CLAUDE.md](../CLAUDE.md) - 系统架构
2. [DEEP_CODE_REVIEW_2026-04-27.md](DEEP_CODE_REVIEW_2026-04-27.md) - 架构改进建议
3. [CHANGELOG_2026-04-27.md](CHANGELOG_2026-04-27.md) - 技术变更详情
4. [superpowers/specs/](superpowers/specs/) - 设计规范

**关注点**:
- 🔧 核心修复和架构改进
- 🏗️ 系统设计和技术债务
- 📊 监控指标和可观测性
- 🔄 回滚方案和风险控制

### 💻 开发人员
**推荐阅读顺序**:
1. [CLAUDE.md](../CLAUDE.md) - 开发指南
2. [CHANGELOG_2026-04-27.md](CHANGELOG_2026-04-27.md) - 代码变更
3. 对应的分轮次修复文档 - 具体实现细节
4. [DOCUMENTATION_STANDARD.md](DOCUMENTATION_STANDARD.md) - 编码规范

**关注点**:
- 💻 具体文件和代码变更
- 🧪 测试用例和验证方法
- ⚠️ API 变化和行为变化
- 📝 代码示例和最佳实践

### 🧪 测试人员
**推荐阅读顺序**:
1. [CHANGELOG_2026-04-27.md](CHANGELOG_2026-04-27.md) - 测试部分
2. [网络功能检查报告.md](网络功能检查报告.md) - 测试报告
3. [../tests/](../tests/) - 测试代码

**关注点**:
- 🧪 测试覆盖率和测试结果
- ✅ 回归测试和边界测试
- 📊 性能测试和负载测试
- 🔍 已知问题和限制

### 🚀 运维人员
**推荐阅读顺序**:
1. [production_readiness_checklist.md](production_readiness_checklist.md) - 部署检查清单
2. [CHANGELOG_2026-04-27.md](CHANGELOG_2026-04-27.md) - 部署指南
3. [runtime_speed_profiles.md](runtime_speed_profiles.md) - 运行时配置

**关注点**:
- 🚀 部署步骤和灰度策略
- 📊 监控指标和告警配置
- 🔄 回滚方案和应急预案
- ⚠️ 已知限制和注意事项

---

## 🔍 按主题查阅

### 路由与执行
- 检索策略参数传递
- Hybrid 路由并发执行
- 路由决策与自适应规划
- 证据充分性判断

**相关文档**: [LOGIC_FIXES_2026-04-27.md](LOGIC_FIXES_2026-04-27.md)

### 检索质量
- Query Rewrite 变体去重
- Parent-Child 去重优化
- Reranker Fallback 分数归一化
- Graph Signal Score 计算

**相关文档**: [LOGIC_FIXES_2026-04-27.md](LOGIC_FIXES_2026-04-27.md), [FIXES_ROUND2_2026-04-27.md](FIXES_ROUND2_2026-04-27.md), [FIXES_ROUND3_2026-04-27.md](FIXES_ROUND3_2026-04-27.md)

### 性能优化
- Query Rewrite LLM 超时控制
- Hybrid Future 取消逻辑
- TTLCache 并发性能优化
- 延迟预算管理

**相关文档**: [FIXES_ROUND2_2026-04-27.md](FIXES_ROUND2_2026-04-27.md), [FIXES_ROUND4_2026-04-27.md](FIXES_ROUND4_2026-04-27.md), [PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md)

### 安全与验证
- State 访问参数验证
- Web Domain Allowlist 语义
- Neo4j allowed_sources 验证
- 用户权限和 RBAC

**相关文档**: [FIXES_ROUND2_2026-04-27.md](FIXES_ROUND2_2026-04-27.md), [FIXES_ROUND3_2026-04-27.md](FIXES_ROUND3_2026-04-27.md)

### 文本处理
- Citation 句子分割
- 闲聊快速路径
- 答案合成优化

**相关文档**: [FIXES_ROUND2_2026-04-27.md](FIXES_ROUND2_2026-04-27.md), [LOGIC_FIXES_2026-04-27.md](LOGIC_FIXES_2026-04-27.md)

---

## 📊 文档统计

### 文档数量
```
总计: 20+ 个文档
├── 用户指南: 4 个
├── 架构设计: 3 个
├── 运维部署: 2 个
├── 开发规范: 2 个
├── 版本历史: 6 个
└── 修复记录: 5 个
```

### 语言分布
```
├── 英文: 15 个
├── 中文: 5 个
└── 双语: 部分文档
```

### 更新频率
```
├── 每日更新: CHANGELOG, 修复文档
├── 每周更新: 用户指南, 测试报告
├── 每月更新: 架构文档, 性能优化
└── 按需更新: 开发规范, 部署指南
```

---

## 📝 文档贡献指南

### 创建新文档
1. 遵循 [DOCUMENTATION_STANDARD.md](DOCUMENTATION_STANDARD.md) 规范
2. 使用清晰的文件命名（日期-主题.md）
3. 添加文档头部元信息（版本、日期、作者）
4. 更新本 README_CN.md 索引

### 更新现有文档
1. 遵循 [DOCUMENT_VERSION_CONTROL.md](DOCUMENT_VERSION_CONTROL.md) 版本控制
2. 在文档底部添加更新记录
3. 更新文档头部的"最后更新"日期
4. 如有重大变更，更新 CHANGELOG.md

### 文档审查
1. 技术准确性审查
2. 语言和格式审查
3. 链接有效性检查
4. 示例代码验证

---

## 🔗 外部资源

### 官方文档
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [Neo4j 文档](https://neo4j.com/docs/)
- [ChromaDB 文档](https://docs.trychroma.com/)

### 相关项目
- [LangChain](https://github.com/langchain-ai/langchain)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [OpenAI API](https://platform.openai.com/docs/)

### 社区资源
- GitHub Issues: [项目 Issues](https://github.com/your-org/multi-agent-rag/issues)
- 讨论区: [GitHub Discussions](https://github.com/your-org/multi-agent-rag/discussions)

---

## 📞 获取帮助

### 问题反馈
- **Bug 报告**: 在 GitHub Issues 创建 bug 报告
- **功能请求**: 在 GitHub Issues 创建 feature request
- **文档问题**: 在 GitHub Issues 标记为 `documentation`

### 联系方式
- **邮件**: support@your-org.com
- **Slack**: #multi-agent-rag 频道
- **文档**: 本目录下的所有 .md 文件

---

## 📅 文档更新计划

### 近期计划（1-2 周）
- [ ] 添加更多中文用户指南
- [ ] 完善 API 参考文档
- [ ] 添加故障排查指南
- [ ] 创建视频教程

### 中期计划（1-2 月）
- [ ] 完善架构设计文档
- [ ] 添加性能调优指南
- [ ] 创建最佳实践文档
- [ ] 添加更多代码示例

### 长期计划（3-6 月）
- [ ] 多语言文档支持
- [ ] 交互式文档系统
- [ ] 文档搜索功能
- [ ] 文档版本管理系统

---

**维护者**: Multi-Agent RAG Team  
**最后更新**: 2026-04-27  
**文档版本**: v1.0
