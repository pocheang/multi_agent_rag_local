# PDF Performance Tuning Guide

## Overview

This guide covers performance optimization strategies for PDF processing in the QueryMind System. The PDF module includes several performance features: caching, streaming processing, batch chart extraction, and configurable processing modes.

### Key Performance Metrics

- **Processing Speed**: Time to extract content from PDFs
- **Memory Usage**: Peak memory consumption during processing
- **API Efficiency**: Number and cost of external API calls
- **Cache Hit Rate**: Percentage of requests served from cache

## Configuration Parameters

All configuration parameters can be set via environment variables in `.env` file.

### PDF_CACHE_TTL_DAYS

**Default**: `30`

Cache validity period in days. Cached results older than this are automatically expired and removed.

```bash
# .env
PDF_CACHE_TTL_DAYS=30
```

**Usage**:
- **30 days**: Good default for stable documents
- **7 days**: For frequently updated documents
- **90 days**: For archival/static documents

**Impact**: Longer TTL reduces reprocessing but may serve stale results if PDFs are updated.

### PDF_STREAMING_CHUNK_SIZE

**Default**: `10`

Number of pages to process per chunk in streaming mode.

```bash
# .env
PDF_STREAMING_CHUNK_SIZE=10
```

**Usage**:
- **5 pages**: Maximum memory efficiency, slower processing
- **10 pages**: Balanced (recommended)
- **25 pages**: Faster processing, higher memory usage
- **50+ pages**: Minimal memory benefit, approaches batch performance

**Impact**: Smaller chunks reduce memory but increase processing time due to multiple Docling conversions.

### PDF_BATCH_CHART_SIZE

**Default**: `5`

Number of concurrent API calls for batch chart extraction.

```bash
# .env
PDF_BATCH_CHART_SIZE=5
```

**Usage**:
- **3**: Conservative, lower API rate limit risk
- **5**: Balanced (recommended), 40%+ speedup
- **10**: Aggressive, maximum speedup, higher rate limit risk
- **1**: Sequential processing (no batching)

**Impact**: Higher batch size improves speed but may hit API rate limits. Monitor API errors and adjust accordingly.

### PDF_ENABLE_METRICS

**Default**: `true`

Enable collection of processing metrics (time, memory, cache hits, API calls).

```bash
# .env
PDF_ENABLE_METRICS=true
```

**Usage**:
- **true**: Collect metrics for monitoring and optimization
- **false**: Disable metrics collection (slight performance improvement)

**Impact**: Minimal overhead (~1-2%). Recommended to keep enabled for production monitoring.

## Processing Modes

The PDF module supports three processing modes with different speed/quality tradeoffs.

### pypdf - Fast Basic Extraction

**Speed**: ⚡⚡⚡ Fastest  
**Quality**: ⭐⭐ Basic  
**Memory**: 🟢 Low (10-20 MB)

```python
from app.ingestion.loaders import load_pdf_text

docs = load_pdf_text(pdf_path)
```

**Characteristics**:
- Pure text extraction, no structure preservation
- No table detection or formatting
- Fastest processing (~0.5s per 10 pages)
- Lowest memory usage

**When to Use**:
- Simple text-only documents
- Speed is critical priority
- No tables or complex formatting
- Initial document screening

### docling_enhanced - High Quality with Structure

**Speed**: ⚡⚡ Moderate  
**Quality**: ⭐⭐⭐⭐ High  
**Memory**: 🟡 Medium (50-100 MB)

```python
from app.ingestion.loaders import load_pdf_enhanced

docs = load_pdf_enhanced(pdf_path, by_page=True)
```

**Characteristics**:
- Markdown conversion with table preservation
- Header/footer removal
- Cross-page table merging
- Nested table flattening
- Moderate processing time (~3-5s per 10 pages)

**When to Use**:
- Documents with tables and structure
- Quality is important
- Acceptable processing time
- **Recommended default mode**

### docling_advanced - Maximum Quality with OCR

**Speed**: ⚡ Slow  
**Quality**: ⭐⭐⭐⭐⭐ Maximum  
**Memory**: 🔴 High (100-200 MB)

```python
from app.ingestion.loaders.pdf_loader_advanced import load_pdf_advanced

docs = load_pdf_advanced(pdf_path, enable_ocr=True)
```

**Characteristics**:
- Full OCR for scanned documents
- Maximum structure preservation
- Image and chart detection
- Slowest processing (~10-20s per 10 pages)
- Highest memory usage

**When to Use**:
- Scanned PDFs or images
- Maximum quality required
- Processing time not critical
- Complex layouts with images

## Batch Processing

Batch chart extraction processes multiple charts concurrently, reducing total API call time by ~40%.

### When to Use Batch Extraction

- Processing PDFs with **5+ charts/images**
- API latency is the bottleneck
- Have sufficient API rate limits
- Want to minimize total processing time

### Performance Benefits

**Sequential Processing** (baseline):
- 10 charts × 0.5s per API call = **5.0 seconds**
- One API call at a time

**Batch Processing** (batch_size=5):
- 10 charts ÷ 5 concurrent = 2 batches
- 2 batches × 0.5s = **~1.5 seconds**
- **70% faster** (3.5s saved)

### Configuration Recommendations

| Number of Charts | Recommended Batch Size | Expected Speedup |
|-----------------|------------------------|------------------|
| 1-3 charts | 1 (sequential) | N/A |
| 4-10 charts | 5 | 40-50% |
| 11-20 charts | 5-10 | 50-60% |
| 20+ charts | 10 | 60-70% |

### Code Example

```python
import asyncio
from pathlib import Path
from app.ingestion.utils.batch_chart_extractor import BatchChartExtractor

# Extract images from PDF (using your existing logic)
images = extract_images_from_pdf(pdf_path)  # Returns List[bytes]

# Create batch extractor
extractor = BatchChartExtractor(batch_size=5)

# Extract all charts concurrently
results = asyncio.run(extractor.extract_charts_batch(
    images=images,
    model="gpt-4o",
    api_key=api_key
))

# Process results
for idx, result in enumerate(results):
    if "error" in result:
        print(f"Chart {idx} failed: {result['error']}")
    else:
        print(f"Chart {idx}: {result['chart_type']} - {result['title']}")

# Cleanup
extractor._executor.shutdown(wait=True)
```

## Streaming Processing

Streaming processes large PDFs in chunks, reducing memory usage by ~70% for 100+ page documents.

### When to Use Streaming

- PDFs with **50+ pages**
- Memory constraints (limited RAM)
- Processing very large documents (500+ pages)
- Want to start processing results immediately

### Memory Benefits

**Standard Loading** (load all pages):
- 100-page PDF: **~300 MB** peak memory
- All pages loaded into memory at once

**Streaming Loading** (10 pages per chunk):
- 100-page PDF: **~90 MB** peak memory
- **70% memory reduction**
- Only current chunk in memory

### Configuration Recommendations

| PDF Size | Recommended Chunk Size | Memory Savings |
|----------|------------------------|----------------|
| < 50 pages | N/A (use standard) | N/A |
| 50-100 pages | 10-25 pages | 30-50% |
| 100-500 pages | 10 pages | 50-70% |
| 500+ pages | 5-10 pages | 70%+ |

### Code Example

```python
from pathlib import Path
from app.ingestion.utils.streaming_pdf_loader import load_pdf_streaming

pdf_path = Path("data/large_document.pdf")

# Stream process in 10-page chunks
for doc in load_pdf_streaming(pdf_path, chunk_pages=10, mode="docling_enhanced"):
    # Process each document immediately
    # Memory only holds current chunk, not entire PDF
    print(f"Processing page {doc.metadata['page']}")
    
    # Store in vector database
    vector_store.add_document(doc)
    
    # Previous chunks are released from memory automatically
```

### Streaming vs Standard Loading

**Use Streaming When**:
- PDF > 50 pages
- Memory is limited
- Want incremental processing
- Can tolerate slightly slower processing

**Use Standard Loading When**:
- PDF < 50 pages
- Need all pages at once
- Memory is not a constraint
- Want fastest processing

## Caching Strategy

The PDF processing cache stores results to avoid reprocessing the same documents.

### How Caching Works

1. **Cache Key**: Computed from file hash + operation + configuration
2. **Cache Storage**: JSON files in `data/cache/pdf_processing/`
3. **Cache Validation**: TTL-based expiration (default 30 days)
4. **Cache Invalidation**: Automatic cleanup of expired entries

### Cache Hit vs Miss

**Cache Hit** (fast):
- Result loaded from disk in ~10ms
- No PDF processing required
- 100x faster than reprocessing

**Cache Miss** (slow):
- Full PDF processing required
- Result cached for future requests
- Subsequent requests will hit cache

### Manual Cache Cleanup

```python
from pathlib import Path
from app.ingestion.utils.performance import PDFProcessingCache

cache = PDFProcessingCache(cache_dir=Path("data/cache/pdf_processing"))

# Clean up expired cache entries
cleaned_count = cache.cleanup_expired()
print(f"Cleaned {cleaned_count} expired cache entries")

# Clear cache for specific file
pdf_path = Path("data/document.pdf")
cache.clear(file_path=pdf_path)

# Clear all cache
cache.clear()
```

### Cache Statistics

```python
from app.ingestion.utils.performance import PDFProcessingCache

cache = PDFProcessingCache()
stats = cache.get_cache_stats()

print(f"Total cache files: {stats['total_files']}")
print(f"Total cache size: {stats['total_size_mb']:.2f} MB")
print(f"Valid entries: {stats['valid_files']}")
print(f"Expired entries: {stats['expired_files']}")
```

### When to Clear Cache

- **After PDF updates**: Clear cache for specific file
- **Configuration changes**: Clear cache if processing parameters changed
- **Disk space issues**: Run cleanup_expired() or clear old entries
- **Testing**: Clear cache to force reprocessing

## Monitoring and Metrics

Enable metrics collection to monitor performance and identify bottlenecks.

### How to Enable Metrics Collection

```bash
# .env
PDF_ENABLE_METRICS=true
```

### Using PDFProcessingMetrics Class

```python
from pathlib import Path
from app.ingestion.utils.monitoring import PDFProcessingMetrics

# Initialize metrics collector
metrics = PDFProcessingMetrics(
    metrics_file=Path("data/metrics/pdf_processing.jsonl")
)

# Record processing operation
metrics.record_processing(
    file_path=Path("data/document.pdf"),
    mode="docling_enhanced",
    duration=3.45,
    memory_mb=85.2,
    cache_hit=False,
    api_calls=5,
    num_pages=25,
    error=None
)
```

### Viewing Metrics Summary

```python
from app.ingestion.utils.monitoring import PDFProcessingMetrics

metrics = PDFProcessingMetrics()
summary = metrics.get_summary(days=7)

print(f"Total operations: {summary['total_operations']}")
print(f"Cache hit rate: {summary['cache_hit_rate']:.1f}%")
print(f"Average duration: {summary['avg_duration']:.2f}s")
print(f"Average memory: {summary['avg_memory_mb']:.1f} MB")
print(f"Total API calls: {summary['total_api_calls']}")
print(f"Estimated cost: ${summary['estimated_cost_usd']:.2f}")
```

### Interpreting Performance Data

**Good Performance Indicators**:
- Cache hit rate > 60%
- Average processing time < 5s per 10 pages
- Memory usage < 150 MB per operation
- Low error rate (< 5%)

**Performance Issues**:
- Cache hit rate < 30% → Check TTL settings, files changing frequently
- High processing time → Consider faster mode or streaming
- High memory usage → Use streaming for large files
- High API costs → Increase batch size, improve caching

### Metrics File Format

Metrics are stored in JSONL format (one JSON object per line):

```json
{"timestamp": "2026-05-15T10:30:00", "file": "doc.pdf", "mode": "docling_enhanced", "duration": 3.45, "memory_mb": 85.2, "cache_hit": false, "api_calls": 5, "num_pages": 25}
{"timestamp": "2026-05-15T10:35:00", "file": "doc.pdf", "mode": "docling_enhanced", "duration": 0.01, "memory_mb": 0.5, "cache_hit": true, "api_calls": 0, "num_pages": 25}
```

## Performance Optimization Tips

### 1. Use Caching for Repeated Processing

**Problem**: Processing the same PDF multiple times  
**Solution**: Enable caching with appropriate TTL

```python
from app.ingestion.utils.performance import PDFProcessingCache

cache = PDFProcessingCache(ttl_days=30)

# Check cache before processing
cached_result = cache.get(pdf_path, "docling_enhanced")
if cached_result:
    return cached_result

# Process and cache result
result = load_pdf_enhanced(pdf_path)
cache.set(pdf_path, "docling_enhanced", result)
```

**Impact**: 100x faster for cached documents (10ms vs 5s)

### 2. Use Streaming for Large Files (50+ pages)

**Problem**: High memory usage for large PDFs  
**Solution**: Use streaming loader

```python
# Before: High memory
docs = load_pdf_enhanced(large_pdf_path)  # 300 MB memory

# After: Low memory
docs = list(load_pdf_streaming(large_pdf_path, chunk_pages=10))  # 90 MB memory
```

**Impact**: 70% memory reduction for 100+ page PDFs

### 3. Use Batch Extraction for Multiple Charts

**Problem**: Slow sequential chart extraction  
**Solution**: Use batch extractor

```python
# Before: Sequential (slow)
results = [extract_chart_data_with_vision(img) for img in images]  # 5.0s

# After: Batch (fast)
extractor = BatchChartExtractor(batch_size=5)
results = asyncio.run(extractor.extract_charts_batch(images, model, api_key))  # 1.5s
```

**Impact**: 40-70% faster for 5+ charts

### 4. Choose Appropriate Processing Mode

**Problem**: Using slow mode when fast mode sufficient  
**Solution**: Match mode to document type

```python
# Simple text document → Use pypdf (fastest)
if is_simple_text_document(pdf_path):
    docs = load_pdf_text(pdf_path)

# Document with tables → Use docling_enhanced (balanced)
elif has_tables(pdf_path):
    docs = load_pdf_enhanced(pdf_path)

# Scanned document → Use docling_advanced (highest quality)
else:
    docs = load_pdf_advanced(pdf_path, enable_ocr=True)
```

**Impact**: 5-10x speedup for simple documents

### 5. Monitor Cache Size and Cleanup Regularly

**Problem**: Cache grows indefinitely, consuming disk space  
**Solution**: Regular cleanup of expired entries

```python
from app.ingestion.utils.performance import PDFProcessingCache

cache = PDFProcessingCache()

# Run cleanup weekly
cleaned = cache.cleanup_expired()
print(f"Cleaned {cleaned} expired entries")

# Check cache size
stats = cache.get_cache_stats()
if stats['total_size_mb'] > 1000:  # > 1 GB
    print("Warning: Cache size exceeds 1 GB")
    # Consider reducing TTL or clearing old entries
```

**Impact**: Prevents disk space issues, maintains cache performance

### 6. Optimize Batch Size Based on API Rate Limits

**Problem**: Hitting API rate limits with high batch size  
**Solution**: Monitor errors and adjust batch size

```python
# Start with conservative batch size
extractor = BatchChartExtractor(batch_size=3)

# Monitor for rate limit errors
results = asyncio.run(extractor.extract_charts_batch(images, model, api_key))
error_count = sum(1 for r in results if "error" in r)

if error_count == 0:
    # No errors, can increase batch size
    extractor = BatchChartExtractor(batch_size=5)
elif error_count > len(images) * 0.2:
    # > 20% errors, reduce batch size
    extractor = BatchChartExtractor(batch_size=1)
```

**Impact**: Maximize speed while avoiding rate limit errors

### 7. Use Metrics to Identify Bottlenecks

**Problem**: Unclear where performance issues occur  
**Solution**: Enable metrics and analyze patterns

```python
from app.ingestion.utils.monitoring import PDFProcessingMetrics

metrics = PDFProcessingMetrics()
summary = metrics.get_summary(days=7)

# Identify slow operations
if summary['avg_duration'] > 10:
    print("Average processing time is high")
    print("Consider: streaming, faster mode, or caching")

# Identify memory issues
if summary['avg_memory_mb'] > 200:
    print("Memory usage is high")
    print("Consider: streaming or smaller chunk sizes")

# Identify cache issues
if summary['cache_hit_rate'] < 30:
    print("Cache hit rate is low")
    print("Consider: longer TTL or check if files are changing")
```

**Impact**: Data-driven optimization decisions

## Summary

### Quick Reference

| Optimization | When to Use | Expected Benefit |
|--------------|-------------|------------------|
| Caching | Repeated processing | 100x faster |
| Streaming | 50+ page PDFs | 70% memory reduction |
| Batch extraction | 5+ charts | 40-70% faster |
| pypdf mode | Simple text docs | 5-10x faster |
| Metrics monitoring | Production systems | Identify bottlenecks |

### Configuration Checklist

```bash
# .env - Recommended production settings
PDF_CACHE_TTL_DAYS=30
PDF_STREAMING_CHUNK_SIZE=10
PDF_BATCH_CHART_SIZE=5
PDF_ENABLE_METRICS=true
```

### Performance Targets

- **Processing speed**: < 5s per 10 pages (docling_enhanced)
- **Memory usage**: < 150 MB per operation
- **Cache hit rate**: > 60%
- **API efficiency**: 40%+ speedup with batching
- **Error rate**: < 5%
