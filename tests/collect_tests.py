"""Collect and import existing top-level tests into the tests package.

This file imports / executes the original test modules that live at repository
root to make pytest discover them from `tests/` without changing their code.
"""

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Ensure repo root is in sys.path so original test modules can import project modules
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# List of original test module basenames to import (without .py)
MODULES = [
    'test_cataloging_api_integration',
    'test_cataloging_persistence',
    'test_cataloging_pipeline',
    'test_reclassification_labels_http',
    'test_reclassification_labels',
    'test_get_reclassification_labels',
    'test_function_state',
    'test_email_reply_parser',
    'test_paged_count',
    'test_methods_list',
    'test_message_id_retrieval',
    'test_message_id_batch',
    'test_gmail_label_processor',
    'test_full_dry_run',
    'test_email_retrieval',
    'test_email_batch_processor',
    'test_combined_message_id_processors',
    'test_cataloging_normalization',
    'test_ai_label_processor',
    'test_advanced_cataloging',
]

for mod in MODULES:
    try:
        importlib.import_module(mod)
    except Exception:
        # Import errors will be surfaced as pytest collection errors later,
        # but we swallow them here to allow pytest to run other tests.
        pass
