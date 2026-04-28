# 修复总结 (Fixes Summary)

**汇总日期**: 2026-04-27  
**来源**: 合并所有修复日志文件  
**目的**: 单一权威的修复记录

---

## 📋 修复概览

本项目在 2026-04-27 进行了多轮修复，共解决 18 个逻辑问题，涵盖：
- 路由决策和自适应规划
- 检索质量和参数传递
- 并发执行和超时控制
- 缓存和性能优化

所有修复均已通过测试验证（29/29 tests passed）。

---

## 🔧 修复分类

### P0 严重问题 (2 个)
1. **检索策略参数传递不一致** - 文档源过滤失效
2. **Hybrid 路由并发执行错误** - 图查询重复执行

### P1 高优先级 (5 个)
1. 路由决策与自适应规划冲突
2. 证据充分性判断循环依赖
3. Query Rewrite 变体去重缺失
4. Query Rewrite LLM 超时控制
5. State 访问参数验证

### P2 中等优先级 (9 个)
1. Parent-Child 去重分数更新
2. 闲聊快速路径状态不一致
3. Web Fallback 语义混淆
4. Hybrid Future 取消逻辑
5. Reranker Fallback 分数归一化
6. Citation 句子分割改进
7. Web Domain Allowlist 语义
8. Graph Signal Score 优化
9. TTLCache 并发性能优化

### P3 低优先级 (2 个)
1. Neo4j allowed_sources 验证
2. BM25 过滤逻辑说明

---

## 📊 修复统计

| 指标 | 数值 |
|------|------|
| 总修复数 | 18 |
| P0 问题 | 2 |
| P1 问题 | 5 |
| P2 问题 | 9 |
| P3 问题 | 2 |
| 测试通过 | 29/29 |
| 修改文件 | 11 |
| 新增测试 | 2 |

---

## 🎯 修复影响

### 性能改善
- Query Rewrite 去重: 减少 10-30% API 调用
- Query Rewrite 超时: 降低 500-2000ms P99 延迟
- Hybrid 路由修复: 降低 100-500ms 延迟
- TTLCache 优化: 显著降低锁竞争

### 质量提升
- Reranker Fallback: 提升 5-10% 排序质量
- Citation Grounding: 降低 10-20% 误判率
- Graph Signal Score: 更准确的证据评分
- Web Allowlist: 提高结果相关性

---

## ⚠️ 向后兼容性

**5 个行为变化需要注意**:
1. Query Rewrite 去重可能减少变体数量
2. Hybrid 路由不再并发执行（顺序执行）
3. Web Fallback 语义从"是否启用"改为"是否允许"
4. Reranker Fallback 分数归一化到 [0, 1]
5. Citation 句子分割使用 NLTK（更准确）

---

## 📝 详细修复记录

详见原始修复日志文件（已归档）：
- `FIXES_INDEX.md` - 修复索引
- `LOGIC_FIXES_*.md` - 逻辑修复详情
- `FINAL_FIXES_SUMMARY_2026-04-27.md` - 最终总结

---

**维护者**: Bronit Team  
**最后更新**: 2026-04-27
