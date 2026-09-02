# Documentation Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** 将 QueryMind 当前文档整理为企业协作和 GitHub 友好的单一入口、分 audience 导航、统一命名和可持续校验体系。

**Architecture:** 保留现有领域目录，收敛入口与索引；当前文档只描述源码和配置可验证的行为，旧报告与旧入口隔离到归档。发布说明暂不物理批量改名，以兼容现有 GitHub 链接，并从下一版开始使用规范文件名。

**Tech Stack:** Markdown、PowerShell、GitHub-compatible relative links、现有 Python/Conda 工具链。

## Global Constraints

- 不删除历史资料，不重置或覆盖工作区已有未提交变更。
- 不修改与文档整理无关的 Python、TypeScript、配置和部署代码。
- 根目录标准 GitHub 文件名可保留大写；`docs/` 下新增当前文档使用小写 `kebab-case.md`。
- 当前技术事实必须能在代码、配置、Compose 文件、`package.json` 或测试命令中找到证据。
- 旧发布文件名先保留兼容；`docs/releases/README.md` 定义 canonical 版本入口和下一版本命名规则。

---

### Task 1: 收敛文档入口与领域导航

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/INDEX.md`
- Modify: `docs/getting-started/README.md`
- Modify: `docs/user-guide/README.md`
- Modify: `docs/architecture/README.md`
- Modify: `docs/features/README.md`
- Modify: `docs/development/README.md`
- Modify: `docs/operations/README.md`
- Modify: `docs/reference/README.md`
- Modify: `docs/zh-CN/README.md`
- Modify: `docs/zh-CN/INDEX.md`

**Interfaces:**
- Produces one current navigation path from `README.md` → `docs/README.md` → domain `README.md`.
- Every listed domain entry points to an existing file or directory README.

- [ ] Rewrite duplicated or stale navigation text to describe only the current directory structure.
- [ ] Add audience labels and a short “choose this path” table to `docs/README.md`.
- [ ] Keep `docs/INDEX.md` as a compatibility redirect page.
- [ ] Remove links to `docs/guides/`, `docs/project/`, `internal_docs/`, and missing `.env.docker.example` from current entry points.
- [ ] Verify with `rg -n "docs/(guides|project)|internal_docs|\.env\.docker\.example" README.md docs --glob '*.md'`, excluding `docs/archive/legacy/` and historical release text.

### Task 2: Update getting-started and operations facts

**Files:**
- Modify: `docs/getting-started/quick-start.md`
- Modify: `docs/getting-started/setup.md`
- Modify: `docs/getting-started/configuration.md`
- Modify: `docs/getting-started/startup.md`
- Modify: `docs/operations/README.md`
- Modify: `docs/operations/docker.md`
- Modify: `docs/operations/deployment.md`
- Modify: `docs/operations/quick-deploy.md`
- Modify: `docs/operations/frontend-access.md`
- Modify: `docs/operations/troubleshooting/README.md`
- Modify: `docs/operations/runbooks/README.md`

**Interfaces:**
- Commands and paths must match `AGENTS.md`, `.env.example`, `docker-compose*.yml`, `app/api/main.py`, `app/main.py`, `frontend/package.json`, and existing scripts.

- [ ] Consolidate the shortest local startup path around `conda activate rag-local`, backend port `8000`, frontend port `5173`, and the actual Uvicorn entry point.
- [ ] Separate setup prerequisites, environment configuration, startup, Docker deployment, and troubleshooting so each topic has one owner page.
- [ ] Replace obsolete Docker example filenames and unsupported commands with repository-backed commands.
- [ ] Add owner/status/last-verified metadata to current operational entry pages.
- [ ] Verify all commands and referenced paths with `Test-Path`, `rg`, and the project command list in `AGENTS.md`.

### Task 3: Normalize current architecture, feature, development, and reference navigation

**Files:**
- Modify: `docs/architecture/README.md`
- Modify: `docs/architecture/overview.md`
- Modify: `docs/architecture/multi-agent-system.md`
- Modify: `docs/architecture/retrieval-system.md`
- Modify: `docs/architecture/data-storage.md`
- Modify: `docs/features/README.md`
- Modify: `docs/features/agents/README.md`
- Modify: `docs/features/pdf/README.md`
- Modify: `docs/features/rag/README.md`
- Modify: `docs/development/README.md`
- Modify: `docs/development/workflow.md`
- Modify: `docs/development/testing.md`
- Modify: `docs/development/github-release.md`
- Modify: `docs/reference/README.md`
- Modify: `docs/reference/configuration.md`
- Modify: `docs/reference/api-examples.md`
- Modify: `docs/reference/faq.md`

**Interfaces:**
- Domain indexes are the only navigation authority for their directory.
- Architecture pages explain current boundaries; feature pages explain user-visible behavior; reference pages provide exact contracts.

- [ ] Remove duplicate “quick reference” sections that repeat the getting-started path.
- [ ] Replace temporary titles such as “Agent优化系统” with `QueryMind（智询）` and stable feature names.
- [ ] Mark optional Neo4j, web research, OCR, and model integrations as optional where the code/config confirms fallback behavior.
- [ ] Split FAQ entries by user, operations, and development ownership using links instead of copied instructions.
- [ ] Add `Owner`, `Status`, and `Last verified` to current reference and architecture entry pages.
- [ ] Verify names against `app/`, `config/`, `scripts/`, and `frontend/package.json`.

### Task 4: Make release, design, template, and archive indexes authoritative

**Files:**
- Modify: `docs/releases/README.md`
- Modify: `docs/design/INDEX.md`
- Modify: `docs/templates/README.md`
- Modify: `docs/archive/INDEX.md`
- Modify: `docs/history/README.md`
- Modify: `docs/history/VERSION_HISTORY.md`
- Modify: `docs/DOCUMENTATION_POLICY.md`
- Modify: `docs/development/github-release.md`

**Interfaces:**
- `docs/releases/README.md` maps every version file to exactly one canonical release entry.
- `docs/archive/INDEX.md` contains only existing archive paths and explicitly states that archive content is historical.
- `docs/DOCUMENTATION_POLICY.md` defines naming, ownership, lifecycle, review, and release rules.

- [ ] Enumerate every file under `docs/releases/` and add missing versions to the release index.
- [ ] Keep existing `RELEASE_NOTES_vX.Y.Z.md` and `RELEASE_vX.Y.Z.md` links as compatibility names; define `release-notes-vX.Y.Z.md` for new releases.
- [ ] Remove the duplicate CSS design link and update design directory guidance to match the repository.
- [ ] Rewrite the template index in readable UTF-8 Chinese/English and point examples to current directories.
- [ ] Replace nonexistent archive links such as `../guides/`, `../project/`, and `internal_docs/` with existing archive or current links.
- [ ] Add a release-note checklist: summary, user impact, breaking changes, migration, verification, and documentation links.

### Task 5: Add a repeatable documentation integrity checker

**Files:**
- Create: `scripts/check_docs.py`
- Modify: `docs/DOCUMENTATION_POLICY.md`
- Modify: `AGENTS.md`

**Interfaces:**
- Command: `conda run -n rag-local python scripts/check_docs.py`
- Exit code `0`: all current-document checks pass.
- Exit code `1`: one or more broken links, stale current paths, duplicate release mappings, or invalid current filenames.

- [ ] Implement a standard-library-only checker that scans current `docs/` Markdown while excluding `docs/archive/legacy/` and code fences.
- [ ] Validate relative Markdown links, local image paths, forbidden current paths, duplicate release version mappings, and current filename policy.
- [ ] Print actionable failures with source file and target path.
- [ ] Document the command in `AGENTS.md` and the PR checklist in `docs/DOCUMENTATION_POLICY.md`.
- [ ] Run the checker before and after the content updates to demonstrate the intended failure-to-pass improvement.

### Task 6: Final verification and change-scope review

**Files:**
- Verify: all modified Markdown files
- Verify: `scripts/check_docs.py`

- [ ] Run `conda run -n rag-local python scripts/check_docs.py`.
- [ ] Run `git diff --check` for all documentation changes.
- [ ] Run `pytest -q` only if the documentation change exposes a project-level command/config mismatch; otherwise report it as not required for Markdown-only changes.
- [ ] Run `git status --short` and confirm no unrelated files were modified by this implementation.
- [ ] Record any environment-blocked checks with exact rerun commands instead of classifying them as failures.

