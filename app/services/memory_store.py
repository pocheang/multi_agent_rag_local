import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings

try:
    from rank_bm25 import BM25Okapi
except Exception:  # pragma: no cover - dependency fallback
    BM25Okapi = None  # type: ignore[assignment]

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\\-]+|[\\u4e00-\\u9fff]")


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall((text or "").lower())

SHORT_TERM_ROUNDS = 3
LONG_TERM_WINDOW_SIZE = 20
LONG_TERM_TOP_N = 5
LONG_TERM_RETRIEVAL_TOP_K = 3
LONG_TERM_FALLBACK_K = 2


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def score_memory_candidate(answer: str, signals: dict[str, Any] | None = None) -> tuple[float, dict[str, Any]]:
    payload = signals or {}
    vector_retrieved = min(_normalize_int(payload.get("vector_retrieved")), 3)
    citation_count = min(_normalize_int(payload.get("citation_count")), 4)
    web_used = _normalize_bool(payload.get("web_used"))
    answer_len = min(len((answer or "").strip()), 600)

    score = (
        0.35 * (vector_retrieved / 3)
        + 0.30 * (citation_count / 4)
        + 0.20 * (0.0 if web_used else 1.0)
        + 0.15 * (answer_len / 600)
    )
    normalized_signals = {
        "vector_retrieved": vector_retrieved,
        "citation_count": citation_count,
        "web_used": web_used,
        "route": str(payload.get("route", "")),
        "reason": str(payload.get("reason", "")),
    }
    return round(float(score), 6), normalized_signals


def _is_candidate_answer_usable(answer: str, signals: dict[str, Any] | None = None) -> bool:
    text = (answer or "").strip()
    if len(text) < 20:
        return False
    payload = signals or {}
    reason = str(payload.get("reason", "")).strip().lower()
    if "pdf_agent_" in reason:
        return False
    return True


def _pair_user_assistant_rounds(messages: list[dict[str, Any]]) -> list[tuple[str, str]]:
    rounds: list[tuple[str, str]] = []
    pending_user: str | None = None
    for msg in messages:
        role = str(msg.get("role", "")).strip().lower()
        content = str(msg.get("content", "")).strip()
        if not content:
            continue
        if role == "user":
            pending_user = content
            continue
        if role == "assistant" and pending_user:
            rounds.append((pending_user, content))
            pending_user = None
    return rounds


def build_short_term_memory_context(messages: list[dict[str, Any]], rounds: int = SHORT_TERM_ROUNDS) -> str:
    if rounds <= 0:
        return ""
    paired = _pair_user_assistant_rounds(messages)
    if not paired:
        return ""
    recent = paired[-rounds:]
    blocks: list[str] = []
    for idx, (question, answer) in enumerate(recent, start=1):
        blocks.append(f"[Round {idx}]\nQ: {question}\nA: {answer}")
    return "Short-term memory (latest rounds):\n" + "\n\n".join(blocks)


def retrieve_relevant_long_term_memories(
    question: str,
    memories: list[dict[str, Any]],
    top_k: int = LONG_TERM_RETRIEVAL_TOP_K,
    fallback_k: int = LONG_TERM_FALLBACK_K,
) -> list[dict[str, Any]]:
    active = [m for m in memories if not m.get("deleted")]
    if not active:
        return []

    query_tokens = tokenize(question)
    docs = [f"{m.get('question', '')}\n{m.get('answer', '')}" for m in active]
    tokenized = [tokenize(d) for d in docs]

    ranked_indexes: list[int] = []
    if query_tokens and any(tokenized):
        if BM25Okapi is not None:
            bm25 = BM25Okapi(tokenized)
            scores = bm25.get_scores(query_tokens)
            ranked = sorted(
                ((idx, float(score)) for idx, score in enumerate(scores) if float(score) > 0),
                key=lambda x: x[1],
                reverse=True,
            )
            ranked_indexes = [idx for idx, _score in ranked[: max(1, top_k)]]
        else:
            query_set = set(query_tokens)
            overlap_scores = []
            for idx, doc_tokens in enumerate(tokenized):
                score = len(query_set.intersection(set(doc_tokens)))
                if score > 0:
                    overlap_scores.append((idx, float(score)))
            overlap_scores.sort(key=lambda x: x[1], reverse=True)
            ranked_indexes = [idx for idx, _score in overlap_scores[: max(1, top_k)]]

    if ranked_indexes:
        return [active[idx] for idx in ranked_indexes]

    by_recency = sorted(active, key=lambda x: x.get("created_at", ""), reverse=True)
    return by_recency[: max(1, fallback_k)]


def build_long_term_memory_context(
    question: str,
    long_term_memories: list[dict[str, Any]],
    top_k: int = LONG_TERM_RETRIEVAL_TOP_K,
    fallback_k: int = LONG_TERM_FALLBACK_K,
) -> str:
    selected = retrieve_relevant_long_term_memories(question, long_term_memories, top_k=top_k, fallback_k=fallback_k)
    if not selected:
        return ""

    blocks: list[str] = []
    for idx, item in enumerate(selected, start=1):
        score = float(item.get("score", 0.0) or 0.0)
        blocks.append(
            f"[Memory {idx}] score={score:.3f}\n"
            f"Q: {item.get('question', '')}\n"
            f"A: {item.get('answer', '')}"
        )
    return "Long-term memory (selected):\n" + "\n\n".join(blocks)


def build_memory_context(
    question: str,
    session_messages: list[dict[str, Any]],
    long_term_memories: list[dict[str, Any]],
) -> str:
    short_term = build_short_term_memory_context(session_messages, rounds=SHORT_TERM_ROUNDS)
    long_term = build_long_term_memory_context(
        question=question,
        long_term_memories=long_term_memories,
        top_k=LONG_TERM_RETRIEVAL_TOP_K,
        fallback_k=LONG_TERM_FALLBACK_K,
    )
    parts = [part for part in [short_term, long_term] if part]
    return "\n\n".join(parts)


class MemoryStore:
    def __init__(self, base_dir: Path | None = None):
        settings = get_settings()
        self.base_dir = base_dir or (settings.sessions_path / "_long_memory")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_session_payload(self, session_id: str) -> dict[str, Any]:
        path = self.base_dir / f"{session_id}.json"
        if not path.exists():
            return self._new_payload(session_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("session_id", session_id)
        data.setdefault("updated_at", _now_iso())
        data.setdefault("candidates", [])
        data.setdefault("long_term_ids", [])
        return data

    def list_long_term(self, session_id: str) -> list[dict[str, Any]]:
        data = self.get_session_payload(session_id)
        valid = {
            str(item.get("candidate_id")): item
            for item in data.get("candidates", [])
            if item.get("candidate_id") and not item.get("deleted")
        }
        out: list[dict[str, Any]] = []
        for candidate_id in data.get("long_term_ids", []):
            item = valid.get(str(candidate_id))
            if item is not None:
                out.append(item)
        return out

    def add_candidate(self, session_id: str, question: str, answer: str, signals: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if not _is_candidate_answer_usable(answer, signals):
            return None
        score, normalized_signals = score_memory_candidate(answer=answer, signals=signals)
        now = _now_iso()
        candidate = {
            "candidate_id": uuid.uuid4().hex,
            "question": (question or "").strip(),
            "answer": (answer or "").strip(),
            "score": score,
            "signals": normalized_signals,
            "created_at": now,
            "deleted": False,
        }

        data = self.get_session_payload(session_id)
        data.setdefault("candidates", []).append(candidate)
        data["candidates"] = sorted(data.get("candidates", []), key=lambda x: x.get("created_at", ""), reverse=True)[
            :LONG_TERM_WINDOW_SIZE
        ]
        data["updated_at"] = now
        self._recompute_long_term_ids(data)
        self._write(session_id, data)
        return candidate

    def delete_long_term(self, session_id: str, candidate_id: str) -> bool:
        data = self.get_session_payload(session_id)
        hit = False
        for item in data.get("candidates", []):
            if str(item.get("candidate_id")) != candidate_id:
                continue
            if item.get("deleted"):
                return False
            item["deleted"] = True
            hit = True
            break
        if not hit:
            return False
        data["updated_at"] = _now_iso()
        self._recompute_long_term_ids(data)
        self._write(session_id, data)
        return True

    @staticmethod
    def _new_payload(session_id: str) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "updated_at": _now_iso(),
            "candidates": [],
            "long_term_ids": [],
        }

    def _write(self, session_id: str, payload: dict[str, Any]) -> None:
        path = self.base_dir / f"{session_id}.json"
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)

    @staticmethod
    def _recompute_long_term_ids(payload: dict[str, Any]) -> None:
        candidates = [x for x in payload.get("candidates", []) if not x.get("deleted")]
        ranked = sorted(
            candidates,
            key=lambda x: (float(x.get("score", 0.0) or 0.0), x.get("created_at", "")),
            reverse=True,
        )
        payload["long_term_ids"] = [str(item.get("candidate_id")) for item in ranked[:LONG_TERM_TOP_N] if item.get("candidate_id")]
