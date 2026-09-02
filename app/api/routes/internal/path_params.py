"""Constrained path parameters shared by route modules.

A path parameter typed as a bare `str` accepts anything the URL can carry, and
percent-decoding means that includes `\\r` and `\\n`. Anything that then reaches
a log lets the caller forge log lines -- `pythonsecurity:S5145`, raised against
`agent_health.py` where the execution id was logged on the failure path.

Constraining the parameter is better than sanitising at the log call, because it
fixes every use of the value rather than the one a scanner happened to notice,
and it turns a malformed id into a 422 at the edge instead of a 404 or a 500
from somewhere deeper.

`_ID_CHARS` is deliberately wider than a UUID even though every execution id is
one today: `ToolAgentService` falls back to `request_id` when there is no
execution id, and pinning the format here would make this module the thing that
has to change when that one does. What matters for the defect is that the class
excludes every whitespace and control character, which it does.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Path

_ID_CHARS = r"^[A-Za-z0-9_-]{1,128}$"

ExecutionId = Annotated[
    str,
    Path(
        pattern=_ID_CHARS,
        description="Execution id from a query response.",
    ),
]
