# RAG Diagnostics

Capture query, tenant/user, request ID, expected sources/answer, actual result, timing, provider/model, profile, data/index version, and last known good.

Trace the first failing stage:

1. ingestion, parsing, chunking, embedding, index write;
2. tenant/document filters, expansion, vector/BM25/graph retrieval;
3. fusion, reranking, routing, agent/tool;
4. synthesis, grounding, citations, streaming/API/frontend.

Form one hypothesis and run a discriminating test. Add a regression/golden-set case. Validate correctness, isolation, recall/precision or groundedness, latency, and fallback.

Useful paths: `app/ingestion/`, `app/retrievers/`, `app/graph/`, `app/agents/`, `scripts/eval_retrieval.py`, `scripts/eval_rag_ragas.py`.

Do not clear indexes, reset graphs, delete data, disable tenant filters, or restart dependencies as the first step.
