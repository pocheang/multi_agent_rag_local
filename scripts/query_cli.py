import argparse
import json
from collections.abc import Mapping

from app.pipeline.contracts import PipelineRequest
from app.pipeline.profiles import PipelineProfile
from app.pipeline.rag_pipeline import RAGPipeline


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
    pipeline_result = RAGPipeline().execute_sync(
        PipelineRequest(
            question=args.question,
            profile=PipelineProfile.STANDARD,
            **kwargs,
        )
    )
    result = pipeline_result.execution_metadata.get("compatibility_payload")
    if not isinstance(result, Mapping):
        raise RuntimeError("standard pipeline did not provide its compatibility payload")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
