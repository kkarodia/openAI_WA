# Build stage
FROM python:3.10-slim AS builder

# Set working directory
WORKDIR /app

# Set environment variables
ENV LANG=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Ensures pip uses the virtualenv
    PATH="/venv/bin:$PATH" \
    # Keeps Python from generating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    # Turns off buffering for easier container logging
    PYTHONUNBUFFERED=1 \
    # Prevents pip from caching
    PIP_NO_CACHE_DIR=1 \
    # Don't check for pip updates
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /venv

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    # Add gunicorn with proper workers for Flask
    && pip install --no-cache-dir gunicorn gevent

# Runtime stage
FROM python:3.10-slim AS app

# Create non-root user for security
RUN useradd --create-home appuser

# Set working directory
WORKDIR /app

# Set environment variables
ENV PATH="/venv/bin:$PATH" \
    PYTHONPATH=/app \
    # Configure Gunicorn
    WORKERS=2 \
    THREADS=4 \
    TIMEOUT=120 \
    # Configure Flask
    FLASK_APP=app.py \
    FLASK_ENV=production

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libxml2 \
        # Add CA certificates for HTTPS
        ca-certificates \
        && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /venv /venv

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

# Start Gunicorn with proper configuration for Flask
ENTRYPOINT ["gunicorn", \
    "--bind", "0.0.0.0:8080", \
    "--worker-class", "gevent", \
    "--workers", "${WORKERS}", \
    "--threads", "${THREADS}", \
    "--timeout", "${TIMEOUT}", \
    "--access-logfile", "-", \
    "--error-logfile", "-", \
    "--log-level", "info", \
    "app:app"]