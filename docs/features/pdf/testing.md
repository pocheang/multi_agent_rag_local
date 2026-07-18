# PDF Testing Guide

## Overview

This guide covers testing strategies and best practices for the PDF processing module. The testing suite includes unit tests, integration tests, and performance benchmarks to ensure reliability, correctness, and performance of PDF processing operations.

### Testing Philosophy

- **Fast and Isolated**: Tests should run quickly and independently
- **Mock External Dependencies**: API calls to OpenAI and Anthropic are mocked
- **Comprehensive Coverage**: Target 80%+ code coverage
- **Real-World Scenarios**: Test edge cases and error conditions
- **Performance Validation**: Benchmark critical operations

## Running Unit Tests

Unit tests validate individual components in isolation with mocked dependencies.

### Run All Unit Tests

```bash
conda activate rag-local
pytest tests/unit/ -v
```

### Run Specific Test File

```bash
pytest tests/unit/test_streaming_pdf_loader.py -v
```

### Run with Coverage Report

```bash
pytest tests/unit/ --cov=app.ingestion --cov-report=html --cov-report=term
```

This generates:
- Terminal coverage summary
- HTML report in `htmlcov/index.html`

### Expected Output

```
tests/unit/test_streaming_pdf_loader.py::test_load_pdf_streaming_yields_documents_in_chunks PASSED
tests/unit/test_pdf_utils.py::test_compute_file_hash PASSED
tests/unit/test_performance_cache.py::test_cache_set_and_get PASSED
tests/unit/test_cache_ttl.py::test_cache_expiration PASSED
tests/unit/test_chart_extractor.py::test_detect_chart_in_image PASSED

==================== 25 passed in 2.34s ====================
```

## Running Performance Benchmarks

Performance benchmarks measure processing speed, memory usage, and API efficiency.

### Run All Benchmarks

```bash
conda activate rag-local
python tests/performance/run_all_benchmarks.py
```

### Run Specific Benchmark

```bash
# PDF processing modes comparison
python tests/performance/benchmark_pdf_processing.py data/test_pdfs/sample.pdf

# Batch chart extraction performance
python tests/performance/test_batch_benchmarks.py
```

### Interpreting Benchmark Results

Results are saved to `tests/performance/benchmark_results.json`:

```json
{
  "timestamp": "2026-05-15T10:30:00",
  "benchmarks": [
    {
      "mode": "pypdf",
      "file_name": "sample.pdf",
      "time_seconds": 0.45,
      "memory_mb": 12.3,
      "num_docs": 10,
      "success": true
    },
    {
      "operation": "batch_chart_extraction",
      "num_images": 10,
      "batch_size": 5,
      "speedup_factor": 1.85,
      "time_saved_percent": 45.9,
      "meets_40_percent_target": true
    }
  ]
}
```

### Performance Baseline Expectations

| Operation | Expected Time | Expected Memory | Target |
|-----------|--------------|-----------------|--------|
| pypdf (10 pages) | < 1s | < 20 MB | Fast baseline |
| docling_enhanced (10 pages) | < 5s | < 100 MB | Quality extraction |
| Streaming (100 pages) | < 30s | < 150 MB | 70% memory reduction |
| Batch charts (10 images) | < 2s | < 50 MB | 40% faster than sequential |

## Running Integration Tests

Integration tests validate end-to-end workflows with real file processing (but mocked APIs).

### Run All Integration Tests

```bash
conda activate rag-local
pytest tests/integration/ -v
```

### Run Specific Integration Test

```bash
pytest tests/integration/test_streaming_pdf.py -v
pytest tests/integration/test_batch_chart_extraction.py -v
pytest tests/integration/test_error_scenarios.py -v
```

### What Integration Tests Cover

- **Streaming PDF Processing**: End-to-end streaming workflow with chunked processing
- **Batch Chart Extraction**: Multi-image concurrent extraction with error handling
- **Error Scenarios**: File not found, corrupted PDFs, API failures, timeout handling
- **Cache Integration**: Cache hit/miss behavior with TTL validation
- **Metrics Collection**: Performance metrics recording and aggregation

### Test Data Requirements

Integration tests use files from `data/test_pdfs/`:

```
data/test_pdfs/
├── sample.pdf          # Small test file (5-10 pages)
├── large.pdf           # Large test file (50+ pages)
├── with_charts.pdf     # PDF containing charts/images
└── corrupted.pdf       # Invalid PDF for error testing
```

Create test files or use existing project PDFs for integration testing.

## Adding New Tests

### Test File Placement

```
tests/
├── unit/                    # Unit tests (isolated, mocked)
│   ├── test_streaming_pdf_loader.py
│   ├── test_performance_cache.py
│   └── test_chart_extractor.py
├── integration/             # Integration tests (end-to-end)
│   ├── test_streaming_pdf.py
│   └── test_batch_chart_extraction.py
└── performance/             # Performance benchmarks
    ├── benchmark_pdf_processing.py
    └── test_batch_benchmarks.py
```

### Naming Conventions

- **Unit tests**: `test_<module_name>.py`
- **Integration tests**: `test_<feature_name>.py`
- **Test functions**: `test_<what_it_tests>()`
- **Fixtures**: `<resource_name>_fixture()` or `mock_<dependency>()`

### Test Structure and Fixtures

```python
"""Tests for streaming PDF loader."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

@pytest.fixture
def sample_pdf_path(tmp_path):
    """Create a temporary test PDF file."""
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 test content")
    return pdf_file

@pytest.fixture
def mock_docling_converter():
    """Mock Docling DocumentConverter."""
    with patch('docling.document_converter.DocumentConverter') as mock:
        yield mock

def test_streaming_loader_processes_chunks(sample_pdf_path, mock_docling_converter):
    """Test that streaming loader processes PDF in chunks."""
    from app.ingestion.utils.streaming_pdf_loader import load_pdf_streaming
    
    # Setup mock
    mock_converter = mock_docling_converter.return_value
    mock_result = Mock()
    mock_result.document.pages = {1: Mock(), 2: Mock(), 3: Mock()}
    mock_converter.convert.return_value = mock_result
    
    # Execute
    docs = list(load_pdf_streaming(sample_pdf_path, chunk_pages=2))
    
    # Assert
    assert len(docs) > 0
    assert mock_converter.convert.call_count >= 2  # Initial + chunks
```

### Mocking External Dependencies

#### Mock OpenAI API

```python
from unittest.mock import patch

@pytest.fixture
def mock_openai_api():
    """Mock OpenAI API calls."""
    with patch('app.ingestion.utils.chart_extractor._extract_with_openai') as mock:
        mock.return_value = {
            "chart_type": "bar",
            "title": "Test Chart",
            "data": [{"label": "A", "value": 10}]
        }
        yield mock
```

#### Mock Anthropic API

```python
from unittest.mock import patch

@pytest.fixture
def mock_anthropic_api():
    """Mock Anthropic API calls."""
    with patch('app.ingestion.utils.chart_extractor._extract_with_anthropic') as mock:
        mock.return_value = {
            "chart_type": "line",
            "title": "Test Chart",
            "data": [{"x": 1, "y": 10}]
        }
        yield mock
```

#### Mock Docling Converter

```python
from unittest.mock import Mock, patch

@pytest.fixture
def mock_docling():
    """Mock Docling document converter."""
    with patch('docling.document_converter.DocumentConverter') as mock_converter:
        mock_instance = mock_converter.return_value
        mock_result = Mock()
        mock_result.document.export_to_markdown.return_value = "# Test Content"
        mock_result.document.pages = [Mock(), Mock()]
        mock_instance.convert.return_value = mock_result
        yield mock_instance
```

## Testing Best Practices

### 1. Use pytest Fixtures for Test Data

```python
@pytest.fixture
def pdf_cache(tmp_path):
    """Create temporary cache for testing."""
    from app.ingestion.utils.performance import PDFProcessingCache
    return PDFProcessingCache(cache_dir=tmp_path / "cache", ttl_days=1)
```

### 2. Mock External API Calls

Never make real API calls in tests. Always mock OpenAI, Anthropic, and other external services.

```python
@patch('app.ingestion.utils.chart_extractor.extract_chart_data_with_vision')
def test_chart_extraction(mock_extract):
    mock_extract.return_value = {"chart_type": "bar"}
    # Test code here
```

### 3. Test Edge Cases and Error Scenarios

```python
def test_streaming_loader_handles_missing_file():
    """Test error handling for non-existent PDF."""
    from app.ingestion.utils.streaming_pdf_loader import load_pdf_streaming
    
    result = list(load_pdf_streaming(Path("/nonexistent/file.pdf")))
    assert result == []  # Should return empty, not crash

def test_cache_handles_corrupted_data(pdf_cache, sample_pdf_path):
    """Test cache handles corrupted JSON gracefully."""
    cache_path = pdf_cache.get_cache_path(sample_pdf_path, "test")
    cache_path.write_text("invalid json {{{")
    
    result = pdf_cache.get(sample_pdf_path, "test")
    assert result is None  # Should return None, not crash
```

### 4. Keep Tests Fast and Isolated

- Use `tmp_path` fixture for temporary files
- Clean up resources in teardown
- Don't depend on external files or state
- Use small test data (< 1 MB)

```python
def test_with_temp_file(tmp_path):
    """Test using temporary directory."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"test content")
    # Test code here
    # Cleanup automatic via tmp_path
```

### 5. Use Parametrized Tests for Multiple Scenarios

```python
@pytest.mark.parametrize("chunk_size,expected_chunks", [
    (10, 10),
    (25, 4),
    (50, 2),
    (100, 1),
])
def test_streaming_chunk_sizes(chunk_size, expected_chunks):
    """Test different chunk sizes produce expected number of chunks."""
    # Test with 100-page PDF
    # Assert chunk count matches expected
```

## Test Coverage Goals

### Target: 80%+ Coverage

Focus coverage on:
- Core processing logic (`pdf_loader.py`, `streaming_pdf_loader.py`)
- Cache operations (`performance.py`)
- Chart extraction (`chart_extractor.py`, `batch_chart_extractor.py`)
- Error handling paths

### Check Coverage

```bash
pytest tests/unit/ --cov=app.ingestion --cov-report=term-missing
```

Output shows uncovered lines:

```
Name                                    Stmts   Miss  Cover   Missing
---------------------------------------------------------------------
app/ingestion/loaders/pdf_loader.py        45      3    93%   67-69
app/ingestion/utils/performance.py         120     15    88%   145-150, 200-205
app/ingestion/utils/chart_extractor.py     80      10    88%   120-125, 180
---------------------------------------------------------------------
TOTAL                                      245     28    89%
```

### What to Prioritize for Coverage

1. **Critical paths**: Main processing functions
2. **Error handling**: Exception handling and fallbacks
3. **Edge cases**: Empty inputs, invalid data, boundary conditions
4. **Public APIs**: All exported functions and classes

### What NOT to Prioritize

- Logging statements
- Type hints and docstrings
- Simple getters/setters
- Third-party library code

## Running Tests in CI/CD

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: conda-incubator/setup-miniconda@v2
        with:
          environment-file: environment.yml
          activate-environment: rag-local
      - name: Run unit tests
        run: |
          conda activate rag-local
          pytest tests/unit/ -v --cov=app.ingestion --cov-report=xml
      - name: Run integration tests
        run: |
          conda activate rag-local
          pytest tests/integration/ -v
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Troubleshooting Tests

### Tests Fail with Import Errors

```bash
# Ensure conda environment is activated
conda activate rag-local

# Install test dependencies
pip install pytest pytest-cov pytest-mock
```

### Docling Import Errors

```bash
# Install docling if missing
pip install docling
```

### Mock Not Working

Ensure patch path matches the import location in the tested module:

```python
# If module does: from docling.document_converter import DocumentConverter
# Then patch: 'app.ingestion.loaders.pdf_loader.DocumentConverter'

# If module does: import docling.document_converter
# Then patch: 'docling.document_converter.DocumentConverter'
```

### Tests Run Slowly

- Check for real API calls (should be mocked)
- Reduce test data size
- Use `pytest -v --durations=10` to find slow tests

## Summary

- **Unit tests**: `pytest tests/unit/ -v --cov=app.ingestion`
- **Integration tests**: `pytest tests/integration/ -v`
- **Benchmarks**: `python tests/performance/run_all_benchmarks.py`
- **Coverage target**: 80%+ on core modules
- **Always mock**: OpenAI, Anthropic, external APIs
- **Test edge cases**: Errors, empty inputs, invalid data
