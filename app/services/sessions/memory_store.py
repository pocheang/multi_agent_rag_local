import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.domain.knowledge import MemoryItem
from app.memory.resolver import MemoryResolver
from app.services.sessions.history import validate_session_id

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover - dependency fallback
    BM25Okapi = None  # type: ignore[assignment]

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\\-]+|[\\u4e00-\\u9fff]")


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall((text or "").lower())


SHORT_TERM_ROUNDS = 3
LONG_TERM_WINDOW_SIZE = 20
LONG_TERM_TOP_N = 5
LONG_TERM_RETRIEVAL_TOP_K = 3
LONG_TERM_FALLBACK_K = 2
GLOBAL_MEMORY_SESSION_ID = "_global"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (ValueError, TypeError):
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
    docs = [str(m.get("content") or f"{m.get('question', '')}\n{m.get('answer', '')}") for m in active]
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
        content = str(item.get("content", "") or "").strip()
        if content:
            blocks.append(f"[Memory {idx}] kind={item.get('kind', 'unknown')} score={score:.3f}\n{content}")
        else:
            blocks.append(
                f"[Memory {idx}] score={score:.3f}\nQ: {item.get('question', '')}\nA: {item.get('answer', '')}"
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
        self.settings = settings
        self.base_dir = base_dir or (settings.sessions_path / "_long_memory")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.resolver = MemoryResolver(settings)

    def get_session_payload(self, session_id: str) -> dict[str, Any]:
        session_id = validate_session_id(session_id)
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
        session_id = validate_session_id(session_id)
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
        if session_id == GLOBAL_MEMORY_SESSION_ID:
            return out
        global_rows = self.list_global()
        row_map = {str(row.get("candidate_id")): row for row in (*global_rows, *out)}
        session_items = tuple(item for row in out if (item := memory_item_from_row(row)) is not None)
        global_items = tuple(item for row in global_rows if (item := memory_item_from_row(row)) is not None)
        resolution = self.resolver.resolve((), (*global_items, *session_items))
        structured = [row_map[item.memory_id] for item in resolution.items if item.memory_id in row_map]
        legacy = [row for row in out if memory_item_from_row(row) is None]
        return [*structured, *legacy][:LONG_TERM_TOP_N]

    def list_global(self) -> list[dict[str, Any]]:
        data = self.get_session_payload(GLOBAL_MEMORY_SESSION_ID)
        return [
            item
            for item in data.get("candidates", [])
            if item.get("candidate_id") and not item.get("deleted")
        ]

    def add_candidate(
        self, session_id: str, question: str, answer: str, signals: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        session_id = validate_session_id(session_id)
        proposed = self.resolver.propose(question, source_session_id=session_id)
        if proposed is None:
            return None
        score, normalized_signals = score_memory_candidate(answer=answer, signals=signals)
        score = max(score, {"explicit_remember": 1.0, "preference": 0.9, "stable_fact": 0.85, "task": 0.8}[proposed.kind])
        now = _now_iso()
        candidate = {
            "candidate_id": proposed.memory_id,
            "question": (question or "").strip(),
            "answer": proposed.content,
            "content": proposed.content,
            "kind": proposed.kind,
            "memory_key": proposed.memory_key,
            "score": score,
            "signals": normalized_signals,
            "created_at": now,
            "updated_at": proposed.updated_at,
            "expires_at": proposed.expires_at,
            "supersedes": proposed.supersedes,
            "source_session_id": session_id,
            "deleted": False,
        }

        candidate = self._upsert_global(candidate)
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
        session_id = validate_session_id(session_id)
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
        if session_id != GLOBAL_MEMORY_SESSION_ID:
            self._expire_in_payload(GLOBAL_MEMORY_SESSION_ID, candidate_id)
        return True

    def upsert_memory(self, item: MemoryItem) -> MemoryItem:
        normalized = self.resolver.normalize_item(item)
        candidate = _candidate_from_memory(normalized)
        canonical = self._upsert_global(candidate)
        return memory_item_from_row(canonical) or normalized

    def expire_memory(self, memory_id: str) -> bool:
        return self._expire_in_payload(GLOBAL_MEMORY_SESSION_ID, memory_id)

    @staticmethod
    def _new_payload(session_id: str) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "updated_at": _now_iso(),
            "candidates": [],
            "long_term_ids": [],
        }

    def _write(self, session_id: str, payload: dict[str, Any]) -> None:
        session_id = validate_session_id(session_id)
        path = self.base_dir / f"{session_id}.json"
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)

    def _upsert_global(self, candidate: dict[str, Any]) -> dict[str, Any]:
        data = self.get_session_payload(GLOBAL_MEMORY_SESSION_ID)
        memory_key = str(candidate.get("memory_key", "") or "")
        for existing in data.get("candidates", []):
            if existing.get("deleted") or not memory_key or str(existing.get("memory_key", "")) != memory_key:
                continue
            if _normalized_memory_content(existing) == _normalized_memory_content(candidate):
                existing["updated_at"] = candidate.get("updated_at")
                existing["source_session_id"] = candidate.get("source_session_id")
                self._recompute_long_term_ids(data)
                self._write(GLOBAL_MEMORY_SESSION_ID, data)
                return dict(existing)
            existing["deleted"] = True
            candidate["supersedes"] = existing.get("candidate_id")
        data.setdefault("candidates", []).append(dict(candidate))
        data["candidates"] = sorted(
            data.get("candidates", []),
            key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""),
            reverse=True,
        )[: self.settings.long_term_memory_max_items]
        data["updated_at"] = _now_iso()
        self._recompute_long_term_ids(data)
        self._write(GLOBAL_MEMORY_SESSION_ID, data)
        return dict(candidate)

    def _expire_in_payload(self, session_id: str, memory_id: str) -> bool:
        data = self.get_session_payload(session_id)
        found = False
        for item in data.get("candidates", []):
            if str(item.get("candidate_id")) == memory_id and not item.get("deleted"):
                item["deleted"] = True
                found = True
        if found:
            data["updated_at"] = _now_iso()
            self._recompute_long_term_ids(data)
            self._write(session_id, data)
        return found

    @staticmethod
    def _recompute_long_term_ids(payload: dict[str, Any]) -> None:
        candidates = [x for x in payload.get("candidates", []) if not x.get("deleted")]
        ranked = sorted(
            candidates,
            key=lambda x: (float(x.get("score", 0.0) or 0.0), x.get("created_at", "")),
            reverse=True,
        )
        payload["long_term_ids"] = [
            str(item.get("candidate_id")) for item in ranked[:LONG_TERM_TOP_N] if item.get("candidate_id")
        ]


def memory_item_from_row(row: dict[str, Any]) -> MemoryItem | None:
    memory_id = str(row.get("candidate_id", "") or "").strip()
    content = str(row.get("content") or row.get("answer") or "").strip()
    kind = str(row.get("kind", "") or "").strip()
    if not memory_id or not content or kind not in {"preference", "stable_fact", "task", "explicit_remember"}:
        return None
    try:
        return MemoryItem(
            memory_id=memory_id,
            kind=kind,
            content=content,
            memory_key=str(row.get("memory_key", "") or ""),
            updated_at=str(row.get("updated_at") or row.get("created_at") or _now_iso()),
            expires_at=str(row.get("expires_at")) if row.get("expires_at") else None,
            supersedes=str(row.get("supersedes")) if row.get("supersedes") else None,
            source_session_id=str(row.get("source_session_id")) if row.get("source_session_id") else None,
        )
    except (TypeError, ValueError):
        return None


def _candidate_from_memory(item: MemoryItem) -> dict[str, Any]:
    return {
        "candidate_id": item.memory_id,
        "question": "",
        "answer": item.content,
        "content": item.content,
        "kind": item.kind,
        "memory_key": item.memory_key,
        "score": 1.0,
        "signals": {"reason": "governed_memory_upsert"},
        "created_at": item.updated_at,
        "updated_at": item.updated_at,
        "expires_at": item.expires_at,
        "supersedes": item.supersedes,
        "source_session_id": item.source_session_id,
        "deleted": False,
    }


def _normalized_memory_content(row: dict[str, Any]) -> str:
    return " ".join(str(row.get("content") or row.get("answer") or "").casefold().split())


__all__ = [
    "MemoryStore",
    "build_long_term_memory_context",
    "build_memory_context",
    "build_short_term_memory_context",
    "memory_item_from_row",
    "retrieve_relevant_long_term_memories",
    "score_memory_candidate",
]
