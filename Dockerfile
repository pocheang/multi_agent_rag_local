# Multi-stage build for QueryMind Backend
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY pyproject.toml ./
COPY requirements/runtime.txt ./requirements/

# Install Python dependencies from the lock: pinned and hashed, so an image
# rebuilt in six months installs what this one did. `pip install --upgrade pip`
# used to lead this and was removed with the same reasoning -- an unpinned
# upgrade is the floating dependency this file is trying to stop having, and the
# image tag already fixes pip's version.
RUN pip install --no-cache-dir --only-binary :all: --no-binary jieba -r requirements/runtime.txt && \
    pip install --no-cache-dir -e . --no-deps

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY app ./app
COPY scripts ./scripts
COPY config ./config
COPY deploy ./deploy

# Create necessary directories
RUN mkdir -p /app/data/chroma /app/data/chunks /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
