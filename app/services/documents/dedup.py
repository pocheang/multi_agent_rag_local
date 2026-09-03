from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
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

    def __init__(
        self,
        message: str,
        *,
        file_size: int | None = None,
        total_size: int | None = None,
        max_file_size: int | None = None,
        max_total_size: int | None = None,
        filename: str | None = None,
    ):
        super().__init__(message)
        self.file_size = file_size
        self.total_size = total_size
        self.max_file_size = max_file_size
        self.max_total_size = max_total_size
        self.filename = filename


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


_VALID_VISIBILITIES = frozenset({"private", "public"})


def _normalized_visibility(value: str | None) -> str:
    """Anything that is not a visibility this system knows is private."""

    normalized = str(value or "private").strip().lower()
    return normalized if normalized in _VALID_VISIBILITIES else "private"


def _resolve_visibility(
    *,
    role: str,
    requested_visibility: str,
    visibility_applied: str | None,
    public_visibility_approved: bool | None,
) -> str:
    """What these documents will actually be indexed as.

    Two ways in. The public route decides authorization itself and passes the
    already-approved answer; every other caller gets the compatibility rule,
    where only an admin may ask for public.

    Approval must be exactly ``True``. A missing answer is not a yes, which is
    the whole point of the check: this is the last place a private document can
    stop being private.
    """

    if visibility_applied is None:
        requested = _normalized_visibility(requested_visibility)
        return requested if str(role).lower() == "admin" else "private"

    applied = _normalized_visibility(visibility_applied)
    if applied == "public" and public_visibility_approved is not True:
        return "private"
    return applied


def _sanitized_upload_name(raw_filename: str) -> str | None:
    """The name this file will be stored under, or None if it is not one we will write.

    The caller has already reduced the upload to its basename, so this is about
    what the name *is*: dot- and underscore-prefixed names are ours, not a
    caller's, and a name that empties out has nothing left to store.
    """

    safe = raw_filename.replace("/", "").replace("\\", "").replace("..", "")
    if not safe or safe.startswith(".") or safe.startswith("_"):
        return None
    return safe


@dataclass
class _ReadUpload:
    """One upload, read once: kept in memory, hashed, and capped on the way through."""

    chunks: list[bytes]
    head: bytes
    size: int
    sha256: str


async def _read_upload(
    uploaded_file: Any,
    *,
    safe_filename: str,
    read_chunk: int,
    max_file_bytes: int,
    max_total_bytes: int,
    total_so_far: int,
) -> _ReadUpload:
    """Read, hash and cap in one pass.

    Both caps are tested per chunk rather than after the read, so an oversized
    upload costs the bytes already read and stops there. The first 16 bytes are
    kept separately: that is what the signature check looks at, and it has to be
    available before deciding whether to keep the rest.
    """

    head = b""
    size = 0
    chunks: list[bytes] = []
    digest = hashlib.sha256()
    try:
        while True:
            chunk = await uploaded_file.read(read_chunk)
            if not chunk:
                break
            if len(head) < 16:
                head = (head + chunk)[:16]
            size += len(chunk)
            if size > max_file_bytes:
                raise UploadPayloadTooLargeError(
                    f"文件 '{safe_filename}' 过大",
                    file_size=size,
                    max_file_size=max_file_bytes,
                    filename=safe_filename,
                )
            if total_so_far + size > max_total_bytes:
                raise UploadPayloadTooLargeError(
                    "上传总大小超过限制",
                    total_size=total_so_far + size,
                    max_total_size=max_total_bytes,
                )
            chunks.append(chunk)
            digest.update(chunk)
    finally:
        await uploaded_file.close()
    return _ReadUpload(chunks=chunks, head=head, size=size, sha256=digest.hexdigest())


def _existing_duplicate(sha256: str, owner_user_id: str) -> dict | None:
    """A previous upload of this user's with the same hash, still on disk and unchanged.

    The index can outlive the file it points at, so a row alone is not evidence:
    the stored copy is re-hashed before this request is told it already has one.
    """

    duplicate = find_duplicate_for_user(sha256, owner_user_id)
    if duplicate is None:
        return None
    source = Path(str(duplicate.get("source", "") or ""))
    if not source.is_file() or compute_sha256(source) != sha256:
        return None
    return duplicate


@dataclass
class _UploadBatch:
    """The running state of one request's uploads.

    Six accumulators that only ever move together, including the byte total the
    per-request cap is measured against -- which is what makes it a batch rather
    than a list of files.
    """

    saved: list[StoredUpload] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    reused_document_ids: list[str] = field(default_factory=list)
    pending_hashes: set[str] = field(default_factory=set)
    total_bytes: int = 0


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

    applied_visibility = _resolve_visibility(
        role=role,
        requested_visibility=requested_visibility,
        visibility_applied=visibility_applied,
        public_visibility_approved=public_visibility_approved,
    )

    # Every file this user uploads lands here, and that layout is what document
    # visibility falls back to for rows indexed before owner metadata existed.
    user_upload_root = uploads_path / owner_user_id
    user_upload_root.mkdir(parents=True, exist_ok=True)

    batch = _UploadBatch()
    for uploaded_file in files:
        await _store_one_upload(
            uploaded_file,
            batch=batch,
            owner_user_id=owner_user_id,
            user_upload_root=user_upload_root,
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
            read_chunk=max(16 * 1024, int(read_chunk_bytes)),
            supported_suffixes=supported_suffixes,
            signature_suffixes=signature_suffixes,
            is_valid_signature=is_valid_signature,
            agent_class_for_upload=agent_class_for_upload,
            parser_profile_for_upload=parser_profile_for_upload,
        )

    return UploadStorageResult(
        saved_uploads=batch.saved,
        skipped_files=batch.skipped,
        duplicate_files=batch.duplicates,
        reused_document_ids=batch.reused_document_ids,
        visibility_applied=applied_visibility,
    )


async def _store_one_upload(
    uploaded_file: Any,
    *,
    batch: _UploadBatch,
    owner_user_id: str,
    user_upload_root: Path,
    max_file_bytes: int,
    max_total_bytes: int,
    read_chunk: int,
    supported_suffixes: set[str],
    signature_suffixes: set[str],
    is_valid_signature: Callable[[str, bytes], bool],
    agent_class_for_upload: Callable[[str], str],
    parser_profile_for_upload: Callable[[Path, str], dict[str, Any]],
) -> None:
    """Everything that happens to one uploaded file, in the order it happens.

    Screen the name, read it once under both caps, check the signature, check it
    against what is already stored and against the rest of this request, and only
    then write it. Refusals raise and abandon the whole request; a file that is
    merely uninteresting is recorded and skipped.
    """

    if not uploaded_file.filename:
        return

    raw_filename = Path(uploaded_file.filename).name
    safe_filename = _sanitized_upload_name(raw_filename)
    if safe_filename is None:
        batch.skipped.append(raw_filename)
        return

    suffix = Path(safe_filename).suffix.lower()
    if suffix not in supported_suffixes:
        batch.skipped.append(safe_filename)
        return

    upload = await _read_upload(
        uploaded_file,
        safe_filename=safe_filename,
        read_chunk=read_chunk,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
        total_so_far=batch.total_bytes,
    )
    batch.total_bytes += upload.size
    if upload.size <= 0:
        return

    # The extension is the caller's claim; the first bytes are the evidence.
    if suffix in signature_suffixes and not is_valid_signature(suffix, upload.head):
        raise UploadInvalidFileError(f"invalid file signature: {safe_filename}")

    if _record_if_duplicate(upload.sha256, safe_filename, owner_user_id=owner_user_id, batch=batch):
        return

    target = user_upload_root / safe_filename
    try:
        await _replace_file_atomically(target, upload.chunks)
    except Exception as exc:
        raise UploadWriteError(f"Failed to write file: {safe_filename}") from exc

    batch.pending_hashes.add(upload.sha256)
    agent_class = agent_class_for_upload(safe_filename)
    batch.saved.append(
        StoredUpload(
            path=target,
            filename=safe_filename,
            sha256=upload.sha256,
            agent_class=agent_class,
            parser_profile=parser_profile_for_upload(target, agent_class),
        )
    )


def _record_if_duplicate(sha256: str, safe_filename: str, *, owner_user_id: str, batch: _UploadBatch) -> bool:
    """Two kinds of duplicate: one this user already has, and one earlier in this request.

    Only the first can hand back a document id to reuse -- the other copy in this
    request has not been indexed yet either.
    """

    duplicate = _existing_duplicate(sha256, owner_user_id)
    if duplicate is not None:
        batch.duplicates.append(safe_filename)
        if duplicate.get("document_id"):
            batch.reused_document_ids.append(str(duplicate["document_id"]))
        return True
    if sha256 in batch.pending_hashes:
        batch.duplicates.append(safe_filename)
        return True
    return False


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
