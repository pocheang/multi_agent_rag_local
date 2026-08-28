# Prompts Organization Implementation Plan

> For agentic workers: use superpowers:executing-plans task-by-task with review checkpoints.

**Goal:** Reorganize every prompt module under app/prompts by project capability while preserving prompt text, public imports, PromptManager behavior, and runtime execution semantics.

**Architecture:** core owns runtime Agent templates, retrieval owns retrieval templates, and skills owns domain templates. Root-level modules remain logic-free compatibility exports where callers require them; manager.py, __init__.py, and README.md remain public entry points.

**Tech Stack:** Python 3.11+, package imports, PowerShell, Conda environment rag-local, Ruff, Python AST.

## Global Constraints

- Do not modify or run tests/.
- Do not modify frontend/, CI/workflow files, pyproject.toml, package/lock files, migrations, or deployment/release files.
- Preserve the dirty worktree; do not use reset, checkout, clean, commit, push, or PR operations.
- Do not change prompt string contents, exported names, PromptManager keys, HTTP/SSE behavior, model selection, or retrieval behavior.
- Every moved root module must remain a logic-free compatibility export when callers require it.
- Use conda run -n rag-local for Python tooling.

---

### Task 1: Record inventory and migration map

**Files:**
- Inspect app/prompts/*.py, app/prompts/__init__.py, app/prompts/manager.py, app/prompts/README.md.
- Inspect app/**/*.py, scripts/**/*.py, tests/**/*.py, docs/**/*.md, and config/**/*.
- Modify docs/development/refactor-removal-register.md only for new migration evidence.

**Interfaces:**
- Consumes current module paths and exported symbols.
- Produces the evidence-backed mapping used by later tasks.

- [ ] Step 1: Capture imports and references.

~~~powershell
rg -n --glob '*.py' --glob '*.md' --glob '*.json' 'app\.prompts|from \.((ai_knowledge|comparison_timeline|cybersecurity_skills|intent|manager|pdf_web|rag_quick_retrieval|react|review|router|self_rag|synthesis)_prompts)' app scripts tests docs config
~~~

Classify every result as production, script, test, documentation, or package export. Do not edit callers during this task.

- [ ] Step 2: Capture definitions and exports.

~~~powershell
rg -n '^(__all__|[A-Z][A-Z0-9_]+\s*=|def get_|class PromptManager|from \.|import app\.prompts)' app/prompts
~~~

Confirm every exported symbol has one implementation after migration.

- [ ] Step 3: Freeze this destination map.

~~~text
core: canonical_agent_prompts.py, router_prompts.py, intent_prompts.py,
      synthesis_prompts.py, review_prompts.py, react_prompts.py
retrieval: rag_quick_retrieval_prompts.py, self_rag_prompts.py
skills: ai_knowledge_prompts.py, cybersecurity_skills_prompts.py,
        comparison_timeline_prompts.py, pdf_web_prompts.py
root: manager.py, __init__.py, README.md
~~~

---

### Task 2: Create capability subpackages

**Files:**
- Create app/prompts/core/__init__.py.
- Create app/prompts/retrieval/__init__.py.
- Create app/prompts/skills/__init__.py.

**Interfaces:**
- Consumes current prompt module symbols.
- Produces package namespaces without eager PromptManager construction or model clients.

- [ ] Step 1: Add minimal package markers.

Each marker contains a docstring and no wildcard imports or runtime initialization.

- [ ] Step 2: Parse the markers.

~~~powershell
conda run -n rag-local python -c "import ast; from pathlib import Path; files=[Path('app/prompts/core/__init__.py'),Path('app/prompts/retrieval/__init__.py'),Path('app/prompts/skills/__init__.py')]; [ast.parse(p.read_text(encoding='utf-8-sig'), filename=str(p)) for p in files]; print('prompt package markers parsed')"
~~~

---

### Task 3: Move prompt implementations without changing content

**Files:**
- Move canonical_agent_prompts.py, router_prompts.py, intent_prompts.py, synthesis_prompts.py, review_prompts.py, and react_prompts.py from app/prompts/ to app/prompts/core/.
- Move rag_quick_retrieval_prompts.py and self_rag_prompts.py from app/prompts/ to app/prompts/retrieval/.
- Move ai_knowledge_prompts.py, cybersecurity_skills_prompts.py, comparison_timeline_prompts.py, and pdf_web_prompts.py from app/prompts/ to app/prompts/skills/.

**Interfaces:**
- Consumes exact existing module contents.
- Produces identical symbols at canonical subpackage paths.

- [ ] Step 1: Move files as path-only operations.

Preserve encoding and line endings. Do not remove root compatibility paths until Task 4 is ready.

- [ ] Step 2: Fix package-relative imports only.

Resolve relative imports against the new package. Do not alter prompt literals, exported names, or manager semantics.

- [ ] Step 3: Check one implementation per symbol.

~~~powershell
rg -n '^([A-Z][A-Z0-9_]+\s*=|def |class )' app/prompts/core app/prompts/retrieval app/prompts/skills
~~~

---

### Task 4: Restore root compatibility and unified exports

**Files:**
- Modify app/prompts/__init__.py.
- Modify app/prompts/manager.py.
- Create or modify root compatibility modules only when Task 1 found a real caller or documented public import.

**Interfaces:**
- Consumes moved modules in core, retrieval, and skills.
- Produces unchanged imports from app.prompts, app.prompts.manager, and documented historical module paths.

- [ ] Step 1: Update app.prompts.__init__.

Point imports to new packages while preserving __all__, aliases, convenience functions, and CANONICAL_* names.

- [ ] Step 2: Update manager.py.

Change only internal imports. Preserve PromptManager keys, values, get_prompt, format_prompt, get_prompt_manager, and singleton behavior.

- [ ] Step 3: Keep compatibility modules logic-free.

Retained root modules contain imports and __all__ only. They must not define duplicate prompt literals, helpers, registries, or managers.

- [ ] Step 4: Audit old imports.

~~~powershell
rg -n --glob '*.py' 'from app\.prompts\.(canonical_agent_prompts|router_prompts|intent_prompts|synthesis_prompts|review_prompts|react_prompts|rag_quick_retrieval_prompts|self_rag_prompts|ai_knowledge_prompts|cybersecurity_skills_prompts|comparison_timeline_prompts|pdf_web_prompts) import' app scripts tests
~~~

Keep compatibility exports for real callers; update production-only imports to canonical subpackages where safe. Do not modify tests.

---

### Task 5: Update documentation and ownership guidance

**Files:**
- Modify app/prompts/README.md.
- Modify stale backend prompt paths in docs/**/*.md.
- Modify docs/development/refactor-removal-register.md with migration evidence.

**Interfaces:**
- Consumes final layout and compatibility decisions.
- Produces a complete module-to-capability owner map.

- [ ] Step 1: Replace the flat tree in README.

Document core, retrieval, skills, root public files, canonical owner rules, one runtime import example, and one PromptManager import example.

- [ ] Step 2: Find stale documentation paths.

~~~powershell
rg -n --glob '*.md' 'app/prompts/(canonical_agent_prompts|router_prompts|intent_prompts|synthesis_prompts|review_prompts|react_prompts|rag_quick_retrieval_prompts|self_rag_prompts|ai_knowledge_prompts|cybersecurity_skills_prompts|comparison_timeline_prompts|pdf_web_prompts)\.py' docs app/prompts
~~~

Update paths made stale by the move. Preserve historical migration examples when they explicitly describe compatibility paths.

- [ ] Step 3: Record evidence.

Add pre/post import audits, canonical owners, retained compatibility paths, and confirmation that prompt text was not changed to the removal register.

---

### Task 6: Static and import-boundary verification

**Files:**
- Inspect only changed backend Python files and prompt documentation.

**Interfaces:**
- Consumes final package tree and compatibility exports.
- Produces static evidence; no tests are changed or run.

- [ ] Step 1: Parse all backend Python.

~~~powershell
conda run -n rag-local python -c "import ast; from pathlib import Path; files=list(Path('app').rglob('*.py')); [ast.parse(p.read_text(encoding='utf-8-sig'), filename=str(p)) for p in files]; print(f'AST OK: {len(files)} app modules')"
~~~

- [ ] Step 2: Run required Ruff subset.

~~~powershell
conda run -n rag-local ruff check --select E9,F63,F7,F82 app
~~~

- [ ] Step 3: Verify public prompt imports without tests.

~~~powershell
conda run -n rag-local python -c "from app.prompts import PromptManager, REACT_SYSTEM_PROMPT, QUERY_DECOMPOSITION_PROMPT; from app.prompts.core.canonical_agent_prompts import ANSWER_PROMPT; from app.prompts.manager import get_prompt_manager; assert PromptManager is not None and REACT_SYSTEM_PROMPT and QUERY_DECOMPOSITION_PROMPT and ANSWER_PROMPT and get_prompt_manager() is not None; print('prompt imports OK')"
~~~

- [ ] Step 4: Check duplicate definitions and stale paths.

~~~powershell
rg -n '^REACT_SYSTEM_PROMPT\s*=|^ANSWER_PROMPT\s*=|^REVIEW_PROMPT\s*=|^ROUTER_PROMPT_TEMPLATE\s*=' app/prompts
rg -n --glob '*.py' 'app\.prompts\.(canonical_agent_prompts|router_prompts|intent_prompts|synthesis_prompts|review_prompts|react_prompts|rag_quick_retrieval_prompts|self_rag_prompts|ai_knowledge_prompts|cybersecurity_skills_prompts|comparison_timeline_prompts|pdf_web_prompts)' app scripts
~~~

Each canonical prompt definition must appear only in its new implementation directory; root matches must be imports or re-exports only.

- [ ] Step 5: Check whitespace.

~~~powershell
git diff --check
~~~

Expected: exit code 0. Do not commit the changes.

