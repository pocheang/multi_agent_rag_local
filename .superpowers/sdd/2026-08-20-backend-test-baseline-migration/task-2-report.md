# Task 2 report: backend test-environment restoration

Date: 2026-08-20

## Scope and preserved changes

- Modified only `pyproject.toml` optional dependencies and the Task 2 evidence in `docs/development/backend-test-baseline-migration.md`.
- Preserved the pre-existing unstaged core-dependency hunk adding `sqlalchemy[asyncio]`, `aiosqlite`, and `asyncpg`; it is not part of this task's patch.
- Added the `multimodal` extra exactly as required:
  - `pandas>=2.2.0,<3.0`
  - `PyMuPDF>=1.24.0`
  - `pdfplumber>=0.11.0`
  - `tabulate>=0.9.0`
- Added `multimodal` to the `full` meta-extra. No dependency was moved into core and no backend behavior or test assertions were changed.

## Baseline environment check

The prescribed eight focused files were run before the edit with:

```powershell
.venv\Scripts\python.exe -m pytest -q tests/mcp/test_server_contracts.py tests/mcp/test_server_transport.py tests/unit/test_chinese_document_indexer.py tests/unit/test_chinese_query_preprocessor.py tests/unit/test_chinese_tokenizer.py tests/integration/test_streaming_pdf.py tests/services/multimodal/test_image_processor.py tests/services/multimodal/test_table_extractor.py
```

Result: 0 tests collected, 8 collection errors. All were declared-environment import failures: `mcp` (two files), `jieba` (three files), `psutil`, `fitz`/PyMuPDF, and `pandas`.

## Installation and dependency verification

The initial `.venv\Scripts\python.exe -m pip install -e '.[dev,multimodal]'` attempt was blocked by the sandbox (`WinError 10013` reaching the package index for build dependencies). The same narrowly scoped command completed after approved escalation, using the current `.venv` only.

The required import probe printed `dependency imports ok` for `jieba`, `mcp`, `pandas`, `psutil`, `fitz`, `pdfplumber`, and `tabulate`. `.venv\Scripts\python.exe -m pip check` returned `No broken requirements found.`

## Focused verification after installation

The same eight files collected 79 tests: **66 passed, 1 skipped, 12 failed** (6.65s). No collection/import error remains.

The 12 remaining failures are separate current-contract/runtime failures and were deliberately not changed:

- `test_chinese_tokenizer.py::TestChineseTokenizer::test_extract_keywords_textrank`: `allowPOS=None` is passed to `jieba.analyse.textrank`, which requires an iterable.
- Five `test_streaming_pdf.py` tests: streaming logs `Docling not available`; `docling` is a distinct existing optional extra and was not part of the requested `.[dev,multimodal]` environment.
- Five image-processor tests: expectations patch legacy module attributes absent from the current `image_processor` contract, plus one downstream empty-description assertion.
- One table-extractor test: expectation patches a legacy `get_chroma_client` attribute absent from the current `table_extractor` contract.

## Full collection

`.venv\Scripts\python.exe -m pytest --collect-only -q` completed with exit 1 after **1478 collected items / 37 collection errors** in 17.38s. This is 10 fewer collection errors than the Task 1 frozen baseline of 47. The remaining errors are legacy-path and chart-extractor migration errors documented in the matrix; the dependency import errors addressed here are resolved. The updated Task 2 evidence is in `docs/development/backend-test-baseline-migration.md`.

## Commit/staging decision

`pyproject.toml` was dirty before this task. Its existing core-dependency change and this task's optional-extra change are independent diff hunks. Only the Task 2 optional-extra hunk may be staged; the preserved core hunk must remain unstaged. The task-owned documentation and this report are independently stageable.
