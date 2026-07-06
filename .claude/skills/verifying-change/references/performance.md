# Performance and Capacity

Define journey, workload/data size, concurrency, environment, SLO, budget, and baseline. Record hardware, model/provider, cache, warmup, and sample count.

Measure end-to-end and decompose API, queue, retrieval, reranking, model/tool, storage, network, and frontend. Use profiles/traces before optimizing. Change one major variable per experiment.

Report p50/p95/p99, throughput, errors/timeouts, saturation, cost, peak/burst/degraded behavior, recovery, capacity headroom, scaling trigger, and failure limit.

Use `scripts/benchmark_pipeline.py`, `scripts/benchmark_optimization.py`, and `tests/performance/` where relevant. Hold RAG data constant and verify quality/security did not regress.
