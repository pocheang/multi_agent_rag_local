import argparse
import json

from app.graph.workflow import run_query


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("question", type=str)
    parser.add_argument("--no-web", action="store_true")
    parser.add_argument("--no-reasoning", action="store_true")
    args = parser.parse_args()

    result = run_query(args.question, use_web_fallback=not args.no_web, use_reasoning=not args.no_reasoning)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
