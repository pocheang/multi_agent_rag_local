# CI Quality Report

- title: runtime_unavailable
- dataset: data/eval/retrieval_eval.jsonl
- strategy: default

```json
{
  "ok": false,
  "reason": "runtime_unavailable",
  "payload": {
    "total": 0,
    "hit": 0,
    "recall_at_k": 0.0,
    "error": "retrieval_runtime_unavailable:RuntimeDependencyError",
    "detail": "Redis connection failed: Error 10061 connecting to localhost:6379. No connection could be made because the target machine actively refused it.\nTraceback (most recent call last):\n  File \"C:\\Users\\pocheang\\Desktop\\llm\\multi_agent_rag_local_v4\\scripts\\eval_retrieval.py\", line 111, in <module>\n    main()\n    ~~~~^^\n  File \"C:\\Users\\pocheang\\Desktop\\llm\\multi_agent_rag_local_v4\\scripts\\eval_retrieval.py\", line 107, in main\n    print(json.dumps(evaluate(cases, retrieval_strategy=strategy), ensure_asci"
  }
}
```
