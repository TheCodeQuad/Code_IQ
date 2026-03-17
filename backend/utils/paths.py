"""
Shared filesystem paths for the backend.

Code lives in: <workspace>/Code_IQ
Data lives in: <workspace>/data

You can override the data root with CODEIQ_DATA_DIR.
"""

from __future__ import annotations

import os
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = APP_ROOT.parent
DATA_ROOT = Path(os.getenv("CODEIQ_DATA_DIR", str(WORKSPACE_ROOT / "data"))).resolve()
