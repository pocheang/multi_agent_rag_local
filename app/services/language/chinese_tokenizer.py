"""Chinese text tokenization service using jieba."""

import logging

import jieba
import jieba.analyse

logger = logging.getLogger(__name__)


class ChineseTokenizer:
    """Handles Chinese text segmentation and keyword extraction."""

    def __init__(self, user_dict_path: str | None = None):
        """Initialize the tokenizer with optional custom dictionary.

        Args:
            user_dict_path: Path to custom dictionary file for domain-specific terms
        """
        self._initialized = False
        self.user_dict_path = user_dict_path

        if user_dict_path:
            try:
                jieba.load_userdict(user_dict_path)
                logger.info(f"Loaded custom dictionary from {user_dict_path}")
            except Exception as e:
                logger.warning(f"Failed to load custom dictionary: {e}")

        self._initialized = True

    def tokenize(self, text: str, cut_all: bool = False) -> list[str]:
        """Segment Chinese text into tokens.

        Args:
            text: Input Chinese text
            cut_all: If True, use full mode (more aggressive segmentation)

        Returns:
            List of tokens
        """
        if not text or not text.strip():
            return []

        tokens = jieba.cut(text, cut_all=cut_all)
        return [token.strip() for token in tokens if token.strip()]

    def tokenize_for_search(self, text: str) -> list[str]:
        """Segment text optimized for search (balanced precision/recall).

        Args:
            text: Input Chinese text

        Returns:
            List of tokens optimized for search
        """
        if not text or not text.strip():
            return []

        tokens = jieba.cut_for_search(text)
        return [token.strip() for token in tokens if token.strip()]

    def extract_keywords(
        self, text: str, topK: int = 10, withWeight: bool = False, allowPOS: tuple | None = None
    ) -> list[str] | list[tuple[str, float]]:
        """Extract keywords using TF-IDF.

        Args:
            text: Input Chinese text
            topK: Number of top keywords to extract
            withWeight: If True, return (keyword, weight) tuples
            allowPOS: Allowed POS tags (e.g., ('n', 'v', 'vn') for nouns and verbs)

        Returns:
            List of keywords or (keyword, weight) tuples
        """
        if not text or not text.strip():
            return []

        keywords = jieba.analyse.extract_tags(text, topK=topK, withWeight=withWeight, allowPOS=allowPOS)

        return keywords

    def extract_keywords_textrank(
        self, text: str, topK: int = 10, withWeight: bool = False, allowPOS: tuple | None = None
    ) -> list[str] | list[tuple[str, float]]:
        """Extract keywords using TextRank algorithm.

        Args:
            text: Input Chinese text
            topK: Number of top keywords to extract
            withWeight: If True, return (keyword, weight) tuples
            allowPOS: Allowed POS tags

        Returns:
            List of keywords or (keyword, weight) tuples
        """
        if not text or not text.strip():
            return []

        keywords = jieba.analyse.textrank(text, topK=topK, withWeight=withWeight, allowPOS=allowPOS)

        return keywords

    def add_word(self, word: str, freq: int | None = None, tag: str | None = None):
        """Add a word to the dictionary dynamically.

        Args:
            word: Word to add
            freq: Word frequency (higher = more likely to be segmented)
            tag: Part-of-speech tag
        """
        jieba.add_word(word, freq, tag)
        logger.debug(f"Added word to dictionary: {word}")

    def remove_word(self, word: str):
        """Remove a word from the dictionary.

        Args:
            word: Word to remove
        """
        jieba.del_word(word)
        logger.debug(f"Removed word from dictionary: {word}")

    def suggest_freq(self, segment: str | tuple, tune: bool = False) -> int:
        """Suggest word frequency to improve segmentation.

        Args:
            segment: Word or tuple of words
            tune: If True, adjust frequency automatically

        Returns:
            Suggested frequency
        """
        return jieba.suggest_freq(segment, tune)


# Global tokenizer instance
_tokenizer: ChineseTokenizer | None = None


def get_tokenizer(user_dict_path: str | None = None) -> ChineseTokenizer:
    """Get or create the global tokenizer instance.

    Args:
        user_dict_path: Path to custom dictionary (only used on first call)

    Returns:
        ChineseTokenizer instance
    """
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = ChineseTokenizer(user_dict_path)
    return _tokenizer
