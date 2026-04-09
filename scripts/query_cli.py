import argparse
import json

from app.graph.workflow import run_query


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("question", type=str)
    parser.add_argument("--no-web", action="store_true")
    parser.add_argument("--no-reasoning", action="store_true")
    parser.add_argument("--retrieval-strategy", type=str, default="")
    args = parser.parse_args()

    kwargs = {
        "use_web_fallback": not args.no_web,
        "use_reasoning": not args.no_reasoning,
    }
    if str(args.retrieval_strategy or "").strip():
        kwargs["retrieval_strategy"] = str(args.retrieval_strategy).strip().lower()
    result = run_query(args.question, **kwargs)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
