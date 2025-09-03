#!/usr/bin/env python
"""
Memory-optimized installer for sentence-transformers
This script installs sentence-transformers and its dependencies with
controlled memory usage by installing dependencies incrementally.
"""
import os
import subprocess
import sys
import tempfile

def install_with_memory_optimization():
    """Install sentence-transformers with memory optimization."""
    print("Starting memory-optimized installation of sentence-transformers...")
    
    # Create a temporary directory for downloads
    with tempfile.TemporaryDirectory() as tmp_dir:
        # First install PyTorch (the largest dependency)
        print("Step 1/4: Installing PyTorch...")
        subprocess.check_call([
            sys.executable, '-m', 'pip', 'install', 
            '--no-cache-dir', 'torch==2.1.0'
        ])
        
        # Then install transformers without dependencies
        print("Step 2/4: Installing transformers...")
        subprocess.check_call([
            sys.executable, '-m', 'pip', 'install',
            '--no-cache-dir', 'transformers==4.33.3'
        ])
        
        # Install other core dependencies
        print("Step 3/4: Installing core dependencies...")
        subprocess.check_call([
            sys.executable, '-m', 'pip', 'install',
            '--no-cache-dir', 'tqdm', 'nltk', 'scikit-learn', 'scipy'
        ])
        
        # Finally install sentence-transformers without reinstalling dependencies
        print("Step 4/4: Installing sentence-transformers...")
        subprocess.check_call([
            sys.executable, '-m', 'pip', 'install',
            '--no-cache-dir', '--no-deps', 'sentence-transformers'
        ])
    
    print("sentence-transformers installation complete!")

if __name__ == "__main__":
    install_with_memory_optimization()
