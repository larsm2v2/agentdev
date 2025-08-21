# ML Optimized Build Guide

This guide explains how to build and run the Email Librarian system with sentence-transformers for advanced embedding capabilities while optimizing memory usage.

## Why Memory Optimization Matters

The sentence-transformers library and its dependencies (particularly PyTorch) require significant memory during installation. This can cause Docker builds to fail with "out of memory" errors on systems with limited resources.

## Building the ML-Enabled Image

We've created optimized build scripts that manage memory usage by:

1. Installing dependencies incrementally
2. Using the `--no-cache-dir` option for pip
3. Separating the heaviest dependencies (PyTorch) to be installed first
4. Using Docker BuildKit memory limits

### On Windows

```powershell
# From the project root
.\build-ml-image.ps1
```

### On Linux/MacOS

```bash
# From the project root
chmod +x build-ml-image.sh
./build-ml-image.sh
```

## Manual Building

If you prefer to build manually, use:

```bash
# Set memory limit (adjust based on your system)
DOCKER_BUILDKIT=1 docker build --memory=4g --target ml-enabled -t email-librarian-ml:latest .
```

## Using the ML-Enabled Image

Once built, you can run the ML-enabled image:

```bash
docker run -p 8000:8000 email-librarian-ml:latest
```

## Checking if ML Features are Available

When the application starts, it will log whether sentence-transformers is available:

```text
✅ sentence-transformers available. Semantic search enabled.
```

or

```text
⚠️ sentence-transformers not available. Semantic search disabled.
```

## Installing sentence-transformers After Deployment

If you've deployed a container without sentence-transformers but want to add it later:

```bash
# Connect to running container
docker exec -it your-container-name bash

# Install with memory optimization
python /app/install_transformers.py

# Restart the application process
```
