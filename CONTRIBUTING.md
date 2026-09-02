# Contributing to QueryMind

Thank you for your interest in contributing to QueryMind! This document provides guidelines and instructions for contributing.

---

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Commit Message Guidelines](#commit-message-guidelines)
- [Pull Request Process](#pull-request-process)
- [Documentation](#documentation)
- [Community](#community)

---

## 📜 Code of Conduct

By participating in this project, you agree to maintain a respectful, inclusive, and collaborative environment. Be considerate, professional, and constructive in all interactions.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Git
- Conda (recommended)
- Basic knowledge of FastAPI, React, and LangChain

### Setup Development Environment

1. **Fork and clone the repository:**

```bash
git clone https://github.com/YOUR_USERNAME/querymind.git
cd querymind
```

2. **Create development environment:**

```bash
# Create conda environment
conda create -n rag-local python=3.11
conda activate rag-local

# Install dependencies (including dev dependencies)
pip install -e ".[dev]"
```

3. **Configure environment:**

```bash
# Copy development config
cp config/env/development.env.example .env

# Edit .env with your API keys and settings
```

4. **Initialize database:**

```bash
python scripts/init_db.py
```

5. **Verify installation:**

```bash
# Run tests
pytest -q

# Check code style
ruff check .
```

---

## 🔄 Development Workflow

### 1. Create a Feature Branch

```bash
# Update main branch
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/amazing-feature
# or
git checkout -b fix/bug-description
```

**Branch Naming Conventions:**
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions or modifications
- `chore/` - Maintenance tasks

### 2. Make Your Changes

- Write clean, readable code
- Follow existing code style
- Add tests for new features
- Update documentation as needed

### 3. Test Your Changes

```bash
# Run all tests
pytest -q

# Run with coverage
pytest --cov=app tests/

# Linting and formatting
ruff check .
ruff format --check .

# Formatting
ruff format .
```

### 4. Commit Your Changes

```bash
git add .
git commit -m "feat: add amazing feature"
```

See [Commit Message Guidelines](#commit-message-guidelines) for details.

### 5. Push and Create Pull Request

```bash
git push origin feature/amazing-feature
```

Then create a Pull Request on GitHub.

---

## 📝 Coding Standards

### Python Code Style

We use **Ruff** for linting and formatting:

```bash
# Format code
ruff format .

# Check linting
ruff check .

# Auto-fix issues
ruff check --fix .
```

**Key Principles:**
- Follow PEP 8
- Maximum line length: 100 characters
- Use type hints for function signatures
- Write docstrings for public functions/classes
- Keep functions focused and small (<50 lines)

**Example:**

```python
def process_query(query: str, top_k: int = 10) -> list[Document]:
    """
    Process a user query and return relevant documents.

    Args:
        query: The user's query string
        top_k: Number of top documents to return (default: 10)

    Returns:
        List of relevant Document objects

    Raises:
        ValueError: If query is empty or top_k is invalid
    """
    if not query:
        raise ValueError("Query cannot be empty")
    
    # Implementation...
    return documents
```

### TypeScript/JavaScript Code Style

We use **ESLint** and **Prettier**:

```bash
cd frontend

# Format code
npm run format

# Check linting
npm run lint

# Auto-fix issues
npm run lint:fix
```

**Key Principles:**
- Use TypeScript for type safety
- Functional components with hooks
- Avoid `any` types - use proper types
- Use meaningful variable names
- Keep components small and focused

---

## 🧪 Testing Guidelines

### Test Structure

```
tests/
├── unit/              # Unit tests (isolated functions)
├── integration/       # Integration tests (multiple components)
├── performance/       # Performance benchmarks
└── fixtures/          # Test data and fixtures
```

### Writing Tests

**Unit Test Example:**

```python
import pytest
from app.agents.router_agent import RouterAgent

def test_router_classifies_query_correctly():
    """Test that router correctly classifies query type."""
    agent = RouterAgent()
    
    query = "What is the capital of France?"
    result = agent.classify(query)
    
    assert result.route == "vector"
    assert result.confidence > 0.8
```

**Integration Test Example:**

```python
import pytest
from fastapi.testclient import TestClient
from app.api.main import app

@pytest.mark.integration
def test_query_endpoint_returns_valid_response():
    """Test end-to-end query processing."""
    client = TestClient(app)
    
    response = client.post(
        "/api/query",
        json={"query": "What is RAG?"}
    )
    
    assert response.status_code == 200
    assert "answer" in response.json()
    assert "citations" in response.json()
```

### Test Requirements

- ✅ All new features must include tests
- ✅ Bug fixes must include regression tests
- ✅ Land each fix with the regression test that would have caught it
- ✅ Tests must pass before PR can be merged
- ✅ Use meaningful test names that describe behavior

---

## 💬 Commit Message Guidelines

We follow the **Conventional Commits** specification:

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation changes
- `style` - Code style changes (formatting, no logic change)
- `refactor` - Code refactoring (no feature change)
- `test` - Adding or updating tests
- `chore` - Maintenance tasks (dependencies, build config)
- `perf` - Performance improvements
- `ci` - CI/CD configuration changes

### Examples

```bash
# Feature
feat(agents): add graph RAG agent for entity queries

Add new GraphRAGAgent that queries Neo4j for entity relationships.
Includes Cypher query generation and result parsing.

Closes #123

# Bug fix
fix(api): handle empty query string gracefully

Previously crashed with ValueError. Now returns 400 with error message.

# Documentation
docs(readme): update installation instructions for Python 3.11

# Refactor
refactor(retrieval): extract common retrieval logic to base class

# Breaking change
feat(api)!: change response format to include metadata

BREAKING CHANGE: API responses now include metadata field.
Update clients to handle new format.
```

### Guidelines

- Use imperative mood: "add" not "added" or "adds"
- First line ≤72 characters
- Provide context in body if needed
- Reference issues: "Closes #123" or "Fixes #456"
- Mark breaking changes with `!` and `BREAKING CHANGE:` in footer

---

## 🔀 Pull Request Process

### Before Submitting

- [ ] Code follows style guidelines
- [ ] All tests pass (`pytest -q`)
- [ ] Added tests for new features
- [ ] Documentation updated (if needed)
- [ ] Commit messages follow guidelines
- [ ] No merge conflicts with main branch

### PR Title

Use the same format as commit messages:

```
feat(agents): add graph RAG agent
fix(api): handle empty query string
docs(contributing): clarify testing guidelines
```

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe how you tested your changes

## Checklist
- [ ] Tests pass locally
- [ ] Added tests for new features
- [ ] Documentation updated
- [ ] Follows code style guidelines
```

### Review Process

1. Automated checks run (tests, linting)
2. At least one maintainer reviews code
3. Address review feedback
4. Maintainer approves and merges

### After Merge

- Delete your feature branch
- Update your local main branch
- Celebrate! 🎉

---

## 📚 Documentation

### When to Update Documentation

Update documentation when you:

- Add new features or APIs
- Change existing behavior
- Fix bugs that affect usage
- Add new configuration options

### Documentation Structure

```
docs/
├── getting-started/   # Installation, setup
├── user-guide/        # End-user guides
├── architecture/      # System design
├── development/       # Developer guides
├── operations/        # Deployment, ops
└── reference/         # API, config docs
```

### Writing Documentation

- Use clear, concise language
- Include code examples
- Add screenshots for UI features
- Keep consistent formatting
- Update table of contents

**Documentation Guide:** [docs/README.md](docs/README.md), and the daily-log convention in [CLAUDE.md](CLAUDE.md).

---

## 👥 Community

### Communication Channels

- **GitHub Issues** - Bug reports, feature requests
- **GitHub Discussions** - General questions, ideas
- **Pull Requests** - Code contributions
- **Email** - po.cheang@gmail.com (security issues)

### Getting Help

- Read [CLAUDE.md](CLAUDE.md), which describes how the system works today
- Search existing [GitHub Issues](https://github.com/pocheang/querymind/issues)
- Ask in [GitHub Discussions](https://github.com/pocheang/querymind/discussions)

### Code Review

All contributions go through code review. Reviewers will:

- Check code quality and style
- Verify tests pass
- Suggest improvements
- Ensure documentation is updated

Be patient and responsive to feedback!

---

## 🏆 Recognition

Contributors are recognized in:

- GitHub contributors page
- Release notes (for significant contributions)
- Special thanks in documentation

---

## 📜 License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).

---

## ❓ Questions?

If you have questions about contributing:

1. Check this guide first
2. Search [GitHub Issues](https://github.com/pocheang/querymind/issues)
3. Ask in [GitHub Discussions](https://github.com/pocheang/querymind/discussions)
4. Email: po.cheang@gmail.com

---

Thank you for contributing to QueryMind! 🎉

**Together, we're building the future of intelligent knowledge retrieval.**
