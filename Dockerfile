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

# Install dependencies but exclude sentence-transformers by default
RUN python -m pip install --no-cache-dir --upgrade pip && \
    grep -v "sentence-transformers" requirements.txt > requirements.filtered.txt && \
    pip install --no-cache-dir -r requirements.filtered.txt

# Copy the memory-optimized installer script
COPY install_transformers.py /app/

# Create a comment explaining how to install sentence-transformers if needed
# To install sentence-transformers, run: python /app/install_transformers.py

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
COPY install_transformers.py /app/
# Ensure pip can reach PyPI directly even if Docker daemon has proxy configured
ENV HTTP_PROXY="" \
        http_proxy="" \
        HTTPS_PROXY="" \
        https_proxy="" \
        NO_PROXY="pypi.org,files.pythonhosted.org,localhost,127.0.0.1"

# Filter out sentence-transformers from requirements
RUN grep -v "sentence-transformers" requirements.txt > requirements.filtered.txt

# Production: prefer wheelhouse if available to make builds deterministic and offline-capable
RUN if [ -d /wheelhouse ]; then \
            python -m pip install --no-cache-dir --upgrade pip && \
            pip install --no-cache-dir --no-index --find-links=/wheelhouse -r requirements.filtered.txt; \
        else \
            python -m pip install --no-cache-dir --upgrade pip && \
            pip install --no-cache-dir -r requirements.filtered.txt; \
        fi

# Copy the memory-optimized installer script
COPY install_transformers.py /app/

# Add comment about how to reinstall sentence-transformers later if needed
RUN echo "# To install sentence-transformers with memory optimization, run: python /app/install_transformers.py" > /app/EMBEDDINGS.md

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

#############################################
# ML-enabled stage with sentence-transformers
#############################################
FROM production AS ml-enabled

USER root
# Install sentence-transformers with memory optimization
RUN python /app/install_transformers.py
USER app

# This target can be built with:
# docker build --target ml-enabled -t email-librarian-ml:latest .