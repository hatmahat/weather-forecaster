# Build stage
FROM python:3.12-slim AS builder

# Optional PyTorch install (CPU and CUDA wheels come from different indexes).
# Leave INSTALL_TORCH=false unless your models need torch.
ARG INSTALL_TORCH=false
# With INSTALL_TORCH=true: USE_GPU=true installs the CUDA 11.8 build, otherwise the CPU build.
ARG USE_GPU=false

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt && \
    if [ "$INSTALL_TORCH" = "true" ]; then \
        if [ "$USE_GPU" = "true" ]; then \
            pip install --no-cache-dir --user torch --index-url https://download.pytorch.org/whl/cu118; \
        else \
            pip install --no-cache-dir --user torch --index-url https://download.pytorch.org/whl/cpu; \
        fi; \
    fi

# Runtime stage
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/root/.local/bin:$PATH

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code and migrations (so `alembic upgrade head` works in the container)
COPY app/ ./app/
COPY alembic.ini ./
COPY migrations/ ./migrations/

# Expose port
EXPOSE 8000

# Health check (using curl instead of Python)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application.
# Keep a SINGLE worker: the job queue and stale-job scheduler are in-process (see ARCHITECTURE.md).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
