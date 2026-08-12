from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

try:
    import aiofiles
except ModuleNotFoundError:
    aiofiles = None

from app.services.documents.registry import list_document_records


class UploadStorageError(Exception):
    """Base error raised while persisting an uploaded document."""


class UploadPayloadTooLargeError(UploadStorageError):
    """Raised when a file or request exceeds its configured byte limit."""


class UploadInvalidFileError(UploadStorageError):
    """Raised when an uploaded file fails signature validation."""


class UploadWriteError(UploadStorageError):
    """Raised when a validated upload cannot be written to storage."""


@dataclass
class StoredUpload:
    path: Path
    filename: str
    sha256: str
    agent_class: str
    parser_profile: dict[str, Any]


@dataclass
class UploadStorageResult:
    saved_uploads: list[StoredUpload]
    skipped_files: list[str]
    duplicate_files: list[str]
    reused_document_ids: list[str]
    visibility_applied: str


async def _write_file_bytes(target: Path, chunks: list[bytes]) -> None:
    """Write uploaded bytes using aiofiles when available, else a thread fallback."""
    if aiofiles is not None:
        async with aiofiles.open(target, "wb") as out:
            for chunk in chunks:
                await out.write(chunk)
        return

    await asyncio.to_thread(target.write_bytes, b"".join(chunks))


async def _replace_file_atomically(target: Path, chunks: list[bytes]) -> None:
    """Write a sibling temporary file, then atomically replace ``target``."""
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.upload")
    try:
        await _write_file_bytes(temporary, chunks)
        await asyncio.to_thread(temporary.replace, target)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise


async def store_uploaded_files(
    *,
    files: list[Any],
    owner_user_id: str,
    role: str,
    requested_visibility: str,
    uploads_path: Path,
    max_files: int,
    max_file_bytes: int,
    max_total_bytes: int,
    read_chunk_bytes: int,
    supported_suffixes: set[str],
    signature_suffixes: set[str],
    is_valid_signature: Callable[[str, bytes], bool],
    agent_class_for_upload: Callable[[str], str],
    parser_profile_for_upload: Callable[[Path, str], dict[str, Any]],
    visibility_applied: str | None = None,
    public_visibility_approved: bool | None = None,
) -> UploadStorageResult:
    """Validate, persist, hash, and deduplicate a request's document uploads."""
    if len(files) > max_files:
        raise UploadStorageError(f"too many files, max={max_files}")

    normalized_visibility = str(requested_visibility or "private").strip().lower()
    if normalized_visibility not in {"private", "public"}:
        normalized_visibility = "private"
    if visibility_applied is None:
        # Compatibility fallback for non-route callers. Public-route authorization
        # supplies the already-approved visibility instead.
        applied_visibility = normalized_visibility if str(role).lower() == "admin" else "private"
    else:
        applied_visibility = str(visibility_applied or "private").strip().lower()
        if applied_visibility not in {"private", "public"}:
            applied_visibility = "private"
        if applied_visibility == "public" and public_visibility_approved is not True:
            applied_visibility = "private"

    saved_uploads: list[StoredUpload] = []
    skipped_files: list[str] = []
    duplicate_files: list[str] = []
    reused_document_ids: list[str] = []
    pending_hashes: set[str] = set()
    total_uploaded_bytes = 0
    read_chunk = max(16 * 1024, int(read_chunk_bytes))
    user_upload_root = uploads_path / owner_user_id
    user_upload_root.mkdir(parents=True, exist_ok=True)

    for uploaded_file in files:
        if not uploaded_file.filename:
            continue

        raw_filename = Path(uploaded_file.filename).name
        safe_filename = raw_filename.replace("/", "").replace("\\", "").replace("..", "")
        if not safe_filename or safe_filename.startswith(".") or safe_filename.startswith("_"):
            skipped_files.append(raw_filename)
            continue

        suffix = Path(safe_filename).suffix.lower()
        if suffix not in supported_suffixes:
            skipped_files.append(safe_filename)
            continue

        target = user_upload_root / safe_filename
        file_uploaded_bytes = 0
        file_head = b""
        file_chunks: list[bytes] = []
        file_digest = hashlib.sha256()
        try:
            while True:
                chunk = await uploaded_file.read(read_chunk)
                if not chunk:
                    break
                if len(file_head) < 16:
                    file_head = (file_head + chunk)[:16]
                file_uploaded_bytes += len(chunk)
                total_uploaded_bytes += len(chunk)
                if file_uploaded_bytes > max_file_bytes:
                    raise UploadPayloadTooLargeError(f"file too large: {target.name}")
                if total_uploaded_bytes > max_total_bytes:
                    raise UploadPayloadTooLargeError("total upload size exceeded")
                file_chunks.append(chunk)
                file_digest.update(chunk)
        finally:
            await uploaded_file.close()

        if file_uploaded_bytes <= 0:
            continue
        if suffix in signature_suffixes and not is_valid_signature(suffix, file_head):
            raise UploadInvalidFileError(f"invalid file signature: {safe_filename}")

        sha256 = file_digest.hexdigest()
        duplicate = find_duplicate_for_user(sha256, owner_user_id)
        if duplicate is not None:
            duplicate_source = Path(str(duplicate.get("source", "") or ""))
            if (
                not duplicate_source.is_file()
                or compute_sha256(duplicate_source) != sha256
            ):
                duplicate = None
        if duplicate is not None:
            duplicate_files.append(safe_filename)
            if duplicate.get("document_id"):
                reused_document_ids.append(str(duplicate["document_id"]))
            continue

        if sha256 in pending_hashes:
            duplicate_files.append(safe_filename)
            continue

        try:
            await _replace_file_atomically(target, file_chunks)
        except Exception as exc:
            raise UploadWriteError(f"Failed to write file: {safe_filename}") from exc

        pending_hashes.add(sha256)

        agent_class = agent_class_for_upload(safe_filename)
        saved_uploads.append(
            StoredUpload(
                path=target,
                filename=safe_filename,
                sha256=sha256,
                agent_class=agent_class,
                parser_profile=parser_profile_for_upload(target, agent_class),
            )
        )

    return UploadStorageResult(
        saved_uploads=saved_uploads,
        skipped_files=skipped_files,
        duplicate_files=duplicate_files,
        reused_document_ids=reused_document_ids,
        visibility_applied=applied_visibility,
    )


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def find_duplicate_for_user(sha256: str, owner_user_id: str, path: Path | None = None) -> dict | None:
    for row in list_document_records(path=path):
        if str(row.get("sha256", "")) != str(sha256):
            continue
        if str(row.get("owner_user_id", "")) != str(owner_user_id):
            continue
        if str(row.get("status", "")) in {"pending", "indexing", "ready"}:
            return row
    return None
