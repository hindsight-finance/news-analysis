"""Pytest bootstrap: make the repo root importable from any working directory.

The analysis scripts live at the project root and are imported by name
(`import main`, `from exploration import ...`). Inserting the repo root on
sys.path here lets `pytest` run from anywhere, not just the project root.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
