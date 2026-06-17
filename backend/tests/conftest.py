"""Pytest fixtures + path setup for the backend test suite.

Puts the repo root on sys.path so `import backend...` resolves whether pytest
is invoked from the repo root (`pytest backend/tests`) or from `backend/`.
Mirrors the `sys.path.insert` pattern used by every script in backend/scripts/.
"""

import os
import sys
from pathlib import Path

import pytest

# backend/tests/conftest.py -> parents[2] is the repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# Skip marker for tests that need a live Gemini key (the pure unit suite runs
# fully offline; CI without a key still goes green).
requires_gemini = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set — skipping live-API test",
)
