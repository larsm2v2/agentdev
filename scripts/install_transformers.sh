#!/bin/bash
# Script to install sentence-transformers with memory optimization

# Set pip to not use cache to reduce memory usage
export PIP_NO_CACHE_DIR=1

# First install core dependencies of sentence-transformers separately
pip install --no-cache-dir torch==2.1.0 transformers==4.33.3

# Then install sentence-transformers without reinstalling its dependencies
pip install --no-cache-dir --no-deps sentence-transformers

# Optional: clean up any temporary files
find /tmp -type d -name "pip-*" -exec rm -rf {} +
