# Workflow Visual + Low-Code Setup

This project can use:

- `LangGraph Studio` for workflow visualization and debugging.
- `n8n` for low-code orchestration around your API.

## 1) LangGraph Studio (for `app/graph/workflow.py`)

### Prerequisites

- Python 3.11+
- Project dependencies installed (`pip install -e .`)

### Start Studio

From project root:

```bash
langgraph dev
```

This uses [`langgraph.json`](../langgraph.json), which points to:

- graph id: `local_rag_workflow`
- entrypoint: `app.graph.studio_entry:get_graph`

In Studio, run with an input state like:

```json
{
  "question": "请总结系统架构",
  "use_web_fallback": true,
  "use_reasoning": true,
  "memory_context": "",
  "allowed_sources": []
}
```

## 2) n8n (for low-code automation)

### Start services

```bash
docker compose up -d neo4j n8n
```

Open n8n:

- http://localhost:5678

### Suggested minimal n8n flow

1. `Webhook` (POST `/rag-query`)
2. `HTTP Request` (POST `http://host.docker.internal:8000/query`)
3. `Respond to Webhook`

`HTTP Request` body example:

```json
{
  "question": "={{ $json.body.question }}",
  "use_web_fallback": true,
  "use_reasoning": true,
  "session_id": "={{ $json.body.session_id }}"
}
```

If your API requires auth, add header:

```text
Authorization: Bearer <token>
```

## Recommended split of responsibilities

- Keep all core routing/retrieval/synthesis logic in Python LangGraph.
- Use n8n only for surrounding automation:
  - scheduled jobs
  - approvals
  - notifications (email/IM)
  - ticketing integration

