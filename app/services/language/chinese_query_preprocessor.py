"""Chinese query preprocessing service."""

import logging
import re
from typing import Any

from app.services.language.chinese_tokenizer import ChineseTokenizer, get_tokenizer
from app.services.query.synonyms import SynonymExpander, get_expander

logger = logging.getLogger(__name__)


class ChineseQueryPreprocessor:
    """Preprocesses Chinese queries for improved retrieval."""

    def __init__(
        self,
        tokenizer: ChineseTokenizer | None = None,
        expander: SynonymExpander | None = None,
        enable_synonym_expansion: bool = True,
        enable_stopword_removal: bool = True,
    ):
        """Initialize the preprocessor.

        Args:
            tokenizer: Chinese tokenizer instance
            expander: Synonym expander instance
            enable_synonym_expansion: Whether to expand queries with synonyms
            enable_stopword_removal: Whether to remove stopwords
        """
        self.tokenizer = tokenizer or get_tokenizer()
        self.expander = expander or get_expander()
        self.enable_synonym_expansion = enable_synonym_expansion
        self.enable_stopword_removal = enable_stopword_removal

        # Common Chinese stopwords
        self.stopwords = self._load_default_stopwords()

    def _load_default_stopwords(self) -> set:
        """Load default Chinese stopwords."""
        stopwords = {
            # Common particles
            "的",
            "了",
            "在",
            "是",
            "我",
            "有",
            "和",
            "就",
            "不",
            "人",
            "都",
            "一",
            "一个",
            "上",
            "也",
            "很",
            "到",
            "说",
            "要",
            "去",
            "你",
            "会",
            "着",
            "没有",
            "看",
            "好",
            "自己",
            "这",
            "那",
            "里",
            "就是",
            "还",
            "为",
            "能",
            "他",
            # Question words
            "什么",
            "怎么",
            "如何",
            "哪里",
            "哪个",
            "为什么",
            "多少",
            # Conjunctions
            "但是",
            "因为",
            "所以",
            "如果",
            "虽然",
            "然而",
            "而且",
            "或者",
            # Common verbs (low semantic value)
            "可以",
            "需要",
            "应该",
            "必须",
            "想要",
            "希望",
            # Punctuation and symbols
            "，",
            "。",
            "！",
            "？",
            "；",
            "：",
            "、",
            """, """,
            "'",
            "（",
            "）",
            "【",
            "】",
            "《",
            "》",
            "…",
            "—",
        }
        return stopwords

    def detect_language(self, text: str) -> str:
        """Detect if text is primarily Chinese or English.

        Args:
            text: Input text

        Returns:
            "chinese", "english", or "mixed"
        """
        if not text:
            return "unknown"

        chinese_chars = len(re.findall(r"[一-鿿]", text))
        english_chars = len(re.findall(r"[a-zA-Z]", text))
        total_chars = chinese_chars + english_chars

        if total_chars == 0:
            return "unknown"

        chinese_ratio = chinese_chars / total_chars

        if chinese_ratio > 0.7:
            return "chinese"
        elif chinese_ratio < 0.3:
            return "english"
        else:
            return "mixed"

    def normalize_text(self, text: str) -> str:
        """Normalize Chinese text.

        Args:
            text: Input text

        Returns:
            Normalized text
        """
        # Convert full-width to half-width
        text = text.replace("　", " ")  # Full-width space to half-width

        # Normalize quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(""", "'").replace(""", "'")

        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def remove_stopwords(self, tokens: list[str]) -> list[str]:
        """Remove stopwords from token list.

        Args:
            tokens: List of tokens

        Returns:
            Filtered tokens
        """
        if not self.enable_stopword_removal:
            return tokens

        filtered = [token for token in tokens if token not in self.stopwords]

        # Keep at least one token even if all are stopwords
        if not filtered and tokens:
            filtered = [tokens[0]]

        return filtered

    def preprocess(
        self, query: str, expand_synonyms: bool = True, return_metadata: bool = False
    ) -> str | dict[str, Any]:
        """Preprocess a Chinese query.

        Args:
            query: Input query string
            expand_synonyms: Whether to expand with synonyms
            return_metadata: If True, return dict with metadata

        Returns:
            Preprocessed query string or dict with metadata
        """
        if not query or not query.strip():
            return (
                ""
                if not return_metadata
                else {"processed_query": "", "original_query": query, "tokens": [], "language": "unknown"}
            )

        # Detect language
        language = self.detect_language(query)

        # Normalize text
        normalized = self.normalize_text(query)

        # Tokenize based on language
        if language == "chinese" or language == "mixed":
            tokens = self.tokenizer.tokenize_for_search(normalized)
        else:
            # For English, simple split
            tokens = normalized.split()

        # Remove stopwords
        filtered_tokens = self.remove_stopwords(tokens)

        # Expand with synonyms if enabled
        if expand_synonyms and self.enable_synonym_expansion and language in ["chinese", "mixed"]:
            expanded_tokens = self.expander.expand_query(filtered_tokens, max_expansions=2)
        else:
            expanded_tokens = filtered_tokens

        # Reconstruct query
        processed_query = " ".join(expanded_tokens)

        if return_metadata:
            return {
                "processed_query": processed_query,
                "original_query": query,
                "normalized_query": normalized,
                "tokens": tokens,
                "filtered_tokens": filtered_tokens,
                "expanded_tokens": expanded_tokens,
                "language": language,
                "stopwords_removed": len(tokens) - len(filtered_tokens),
                "synonyms_added": len(expanded_tokens) - len(filtered_tokens),
            }

        return processed_query

    def extract_keywords(self, query: str, topK: int = 5) -> list[str]:
        """Extract key terms from query.

        Args:
            query: Input query
            topK: Number of keywords to extract

        Returns:
            List of keywords
        """
        language = self.detect_language(query)

        if language in ["chinese", "mixed"]:
            # Use jieba keyword extraction
            keywords = self.tokenizer.extract_keywords(query, topK=topK)
            return keywords
        else:
            # For English, use simple tokenization
            tokens = query.lower().split()
            filtered = self.remove_stopwords(tokens)
            return filtered[:topK]

    def add_stopword(self, word: str):
        """Add a custom stopword.

        Args:
            word: Stopword to add
        """
        self.stopwords.add(word)
        logger.debug(f"Added stopword: {word}")

    def remove_stopword(self, word: str):
        """Remove a word from stopwords.

        Args:
            word: Word to remove from stopwords
        """
        self.stopwords.discard(word)
        logger.debug(f"Removed stopword: {word}")


# Global preprocessor instance
_preprocessor: ChineseQueryPreprocessor | None = None


def get_preprocessor(
    enable_synonym_expansion: bool = True, enable_stopword_removal: bool = True
) -> ChineseQueryPreprocessor:
    """Get or create the global preprocessor instance.

    Args:
        enable_synonym_expansion: Whether to enable synonym expansion
        enable_stopword_removal: Whether to enable stopword removal

    Returns:
        ChineseQueryPreprocessor instance
    """
    global _preprocessor
    if _preprocessor is None:
        _preprocessor = ChineseQueryPreprocessor(
            enable_synonym_expansion=enable_synonym_expansion, enable_stopword_removal=enable_stopword_removal
        )
    return _preprocessor
