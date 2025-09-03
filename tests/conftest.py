import sys
import os

# Ensure project root and the src/ directory are on sys.path so imports like
# `src.core...` and `core...` resolve during pytest collection and test runs.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "src")

for p in (ROOT, SRC_DIR):
    if p and p not in sys.path:
        sys.path.insert(0, p)
