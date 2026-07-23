# ============================================================
# NexusFlow Dockerfile — Multi-stage build
# ============================================================
# Stage 1: builder — install dependencies
# Stage 2: runtime — minimal image with only runtime deps
# ============================================================

# ---------- Stage 1: Builder ----------
FROM python:3.11-slim AS builder

WORKDIR /build

# Copy only dependency files first for better layer caching
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir --prefix=/install .

# Copy full source and install
COPY . .
RUN pip install --no-cache-dir --prefix=/install .

# ---------- Stage 2: Runtime ----------
FROM python:3.11-slim AS runtime

LABEL maintainer="NexusFlow Team"
LABEL description="NexusFlow — 面向超长程复杂任务的群体智能引擎"
LABEL version="3.1.0"

# System deps for PDF processing
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --from=builder /build /app

# Create data directory for persistence
RUN mkdir -p /app/data /app/logs

# Non-root user for security
RUN useradd -m -r nexusflow && \
    chown -R nexusflow:nexusflow /app
USER nexusflow

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NEXUSFLOW_DATA_DIR=/app/data \
    NEXUSFLOW_LOG_DIR=/app/logs

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8900/health || curl -f http://localhost:8900/ || exit 1

EXPOSE 8900

# Default: start the dashboard server
CMD ["nexusflow", "serve"]
