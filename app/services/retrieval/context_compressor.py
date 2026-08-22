"""Rule-based context compression for retrieval results."""

import logging
import re
import time

from app.services.observability.tracing import traced_span

logger = logging.getLogger(__name__)


class RuleBasedCompressor:
    """Fast rule-based context compressor without neural-network calls."""

    def __init__(
        self,
        max_length: int = 4000,
        keep_ratio: float = 0.6,
        min_sentence_length: int = 10,
        max_sentence_length: int = 300,
    ):
        self.max_length = max_length
        self.keep_ratio = keep_ratio
        self.min_sentence_length = min_sentence_length
        self.max_sentence_length = max_sentence_length
        self.stopwords = {
            "the",
            "is",
            "are",
            "a",
            "an",
            "to",
            "of",
            "in",
            "on",
            "for",
            "and",
            "or",
            "but",
            "with",
            "at",
            "by",
            "from",
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
            "上",
            "也",
            "很",
            "到",
            "说",
            "要",
        }

    def compress(
        self,
        query: str,
        documents: list[dict],
        max_length: int | None = None,
    ) -> tuple[list[dict], dict]:
        start_time = time.time()
        max_len = max_length or self.max_length
        if not documents:
            return [], {"status": "no_documents", "time_ms": 0}

        with traced_span("compression.rule_based", {"doc_count": len(documents)}):
            query_terms = self._extract_terms(query)
            compressed_docs = []
            current_length = 0
            total_original_chars = 0
            total_compressed_chars = 0

            for doc in documents:
                if current_length >= max_len:
                    break
                content = doc.get("text", "") or doc.get("content", "")
                total_original_chars += len(content)
                compressed_content, sent_stats = self._compress_document(
                    content,
                    query_terms,
                    remaining_budget=max_len - current_length,
                )
                if compressed_content:
                    compressed_doc = {
                        **doc,
                        "text": compressed_content,
                        "original_length": len(content),
                        "compressed_length": len(compressed_content),
                        "compression_ratio": round(len(compressed_content) / len(content), 2) if content else 0,
                        "sentences_kept": sent_stats["kept"],
                        "sentences_total": sent_stats["total"],
                    }
                    compressed_docs.append(compressed_doc)
                    current_length += len(compressed_content)
                    total_compressed_chars += len(compressed_content)

            elapsed_ms = (time.time() - start_time) * 1000
            diagnostics = {
                "status": "success",
                "time_ms": round(elapsed_ms, 2),
                "original_docs": len(documents),
                "compressed_docs": len(compressed_docs),
                "original_chars": total_original_chars,
                "compressed_chars": total_compressed_chars,
                "overall_compression_ratio": round(total_compressed_chars / total_original_chars, 2)
                if total_original_chars > 0
                else 0,
                "info_retention_estimate": round(self.keep_ratio * 100, 1),
            }
            logger.info(
                f"Rule-based compression in {diagnostics['time_ms']}ms: "
                f"{total_original_chars} → {total_compressed_chars} chars "
                f"({diagnostics['overall_compression_ratio']:.0%} compression)"
            )
            return compressed_docs, diagnostics

    def _compress_document(
        self,
        content: str,
        query_terms: set[str],
        remaining_budget: int,
    ) -> tuple[str, dict]:
        sentences = self._split_sentences(content)
        if not sentences:
            return "", {"total": 0, "kept": 0}

        scored_sentences = []
        for index, sentence in enumerate(sentences):
            score = self._score_sentence(
                sentence,
                query_terms,
                position=index,
                total_sentences=len(sentences),
            )
            scored_sentences.append((sentence, score, index))
        scored_sentences.sort(key=lambda item: item[1], reverse=True)
        keep_count = max(1, int(len(scored_sentences) * self.keep_ratio))
        kept_sentences = scored_sentences[:keep_count]
        kept_sentences.sort(key=lambda item: item[2])

        compressed_parts = []
        current_len = 0
        for sentence, _score, _position in kept_sentences:
            sentence_len = len(sentence)
            if current_len + sentence_len > remaining_budget:
                break
            compressed_parts.append(sentence)
            current_len += sentence_len
        return " ".join(compressed_parts), {"total": len(sentences), "kept": len(compressed_parts)}

    def _split_sentences(self, text: str) -> list[str]:
        sentences = re.split(r"[.!?。！？\n]+", text)
        cleaned = []
        for sentence in sentences:
            sentence = sentence.strip()
            if self.min_sentence_length <= len(sentence) <= self.max_sentence_length:
                cleaned.append(sentence)
        return cleaned

    def _score_sentence(
        self,
        sentence: str,
        query_terms: set[str],
        position: int,
        total_sentences: int,
    ) -> float:
        sentence_terms = self._extract_terms(sentence)
        if query_terms:
            overlap = len(query_terms & sentence_terms)
            overlap_score = min(1.0, overlap / len(query_terms))
        else:
            overlap_score = 0.5

        sentence_length = len(sentence)
        if 20 <= sentence_length <= 200:
            length_score = 1.0
        elif sentence_length < 20:
            length_score = 0.5
        else:
            length_score = 0.7

        position_score = 1.0 if position == 0 or position == total_sentences - 1 else 0.8
        return overlap_score * 0.70 + length_score * 0.15 + position_score * 0.15

    def _extract_terms(self, text: str) -> set[str]:
        tokens = re.findall(r"[a-zA-Z0-9_]+|[一-鿿]", text.lower())
        return {token for token in tokens if len(token) >= 2 and token not in self.stopwords}


_compressor: RuleBasedCompressor | None = None


def get_rule_compressor(
    max_length: int = 4000,
    keep_ratio: float = 0.6,
) -> RuleBasedCompressor:
    global _compressor
    if _compressor is None:
        _compressor = RuleBasedCompressor(max_length=max_length, keep_ratio=keep_ratio)
    return _compressor


def compress_context(
    query: str,
    documents: list[dict],
    max_length: int = 4000,
) -> tuple[list[dict], dict]:
    compressor = get_rule_compressor(max_length=max_length)
    return compressor.compress(query, documents, max_length)
