"""Test package.

Importing this package puts the support library on `sys.path` so the tests run
under a plain `python3 -m unittest discover` with no installation step.
"""

from __future__ import annotations

from pathlib import Path
import sys

_LIBRARY = Path(__file__).resolve().parents[1] / "scripts" / "python"
if str(_LIBRARY) not in sys.path:
    sys.path.insert(0, str(_LIBRARY))
