"""
Graph RAG + PDF Accuracy Optimization Tool

This script provides tools to optimize Graph RAG accuracy after PDF processing:
1. Enhanced entity extraction from PDF content
2. Improved graph signal scoring
3. PDF structure-aware entity recognition
4. Cross-language entity linking
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.graph.knowledge.client import Neo4jClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


_configure_stdio()

# Enhanced entity patterns for PDF content
PDF_ENTITY_PATTERNS = {
    # Technical terms
    "tech": re.compile(
        r"\b(?:AI|ML|DL|NLP|LLM|RAG|API|GPU|CPU|HTTP|HTTPS|REST|GraphQL|"
        r"Docker|Kubernetes|Redis|MongoDB|PostgreSQL|MySQL|Neo4j)\b"
    ),
    # Organizations
    "org": re.compile(
        r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Inc|Corp|Ltd|LLC|GmbH|AG))\.?)\b"
    ),
    # Products/Systems
    "product": re.compile(
        r"\b(?:[A-Z][a-z]+(?:[A-Z][a-z]+)+)\b"  # CamelCase words
    ),
    # Chinese entities
    "chinese": re.compile(
        r"[一-鿿]{2,}"
    ),
}

# Enhanced entity aliases for better matching
ENHANCED_ALIASES = {
    # AI/ML terms
    "ai": ["artificial intelligence", "人工智能", "AI"],
    "ml": ["machine learning", "机器学习", "ML"],
    "llm": ["large language model", "大语言模型", "大模型"],
    "rag": ["retrieval augmented generation", "检索增强生成"],
    "nlp": ["natural language processing", "自然语言处理"],

    # Technical terms
    "api": ["application programming interface", "应用程序接口"],
    "gpu": ["graphics processing unit", "图形处理器"],
    "cpu": ["central processing unit", "中央处理器"],

    # Common acronyms
    "pdf": ["portable document format"],
    "ocr": ["optical character recognition", "光学字符识别"],
    "ui": ["user interface", "用户界面"],
    "ux": ["user experience", "用户体验"],
}


class GraphRAGOptimizer:
    """Optimizer for Graph RAG accuracy with PDF content."""

    def __init__(self):
        self.settings = get_settings()
        self.client: Neo4jClient | None = None

    def close(self):
        """Close Neo4j connection."""
        if self.client is not None:
            self.client.close()
            self.client = None

    def _get_client(self) -> Neo4jClient:
        if self.client is None:
            self.client = Neo4jClient()
        return self.client

    def extract_pdf_entities(self, text: str, source: str = "") -> list[dict[str, Any]]:
        """
        Extract entities from PDF text with enhanced patterns.

        Args:
            text: PDF text content
            source: Source document name

        Returns:
            List of entities with type, text, and position
        """
        entities = []

        # Extract by pattern type
        for entity_type, pattern in PDF_ENTITY_PATTERNS.items():
            for match in pattern.finditer(text):
                entity_text = match.group(0)
                entities.append({
                    "type": entity_type,
                    "text": entity_text,
                    "start": match.start(),
                    "end": match.end(),
                    "source": source,
                })

        # Deduplicate by text
        seen = set()
        unique_entities = []
        for entity in entities:
            key = (entity["type"], entity["text"].lower())
            if key not in seen:
                seen.add(key)
                unique_entities.append(entity)

        return unique_entities

    def enrich_entities_with_aliases(self, entities: list[dict]) -> list[dict]:
        """
        Enrich entities with cross-language aliases.

        Args:
            entities: List of entity dictionaries

        Returns:
            Entities with added aliases
        """
        for entity in entities:
            text_lower = entity["text"].lower()
            if text_lower in ENHANCED_ALIASES:
                entity["aliases"] = ENHANCED_ALIASES[text_lower]
            else:
                entity["aliases"] = []

        return entities

    def calculate_enhanced_graph_signal(
        self,
        entities: list[dict],
        neighbors: list[dict],
        paths: list[dict],
        pdf_structure_score: float = 0.0,
    ) -> float:
        """
        Calculate enhanced graph signal score with PDF-aware weighting.

        The original scoring is:
        - Entities: 30%
        - Neighbors: 40%
        - Paths: 30%

        Enhanced scoring adds:
        - PDF structure awareness (15% weight)
        - Higher weight for strong relations (up to 10% bonus)

        Args:
            entities: Entity list
            neighbors: Neighbor relationships
            paths: 2-hop paths
            pdf_structure_score: Score from PDF structure (0-1)

        Returns:
            Enhanced signal score (0-1)
        """
        # Base scores
        entity_score = min(1.0, len(entities) / 3.0)  # More aggressive than /4

        # Neighbor score with quality weighting
        if neighbors:
            # Prioritize high-quality relations
            weights = [float(n.get("weight", 0.0)) for n in neighbors]
            high_quality = [w for w in weights if w >= 0.8]

            if high_quality:
                neighbor_score = (sum(weights[:15]) + sum(high_quality) * 0.5) / (len(weights[:15]) + len(high_quality) * 0.5)
            else:
                neighbor_score = sum(weights[:15]) / len(weights[:15])

            neighbor_score = min(1.0, neighbor_score * 1.1)  # 10% boost
        else:
            neighbor_score = 0.0

        # Path score with multi-hop bonus
        if paths:
            weights = [float(p.get("weight", 0.0)) for p in paths]
            path_score = sum(weights[:10]) / len(weights[:10])
            path_score = min(1.0, path_score * 1.15)  # 15% boost for multi-hop
        else:
            path_score = 0.0

        # Weighted combination with PDF structure
        components = []
        weights = []

        if entities:
            components.append(entity_score)
            weights.append(0.25)

        if neighbors:
            components.append(neighbor_score)
            weights.append(0.35)

        if paths:
            components.append(path_score)
            weights.append(0.25)

        if pdf_structure_score > 0:
            components.append(pdf_structure_score)
            weights.append(0.15)

        if not components:
            return 0.0

        # Normalize weights
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]

        # Calculate weighted score
        score = sum(c * w for c, w in zip(components, normalized_weights))

        return min(1.0, score)

    def analyze_pdf_structure_score(self, text: str) -> float:
        """
        Analyze PDF structure quality for graph extraction.

        Factors:
        - Has clear sections/headers (0.3)
        - Has tables (0.2)
        - Has lists (0.2)
        - Has references (0.15)
        - Reasonable text density (0.15)

        Args:
            text: PDF text content

        Returns:
            Structure quality score (0-1)
        """
        score = 0.0

        # Check for headers (markdown-style or numbered)
        if re.search(r"^#+\s+.+$|^\d+\.\s+[A-Z]", text, re.MULTILINE):
            score += 0.3

        # Check for tables (markdown or structured)
        if re.search(r"\|.+\||\t.+\t", text):
            score += 0.2

        # Check for lists
        if re.search(r"^[-*•]\s+|^\d+\.\s+", text, re.MULTILINE):
            score += 0.2

        # Check for references section
        if re.search(r"(?i)references?|bibliography|参考文献", text):
            score += 0.15

        # Check text density (not too sparse, not too dense)
        words = len(text.split())
        chars = len(text)
        if chars > 0:
            density = words / (chars / 100)  # words per 100 chars
            if 3 <= density <= 20:  # reasonable range
                score += 0.15

        return min(1.0, score)

    def get_graph_coverage_stats(self) -> dict:
        """Get statistics about graph coverage and quality."""
        try:
            client = self._get_client()
            with client.driver.session() as session:
                # Total entities
                entity_count_result = session.run(
                    "MATCH (e:Entity) RETURN count(e) as count"
                ).single()
                entity_count = entity_count_result["count"] if entity_count_result else 0

                # Total relationships
                rel_count_result = session.run(
                    "MATCH ()-[r]->() RETURN count(r) as count"
                ).single()
                rel_count = rel_count_result["count"] if rel_count_result else 0

                # Entities with relationships
                connected_result = session.run(
                    "MATCH (e:Entity)-[r]-() WITH e, count(r) as degree "
                    "WHERE degree > 0 RETURN count(e) as count"
                ).single()
                connected_count = connected_result["count"] if connected_result else 0

            # Average degree
            avg_degree = (rel_count * 2 / entity_count) if entity_count > 0 else 0

            # Coverage percentage
            coverage = (connected_count / entity_count * 100) if entity_count > 0 else 0

            return {
                "available": True,
                "total_entities": entity_count,
                "total_relationships": rel_count,
                "connected_entities": connected_count,
                "isolated_entities": entity_count - connected_count,
                "average_degree": round(avg_degree, 2),
                "coverage_percentage": round(coverage, 2),
            }
        except Exception as e:
            logger.warning("Failed to get coverage stats: %s", e)
            return {
                "available": False,
                "error": type(e).__name__,
                "message": "Neo4j is unavailable. Start Neo4j to inspect graph coverage.",
            }

    def suggest_optimizations(self, stats: dict) -> list[str]:
        """
        Suggest optimizations based on graph statistics.

        Args:
            stats: Graph coverage statistics

        Returns:
            List of optimization suggestions
        """
        suggestions = []

        if not stats.get("available", True):
            return [
                "Start Neo4j and rerun `python scripts/optimize_graph_rag_accuracy.py stats`.",
                "Use `analyze` or `extract` for PDF-only checks without graph connectivity.",
            ]

        coverage = stats.get("coverage_percentage", 0)
        avg_degree = stats.get("average_degree", 0)
        isolated = stats.get("isolated_entities", 0)

        if coverage < 60:
            suggestions.append(
                f"⚠️  Low graph coverage ({coverage:.1f}%). Consider:\n"
                "   - Re-processing PDFs with enhanced entity extraction\n"
                "   - Adding more relationship types\n"
                "   - Cross-referencing entities across documents"
            )

        if avg_degree < 2.0:
            suggestions.append(
                f"⚠️  Low connectivity (avg degree: {avg_degree:.1f}). Consider:\n"
                "   - Adding co-occurrence relationships\n"
                "   - Enriching with external knowledge\n"
                "   - Using entity resolution to merge similar entities"
            )

        if isolated > 0:
            suggestions.append(
                f"⚠️  {isolated} isolated entities found. Consider:\n"
                "   - Removing noise entities\n"
                "   - Adding implicit relationships\n"
                "   - Linking to document structure"
            )

        if not suggestions:
            suggestions.append("✅ Graph quality looks good! Consider incremental improvements.")

        return suggestions


def main():
    """Run the optimization tool."""
    import argparse

    parser = argparse.ArgumentParser(description="Graph RAG + PDF Accuracy Optimization Tool")
    parser.add_argument(
        "command",
        choices=["analyze", "extract", "optimize", "stats"],
        help="Command to run",
    )
    parser.add_argument(
        "--pdf-path",
        type=str,
        help="Path to PDF file (for extract command)",
    )
    parser.add_argument(
        "--text",
        type=str,
        help="Text content to analyze",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (JSON)",
    )

    args = parser.parse_args()

    optimizer = GraphRAGOptimizer()

    try:
        if args.command == "stats":
            logger.info("Fetching graph coverage statistics...")
            stats = optimizer.get_graph_coverage_stats()
            suggestions = optimizer.suggest_optimizations(stats)

            print("\n" + "="*60)
            print("GRAPH COVERAGE STATISTICS")
            print("="*60)
            if not stats.get("available", True):
                print("status.................................. unavailable")
                print(f"error................................... {stats.get('error', 'UnknownError')}")
                print(f"message................................. {stats.get('message', '')}")
                print("suggested_action........................ docker compose up -d neo4j")
            else:
                for key, value in stats.items():
                    if key == "available":
                        continue
                    print(f"{key:.<40} {value}")

            print("\n" + "="*60)
            print("OPTIMIZATION SUGGESTIONS")
            print("="*60)
            for suggestion in suggestions:
                print(f"\n{suggestion}")

            if args.output:
                output_data = {
                    "stats": stats,
                    "suggestions": suggestions,
                }
                Path(args.output).write_text(json.dumps(output_data, indent=2, ensure_ascii=False))
                logger.info(f"Results saved to {args.output}")

        elif args.command == "extract":
            if not args.pdf_path:
                logger.error("--pdf-path required for extract command")
                return

            pdf_path = Path(args.pdf_path)
            if not pdf_path.exists():
                logger.error(f"PDF file not found: {pdf_path}")
                return

            logger.info(f"Extracting entities from {pdf_path.name}...")

            # Read PDF text (simplified - use proper loader in production)
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(pdf_path))
                text = "\n".join(page.extract_text() for page in reader.pages)
            except Exception as e:
                logger.error(f"Failed to read PDF: {e}")
                return

            entities = optimizer.extract_pdf_entities(text, str(pdf_path))
            entities = optimizer.enrich_entities_with_aliases(entities)

            print(f"\nExtracted {len(entities)} entities:")
            for entity in entities[:20]:  # Show first 20
                aliases = entity.get("aliases", [])
                alias_str = f" (aliases: {', '.join(aliases[:3])})" if aliases else ""
                print(f"  [{entity['type']}] {entity['text']}{alias_str}")

            if len(entities) > 20:
                print(f"  ... and {len(entities) - 20} more")

            if args.output:
                Path(args.output).write_text(json.dumps(entities, indent=2, ensure_ascii=False))
                logger.info(f"Entities saved to {args.output}")

        elif args.command == "analyze":
            if not args.text and not args.pdf_path:
                logger.error("--text or --pdf-path required for analyze command")
                return

            if args.pdf_path:
                pdf_path = Path(args.pdf_path)
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(str(pdf_path))
                    text = "\n".join(page.extract_text() for page in reader.pages)
                except Exception as e:
                    logger.error(f"Failed to read PDF: {e}")
                    return
            else:
                text = args.text

            logger.info("Analyzing PDF structure...")
            structure_score = optimizer.analyze_pdf_structure_score(text)

            print("\n" + "="*60)
            print("PDF STRUCTURE ANALYSIS")
            print("="*60)
            print(f"Structure Quality Score: {structure_score:.2f}")

            if structure_score >= 0.7:
                print("✅ Excellent structure for graph extraction")
            elif structure_score >= 0.5:
                print("⚠️  Good structure, some improvements possible")
            else:
                print("❌ Poor structure, consider enhanced preprocessing")

            # Extract entities
            entities = optimizer.extract_pdf_entities(text)
            print(f"\nExtracted Entities: {len(entities)}")

            # Calculate enhanced signal (mock data for demo)
            signal_score = optimizer.calculate_enhanced_graph_signal(
                entities=[{"entity": e["text"]} for e in entities[:10]],
                neighbors=[],
                paths=[],
                pdf_structure_score=structure_score,
            )
            print(f"Enhanced Graph Signal: {signal_score:.2f}")

        elif args.command == "optimize":
            logger.info("Running optimization analysis...")
            stats = optimizer.get_graph_coverage_stats()
            suggestions = optimizer.suggest_optimizations(stats)

            print("\n" + "="*60)
            print("OPTIMIZATION REPORT")
            print("="*60)
            print("\nCurrent State:")
            for key, value in stats.items():
                print(f"  {key}: {value}")

            print("\nRecommendations:")
            for i, suggestion in enumerate(suggestions, 1):
                print(f"\n{i}. {suggestion}")

            if args.output:
                output_data = {
                    "timestamp": str(Path(".").absolute()),
                    "stats": stats,
                    "recommendations": suggestions,
                }
                Path(args.output).write_text(json.dumps(output_data, indent=2, ensure_ascii=False))
                logger.info(f"Report saved to {args.output}")

    finally:
        optimizer.close()


if __name__ == "__main__":
    main()
