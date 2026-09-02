"""Batch processing utilities for optimization."""

import asyncio
import logging
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class BatchProcessor:
    """Batch processor for efficient processing of multiple items."""

    def __init__(self, batch_size: int = 100, max_concurrent: int = 5):
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def process_batch(
        self,
        items: list[T],
        process_func: Callable[[list[T]], Any],
    ) -> list[R]:
        """Process items in batches.

        Args:
            items: Items to process
            process_func: Function to process each batch

        Returns:
            List of processed results
        """
        if not items:
            return []

        results: list[R] = []

        for i in range(0, len(items), self.batch_size):
            batch = items[i : i + self.batch_size]

            async with self._semaphore:
                try:
                    batch_result = await process_func(batch)
                    results.extend(batch_result)
                except Exception:
                    logger.exception(f"Error processing batch {i}")
                    # Continue with next batch

        return results

    async def process_concurrent(
        self,
        items: list[T],
        process_func: Callable[[T], Any],
    ) -> list[R]:
        """Process items concurrently with semaphore control.

        Args:
            items: Items to process
            process_func: Function to process each item

        Returns:
            List of processed results
        """

        async def process_with_sem(item: T) -> R:
            async with self._semaphore:
                return await process_func(item)

        tasks = [process_with_sem(item) for item in items]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def map_batch(
        self,
        items: list[T],
        map_func: Callable[[T], R],
    ) -> list[R]:
        """Map function over items in batches.

        Args:
            items: Items to map
            map_func: Mapping function

        Returns:
            List of mapped results
        """
        results: list[R] = []

        for i in range(0, len(items), self.batch_size):
            batch = items[i : i + self.batch_size]
            batch_results = [map_func(item) for item in batch]
            results.extend(batch_results)

        return results


def chunk_list(items: list[T], chunk_size: int) -> list[list[T]]:
    """Split list into chunks.

    Args:
        items: List to split
        chunk_size: Size of each chunk

    Returns:
        List of chunks
    """
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


async def deduplicate_async(
    items: list[T],
    key_func: Callable[[T], str] | None = None,
) -> list[T]:
    """Deduplicate items while preserving order.

    Args:
        items: Items to deduplicate
        key_func: Optional function to extract key for comparison

    Returns:
        Deduplicated list
    """
    seen = set()
    result: list[T] = []

    for item in items:
        key = key_func(item) if key_func else item
        if key not in seen:
            seen.add(key)
            result.append(item)

    return result
