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

# Copy the lock. pyproject.toml is not needed here any more: nothing in this
# stage resolves from it.
COPY requirements/runtime.txt ./requirements/

# Install Python dependencies from the lock: pinned and hashed, so an image
# rebuilt in six months installs what this one did. `pip install --upgrade pip`
# used to lead this and was removed with the same reasoning -- an unpinned
# upgrade is the floating dependency this file is trying to stop having, and the
# image tag already fixes pip's version.
#
# The application itself is not installed. It used to be, as `pip install -e .`,
# which worked only because both stages happen to use WORKDIR /app -- the
# editable path hook baked into the builder's site-packages pointed at a
# directory the production stage refills with `COPY app ./app`. The code is
# copied in either way, so PYTHONPATH below says what that was relying on.
RUN pip install --no-cache-dir --only-binary :all: --no-binary forbiddenfruit,jieba -r requirements/runtime.txt

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

# Run as a non-root user (docker:S6471). Port 8000 is unprivileged, so nothing
# here needs the capability root was providing.
#
# The writable set is deliberately small and enumerated rather than a blanket
# chown of /app: `data/` covers every path Settings creates at startup (chroma,
# chunks, docs, sessions, uploads, app.db, history.db, sessions_cold),
# `logs/`, and `.runtime/` for the snapshot the configuration centre writes
# after a successful fetch. Application code stays read-only to the process,
# which is most of the value of not being root.
RUN useradd --system --create-home --uid 10001 querymind \
    && mkdir -p /app/data/chroma /app/data/chunks /app/logs /app/.runtime \
    && chown -R querymind:querymind /app/data /app/logs /app/.runtime

USER querymind

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# Where `app` is. uvicorn would also find it -- --app-dir defaults to "" and it
# inserts that into sys.path, which resolves to the working directory -- but a
# production image should not depend on one CLI's default for whether its own
# code is importable.
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
