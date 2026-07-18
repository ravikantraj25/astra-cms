# =============================================================================
# Astra CMS — Dockerfile
# =============================================================================
# Multi-stage build for a lean production image.
# =============================================================================

# ── Stage 1: Build ───────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy only dependency metadata first (cache-friendly)
COPY pyproject.toml ./

# Install production dependencies
RUN uv pip install --system --no-cache-dir .

# ── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="Astra CMS Contributors"
LABEL description="Astra CMS — AI-powered headless CMS toolkit"

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY app/ ./app/
COPY config/ ./config/

# Create runtime directories
RUN mkdir -p logs backups output data \
    && addgroup --system astra \
    && adduser --system --ingroup astra astra \
    && chown -R astra:astra /app

USER astra

ENTRYPOINT ["astra"]
CMD ["--help"]
