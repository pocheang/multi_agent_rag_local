# Testing

Validation guidance for contributors.

- Run unit tests with `pytest -m unit`.
- Run integration tests with `pytest -m integration`.
- Run the complete suite with `pytest tests/ -v`.
- Build the frontend with `npm --prefix frontend run build`.
- Mock external LLM calls in unit tests and record integration prerequisites.

See [development workflow](workflow.md) for the required checks before a pull
request.
