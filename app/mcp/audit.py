"""Secret-free audit sink for MCP tool decisions."""

from __future__ import annotations

from app.mcp.contracts import AuditRecord


class AuditLog:
    """In-process audit store used until a durable service is configured."""

    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def append(self, record: AuditRecord) -> None:
        self.records.append(record)
