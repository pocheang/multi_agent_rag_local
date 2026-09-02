# 日常工作日志 (Daily Work Logs)

## 核心原则：单一真实来源 (Single Source of Truth)

⚠️ **重要**: 每天的工作记录**只能存在于一个地方** - 对应日期的文件夹中。

完成当天工作并整理文档后，**必须删除其他地方的临时记录**，避免：
- ❌ 文档重复（app/docs/、frontend/、根目录等）
- ❌ 信息不一致（多处修改难以同步）
- ❌ 查找困难（不知道哪个版本是最新的）

✅ **正确做法**: 
1. 工作中可以在任何地方写临时笔记
2. 晚上统一整理到 `daily-logs/YYYY-MM-DD/`
3. **删除所有其他地方的临时文档**
4. 保持项目整洁

## 目录结构

每个日期文件夹包含当天完成的所有计划和文档：

```
daily-logs/
├── 2026-08-16/
│   ├── plan.md                              # 工作计划
│   ├── implementation.md                    # 实现记录
│   ├── decisions.md                         # 技术决策
│   ├── summary.md                           # 完成总结
│   ├── BACKEND_SESSION_MANAGEMENT.md        # 详细技术文档（如有）
│   └── COMPLETE_IMPLEMENTATION_SUMMARY.md   # 完整总结（如有）
├── 2026-08-17/
│   ├── plan.md
│   ├── implementation.md
│   ├── decisions.md
│   └── summary.md
└── ...
```

## 文件说明

### 必需文件

#### plan.md - 工作计划
- 记录当天要完成的任务
- 包含优先级和时间估算
- 列出依赖关系

#### implementation.md - 实现记录
- 详细记录代码修改
- 包含关键代码片段
- 记录遇到的问题和解决方案

#### decisions.md - 技术决策
- 记录重要的技术选型
- 说明决策理由和权衡
- 参考架构决策记录 (ADR) 格式

#### summary.md - 完成总结
- 总结当天完成的工作
- 列出未完成的任务
- 记录经验教训

### 可选文件

根据实际需要，可以添加：
- 详细的技术实现文档（如 BACKEND_*.md）
- 设计文档（如 DESIGN_*.md）
- 测试报告（如 TEST_REPORT.md）
- 其他相关文档

**注意**: 这些文档也必须移入日期文件夹，不能散落在项目其他位置。

## 使用规范

### 1. 每天创建新文件夹
- 格式为 `YYYY-MM-DD`
- 使用脚本自动创建：`python scripts/create_daily_log.py`

### 2. 工作流程

**早上**：
```bash
# 创建今天的日志
python scripts/create_daily_log.py

# 填写 plan.md
```

**工作中**：
- 可以在任何地方写临时笔记（app/docs/、根目录、桌面等）
- 持续更新 implementation.md 和 decisions.md

**晚上（重要）**：
1. 完成 summary.md
2. 将所有临时文档移入今天的日期文件夹
3. **删除项目中其他位置的临时文档**
4. 提交 git

### 3. 清理检查清单

完成当天工作后，检查并清理以下位置：

```bash
# 检查这些位置是否有临时文档
app/docs/              # ❌ 应该为空
frontend/docs/         # ❌ 应该为空  
docs/design-previews/  # ❌ 临时设计文档应移走
根目录 *.md           # ❌ 临时笔记应删除或移走
```

正确的做法：
```bash
# 移动临时文档到今天的日志
mv app/docs/*.md docs/development/daily-logs/2026-08-17/

# 确认 app/docs 为空
ls app/docs/
# 应该只看到目录，没有 .md 文件
```

### 4. 完整性要求
- 至少包含 4 个必需文件（plan、implementation、decisions、summary）
- summary.md 中应包含完成情况统计

### 5. 交叉引用
- 使用相对路径链接到其他文档
- 使用绝对路径链接到代码文件

## 自动化脚本

### 创建新日志

```bash
# 创建今天的日志
python scripts/create_daily_log.py

# 创建指定日期的日志
python scripts/create_daily_log.py --date 2026-08-18

# 强制覆盖已存在的文件
python scripts/create_daily_log.py --force
```

## 文档查找

### 查看最近的日志

```bash
# 列出最近 5 天的日志
ls -lt docs/development/daily-logs/ | head -6

# 查看昨天的总结
cat docs/development/daily-logs/2026-08-16/summary.md
```

### Git 历史

所有日志都会提交到 git，可以通过历史查看：

```bash
# 查看某个日期的日志变更
git log --all --full-history -- "docs/development/daily-logs/2026-08-16/*"
```

## 最佳实践

### ✅ 做
1. **每天一个文件夹**，按日期命名
2. **所有文档集中**在对应日期文件夹
3. **晚上统一整理**，删除临时文档
4. **保持项目整洁**，避免文档散落
5. **及时提交 git**，记录工作历史

### ❌ 不做
1. 不在 app/docs/ 长期保留文档
2. 不在多个地方维护相同内容
3. 不跨日期混合记录（昨天的内容不要写到今天的日志）
4. 不遗留临时文档在项目根目录

## 文档生命周期

```
1. 创建      → python scripts/create_daily_log.py
2. 工作中    → 随时更新 implementation.md、decisions.md
3. 当天结束  → 完成 summary.md
4. 整理      → 移动所有临时文档到日期文件夹
5. 清理      → 删除其他位置的临时文档  ⚠️ 重要！
6. 提交      → git add & commit
7. 归档      → 日志永久保留，无需再移动
```

---

**创建日期**: 2026-08-17  
**维护者**: QueryMind 开发团队
