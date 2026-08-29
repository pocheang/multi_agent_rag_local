"""Authorized context assembly with deterministic conflict precedence."""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.contracts import EvidenceItem
from app.domain.knowledge import AccessScope
from app.domain.workflow import ContextBundle
from app.privacy.dlp import mask_evidence

_LAYER_PRIORITY = {
    "evidence": 0,
    "knowledge": 1,
    "current_context": 2,
    "memory": 3,
    "web": 4,
    "tool": 4,
}


class ContextBuilder:
    """Apply access controls before conflict resolution and token truncation."""

    def __init__(self, *, token_budget: int) -> None:
        if token_budget < 1:
            raise ValueError("token_budget must be positive")
        self._token_budget = token_budget

    def build(
        self,
        items: Iterable[EvidenceItem],
        scope: AccessScope,
        *,
        diagnostics: dict[str, object] | None = None,
    ) -> ContextBundle:
        raw = tuple(items)
        authorized = tuple(masked for item in raw if (masked := mask_evidence(item, scope)) is not None)
        resolved, conflict_notes = _resolve_conflicts(authorized)
        bounded, truncated = _truncate(resolved, self._token_budget)
        rendered = "\n\n".join(_render_item(index, item) for index, item in enumerate(bounded, start=1))
        merged_diagnostics = dict(diagnostics or {})
        merged_diagnostics.update(
            {
                "context_input_count": len(raw),
                "context_authorized_count": len(authorized),
                "context_scope_dropped": len(raw) - len(authorized),
                "context_conflicts_dropped": len(conflict_notes),
                "context_conflicts": conflict_notes,
                "context_token_budget": self._token_budget,
                "context_truncated": truncated,
                "context_output_count": len(bounded),
            }
        )
        return ContextBundle(
            evidence=bounded,
            rendered_context=rendered,
            diagnostics=merged_diagnostics,
        )


def _resolve_conflicts(items: tuple[EvidenceItem, ...]) -> tuple[tuple[EvidenceItem, ...], tuple[str, ...]]:
    winners: dict[str, EvidenceItem] = {}
    without_group: list[EvidenceItem] = []
    notes: list[str] = []
    for item in items:
        if not item.conflict_group:
            without_group.append(item)
            continue
        current = winners.get(item.conflict_group)
        if (
            current is None
            or _priority(item) < _priority(current)
            or (_priority(item) == _priority(current) and _score(item) > _score(current))
        ):
            if current is not None:
                notes.append(_conflict_note(item.conflict_group, item, current))
            winners[item.conflict_group] = item
        else:
            notes.append(_conflict_note(item.conflict_group, current, item))
    resolved = without_group + list(winners.values())
    resolved.sort(key=lambda item: (_priority(item), -_score(item), item.item_id))
    return tuple(resolved), tuple(notes[:20])


def _conflict_note(group: str, winner: EvidenceItem, loser: EvidenceItem) -> str:
    return f"{group}: {winner.layer}:{winner.document_id} overrides {loser.layer}:{loser.document_id}"


def _truncate(items: tuple[EvidenceItem, ...], token_budget: int) -> tuple[tuple[EvidenceItem, ...], bool]:
    remaining = token_budget
    bounded: list[EvidenceItem] = []
    truncated = False
    for item in items:
        prefix = _render_item(len(bounded) + 1, item, include_content=False)
        prefix_cost = _estimate_tokens(prefix)
        if prefix_cost >= remaining:
            truncated = True
            break
        content_budget = remaining - prefix_cost
        content_cost = _estimate_tokens(item.content)
        if content_cost <= content_budget:
            bounded.append(item)
            remaining -= prefix_cost + content_cost
            continue
        max_chars = max(1, content_budget * 4)
        bounded.append(item.model_copy(update={"content": item.content[:max_chars].rstrip() + "…"}))
        truncated = True
        break
    return tuple(bounded), truncated


def _render_item(index: int, item: EvidenceItem, *, include_content: bool = True) -> str:
    location = f"document={item.document_id}"
    if item.version is not None:
        location += f", version={item.version}"
    if item.page is not None:
        location += f", page={item.page}"
    if item.chunk_id:
        location += f", chunk={item.chunk_id}"
    if item.image_id:
        location += f", image={item.image_id}"
    header = f"[E{index}] {location}; source={item.source}; layer={item.layer}; retriever={item.retriever}"
    return f"{header}\n{item.content}" if include_content else header


def _priority(item: EvidenceItem) -> int:
    if item.retriever == "current_context":
        return _LAYER_PRIORITY["current_context"]
    return _LAYER_PRIORITY.get(item.layer, 5)


def _score(item: EvidenceItem) -> float:
    return item.score if item.score is not None else -1.0


def _estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


__all__ = ["ContextBuilder"]
