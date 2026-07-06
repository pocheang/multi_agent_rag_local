# 开发流程 (Development Workflow)

本文档详细介绍 QueryMind（智询） 项目的完整开发流程，包括 Git 工作流、分支策略、代码审查和发布流程。

## 目录

- [Git 工作流](#git-工作流)
- [分支策略](#分支策略)
- [提交规范](#提交规范)
- [代码审查流程](#代码审查流程)
- [Pull Request 规范](#pull-request-规范)
- [发布流程](#发布流程)
- [开发环境管理](#开发环境管理)
- [协作最佳实践](#协作最佳实践)

---

## Git 工作流

本项目采用 **Git Flow** 工作流的简化版本，适合中小型团队协作。

### 工作流图示

```
main (生产分支)
  │
  ├─→ develop (开发分支)
  │     │
  │     ├─→ feature/new-agent (功能分支)
  │     ├─→ feature/improve-search (功能分支)
  │     └─→ bugfix/fix-auth (修复分支)
  │
  └─→ hotfix/critical-fix (热修复分支)
```

### 分支类型

| 分支类型 | 命名格式 | 生命周期 | 说明 |
|---------|---------|---------|------|
| `main` | `main` | 永久 | 生产环境代码 |
| `develop` | `develop` | 永久 | 开发环境代码 |
| `feature/*` | `feature/功能名` | 临时 | 新功能开发 |
| `bugfix/*` | `bugfix/问题描述` | 临时 | Bug 修复 |
| `hotfix/*` | `hotfix/紧急修复` | 临时 | 生产环境紧急修复 |
| `release/*` | `release/v0.x.x` | 临时 | 发布准备 |

---

## 分支策略

### 1. Main 分支

**用途**: 生产环境代码，始终保持稳定可发布状态

**保护规则**:
- ❌ 禁止直接推送
- ✅ 必须通过 PR 合并
- ✅ 必须通过所有 CI 测试
- ✅ 需要至少 1 个代码审查批准

**合并来源**:
- `hotfix/*` - 紧急修复
- `release/*` - 版本发布

### 2. Develop 分支

**用途**: 开发环境代码，集成所有已完成的功能

**保护规则**:
- ⚠️ 尽量避免直接推送
- ✅ 推荐通过 PR 合并
- ✅ 必须通过基础测试

**合并来源**:
- `feature/*` - 新功能
- `bugfix/*` - Bug 修复

### 3. Feature 分支

**创建**:
```bash
# 从 develop 创建功能分支
git checkout develop
git pull origin develop
git checkout -b feature/add-new-retriever
```

**命名规范**:
```
feature/功能简述       # 英文，小写，用连字符分隔
```

**示例**:
```
feature/add-graph-agent
feature/improve-reranker
feature/user-analytics
```

**开发流程**:
```bash
# 1. 创建分支
git checkout -b feature/add-new-retriever

# 2. 开发和提交
git add .
git commit -m "feat: add new semantic retriever"

# 3. 推送到远程
git push origin feature/add-new-retriever

# 4. 创建 Pull Request (通过 GitHub/GitLab UI)

# 5. 代码审查和合并后，删除本地分支
git checkout develop
git pull origin develop
git branch -d feature/add-new-retriever
```

### 4. Bugfix 分支

**创建**:
```bash
git checkout develop
git pull origin develop
git checkout -b bugfix/fix-auth-token-expiry
```

**命名规范**:
```
bugfix/问题简述
```

**示例**:
```
bugfix/fix-auth-token-expiry
bugfix/resolve-memory-leak
bugfix/correct-query-encoding
```

### 5. Hotfix 分支

**用途**: 紧急修复生产环境的关键问题

**创建**:
```bash
# 从 main 创建
git checkout main
git pull origin main
git checkout -b hotfix/v0.4.5
```

**流程**:
```bash
# 1. 修复问题并测试
git commit -m "fix: resolve critical security vulnerability"

# 2. 推送并创建 PR
git push origin hotfix/v0.4.5

# 3. 合并到 main
# (通过 PR 审查后合并)

# 4. 同时合并回 develop
git checkout develop
git merge hotfix/v0.4.5
git push origin develop

# 5. 创建 tag
git checkout main
git tag -a v0.4.5 -m "Hotfix: Security vulnerability fix"
git push origin v0.4.5
```

---

## 提交规范

### Conventional Commits

采用 [Conventional Commits](https://www.conventionalcommits.org/) 规范。

**格式**:
```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type 类型

| Type | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat: add graph RAG agent` |
| `fix` | Bug 修复 | `fix: resolve auth token expiry issue` |
| `docs` | 文档更新 | `docs: update API documentation` |
| `style` | 代码格式（不影响功能）| `style: format code with black` |
| `refactor` | 重构 | `refactor: simplify retrieval pipeline` |
| `perf` | 性能优化 | `perf: optimize vector search` |
| `test` | 测试相关 | `test: add unit tests for router agent` |
| `build` | 构建系统 | `build: update dependencies` |
| `ci` | CI 配置 | `ci: add automated testing workflow` |
| `chore` | 其他杂项 | `chore: update .gitignore` |
| `revert` | 回滚 | `revert: revert commit abc123` |

### Scope 范围（可选）

```
feat(api): add new query endpoint
fix(auth): resolve JWT token validation
docs(setup): update installation guide
test(retriever): add BM25 unit tests
```

**常用 scope**:
- `api` - API 相关
- `agents` - 智能体
- `retrieval` - 检索系统
- `auth` - 认证
- `ui` - 前端界面
- `db` - 数据库
- `config` - 配置

### 提交消息示例

**好的提交**:
```bash
feat(agents): add graph RAG agent for entity relationship queries

- Implement Neo4j query builder
- Add entity extraction logic
- Include relationship traversal
- Add unit tests for graph queries

Closes #123
```

**不好的提交**:
```bash
# ❌ 太简略
git commit -m "fix bug"

# ❌ 没有类型前缀
git commit -m "added new feature"

# ❌ 太啰嗦
git commit -m "feat: I added a new agent that does graph queries and it works by connecting to Neo4j database and..."
```

### 提交最佳实践

1. **一个提交做一件事**: 不要在一个提交中混合多个不相关的更改
2. **使用现在时**: "add feature" 而非 "added feature"
3. **首行不超过 50 字符**: 保持简洁
4. **正文详细说明**: 解释"为什么"而非"是什么"
5. **引用 Issue**: 使用 `Closes #123` 或 `Fixes #456`

---

## 代码审查流程

### 审查清单

#### 1. 代码质量
- [ ] 代码风格符合项目规范
- [ ] 没有明显的性能问题
- [ ] 没有安全漏洞（SQL 注入、XSS 等）
- [ ] 错误处理得当
- [ ] 日志记录充分

#### 2. 功能正确性
- [ ] 功能实现符合需求
- [ ] 边界条件处理正确
- [ ] 没有破坏现有功能
- [ ] 测试覆盖充分

#### 3. 代码可维护性
- [ ] 命名清晰易懂
- [ ] 函数和类职责单一
- [ ] 代码注释充分
- [ ] 没有重复代码

#### 4. 文档和测试
- [ ] API 文档更新
- [ ] README 更新（如需要）
- [ ] 单元测试通过
- [ ] 集成测试通过

### 审查流程

```
1. 开发者创建 PR
   ↓
2. 自动运行 CI 检查
   ├─ 代码风格检查 (ruff)
   ├─ 类型检查 (mypy)
   ├─ 单元测试
   └─ 集成测试
   ↓
3. 审查者检查代码
   ├─ 阅读代码逻辑
   ├─ 运行本地测试
   └─ 提出改进建议
   ↓
4. 开发者修改代码
   ↓
5. 审查者批准
   ↓
6. 合并到目标分支
```

### 审查评论规范

**建设性评论**:
```
✅ "这里可以使用缓存来提高性能，建议添加 @lru_cache 装饰器"
✅ "edge case: 当 results 为空时，这里会抛出 IndexError"
✅ "考虑将这个长函数拆分为多个小函数，提高可读性"
```

**避免的评论**:
```
❌ "这代码写得不好"
❌ "为什么不用 X 方法？"（没有解释原因）
❌ "太复杂了"（没有具体建议）
```

---

## Pull Request 规范

### PR 标题

遵循提交规范：
```
feat(api): add streaming query endpoint
fix(auth): resolve JWT token expiry issue
docs: update development workflow guide
```

### PR 描述模板

```markdown
## 📋 变更类型
- [ ] 新功能 (feat)
- [ ] Bug 修复 (fix)
- [ ] 文档更新 (docs)
- [ ] 代码重构 (refactor)
- [ ] 性能优化 (perf)
- [ ] 测试相关 (test)

## 📝 变更描述
简要描述这个 PR 的目的和实现方式。

## 🔗 相关 Issue
Closes #123
Related to #456

## 🧪 测试计划
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 手动测试完成

**测试步骤**:
1. 运行 `pytest tests/test_new_feature.py`
2. 验证 API 端点 `/api/new-endpoint`
3. 检查前端显示正常

## 📸 截图（如适用）
[添加截图或 GIF]

## ⚠️ 破坏性变更
- [ ] 是 - 需要更新 API 文档和迁移指南
- [x] 否

## 📋 审查清单
- [x] 代码符合项目规范
- [x] 添加了必要的测试
- [x] 更新了相关文档
- [x] 没有破坏现有功能
- [x] 通过了所有 CI 检查
```

### PR 最佳实践

1. **保持 PR 小而专注**: 一个 PR 解决一个问题
2. **及时更新**: 定期 rebase develop 分支
3. **回复评论**: 及时回复审查者的评论
4. **自我审查**: 提交前自己先审查一遍
5. **添加截图**: 前端变更添加截图

---

## 发布流程

### 语义化版本

采用 [Semantic Versioning](https://semver.org/) 规范：

```
MAJOR.MINOR.PATCH

例如: v0.4.5
      │ │ │
      │ │ └─ PATCH: Bug 修复
      │ └─── MINOR: 新功能（向后兼容）
      └───── MAJOR: 破坏性变更
```

### 发布步骤

#### 1. 创建 Release 分支

```bash
git checkout develop
git pull origin develop
git checkout -b release/v0.5.0
```

#### 2. 更新版本号

**pyproject.toml**:
```toml
[project]
version = "0.5.0"
```

**package.json** (前端):
```json
{
  "version": "0.5.0"
}
```

**app/__version__.py**:
```python
__version__ = "0.5.0"
```

#### 3. 更新文档

- 更新 `CHANGELOG.md`
- 更新 `README.md` 的版本号
- 创建发布说明 `docs/releases/RELEASE_NOTES_v0.5.0.md`

**CHANGELOG.md 格式**:
```markdown
## [0.5.0] - 2026-06-19

### Added
- Graph RAG agent for entity relationship queries
- Streaming query endpoint with SSE support
- User analytics dashboard

### Changed
- Improved retrieval accuracy with new reranker
- Optimized vector search performance

### Fixed
- Auth token expiry issue
- Memory leak in long-running sessions

### Deprecated
- Old query endpoint `/api/query` (use `/api/v2/query`)

### Removed
- Legacy BM25 implementation

### Security
- Fixed JWT validation vulnerability
```

#### 4. 测试发布候选

```bash
# 运行完整测试套件
pytest

# 运行质量检查
python scripts/ci_quality_gate.py

# 手动烟雾测试
python scripts/dev/smoke_test_query.py
```

#### 5. 合并到 Main

```bash
# 创建 PR: release/v0.5.0 -> main
# 审查并合并

# 在 main 上创建 tag
git checkout main
git pull origin main
git tag -a v0.5.0 -m "Release v0.5.0"
git push origin v0.5.0
```

#### 6. 回合并到 Develop

```bash
git checkout develop
git merge main
git push origin develop
```

#### 7. 发布到 GitHub Releases

通过 GitHub UI 创建 Release：
- 选择 tag: `v0.5.0`
- 发布标题: `v0.5.0 - Feature Name`
- 描述: 从 CHANGELOG.md 复制
- 附件: 可选的构建产物

---

## 开发环境管理

### Conda 环境

**创建**:
```bash
conda create -n rag-local python=3.11
conda activate rag-local
pip install -e ".[dev]"
```

**导出依赖**:
```bash
pip freeze > requirements.txt
```

**环境清理**:
```bash
conda deactivate
conda remove -n rag-local --all
```

### 开发工具

**代码格式化**:
```bash
# Python (使用 ruff)
ruff format app/ tests/

# TypeScript (使用 prettier)
cd frontend
npm run format
```

**代码检查**:
```bash
# Python
ruff check app/ tests/

# TypeScript
cd frontend
npm run lint
```

**类型检查**:
```bash
# Python
mypy app/

# TypeScript
cd frontend
npm run type-check
```

### Pre-commit Hooks

**安装**:
```bash
pip install pre-commit
pre-commit install
```

**配置** (`.pre-commit-config.yaml`):
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

---

## 协作最佳实践

### 1. 沟通

- 🔔 **及时响应**: 24 小时内回复 PR 评论
- 💬 **清晰表达**: 问题描述详细，包含复现步骤
- 🤝 **尊重团队**: 保持专业和友善的态度

### 2. 代码共享

- 📚 **文档先行**: 重大变更前先更新设计文档
- 🔄 **增量提交**: 小步快跑，频繁提交
- ⚡ **快速反馈**: 早期提交 Draft PR 获取反馈

### 3. 问题跟踪

**创建 Issue**:
```markdown
## 🐛 Bug 报告 / 💡 功能请求

### 描述
清晰描述问题或功能

### 复现步骤（Bug）
1. 步骤 1
2. 步骤 2
3. 观察到的错误

### 期望行为
应该发生什么

### 环境信息
- OS: Windows 10
- Python: 3.11.8
- 版本: v0.4.4

### 截图
[如果适用]
```

### 4. 代码质量

- ✅ **编写测试**: 新功能必须有测试
- 📝 **添加注释**: 复杂逻辑添加注释
- 🔍 **代码审查**: 认真审查他人代码
- 🧹 **定期重构**: 及时清理技术债务

---

---

## 快速参考

### Git 命令速查

```bash
# ============ 分支管理 ============
# 创建并切换到新分支
git checkout -b feature/new-feature

# 切换分支
git checkout develop

# 查看所有分支
git branch -a

# 删除本地分支
git branch -d feature/old-feature

# 删除远程分支
git push origin --delete feature/old-feature

# ============ 提交管理 ============
# 查看状态
git status

# 添加文件
git add .
git add <file>

# 提交
git commit -m "feat: add new feature"

# 修改最后一次提交
git commit --amend

# 撤销最后一次提交（保留更改）
git reset --soft HEAD~1

# ============ 同步代码 ============
# 拉取最新代码
git pull origin develop

# 推送代码
git push origin feature/new-feature

# 推送新分支并设置上游
git push -u origin feature/new-feature

# ============ 暂存管理 ============
# 暂存当前更改
git stash

# 查看暂存列表
git stash list

# 恢复暂存
git stash pop

# 应用暂存（不删除）
git stash apply

# ============ 日志查看 ============
# 查看提交历史
git log --oneline

# 查看某文件的修改历史
git log --follow <file>

# 查看差异
git diff
git diff develop
```

### 提交类型速查

| Type | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(api): add user authentication` |
| `fix` | Bug 修复 | `fix(auth): resolve token expiry issue` |
| `docs` | 文档更新 | `docs: update API documentation` |
| `style` | 代码格式 | `style: format with ruff` |
| `refactor` | 重构 | `refactor: simplify query logic` |
| `perf` | 性能优化 | `perf: optimize vector search` |
| `test` | 测试 | `test: add unit tests for router` |
| `build` | 构建 | `build: update dependencies` |
| `ci` | CI 配置 | `ci: add GitHub Actions workflow` |
| `chore` | 杂项 | `chore: update .gitignore` |

### 分支命名速查

| 分支类型 | 格式 | 示例 |
|---------|------|------|
| **功能** | `feature/描述` | `feature/add-graph-agent` |
| **修复** | `bugfix/描述` | `bugfix/fix-auth-error` |
| **热修复** | `hotfix/版本` | `hotfix/v0.4.5` |
| **发布** | `release/版本` | `release/v0.5.0` |

### 常用操作流程速查

#### 开发新功能
```bash
# 1. 更新 develop 分支
git checkout develop
git pull origin develop

# 2. 创建功能分支
git checkout -b feature/new-feature

# 3. 开发和提交
git add .
git commit -m "feat: add new feature"

# 4. 推送分支
git push -u origin feature/new-feature

# 5. 创建 Pull Request（通过 GitHub UI）

# 6. 合并后清理
git checkout develop
git pull origin develop
git branch -d feature/new-feature
```

#### 修复 Bug
```bash
# 1. 从 develop 创建 bugfix 分支
git checkout develop
git pull origin develop
git checkout -b bugfix/fix-issue

# 2. 修复并提交
git add .
git commit -m "fix: resolve issue #123"

# 3. 推送并创建 PR
git push -u origin bugfix/fix-issue
```

#### 紧急热修复
```bash
# 1. 从 main 创建 hotfix 分支
git checkout main
git pull origin main
git checkout -b hotfix/v0.4.5

# 2. 修复并提交
git add .
git commit -m "fix: critical security fix"

# 3. 推送并创建 PR
git push -u origin hotfix/v0.4.5

# 4. 合并到 main 后，也要合并回 develop
git checkout develop
git merge hotfix/v0.4.5
git push origin develop
```

### 代码审查清单速查

**提交 PR 前检查**：
- [ ] 代码符合项目规范（运行 `ruff check`）
- [ ] 所有测试通过（运行 `pytest`）
- [ ] 添加了必要的测试
- [ ] 更新了相关文档
- [ ] 提交消息遵循规范
- [ ] PR 描述清晰完整
- [ ] 没有合并冲突

**审查者检查**：
- [ ] 代码逻辑正确
- [ ] 没有明显的性能问题
- [ ] 没有安全漏洞
- [ ] 错误处理得当
- [ ] 命名清晰易懂
- [ ] 注释充分
- [ ] 没有重复代码

---

## 常见场景

### 场景 1: 同步远程变更

```bash
# 方法 1: Pull
git checkout develop
git pull origin develop

# 方法 2: Fetch + Merge
git fetch origin
git merge origin/develop

# 方法 3: Fetch + Rebase
git fetch origin
git rebase origin/develop
```

### 场景 2: 解决合并冲突

```bash
# 1. 尝试合并
git merge develop

# 2. 查看冲突文件
git status

# 3. 手动解决冲突（编辑文件）

# 4. 标记为已解决
git add <conflicted-files>

# 5. 完成合并
git commit
```

### 场景 3: 撤销提交

```bash
# 撤销最后一次提交（保留更改）
git reset --soft HEAD~1

# 撤销最后一次提交（丢弃更改）
git reset --hard HEAD~1

# 修改最后一次提交
git commit --amend
```

### 场景 4: 暂存工作

```bash
# 暂存当前更改
git stash

# 查看暂存列表
git stash list

# 恢复暂存
git stash pop

# 删除暂存
git stash drop
```

---

## 故障排查

### 问题 1: 合并冲突

**症状**: `git merge` 失败

**解决**:
```bash
# 1. 查看冲突文件
git status

# 2. 编辑文件，删除冲突标记
<<<<<<< HEAD
你的更改
=======
他人的更改
>>>>>>> develop

# 3. 标记为已解决
git add <file>
git commit
```

### 问题 2: 推送被拒绝

**症状**: `git push` 失败

**解决**:
```bash
# 先拉取远程更改
git pull origin develop

# 解决可能的冲突后再推送
git push origin develop
```

### 问题 3: 误提交到错误分支

**解决**:
```bash
# 1. 创建正确的分支（保留当前更改）
git checkout -b correct-branch

# 2. 回到错误的分支
git checkout wrong-branch

# 3. 撤销提交
git reset --hard HEAD~1
```

---

## 下一步

了解开发流程后，建议继续阅读：

1. **[代码规范](./CODE_STANDARDS.md)** - 编码标准和最佳实践
2. **[测试指南](./TESTING_GUIDE.md)** - 测试框架和测试策略
3. **[配置参考](./CONFIGURATION_REFERENCE.md)** - 环境变量完整说明

---

**更新日期**: 2026-06-19  
**文档版本**: 1.1  
**贡献者**: Bronit Team
