"""Immutable per-version evidence manifest persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from app.services.evidence.artifact_store import ArtifactStore
from app.services.evidence.models import ArtifactRecord, EvidenceManifest, ParsedDocument


class ManifestStore:
    """Write each document version once and retain all historical manifests."""

    def __init__(self, artifacts: ArtifactStore | None = None) -> None:
        self.artifacts = artifacts or ArtifactStore()

    def save(self, manifest: EvidenceManifest) -> ArtifactRecord:
        target = (
            self.artifacts.version_path(manifest.tenant_id, manifest.document_id, manifest.version) / "manifest.json"
        )
        if target.exists():
            raise FileExistsError(f"manifest already exists for {manifest.document_id} v{manifest.version}")
        return self.artifacts.put_json(
            manifest.model_dump(mode="json"),
            tenant_id=manifest.tenant_id,
            document_id=manifest.document_id,
            version=manifest.version,
            relative_path="manifest.json",
            kind="manifest",
        )

    def load(self, tenant_id: str, document_id: str, version: int) -> EvidenceManifest:
        target = self.artifacts.version_path(tenant_id, document_id, version) / "manifest.json"
        return EvidenceManifest.model_validate(json.loads(target.read_text(encoding="utf-8")))

    def list_versions(self, tenant_id: str, document_id: str) -> tuple[int, ...]:
        document_root = self.artifacts.version_path(tenant_id, document_id, 1).parent
        if not document_root.exists():
            return ()
        versions = []
        for child in document_root.iterdir():
            if child.is_dir() and child.name.startswith("v") and (child / "manifest.json").is_file():
                try:
                    versions.append(int(child.name[1:]))
                except ValueError:
                    continue
        return tuple(sorted(versions))


def build_manifest(
    parsed: ParsedDocument,
    artifacts: tuple[ArtifactRecord, ...],
    *,
    status: str = "ready",
    error_type: str | None = None,
) -> EvidenceManifest:
    document = parsed.document
    return EvidenceManifest(
        document_id=document.document_id,
        version=document.version,
        tenant_id=document.tenant_id,
        source=document.source,
        sha256=document.sha256,
        parser=parsed.parser,
        fallback_chain=parsed.fallback_chain,
        artifacts=artifacts,
        status=status,
        error_type=error_type,
        created_at=datetime.now(UTC).isoformat(),
    )


__all__ = ["ManifestStore", "build_manifest"]
