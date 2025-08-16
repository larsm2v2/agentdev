# Multi-stage build for Email Librarian
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    netcat-traditional \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

#############################################
# Development stage
#############################################
FROM base AS development

# Copy requirements
COPY requirements.docker.txt requirements.txt
# Ensure pip can reach PyPI directly even if Docker daemon has proxy configured
ENV HTTP_PROXY="" \
        http_proxy="" \
        HTTPS_PROXY="" \
        https_proxy="" \
        NO_PROXY="pypi.org,files.pythonhosted.org,localhost,127.0.0.1"

# If a wheelhouse was provided at build time (COPY wheelhouse /wheelhouse),
# install from it to avoid network access. Otherwise install from PyPI.
RUN if [ -d /wheelhouse ]; then \
            python -m pip install --no-cache-dir --upgrade pip && \
            pip install --no-cache-dir --no-index --find-links=/wheelhouse -r requirements.txt; \
        else \
            python -m pip install --no-cache-dir --upgrade pip && \
            pip install --no-cache-dir -r requirements.txt; \
        fi

# Copy application code
COPY . .

# Make scripts executable
RUN chmod +x docker-entrypoint.sh

# Development command
CMD ["python", "-m", "uvicorn", "src.core.enhanced_email_librarian_server:app", "--host", "0.0.0.0", "--port", "8000"]

#############################################
# Production stage
#############################################
FROM base AS production

# Copy requirements and install
COPY requirements.docker.txt requirements.txt
# Ensure pip can reach PyPI directly even if Docker daemon has proxy configured
ENV HTTP_PROXY="" \
        http_proxy="" \
        HTTPS_PROXY="" \
        https_proxy="" \
        NO_PROXY="pypi.org,files.pythonhosted.org,localhost,127.0.0.1"

# Production: prefer wheelhouse if available to make builds deterministic and offline-capable
RUN if [ -d /wheelhouse ]; then \
            python -m pip install --no-cache-dir --upgrade pip && \
            pip install --no-cache-dir --no-index --find-links=/wheelhouse -r requirements.txt; \
        else \
            python -m pip install --no-cache-dir --upgrade pip && \
            pip install --no-cache-dir -r requirements.txt; \
        fi

# Copy only necessary application files
COPY src/ ./src/
COPY config/ ./config/
COPY migrations/ ./migrations/
COPY frontend/ ./frontend/
COPY docker-entrypoint.sh ./

# Create app user for security
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

# Create necessary directories
RUN mkdir -p logs data email_cache

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["./docker-entrypoint.sh"]

# Default command
CMD ["python", "-m", "src.core.enhanced_email_librarian_server"]