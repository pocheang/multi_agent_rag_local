"""Performance optimization for PDF processing - parallel processing and caching."""

import hashlib
import json
import logging
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def compute_file_hash(file_path: Path) -> str:
    """
    Compute SHA256 hash of file for caching.

    Args:
        file_path: Path to file

    Returns:
        Hex digest of file hash
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_config_hash(config_dict: dict) -> str:
    """
    Compute hash of configuration parameters.

    Args:
        config_dict: Configuration parameters

    Returns:
        Short hash of configuration (8 chars)
    """
    if not config_dict:
        return ""

    # Sort keys for consistent hashing
    config_str = json.dumps(config_dict, sort_keys=True)
    return hashlib.md5(config_str.encode()).hexdigest()[:8]


class PDFProcessingCache:
    """Cache for PDF processing results with configuration-aware keys."""

    def __init__(self, cache_dir: Path = Path("./data/cache/pdf_processing"), ttl_days: int = 30):
        """
        Initialize cache.

        Args:
            cache_dir: Directory to store cache files
            ttl_days: Time-to-live for cache entries in days (default: 30)
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_days = ttl_days
        self.ttl_seconds = ttl_days * 24 * 3600

    def get_cache_path(self, file_path: Path, operation: str, config: dict | None = None) -> Path:
        """
        Get cache file path for a PDF, operation, and configuration.

        Args:
            file_path: Path to PDF file
            operation: Operation name (e.g., 'docling', 'ocr', 'charts')
            config: Configuration parameters that affect the result

        Returns:
            Path to cache file
        """
        file_hash = compute_file_hash(file_path)

        # Include config hash in cache key to avoid collisions
        if config:
            config_hash = compute_config_hash(config)
            cache_file = f"{file_hash}_{operation}_{config_hash}.json"
        else:
            cache_file = f"{file_hash}_{operation}.json"

        return self.cache_dir / cache_file

    def is_cache_valid(self, cache_path: Path) -> bool:
        """
        Check if cache file is valid (exists and not expired).

        Args:
            cache_path: Path to cache file

        Returns:
            True if cache is valid, False if expired or missing
        """
        if not cache_path.exists():
            return False

        try:
            cache_age = time.time() - cache_path.stat().st_mtime
            return cache_age < self.ttl_seconds
        except (OSError, PermissionError) as e:
            logger.warning(f"Failed to check cache validity: {e}")
            return False

    def get(self, file_path: Path, operation: str, config: dict | None = None) -> Any | None:
        """
        Get cached result.

        Args:
            file_path: Path to PDF file
            operation: Operation name (e.g., 'docling', 'ocr', 'charts')
            config: Configuration parameters used for this operation

        Returns:
            Cached result or None
        """
        cache_path = self.get_cache_path(file_path, operation, config)

        # Check if cache is valid (exists and not expired)
        if not self.is_cache_valid(cache_path):
            # Delete expired cache if it exists
            if cache_path.exists():
                try:
                    cache_path.unlink()
                    logger.info(f"Cache expired for {file_path.name}, removing")
                except Exception as e:
                    logger.warning(f"Failed to delete expired cache: {e}")
            return None

        try:
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"Cache hit for {file_path.name} - {operation}")
                return data
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"Cache read failed for {file_path.name}: {e}")
            return None

    def set(self, file_path: Path, operation: str, result: Any, config: dict | None = None) -> None:
        """
        Cache result with atomic write to prevent corruption.

        Args:
            file_path: Path to PDF file
            operation: Operation name
            result: Result to cache (must be JSON serializable)
            config: Configuration parameters used for this operation
        """
        cache_path = self.get_cache_path(file_path, operation, config)

        try:
            # Use temporary file + atomic rename to prevent corruption
            temp_path = cache_path.with_suffix(".tmp")

            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            # Atomic operation - replaces existing file safely
            temp_path.replace(cache_path)
            logger.info(f"Cached result for {file_path.name} - {operation}")

        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Cache write failed for {file_path.name}: {e}")
            # Clean up temp file if it exists
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

    def clear(self, file_path: Path | None = None, operation: str | None = None) -> None:
        """
        Clear cache.

        Args:
            file_path: If provided, clear cache for this file only.
                      If None, clear all cache.
            operation: If provided with file_path, clear only this operation's cache.
        """
        try:
            if file_path:
                file_hash = compute_file_hash(file_path)
                if operation:
                    # Clear specific operation for this file
                    pattern = f"{file_hash}_{operation}_*.json"
                else:
                    # Clear all operations for this file
                    pattern = f"{file_hash}_*.json"

                cleared = 0
                for cache_file in self.cache_dir.glob(pattern):
                    cache_file.unlink()
                    cleared += 1

                if cleared > 0:
                    logger.info(f"Cleared {cleared} cache entries for {file_path.name}")
            else:
                # Clear all cache
                cleared = 0
                for cache_file in self.cache_dir.glob("*.json"):
                    cache_file.unlink()
                    cleared += 1
                logger.info(f"Cleared all cache ({cleared} entries)")

        except OSError as e:
            logger.error(f"Cache clear failed: {e}")

    def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.

        Returns:
            Number of cache files cleaned
        """
        cleaned = 0

        try:
            for cache_file in self.cache_dir.glob("*.json"):
                if not self.is_cache_valid(cache_file):
                    try:
                        cache_file.unlink()
                        cleaned += 1
                    except OSError as e:
                        logger.warning(f"Failed to delete expired cache file {cache_file}: {e}")

            if cleaned > 0:
                logger.info(f"Cleaned {cleaned} expired cache entries")

        except OSError as e:
            logger.warning(f"Cache cleanup failed: {e}")

        return cleaned

    def get_cache_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with keys: total_files, total_size_mb, expired_files, valid_files
        """
        stats = {"total_files": 0, "total_size_mb": 0.0, "expired_files": 0, "valid_files": 0}

        try:
            total_size = 0

            for cache_file in self.cache_dir.glob("*.json"):
                stats["total_files"] += 1

                try:
                    total_size += cache_file.stat().st_size

                    if self.is_cache_valid(cache_file):
                        stats["valid_files"] += 1
                    else:
                        stats["expired_files"] += 1

                except OSError as e:
                    logger.warning(f"Failed to stat cache file {cache_file}: {e}")

            stats["total_size_mb"] = total_size / (1024 * 1024)

        except OSError as e:
            logger.warning(f"Failed to get cache stats: {e}")

        return stats


def process_pdfs_parallel(
    pdf_paths: list[Path], process_func: Callable[[Path], Any], max_workers: int = 4, use_processes: bool = False
) -> list[Any]:
    """
    Process multiple PDFs in parallel.

    Args:
        pdf_paths: List of PDF file paths
        process_func: Function to process each PDF
        max_workers: Maximum number of parallel workers
        use_processes: Use ProcessPoolExecutor instead of ThreadPoolExecutor

    Returns:
        List of results in same order as input
    """
    if len(pdf_paths) == 1:
        # No need for parallel processing
        return [process_func(pdf_paths[0])]

    executor_class = ProcessPoolExecutor if use_processes else ThreadPoolExecutor

    results = [None] * len(pdf_paths)

    with executor_class(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_index = {executor.submit(process_func, pdf_path): i for i, pdf_path in enumerate(pdf_paths)}

        # Collect results as they complete
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                result = future.result()
                results[index] = result
                logger.info(f"Completed {index + 1}/{len(pdf_paths)}")
            except Exception as e:
                logger.error(f"Processing failed for {pdf_paths[index]}: {e}")
                results[index] = None

    return results


def process_pages_parallel(
    pages_data: list[Any], process_func: Callable[[Any], Any], max_workers: int = 4
) -> list[Any]:
    """
    Process multiple pages in parallel.

    Args:
        pages_data: List of page data
        process_func: Function to process each page
        max_workers: Maximum number of parallel workers

    Returns:
        List of results in same order as input
    """
    if len(pages_data) <= 1:
        return [process_func(page) for page in pages_data]

    results = [None] * len(pages_data)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {executor.submit(process_func, page): i for i, page in enumerate(pages_data)}

        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                results[index] = future.result()
            except Exception as e:
                logger.error(f"Page {index} processing failed: {e}")
                results[index] = None

    return results


def estimate_processing_time(file_path: Path, mode: str = "docling_enhanced") -> float:
    """
    Estimate processing time for a PDF.

    Args:
        file_path: Path to PDF file
        mode: Processing mode

    Returns:
        Estimated time in seconds
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(file_path))
        num_pages = len(reader.pages)
    except (ImportError, OSError, ValueError) as e:
        # Fallback estimate based on file size
        logger.debug(f"Failed to read PDF page count, using file size estimate: {e}")
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        num_pages = int(file_size_mb * 2)  # Rough estimate

    # Time estimates per page (seconds)
    time_per_page = {"pypdf": 0.5, "docling": 3.0, "docling_enhanced": 4.0, "hybrid": 5.0}

    base_time = num_pages * time_per_page.get(mode, 3.0)

    # Add overhead
    overhead = 2.0  # seconds

    return base_time + overhead


def should_use_parallel(pdf_paths: list[Path], threshold: int = 3) -> bool:
    """
    Determine if parallel processing is beneficial.

    Args:
        pdf_paths: List of PDF paths
        threshold: Minimum number of files to use parallel processing

    Returns:
        True if parallel processing should be used
    """
    return len(pdf_paths) >= threshold
