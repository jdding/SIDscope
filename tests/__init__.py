"""Test bootstrap: force imports to resolve against this checkout."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

src_text = str(SRC)
if src_text in sys.path:
    sys.path.remove(src_text)
sys.path.insert(0, src_text)
