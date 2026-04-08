import time
from pathlib import Path
from typing import Callable

from app.core.config import Settings
try:
    from app.ingestion.loaders import SUPPORTED_EXTENSIONS
except Exception:
    SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


class AutoIngestWatcher:
    def __init__(
        self,
        settings: Settings,
        ingest_fn: Callable[[list[Path], bool], dict] | None = None,
        delete_index_fn: Callable[..., dict] | None = None,
    ):
        self.settings = settings
        self._ingest_fn = ingest_fn
        self._delete_index_fn = delete_index_fn
        self._last_seen_signatures: dict[str, tuple[int, int]] = {}
        self._indexed_signatures: dict[str, tuple[int, int]] = {}

    def _resolve_ingest_fn(self) -> Callable[[list[Path], bool], dict]:
        if self._ingest_fn is None:
            from app.services.ingest_service import ingest_paths

            self._ingest_fn = ingest_paths
        return self._ingest_fn

    def _resolve_delete_index_fn(self) -> Callable[..., dict]:
        if self._delete_index_fn is None:
            from app.services.index_manager import delete_file_index

            self._delete_index_fn = delete_file_index
        return self._delete_index_fn

    def _watch_roots(self) -> list[Path]:
        roots: list[Path] = []
        if self.settings.auto_ingest_watch_docs:
            roots.append(self.settings.docs_path)
        if self.settings.auto_ingest_watch_uploads:
            roots.append(self.settings.uploads_path)
        uniq: list[Path] = []
        seen: set[str] = set()
        for root in roots:
            key = str(root.resolve())
            if key in seen:
                continue
            seen.add(key)
            uniq.append(root)
        return uniq

    @staticmethod
    def _signature(path: Path) -> tuple[int, int] | None:
        try:
            st = path.stat()
            return (int(st.st_mtime_ns), int(st.st_size))
        except Exception:
            return None

    def _iter_supported_files(self, root: Path):
        if not root.exists() or not root.is_dir():
            return
        iterator = root.rglob("*") if self.settings.auto_ingest_recursive else root.glob("*")
        for path in iterator:
            if not path.is_file():
                continue
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            yield path

    def _ingest_file(self, path: Path, sig: tuple[int, int]) -> bool:
        try:
            self._resolve_delete_index_fn()(path.name, remove_physical_file=False, source=str(path))
        except Exception:
            # Not indexed yet or cannot delete old index: keep going.
            pass

        result = self._resolve_ingest_fn()([path], reset_vector_store=False)
        loaded = int(result.get("loaded_documents", 0) or 0)
        if loaded > 0:
            self._indexed_signatures[str(path.resolve())] = sig
            return True

        # Avoid retry-loop for unreadable files with unchanged signature.
        self._indexed_signatures[str(path.resolve())] = sig
        return False

    def scan_once(self) -> dict[str, int]:
        if not self.settings.auto_ingest_enabled:
            return {"discovered": 0, "ready": 0, "ingested": 0}

        discovered = 0
        ready_paths: list[tuple[Path, tuple[int, int]]] = []
        current_keys: set[str] = set()

        for root in self._watch_roots():
            for path in self._iter_supported_files(root):
                discovered += 1
                key = str(path.resolve())
                current_keys.add(key)
                sig = self._signature(path)
                if sig is None:
                    continue

                if self._indexed_signatures.get(key) == sig:
                    self._last_seen_signatures[key] = sig
                    continue

                prev = self._last_seen_signatures.get(key)
                self._last_seen_signatures[key] = sig
                if prev == sig:
                    ready_paths.append((path, sig))

        for key in list(self._last_seen_signatures.keys()):
            if key not in current_keys:
                self._last_seen_signatures.pop(key, None)
                self._indexed_signatures.pop(key, None)

        ingested = 0
        for path, sig in ready_paths:
            try:
                if self._ingest_file(path, sig):
                    ingested += 1
            except Exception:
                # Keep last seen signature so unchanged file can retry later.
                self._indexed_signatures.pop(str(path.resolve()), None)

        return {"discovered": discovered, "ready": len(ready_paths), "ingested": ingested}

    def run_loop(self, stop_requested: Callable[[], bool]) -> None:
        interval = max(0.5, float(self.settings.auto_ingest_interval_seconds))
        while not stop_requested():
            self.scan_once()
            deadline = time.time() + interval
            while time.time() < deadline:
                if stop_requested():
                    return
                time.sleep(0.1)
