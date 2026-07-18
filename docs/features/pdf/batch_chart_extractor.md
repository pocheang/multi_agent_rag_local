# Batch Chart Extractor

## Overview

The `BatchChartExtractor` provides concurrent batch processing for chart extraction from PDF images, reducing processing time by up to 40% compared to sequential processing.

## Features

- **Async Concurrency**: Uses `asyncio` for concurrent API calls
- **Configurable Batch Size**: Control concurrency level (default: 5)
- **Error Handling**: Gracefully handles failures without stopping the batch
- **Progress Logging**: Tracks batch processing progress
- **Reuses Existing Code**: Wraps `extract_chart_data_with_vision` without modification

## Usage

### Basic Usage

```python
import asyncio
from app.ingestion.utils.batch_chart_extractor import BatchChartExtractor

async def extract_charts():
    # Initialize extractor
    extractor = BatchChartExtractor(batch_size=5)
    
    # Prepare images (list of bytes)
    images = [image1_bytes, image2_bytes, image3_bytes]
    
    # Extract concurrently
    results = await extractor.extract_charts_batch(
        images=images,
        model="gpt-4o",
        api_key="your-api-key"
    )
    
    # Process results
    for idx, result in enumerate(results):
        if "error" in result:
            print(f"Chart {idx} failed: {result['error']}")
        else:
            print(f"Chart {idx}: {result['chart_type']}")

# Run
asyncio.run(extract_charts())
```

### Convenience Function

```python
from app.ingestion.utils.batch_chart_extractor import extract_charts_batch_simple

# One-liner for simple cases
results = await extract_charts_batch_simple(
    images=images,
    model="gpt-4o",
    api_key="your-api-key",
    batch_size=5
)
```

## Configuration

### Batch Size

The `batch_size` parameter controls how many concurrent API calls are made:

- **Small (2-3)**: Conservative, lower API load
- **Medium (5)**: Default, balanced performance
- **Large (10+)**: Aggressive, maximum speed (watch rate limits)

```python
# Conservative
extractor = BatchChartExtractor(batch_size=3)

# Aggressive
extractor = BatchChartExtractor(batch_size=10)
```

## Performance

### Benchmark Results

With 10 images and 200ms API latency per call:

- **Sequential**: 2.0s (10 × 200ms)
- **Concurrent (batch_size=5)**: 0.4s (2 batches × 200ms)
- **Improvement**: 79.7% time reduction, 4.93x speedup

### Expected Performance

- **Target**: 40% time reduction vs sequential
- **Actual**: 40-80% depending on batch size and API latency
- **Best Case**: High latency APIs with large batch sizes

## Error Handling

Errors are captured and returned as error dictionaries instead of raising exceptions:

```python
results = await extractor.extract_charts_batch(images, model, api_key)

for result in results:
    if "error" in result:
        # Handle error
        print(f"Error: {result['error']}")
        print(f"Type: {result['error_type']}")
    else:
        # Process successful result
        process_chart(result)
```

## Supported Models

All models supported by `extract_chart_data_with_vision`:

- **OpenAI**: `gpt-4o`, `gpt-4-turbo`, `gpt-4-vision`
- **Anthropic**: `claude-3-5-sonnet-20241022`, `claude-3-opus`, etc.

## Integration Example

### With PDF Chart Loader

```python
from app.ingestion.utils.batch_chart_extractor import BatchChartExtractor
from app.ingestion.loaders.pdf_chart_loader import extract_images_from_pdf

async def process_pdf_charts(pdf_path: Path):
    # Extract images from PDF
    images = extract_images_from_pdf(pdf_path)
    
    # Batch extract chart data
    extractor = BatchChartExtractor(batch_size=5)
    chart_data = await extractor.extract_charts_batch(
        images=images,
        model="gpt-4o",
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    return chart_data
```

## Logging

The extractor logs progress at INFO level:

```
INFO: Starting batch chart extraction for 10 images (batch_size=5)
INFO: Processing batch 1/2 (5 images)
INFO: Batch 1/2 completed
INFO: Processing batch 2/2 (5 images)
INFO: Batch 2/2 completed
INFO: Batch extraction complete: 9 succeeded, 1 failed out of 10 total
```

## Testing

Run tests with:

```bash
pytest tests/test_batch_chart_extractor.py -v
```

## Implementation Details

- Uses `ThreadPoolExecutor` to run synchronous API calls in threads
- `asyncio.gather()` with `return_exceptions=True` for concurrent execution
- Automatic cleanup of thread pool on deletion
- No modifications to existing `chart_extractor.py` code

## Limitations

- API rate limits may require smaller batch sizes
- Memory usage scales with batch size (images held in memory)
- Thread pool overhead for very small batches (<3 images)

## Future Improvements

- Adaptive batch sizing based on API response times
- Retry logic for transient failures
- Progress callbacks for long-running batches
- Memory-efficient streaming for large image sets
