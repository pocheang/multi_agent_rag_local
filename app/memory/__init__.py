"""Session and governed long-term memory services."""

from typing import Any

from app.memory.resolver import MemoryResolution, MemoryResolver
from app.memory.session import SessionMemory


def __getattr__(name: str) -> Any:
    if name == "GBrainLongTermMemory":
        from app.memory.long_term import GBrainLongTermMemory

        return GBrainLongTermMemory
    raise AttributeError(name)

__all__ = ["GBrainLongTermMemory", "MemoryResolution", "MemoryResolver", "SessionMemory"]
