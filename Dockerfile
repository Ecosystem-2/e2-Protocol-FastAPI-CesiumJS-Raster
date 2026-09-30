# Multi-stage Dockerfile for e2 Protocol: FastAPI + CesiumJS (Raster), the climate tile server
# Uses UV for fast dependency installation and smaller final image

# ============================================================================
# Stage 1: Builder - Install dependencies using UV
# ============================================================================
FROM python:3.13-slim AS builder

# Install GDAL and build dependencies (needed for rasterio compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    gdal-bin \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set GDAL environment variables for building
ENV GDAL_CONFIG=/usr/bin/gdal-config

# Install UV package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock .python-version ./

# Install dependencies into /app/.venv
# Using --frozen to ensure reproducible builds
RUN uv sync --frozen --no-dev

# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.13-slim

# Install runtime dependencies (GDAL/rasterio requirements)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

# Set GDAL environment variables
ENV GDAL_CONFIG=/usr/bin/gdal-config

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

# Copy application code
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser pyproject.toml ./

# AGPL section 5 wants the licence kept with the code we distribute
COPY --chown=appuser:appuser LICENSE.md AUTHORS.md ./

# Section 13 offers users the source of the version actually running, so the build
# has to record which commit that was. Pass --build-arg SOURCE_REVISION=$GITHUB_SHA.
ARG SOURCE_REVISION=""
ENV SOURCE_REVISION=${SOURCE_REVISION}

# Create data directory for GCS credentials
RUN mkdir -p /app/data && chown appuser:appuser /app/data

# Switch to non-root user
USER appuser

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/docs').read()"

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
