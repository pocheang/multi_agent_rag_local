# QueryMind（智询）

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Release](https://img.shields.io/badge/release-v0.6.2.1-green.svg)](https://github.com/pocheang/querymind/releases)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

**Enterprise-grade Agentic RAG system for private knowledge bases**  
Built with FastAPI, React, LangGraph, and hybrid retrieval

---

## ✨ Features

### Multi-Agent Orchestration
- 🎯 **11 Specialized Agents** - Router, Vector RAG, Graph RAG, ReAct, Web Research, Quality Assurance
- 🔄 **LangGraph Workflow** - Stateful execution with conditional routing and retry logic
- 🎨 **Adaptive Planning** - Dynamic strategy selection based on query complexity

### Advanced Retrieval
- 🔍 **Hybrid Search** - Vector (BGE-M3) + BM25 + RRF fusion
- 📊 **Graph RAG** - Neo4j knowledge graph for entity relationship queries
- 🔁 **Reranking** - BGE-Reranker-V2-M3 for precision optimization
- 🌐 **Web Fallback** - External search when local knowledge insufficient

### Quality Assurance
- ✅ **5-Layer Defense** - Route validation, retrieval quality, answer validation, score fusion, context tracking
- 📝 **Citation-First** - Every claim backed by source references `[doc_id:page]`
- 🛡️ **Hallucination Detection** - Pattern-based checks for dates, numbers, entities
- 📈 **Quality Metrics** - Router accuracy 99%, hallucination rate <10%, citation completeness 96%

### Production Ready
- 🔐 **Security** - JWT authentication, RBAC, encrypted API keys
- 📊 **Monitoring** - Prometheus metrics, Grafana dashboards, structured logging
- 🐳 **Docker Support** - One-command deployment with health checks
- ⚙️ **Configuration Governance** - Centralized config in `config/`, runtime profiles

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for frontend)
- **Conda** (recommended for environment management)
- **PostgreSQL** (for user/session management)
- **Neo4j** (optional, for Graph RAG)

### Docker Deployment (Recommended)

```bash
# 1. Set your API key
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

**3. Configure environment:**

```bash
# Copy template
cp config/env/development.env.example .env

# Edit .env with your API keys
# Required: OPENAI_API_KEY or ANTHROPIC_API_KEY
# Optional: NEO4J_URI, REDIS_URL
```

**4. Initialize database:**

```bash
python scripts/init_db.py
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

### Documentation Structure
```
docs/
├── getting-started/      # Installation and setup
├── user-guide/          # End-user guides
├── architecture/        # System design and architecture
├── features/            # Feature-specific guides
├── development/         # Developer documentation
├── operations/          # Deployment and operations
├── reference/           # API, configuration, FAQ
├── releases/            # Release notes and history
└── zh-CN/               # Chinese documentation
```

**Full Documentation:** [docs/README.md](docs/README.md)

---

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                       User Interface                         │
│                    (React + TypeScript)                      │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/SSE
┌────────────────────▼────────────────────────────────────────┐
│                    FastAPI Backend                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            LangGraph State Machine                   │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │  Router Agent → Route Validator Agent       │    │   │
│  │  └──────────────┬──────────────────────────────┘    │   │
│  │                 │                                    │   │
│  │  ┌──────────────▼──────────────────────────────┐    │   │
│  │  │  Retrieval Layer (4 agents)                 │    │   │
│  │  │  • Vector RAG  • Graph RAG                  │    │   │
│  │  │  • ReAct       • Web Research               │    │   │
│  │  └──────────────┬──────────────────────────────┘    │   │
│  │                 │                                    │   │
│  │  ┌──────────────▼──────────────────────────────┐    │   │
│  │  │  Quality Assurance (5 agents)               │    │   │
│  │  │  • Retrieval Quality  • Answer Validator    │    │   │
│  │  │  • Context Tracker    • Quality Orchestrator│    │   │
│  │  │  • Synthesis Agent                          │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │
    ┌────────────────┼────────────────┐
    │                │                │
┌───▼────┐    ┌─────▼─────┐    ┌────▼─────┐
│ChromaDB│    │PostgreSQL │    │  Neo4j   │
│(Vector)│    │  (Users)  │    │ (Graph)  │
└────────┘    └───────────┘    └──────────┘
```

### Key Components

- **11 Specialized Agents** - Each with specific responsibilities
- **LangGraph State Machine** - Orchestrates multi-agent workflow
- **Hybrid Retrieval** - Vector + BM25 + Graph search
- **Quality Assurance** - 5-layer validation and scoring
- **Configuration Governance** - Centralized `config/` directory

**Detailed Architecture:** [CLAUDE.md](CLAUDE.md) — kept current with the code rather than alongside it.

---

## 🛠️ Development

### Tech Stack

**Backend:**
- FastAPI 0.109+ (API framework)
- LangGraph 0.0.20+ (Agent orchestration)
- LangChain 0.1.0+ (LLM integration)
- ChromaDB 0.4.18+ (Vector store)
- Neo4j 5.0+ (Graph database, optional)
- PostgreSQL 14+ (User/session management)

**Frontend:**
- React 18.2+
- TypeScript 5.0+
- Vite 5.0+
- Ant Design 5.0+

**AI Models:**
- OpenAI GPT-4/GPT-5
- Anthropic Claude Opus/Sonnet
- Sentence-Transformers (embeddings)
- BGE-Reranker (reranking)

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
# Copy development config
cp config/env/development.env.example .env

# Edit .env with your settings
```

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
# Required
OPENAI_API_KEY=sk-...              # OpenAI API key
# OR
ANTHROPIC_API_KEY=sk-ant-...       # Anthropic API key

# Optional
NEO4J_URI=bolt://localhost:7687    # Neo4j connection
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

POSTGRES_URL=postgresql://...      # PostgreSQL connection
REDIS_URL=redis://localhost:6379   # Redis (optional)

# API Settings
API_SETTINGS_ENCRYPTION_KEY=...    # For encrypting stored API keys
```

---

## 📊 Performance

### Benchmarks (v0.6.0)

| Metric | Value | Target |
|--------|-------|--------|
| Router Accuracy | 99.0% | >98% ✅ |
| Retrieval Precision@5 | 92.7% | >90% ✅ |
| Hallucination Rate | 8.0% | <10% ✅ |
| Citation Completeness | 96.0% | >95% ✅ |
| P95 Latency | 3.8s | <4s ✅ |
| System Availability | 99.8% | >99.5% ✅ |

**Performance Guide:** see the Quality Metrics and stage-timeout sections of [CLAUDE.md](CLAUDE.md).

---

## 🔒 Security

- ✅ No hardcoded secrets
- ✅ Environment-based configuration
- ✅ JWT authentication with bcrypt
- ✅ RBAC (Role-Based Access Control)
- ✅ API key encryption
- ✅ Input validation and sanitization
- ✅ CORS protection

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
