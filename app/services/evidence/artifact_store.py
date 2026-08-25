"""Owner-scoped filesystem artifact storage with atomic writes."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.services.evidence.models import ArtifactRecord

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_.@-]{1,128}$")


class ArtifactStore:
    """Persist immutable evidence artifacts below a configured root."""

    def __init__(self, root: Path | None = None, *, settings: Settings | None = None) -> None:
        active = settings or get_settings()
        self.root = (root or active.evidence_artifact_path).resolve()

    def version_path(self, tenant_id: str, document_id: str, version: int) -> Path:
        if version < 1:
            raise ValueError("version must be positive")
        target = self.root / _segment(tenant_id) / _segment(document_id) / f"v{version}"
        resolved = target.resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise ValueError("artifact path escaped configured root")
        return resolved

    def resolve(self, uri: str) -> Path:
        prefix = "artifact://"
        if not str(uri).startswith(prefix):
            raise ValueError("unsupported artifact URI")
        relative = Path(str(uri)[len(prefix) :])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("artifact URI escaped configured root")
        target = (self.root / relative).resolve()
        if self.root not in target.parents:
            raise ValueError("artifact URI escaped configured root")
        return target

    def put_file(
        self,
        source: Path,
        *,
        tenant_id: str,
        document_id: str,
        version: int,
    ) -> ArtifactRecord:
        return self.put_bytes(
            source.read_bytes(),
            tenant_id=tenant_id,
            document_id=document_id,
            version=version,
            relative_path=f"original/{source.name}",
            kind="original",
            media_type=mimetypes.guess_type(source.name)[0] or "application/octet-stream",
        )

    def put_bytes(
        self,
        data: bytes,
        *,
        tenant_id: str,
        document_id: str,
        version: int,
        relative_path: str,
        kind: str,
        media_type: str = "application/octet-stream",
        page: int | None = None,
        image_id: str | None = None,
    ) -> ArtifactRecord:
        base = self.version_path(tenant_id, document_id, version)
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("artifact relative path must stay within its version")
        target = (base / relative).resolve()
        if base not in target.parents:
            raise ValueError("artifact path escaped its version")
        digest = hashlib.sha256(data).hexdigest()
        if target.exists():
            existing_digest = hashlib.sha256(target.read_bytes()).hexdigest()
            if existing_digest != digest:
                raise FileExistsError(f"immutable artifact already exists with different content: {relative_path}")
        else:
            _atomic_write(target, data)
        uri_path = "/".join((_segment(tenant_id), _segment(document_id), f"v{version}", *relative.parts))
        return ArtifactRecord(
            artifact_id=f"artifact-{hashlib.sha256(uri_path.encode('utf-8')).hexdigest()[:20]}",
            kind=kind,
            uri=f"artifact://{uri_path}",
            sha256=digest,
            media_type=media_type,
            page=page,
            image_id=image_id,
        )

    def put_json(
        self,
        payload: dict[str, Any],
        *,
        tenant_id: str,
        document_id: str,
        version: int,
        relative_path: str,
        kind: str = "parsed",
    ) -> ArtifactRecord:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        return self.put_bytes(
            data,
            tenant_id=tenant_id,
            document_id=document_id,
            version=version,
            relative_path=relative_path,
            kind=kind,
            media_type="application/json",
        )


def _segment(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("artifact identity segment must not be blank")
    if _SAFE_SEGMENT.fullmatch(normalized):
        return normalized
    return f"id-{hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:24]}"


def _atomic_write(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


__all__ = ["ArtifactStore"]
