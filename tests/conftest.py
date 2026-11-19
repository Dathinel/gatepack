from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))  # run the tests from a checkout without installing

_spec = importlib.util.spec_from_file_location("make_fixtures", ROOT / "scripts" / "make_fixtures.py")
_mf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mf)
make_pdf = _mf.pdf
