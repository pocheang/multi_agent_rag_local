# QueryMind（智询）

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Release](https://img.shields.io/badge/release-v0.6.2.1-green.svg)](https://github.com/pocheang/querymind/releases)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

**Enterprise-grade Agentic RAG system for private knowledge bases**  
Built with FastAPI, React, LangGraph, and hybrid retrieval

---

## ✨ Features

### Pipeline
- 🎯 **Three components always run** - Router (intent and route), Retriever (hybrid search),
  Synthesizer (citation-first generation)
- 🔀 **Three more when the route asks for them** - Planner, a governed Tool Runner, and a
  Finalizer that validates the answer
- 🔄 **LangGraph workflow** - Stateful execution with per-stage timeouts that degrade rather
  than fail the request

### Retrieval
- 🔍 **Hybrid search** - Vector (BGE-M3) + BM25, fused by Reciprocal Rank Fusion
- 📊 **Graph retrieval** - Neo4j for relationship questions, optional; the system runs
  without it
- 🔁 **Reranking** - BGE-Reranker-V2-M3, widened with the question's complexity
- 🌐 **Web search** - On the web route, and as a freshness fallback when enabled
- 🔒 **Scoped, not filtered** - Retrieval is bounded by the caller's access scope before it
  runs, and a missing scope raises rather than searching every tenant's corpus

### Answers
- 📝 **Citation-first** - Claims carry an inline marker during generation; readers see
  `[1]`, `[2]` numbered by first appearance, with a reference list
- 🛡️ **Validation** - Citation completeness, NLI entailment, and sentence-level grounding
  that hedges claims the evidence does not support
- 🔐 **Output DLP** - Secrets are redacted from finalized answers and from the streamed
  draft, at every chunk boundary

### Operations
- 🔑 **Security** - JWT authentication, RBAC, encrypted stored credentials
- ⚙️ **Configuration** - One schema (`Settings`), one precedence chain, an optional Nacos
  configuration centre, and an admin page that shows which layer each value came from
- 📊 **Monitoring** - Prometheus metrics, Grafana dashboards, structured logging
- 🐳 **Docker** - Compose stack with health checks

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for frontend)
- **Conda** (recommended for environment management)
- **Neo4j** (optional, for graph retrieval)

No external database is required: users, sessions, prompts and connector metadata all live
in SQLite under `data/`.

### Docker Deployment (Recommended)

```bash
# 1. Set your API key (optional -- MODEL_BACKEND=local needs none)
export OPENAI_API_KEY="your-api-key"

# 2. Deploy with one command
./deploy/scripts/deploy.sh production balanced

# 3. Access the application
# - Frontend: http://localhost:5173
# - API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
```

**Deployment Profiles:**
- `balanced` - Default (moderate speed, good quality)
- `deep` - Deep analysis (slower, higher quality)
- `fast` - Fast response (higher speed, basic quality)

### Local Development

**1. Create Conda environment:**

```bash
conda create -n rag-local python=3.11
conda activate rag-local
```

**2. Install dependencies:**

```bash
pip install -e .
```

**3. Configure:**

```bash
# Render the runtime configuration. A root .env is NOT read -- app/core/config.py
# reads .runtime/{APP_ENV}.env, which this generates from config/env/ + config/profiles/.
make config-render ENV=development PROFILE=balanced

# ...or without make, which Windows checkouts often lack:
conda run -n rag-local python deploy/scripts/config.py render   --environment development --profile balanced --output .runtime/development.env
```

Nothing else is required to start. The default `MODEL_BACKEND=local` runs an offline
stand-in with no API key and no Ollama, so the app comes up on a fresh checkout. To use a
real model, export the key as a **real environment variable** — the rendered file is read
into settings without being exported, so keys placed there reach the application but not
anything that reads `os.environ` directly:

```bash
export OPENAI_API_KEY=sk-...
```

The database needs no initialisation step: every store creates its own SQLite schema on
first use, under `data/`.

**4. Create a local administrator** (optional, for the admin pages):

```bash
python scripts/create_admin.py     # prints a generated password once
```

**5. Start backend:**

```bash
uvicorn app.api.main:app --reload --port 8000
```

**6. Start frontend (new terminal):**

```bash
cd frontend
npm install
npm run dev
```

**7. Access:**
- Frontend: http://localhost:5173
- API Docs: http://localhost:8000/docs

---

## 📖 Documentation

### Quick Links
- 📗 [CLAUDE.md](CLAUDE.md) - How the system actually works today, in detail
- 📚 [Documentation index](docs/README.md) - What exists and where it lives
- 💻 [Development Guide](docs/development/README.md) - Contributing and development
- 📝 [Release notes](docs/releases/README.md) - Version history

> The architecture, user-guide, operations and reference documents were cleared ahead of
> the v0.7 rewrite and are being regenerated against the new architecture. Until they land,
> [CLAUDE.md](CLAUDE.md) is the accurate description of how the system works today.

---

## 🏗️ Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                       React + TypeScript                     │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTP + SSE
┌───────────────────────────▼──────────────────────────────────┐
│                       FastAPI backend                        │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  LangGraph workflow                    │  │
│  │                                                        │  │
│  │   privacy_permission   resolves the caller's scope     │  │
│  │          ↓             and rewrites the request        │  │
│  │   router               intent, route, skill            │  │
│  │          ↓                                             │  │
│  │   planner              optional: decomposition         │  │
│  │          ↓                                             │  │
│  │   knowledge            vector + BM25 (+ graph, web,    │  │
│  │          ↓             memory, wiki, multimodal)       │  │
│  │   tool                 optional: governed tool loop    │  │
│  │          ↓             select → invoke → observe       │  │
│  │   synthesizer          citation-first generation       │  │
│  │          ↓                                             │  │
│  │   verifier             optional: validate, maybe retry │  │
│  │          ↓                                             │  │
│  │   output_filter        DLP, then citation numbering    │  │
│  └────────────────────────────────────────────────────────┘  │
└───────────────────────────┬──────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
   ┌────▼─────┐      ┌──────▼──────┐     ┌──────▼──────┐
   │ ChromaDB │      │   SQLite    │     │    Neo4j    │
   │ (vectors)│      │(users, etc.)│     │  (optional) │
   └──────────┘      └─────────────┘     └─────────────┘
```

`privacy_permission` and `output_filter` have no timeout fallback on purpose:
skipping scope resolution or output DLP is a hole, not a degradation.

### Key Components

- **Six components** - three always on the path, three the route may add. The
  `app/agents/` directory name is historical; these are components, not autonomous agents.
- **LangGraph workflow** - one graph, one profile, per-stage budgets
- **Hybrid retrieval** - vector + BM25 fused by RRF, graph and web where the route asks
- **Answer validation** - citations, NLI entailment, sentence grounding, output DLP
- **Configuration** - one schema in `app/core/config.py`, layered sources, optional
  configuration centre

**Detailed Architecture:** [CLAUDE.md](CLAUDE.md) — kept current with the code rather than alongside it.

---

## 🛠️ Development

### Tech Stack

Pins live in `pyproject.toml` and `frontend/package.json`; these are the majors.

**Backend:**
- FastAPI 0.138+ (API framework)
- LangGraph 0.2+ / LangChain 0.3+ (orchestration and LLM integration)
- ChromaDB 0.5+ (vector store)
- Neo4j 5.24+ (graph, optional)
- SQLite (users, sessions, prompts, connectors — no external database)

**Frontend:**
- React 18.3 + TypeScript 5.9 + Vite 6
- Zustand (state), i18next (zh/en), Tailwind v4 alongside the stylesheets it is
  replacing

**Models:**
- OpenAI (default `gpt-5.5`), Anthropic, or Ollama
- `MODEL_BACKEND=local` — the default on a fresh checkout — uses an offline
  stand-in with no LLM at all, so the app runs with no API key. Quality figures
  describe the LLM path, not this one.
- Sentence-Transformers BGE-M3 (embeddings), BGE-Reranker-V2-M3 (reranking)

### Setup Development Environment

**1. Clone and setup:**

```bash
git clone https://github.com/pocheang/querymind.git
cd querymind

# Create conda environment
conda create -n rag-local python=3.11
conda activate rag-local

# Install dependencies
pip install -e ".[dev]"  # Includes dev dependencies
```

**2. Configure:**

```bash
make config-render ENV=development PROFILE=balanced
```

Local overrides go in `config/env/development.env` (gitignored); the render step prefers it
over the committed `.example`.

**3. Run tests:**

```bash
# All tests
pytest -q

# With coverage
pytest --cov=app tests/
```

No pytest markers are registered, so `-m unit` and friends select nothing. The
frontend has its own suite: `cd frontend && npm test -- --run`.

**4. Code quality:**

```bash
# Linting
ruff check .

# Formatting
ruff format .
```

Type checking is TypeScript-side only (`cd frontend && npm run type-check`); the
Python code is not under mypy and the tool is not a dependency.

### Contributing

We welcome contributions! Please see:

- [Contributing Guide](CONTRIBUTING.md) - How to contribute
- [Development Guide](docs/development/README.md) - Development process and daily logs
- [CLAUDE.md](CLAUDE.md) - Architecture, conventions, and the reasoning behind them

**Before submitting a PR:**
1. Write tests for new features
2. Ensure all tests pass: `pytest -q`
3. Format code: `ruff format .`
4. Update documentation if needed

---

## ⚙️ Configuration

### Configuration Structure

QueryMind uses a centralized configuration system:

```
config/
├── env/                    # Environment-specific configs
│   ├── development.env.example
│   ├── production.env.example
│   └── test.env.example
├── profiles/               # Runtime profiles
│   ├── balanced.env       # Default profile
│   ├── deep.env          # Deep analysis
│   └── fast.env          # Fast response
├── application/           # Application settings
│   ├── router_calibration.json
│   └── web_activity_config.json
└── observability/         # Monitoring configs
    ├── prometheus/
    ├── grafana/
    └── alertmanager/
```

**Configuration Guide:** [config/README.md](config/README.md), and the Configuration System section of [CLAUDE.md](CLAUDE.md).

### Environment Variables

Key environment variables:

```bash
# Only when you want a real model. With MODEL_BACKEND=local, the default, none
# of these is required.
OPENAI_API_KEY=sk-...              # OpenAI API key
# OR
ANTHROPIC_API_KEY=sk-ant-...       # Anthropic API key

# Optional
NEO4J_URI=bolt://localhost:7687    # Neo4j connection
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

REDIS_URL=redis://localhost:6379   # Redis, optional cache backend

# API Settings
API_SETTINGS_ENCRYPTION_KEY=...    # For encrypting stored API keys
```

---

## 📊 Performance

### Targets

These are the thresholds the project holds itself to, not measurements. This
table used to print six figures as though they had been measured; nothing in the
repository backed them, so they are stated as what they are.

| Metric | Target |
|--------|--------|
| Router accuracy | >95% |
| Retrieval Precision@5 | >0.85 |
| Citation completeness | >90% |
| P95 latency, standard query | <5s |

Two things worth knowing before quoting any number:

- Every figure describes the **LLM path**. `MODEL_BACKEND=local`, the default on a
  fresh checkout, has no model in the loop at all — it routes by keyword and
  assembles an answer from the retrieved excerpts. Quality metrics mean nothing
  there.
- Measuring is a first-class operation, not a spreadsheet: `POST /admin/ops/benchmark/run`
  runs the query set at `config/eval/benchmark_queries.txt` (or `data/eval/` if you
  place one there) **under the requesting administrator's identity**, so it measures
  the corpus that administrator can actually see. The shipped set is
  corpus-agnostic: it exercises latency and route branches, but grounding and
  citation figures only mean something once the queries match documents you have
  ingested.

**Timeouts and degradation:** the stage-budget sections of [CLAUDE.md](CLAUDE.md). Stage
ceilings bound a hang; they are not latency targets, which is why they sit well above the
figures here.

---

## 🔒 Security

- **Passwords** — PBKDF2-HMAC-SHA256 at 600,000 iterations (OWASP 2023), per-user salt
- **Sessions** — JWT, with RBAC on every admin surface
- **Stored credentials** — encrypted at rest with `API_SETTINGS_ENCRYPTION_KEY`, which must
  outlive the process: rotating it turns stored credentials from absent into undecryptable
- **User data isolation** — retrieval is *scoped before it runs*, not filtered afterwards. A
  missing access scope raises rather than searching every tenant's corpus, and the store
  checks each chunk's own owner metadata as a second, independent gate
- **Output DLP** — secrets are redacted from finalized answers and from the streamed draft,
  verified at every chunk boundary
- **Logs** — user questions never reach them; a stable digest is logged instead, enforced by
  an AST guard over every logging call
- **Tool selection is blind to retrieved content** — a document cannot talk the model into
  running a tool

These are properties with tests behind them: `tests/security/` holds 154 of the suite's 528.

**Security Policy:** [SECURITY.md](SECURITY.md)

**Report vulnerabilities:** po.cheang@gmail.com

---

## 📝 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Po Cheang**
- Email: po.cheang@gmail.com
- GitHub: [@pocheang](https://github.com/pocheang)

---

## 🙏 Acknowledgments

This project uses open-source technologies:

- [LangChain](https://github.com/langchain-ai/langchain) - LLM application framework
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent orchestration
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [React](https://react.dev/) - Frontend UI library
- [ChromaDB](https://www.trychroma.com/) - Vector database
- [Neo4j](https://neo4j.com/) - Graph database

---

## 📞 Support

- 📖 [Documentation](docs/README.md)
- 🐛 [Issue Tracker](https://github.com/pocheang/querymind/issues)
- 📧 Email: po.cheang@gmail.com

---

## 🗺️ Roadmap

See [CHANGELOG.md](CHANGELOG.md) for version history and [GitHub Issues](https://github.com/pocheang/querymind/issues) for planned features.

**Current Version:** v0.6.2.1  
**Latest Release:** [v0.6.2.1](https://github.com/pocheang/querymind/releases/tag/v0.6.2.1)

---

<p align="center">
  <b>⭐ If you find QueryMind useful, please consider giving it a star! ⭐</b>
</p>
