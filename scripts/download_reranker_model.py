#!/usr/bin/env python3
"""Download and cache the reranker model for local use.

This script pre-downloads the BAAI/bge-reranker-v2-m3 model to avoid
cold-start delays during the first retrieval request.

Usage:
    python scripts/download_reranker_model.py
"""

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def download_reranker_model():
    """Download the reranker model from Hugging Face."""
    try:
        from sentence_transformers import CrossEncoder
    except ImportError:
        logger.error("sentence-transformers not installed. Install it with:")
        logger.error("  pip install sentence-transformers")
        return False

    try:
        from app.core.config import get_settings
        settings = get_settings()
        model_name = settings.reranker_model_name
    except Exception as e:
        logger.warning(f"Could not load settings: {e}")
        model_name = "BAAI/bge-reranker-v2-m3"

    logger.info(f"Downloading reranker model: {model_name}")
    logger.info("This may take a few minutes on first run...")

    try:
        # Download model (this caches it locally)
        model = CrossEncoder(model_name, trust_remote_code=True)
        logger.info(f"✓ Model downloaded and cached successfully")

        # Test prediction to ensure model works
        logger.info("Testing model...")
        test_query = "What is machine learning?"
        test_doc = "Machine learning is a subset of artificial intelligence."
        score = model.predict([(test_query, test_doc)])
        logger.info(f"✓ Model test passed (score: {score[0]:.4f})")

        return True
    except Exception as e:
        logger.error(f"Failed to download model: {e}")
        return False


if __name__ == "__main__":
    success = download_reranker_model()
    sys.exit(0 if success else 1)
