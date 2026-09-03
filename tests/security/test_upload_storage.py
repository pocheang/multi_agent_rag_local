"""What store_uploaded_files accepts, refuses and deduplicates.

It had no tests. It is the front door for user documents: it decides the name a
file is stored under, the directory it lands in -- which is what
`list_visible_document_rows` falls back to when deciding whose document it is --
and the visibility the row is later indexed with.

Pinned before the function was split up. The cases that matter most are the
refusals and the visibility downgrade, because both fail open if they go wrong:
an accepted file is a file someone else may be able to reach, and a visibility
that stays "public" by accident publishes a private document.
"""

from __future__ import annotations

import io
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from app.services.documents import dedup as dedup_module
from app.services.documents.dedup import (
    UploadInvalidFileError,
    UploadPayloadTooLargeError,
    UploadStorageError,
    UploadWriteError,
    store_uploaded_files,
)


class _Upload:
    """Enough of Starlette's UploadFile to drive the reader."""

    def __init__(self, filename: str | None, data: bytes = b"body") -> None:
        self.filename = filename
        self._buffer = io.BytesIO(data)
        self.closed = False

    async def read(self, size: int) -> bytes:
        return self._buffer.read(size)

    async def close(self) -> None:
        self.closed = True


@dataclass
class _Roots:
    uploads: Path


@pytest.fixture
def roots():
    # Deliberately not pytest's tmp_path: its basetemp needs directory
    # permissions not available on every Windows checkout (see
    # tests/mcp/test_approval_resume.py).
    root = Path(tempfile.mkdtemp(prefix="querymind-uploads-"))
    try:
        yield _Roots(uploads=root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture(autouse=True)
def _no_existing_duplicates(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(dedup_module, "find_duplicate_for_user", lambda sha256, owner_user_id: None)


async def _store(roots: _Roots, files: list[_Upload], **overrides):
    kwargs: dict[str, Any] = {
        "files": files,
        "owner_user_id": "alice",
        "role": "viewer",
        "requested_visibility": "private",
        "uploads_path": roots.uploads,
        "max_files": 10,
        "max_file_bytes": 1024,
        "max_total_bytes": 4096,
        "read_chunk_bytes": 8,
        "supported_suffixes": {".pdf", ".txt"},
        "signature_suffixes": {".pdf"},
        "is_valid_signature": lambda suffix, head: head.startswith(b"%PDF"),
        "agent_class_for_upload": lambda name: "general",
        "parser_profile_for_upload": lambda path, agent_class: {"parser": "default"},
    }
    kwargs.update(overrides)
    return await store_uploaded_files(**kwargs)


@pytest.mark.asyncio
async def test_a_saved_file_lands_under_its_owners_directory(roots: _Roots) -> None:
    """The upload layout is what ownership falls back to when metadata is absent."""

    result = await _store(roots, [_Upload("notes.txt", b"hello")])

    (saved,) = result.saved_uploads
    assert saved.path == roots.uploads / "alice" / "notes.txt"
    assert saved.path.read_bytes() == b"hello"
    assert saved.filename == "notes.txt"
    assert saved.agent_class == "general"
    assert saved.parser_profile == {"parser": "default"}


@pytest.mark.asyncio
async def test_too_many_files_is_refused_before_anything_is_read(roots: _Roots) -> None:
    files = [_Upload(f"f{i}.txt") for i in range(3)]

    with pytest.raises(UploadStorageError, match="too many files"):
        await _store(roots, files, max_files=2)

    assert not any(upload.closed for upload in files)


@pytest.mark.asyncio
@pytest.mark.parametrize("name", [".hidden.txt", "_internal.txt", "../../../etc/passwd"])
async def test_names_that_are_not_ours_to_write_are_skipped(roots: _Roots, name: str) -> None:
    result = await _store(roots, [_Upload(name, b"x")])

    assert result.saved_uploads == []
    assert result.skipped_files


@pytest.mark.asyncio
async def test_a_path_in_the_filename_is_reduced_to_its_basename(roots: _Roots) -> None:
    """`Path(...).name` first, so a traversal cannot choose the directory."""

    result = await _store(roots, [_Upload("subdir/report.txt", b"x")])

    (saved,) = result.saved_uploads
    assert saved.path == roots.uploads / "alice" / "report.txt"


@pytest.mark.asyncio
async def test_an_unsupported_extension_is_skipped_rather_than_stored(roots: _Roots) -> None:
    result = await _store(roots, [_Upload("payload.exe", b"MZ")])

    assert result.saved_uploads == []
    assert result.skipped_files == ["payload.exe"]


@pytest.mark.asyncio
async def test_an_empty_file_is_dropped_quietly(roots: _Roots) -> None:
    """Not reported as skipped: there was nothing to reject."""

    result = await _store(roots, [_Upload("empty.txt", b"")])

    assert result.saved_uploads == []
    assert result.skipped_files == []


@pytest.mark.asyncio
async def test_a_file_over_the_per_file_cap_is_refused_and_names_itself(roots: _Roots) -> None:
    with pytest.raises(UploadPayloadTooLargeError) as excinfo:
        await _store(roots, [_Upload("big.txt", b"x" * 200)], max_file_bytes=64)

    assert excinfo.value.filename == "big.txt"


@pytest.mark.asyncio
async def test_files_that_together_exceed_the_request_cap_are_refused(roots: _Roots) -> None:
    files = [_Upload("a.txt", b"x" * 60), _Upload("b.txt", b"x" * 60)]

    with pytest.raises(UploadPayloadTooLargeError):
        await _store(roots, files, max_file_bytes=100, max_total_bytes=100)


@pytest.mark.asyncio
async def test_a_file_whose_signature_does_not_match_its_extension_is_refused(roots: _Roots) -> None:
    """The extension is the caller's claim; the first bytes are the evidence."""

    with pytest.raises(UploadInvalidFileError, match="report.pdf"):
        await _store(roots, [_Upload("report.pdf", b"not really a pdf")])


@pytest.mark.asyncio
async def test_a_signature_check_only_applies_to_the_suffixes_that_declare_one(roots: _Roots) -> None:
    result = await _store(roots, [_Upload("notes.txt", b"not really a pdf")])

    assert len(result.saved_uploads) == 1


@pytest.mark.asyncio
async def test_a_file_already_stored_for_this_user_is_reused_not_rewritten(
    roots: _Roots, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing = roots.uploads / "alice" / "already.txt"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"hello")

    monkeypatch.setattr(
        dedup_module,
        "find_duplicate_for_user",
        lambda sha256, owner_user_id: {"source": str(existing), "document_id": "doc-7"},
    )

    result = await _store(roots, [_Upload("again.txt", b"hello")])

    assert result.saved_uploads == []
    assert result.duplicate_files == ["again.txt"]
    assert result.reused_document_ids == ["doc-7"]
    assert not (roots.uploads / "alice" / "again.txt").exists()


@pytest.mark.asyncio
async def test_an_index_row_whose_file_is_gone_is_not_treated_as_a_duplicate(
    roots: _Roots, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The index can outlive the file; re-hashing the stored copy is what settles it."""

    monkeypatch.setattr(
        dedup_module,
        "find_duplicate_for_user",
        lambda sha256, owner_user_id: {"source": str(roots.uploads / "alice" / "vanished.txt"), "document_id": "doc-9"},
    )

    result = await _store(roots, [_Upload("again.txt", b"hello")])

    assert [upload.filename for upload in result.saved_uploads] == ["again.txt"]
    assert result.duplicate_files == []


@pytest.mark.asyncio
async def test_the_same_content_twice_in_one_request_is_stored_once(roots: _Roots) -> None:
    files = [_Upload("first.txt", b"same"), _Upload("second.txt", b"same")]

    result = await _store(roots, files)

    assert [upload.filename for upload in result.saved_uploads] == ["first.txt"]
    assert result.duplicate_files == ["second.txt"]


@pytest.mark.asyncio
async def test_a_write_failure_is_reported_as_one(roots: _Roots, monkeypatch: pytest.MonkeyPatch) -> None:
    async def refuse(target, chunks):
        raise OSError("disk full")

    monkeypatch.setattr(dedup_module, "_replace_file_atomically", refuse)

    with pytest.raises(UploadWriteError, match="notes.txt"):
        await _store(roots, [_Upload("notes.txt", b"x")])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "requested", "expected"),
    [
        ("viewer", "public", "private"),
        ("analyst", "public", "private"),
        ("admin", "public", "public"),
        ("admin", "private", "private"),
        ("admin", "nonsense", "private"),
    ],
)
async def test_without_a_decision_from_the_route_only_an_admin_may_publish(
    roots: _Roots, role: str, requested: str, expected: str
) -> None:
    result = await _store(roots, [], role=role, requested_visibility=requested)

    assert result.visibility_applied == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("applied", "approved", "expected"),
    [
        ("public", True, "public"),
        ("public", False, "private"),
        ("public", None, "private"),
        ("private", True, "private"),
        ("nonsense", True, "private"),
    ],
)
async def test_a_public_decision_still_needs_its_approval(
    roots: _Roots, applied: str, approved: bool | None, expected: str
) -> None:
    """Approval is required to be exactly True: a missing answer is not a yes."""

    result = await _store(
        roots,
        [],
        role="admin",
        visibility_applied=applied,
        public_visibility_approved=approved,
    )

    assert result.visibility_applied == expected


@pytest.mark.asyncio
async def test_every_upload_is_closed_even_when_one_is_refused(roots: _Roots) -> None:
    good = _Upload("notes.txt", b"x")
    bad = _Upload("report.pdf", b"not really a pdf")

    with pytest.raises(UploadInvalidFileError):
        await _store(roots, [good, bad])

    assert good.closed and bad.closed
