"""
Session export and import service.

Provides functionality to export sessions to JSON/ZIP formats
and import sessions with conflict handling.
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from app.services.sessions.metadata import (
    SessionMetadata,
    SessionMetadataService,
    get_metadata_service,
)

__all__ = [
    "ExportFormat",
    "ConflictStrategy",
    "ExportedSession",
    "ImportResult",
    "SessionExportService",
    "get_export_service",
]


# ============================================================================
# Constants
# ============================================================================

EXPORT_VERSION = "1.0"


# ============================================================================
# Type Definitions
# ============================================================================

ExportFormat = Literal["json", "zip"]
ConflictStrategy = Literal["skip", "overwrite", "rename"]


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class ExportedSession:
    """Exported session data."""

    session_id: str
    metadata: dict[str, Any]
    messages: list[dict[str, Any]]
    context: dict[str, Any] | None = None
    export_version: str = EXPORT_VERSION
    exported_at: str = ""

    def __post_init__(self):
        if not self.exported_at:
            self.exported_at = datetime.utcnow().isoformat()


@dataclass
class ImportResult:
    """Result of session import."""

    success: bool
    session_id: str
    message: str
    conflicts: list[str] | None = None


# ============================================================================
# Session Export Service
# ============================================================================


class SessionExportService:
    """Service for exporting and importing sessions."""

    def __init__(self, metadata_service: SessionMetadataService | None = None):
        self.metadata_service = metadata_service or get_metadata_service()

    def export_session(
        self,
        session_id: str,
        messages: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> ExportedSession:
        """
        Export a single session.

        Args:
            session_id: Session identifier
            messages: Optional message history
            context: Optional context data

        Returns:
            ExportedSession

        Raises:
            KeyError: If session metadata not found
        """
        # Get metadata
        metadata = self.metadata_service.get_metadata(session_id)
        if metadata is None:
            raise KeyError(f"Session {session_id} not found")

        # Convert metadata to dict
        metadata_dict = self._metadata_to_dict(metadata)

        # Create exported session
        return ExportedSession(
            session_id=session_id,
            metadata=metadata_dict,
            messages=messages or [],
            context=context,
        )

    def export_to_json(
        self,
        session_id: str,
        messages: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Export session to JSON string.

        Args:
            session_id: Session identifier
            messages: Optional message history
            context: Optional context data

        Returns:
            JSON string
        """
        exported = self.export_session(session_id, messages, context)
        return json.dumps(asdict(exported), indent=2, ensure_ascii=False)

    def export_to_file(
        self,
        session_id: str,
        output_path: str | Path,
        messages: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """
        Export session to JSON file.

        Args:
            session_id: Session identifier
            output_path: Output file path
            messages: Optional message history
            context: Optional context data
        """
        json_str = self.export_to_json(session_id, messages, context)

        output_path = Path(output_path)
        output_path.write_text(json_str, encoding="utf-8")

    def export_multiple_to_zip(
        self,
        session_ids: list[str],
        output_path: str | Path,
        messages_map: dict[str, list[dict[str, Any]]] | None = None,
        context_map: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """
        Export multiple sessions to ZIP archive.

        Args:
            session_ids: List of session identifiers
            output_path: Output ZIP file path
            messages_map: Map of session_id -> messages
            context_map: Map of session_id -> context
        """
        messages_map = messages_map or {}
        context_map = context_map or {}

        output_path = Path(output_path)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for session_id in session_ids:
                try:
                    # Get JSON for this session
                    json_str = self.export_to_json(
                        session_id,
                        messages=messages_map.get(session_id),
                        context=context_map.get(session_id),
                    )

                    # Add to ZIP
                    filename = f"{session_id}.json"
                    zf.writestr(filename, json_str)

                except KeyError as e:
                    # Session not found, skip it
                    print(f"Warning: {e}")
                    continue

    def import_from_json(
        self,
        json_str: str,
        conflict_strategy: ConflictStrategy = "skip",
    ) -> ImportResult:
        """
        Import session from JSON string.

        Args:
            json_str: JSON string
            conflict_strategy: How to handle conflicts
                - "skip": Skip if session exists
                - "overwrite": Overwrite existing session
                - "rename": Create with new ID

        Returns:
            ImportResult
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return ImportResult(
                success=False,
                session_id="",
                message=f"Invalid JSON: {e}",
            )

        # Validate
        validation_result = self._validate_import_data(data)
        if not validation_result.success:
            return validation_result

        session_id = data["session_id"]

        # Check for conflicts
        existing = self.metadata_service.get_metadata(session_id)

        if existing is not None:
            if conflict_strategy == "skip":
                return ImportResult(
                    success=False,
                    session_id=session_id,
                    message="Session already exists (skipped)",
                    conflicts=["session_id"],
                )
            elif conflict_strategy == "rename":
                # Generate new ID
                session_id = self._generate_unique_id(session_id)
            elif conflict_strategy == "overwrite":
                # Will overwrite below
                pass

        # Import metadata
        try:
            metadata_dict = data["metadata"]
            metadata = self._dict_to_metadata(session_id, metadata_dict)

            # Store metadata
            self.metadata_service._metadata_store[session_id] = metadata

            return ImportResult(
                success=True,
                session_id=session_id,
                message="Session imported successfully",
            )

        except Exception as e:
            return ImportResult(
                success=False,
                session_id=session_id,
                message=f"Import failed: {e}",
            )

    def import_from_file(
        self,
        file_path: str | Path,
        conflict_strategy: ConflictStrategy = "skip",
    ) -> ImportResult:
        """
        Import session from JSON file.

        Args:
            file_path: Input file path
            conflict_strategy: Conflict handling strategy

        Returns:
            ImportResult
        """
        file_path = Path(file_path)
        json_str = file_path.read_text(encoding="utf-8")

        return self.import_from_json(json_str, conflict_strategy)

    def import_from_zip(
        self,
        zip_path: str | Path,
        conflict_strategy: ConflictStrategy = "skip",
    ) -> list[ImportResult]:
        """
        Import multiple sessions from ZIP archive.

        Args:
            zip_path: Input ZIP file path
            conflict_strategy: Conflict handling strategy

        Returns:
            List of ImportResult for each session
        """
        zip_path = Path(zip_path)
        results = []

        with zipfile.ZipFile(zip_path, "r") as zf:
            for filename in zf.namelist():
                if not filename.endswith(".json"):
                    continue

                json_str = zf.read(filename).decode("utf-8")
                result = self.import_from_json(json_str, conflict_strategy)
                results.append(result)

        return results

    def _metadata_to_dict(self, metadata: SessionMetadata) -> dict[str, Any]:
        """Convert SessionMetadata to dict."""
        return {
            "session_id": metadata.session_id,
            "tags": metadata.tags,
            "category": metadata.category,
            "description": metadata.description,
            "auto_tags": metadata.auto_tags,
            "created_at": metadata.created_at.isoformat(),
            "updated_at": metadata.updated_at.isoformat(),
            "query_count": metadata.query_count,
            "last_query_at": metadata.last_query_at.isoformat() if metadata.last_query_at else None,
        }

    def _dict_to_metadata(
        self,
        session_id: str,
        metadata_dict: dict[str, Any],
    ) -> SessionMetadata:
        """Convert dict to SessionMetadata."""
        return SessionMetadata(
            session_id=session_id,
            tags=metadata_dict.get("tags", []),
            category=metadata_dict.get("category"),
            description=metadata_dict.get("description"),
            auto_tags=metadata_dict.get("auto_tags", []),
            created_at=datetime.fromisoformat(metadata_dict["created_at"]),
            updated_at=datetime.fromisoformat(metadata_dict["updated_at"]),
            query_count=metadata_dict.get("query_count", 0),
            last_query_at=datetime.fromisoformat(metadata_dict["last_query_at"])
            if metadata_dict.get("last_query_at")
            else None,
        )

    def _validate_import_data(self, data: dict[str, Any]) -> ImportResult:
        """Validate import data structure."""
        # Check required fields
        required_fields = ["session_id", "metadata", "export_version"]
        for field in required_fields:
            if field not in data:
                return ImportResult(
                    success=False,
                    session_id="",
                    message=f"Missing required field: {field}",
                )

        # Check version compatibility
        if data["export_version"] != EXPORT_VERSION:
            return ImportResult(
                success=False,
                session_id=data["session_id"],
                message=f"Incompatible export version: {data['export_version']}",
            )

        return ImportResult(
            success=True,
            session_id=data["session_id"],
            message="Validation passed",
        )

    def _generate_unique_id(self, base_id: str) -> str:
        """Generate unique session ID by appending suffix."""
        suffix = 1
        while True:
            new_id = f"{base_id}_{suffix}"
            if self.metadata_service.get_metadata(new_id) is None:
                return new_id
            suffix += 1


# ============================================================================
# Singleton Instance
# ============================================================================

_export_service_instance: SessionExportService | None = None


def get_export_service() -> SessionExportService:
    """
    Get singleton instance of SessionExportService.

    Returns:
        Singleton service instance
    """
    global _export_service_instance
    if _export_service_instance is None:
        _export_service_instance = SessionExportService()
    return _export_service_instance
