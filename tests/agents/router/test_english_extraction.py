"""Test English language support for history extraction in EnhancedRouterService."""

import pytest
from app.agents.router.enhanced_service import EnhancedRouterService


class TestEnglishHistoryExtraction:
    """Test suite for English language history extraction."""

    @pytest.fixture
    def service(self):
        """Create EnhancedRouterService instance."""
        return EnhancedRouterService()

    def test_english_scenario_extraction(self, service):
        """Test scenario extraction from English text."""
        test_cases = [
            ("I want to build an enterprise knowledge base", {"scenario": "企业知识库"}),
            ("We need customer service support system", {"scenario": "客服问答"}),
            ("Building a code documentation system", {"scenario": "代码知识库"}),
            ("Need data analytics dashboard", {"scenario": "数据分析"}),
            ("Our company needs internal knowledge management", {"scenario": "企业知识库"}),
        ]

        for question, expected in test_cases:
            result = service._extract_info_from_history(question, "")
            assert "scenario" in result, f"Failed to extract scenario from: {question}"
            assert result["scenario"] == expected["scenario"], \
                f"Expected {expected['scenario']}, got {result.get('scenario')}"

    def test_english_data_source_extraction(self, service):
        """Test data source extraction from English text."""
        test_cases = [
            ("We have PDF documents to process", {"data_source": "PDF文档"}),
            ("Data comes from MySQL database", {"data_source": "数据库"}),
            ("Using REST API as data source", {"data_source": "API接口"}),
            ("Need to crawl web pages", {"data_source": "网页爬取"}),
            ("PostgreSQL database backend", {"data_source": "数据库"}),
        ]

        for question, expected in test_cases:
            result = service._extract_info_from_history(question, "")
            assert "data_source" in result, f"Failed to extract data_source from: {question}"
            assert result["data_source"] == expected["data_source"], \
                f"Expected {expected['data_source']}, got {result.get('data_source')}"

    def test_english_scale_extraction_numeric(self, service):
        """Test scale extraction from numeric patterns."""
        test_cases = [
            ("Our dataset is about 0.5GB", {"scale": "小型（<1GB）"}),
            ("We have 5GB of data", {"scale": "中型（1-10GB）"}),
            ("Dataset size is 50GB", {"scale": "大型（10-100GB）"}),
            ("Over 200GB of documents", {"scale": "超大型（>100GB）"}),
            ("About 10.5 GB total", {"scale": "大型（10-100GB）"}),
        ]

        for question, expected in test_cases:
            result = service._extract_info_from_history(question, "")
            assert "scale" in result, f"Failed to extract scale from: {question}"
            assert result["scale"] == expected["scale"], \
                f"Expected {expected['scale']}, got {result.get('scale')} for: {question}"

    def test_english_scale_extraction_keywords(self, service):
        """Test scale extraction from keyword patterns."""
        test_cases = [
            ("Small dataset for testing", {"scale": "小型（<1GB）"}),
            ("Medium scale project", {"scale": "中型（1-10GB）"}),
            ("Large amount of data", {"scale": "大型（10-100GB）"}),
            ("Massive data warehouse", {"scale": "大型（10-100GB）"}),
        ]

        for question, expected in test_cases:
            result = service._extract_info_from_history(question, "")
            assert "scale" in result, f"Failed to extract scale from: {question}"
            assert result["scale"] == expected["scale"], \
                f"Expected {expected['scale']}, got {result.get('scale')}"

    def test_english_performance_extraction(self, service):
        """Test performance requirement extraction from English text."""
        test_cases = [
            ("Need real-time response", {"performance_requirement": "实时（<1秒）"}),
            ("Should be fast, under 2 seconds", {"performance_requirement": "快速（1-3秒）"}),
            ("Normal response time is acceptable", {"performance_requirement": "一般（3-5秒）"}),
            ("Immediate results required", {"performance_requirement": "实时（<1秒）"}),
            ("Quick turnaround needed", {"performance_requirement": "快速（1-3秒）"}),
        ]

        for question, expected in test_cases:
            result = service._extract_info_from_history(question, "")
            assert "performance_requirement" in result, \
                f"Failed to extract performance from: {question}"
            assert result["performance_requirement"] == expected["performance_requirement"], \
                f"Expected {expected['performance_requirement']}, got {result.get('performance_requirement')}"

    def test_combined_english_extraction(self, service):
        """Test extraction of multiple fields from combined English text."""
        question = "Build enterprise knowledge base with PDF documents"
        history = "Dataset is about 50GB. Need fast response under 2 seconds."

        result = service._extract_info_from_history(question, history)

        assert "scenario" in result
        assert result["scenario"] == "企业知识库"

        assert "data_source" in result
        assert result["data_source"] == "PDF文档"

        assert "scale" in result
        assert result["scale"] == "大型（10-100GB）"

        assert "performance_requirement" in result
        assert result["performance_requirement"] == "快速（1-3秒）"

    def test_mixed_language_extraction(self, service):
        """Test extraction from mixed Chinese-English text."""
        question = "我们需要一个 enterprise knowledge base"
        history = "数据来源是 PDF documents，大约 50GB"

        result = service._extract_info_from_history(question, history)

        # Should extract from both languages
        assert "scenario" in result
        assert "data_source" in result
        assert "scale" in result

    def test_case_insensitive_extraction(self, service):
        """Test that extraction is case-insensitive."""
        test_cases = [
            "ENTERPRISE KNOWLEDGE BASE",
            "Enterprise Knowledge Base",
            "enterprise knowledge base",
        ]

        for question in test_cases:
            result = service._extract_info_from_history(question, "")
            assert "scenario" in result, f"Case-insensitive match failed for: {question}"
            assert result["scenario"] == "企业知识库"

    def test_no_false_positives(self, service):
        """Test that we don't extract information that isn't there."""
        question = "What is machine learning?"
        history = "Tell me about neural networks."

        result = service._extract_info_from_history(question, history)

        # Should not extract anything from generic questions
        assert len(result) == 0, f"False positive extraction: {result}"

    def test_partial_extraction(self, service):
        """Test extraction when only some information is available."""
        question = "I need a knowledge base"
        history = "It will use PDF files"

        result = service._extract_info_from_history(question, history)

        # Should extract data_source but not necessarily other fields
        assert "data_source" in result
        assert result["data_source"] == "PDF文档"

        # These may or may not be present - that's OK
        # We're just verifying we don't crash and extract what we can
