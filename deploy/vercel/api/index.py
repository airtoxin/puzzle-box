"""Bootstrap only the curated local sources shipped by prepare_vercel.py."""

import os
import importlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PATHS = [ROOT, ROOT / "examples", *(ROOT / "packages" / name / "src" for name in ("puzzle", "puzzle-defs", "generator"))]
sys.path[:0] = [str(path) for path in PATHS]
# The bounded child needs local sources AND the runtime's installed dependency
# paths. Vercel injects its bundle/virtualenv into sys.path; sys.executable alone
# does not guarantee the same imports in a fresh child interpreter.
os.environ["PYTHONPATH"] = os.pathsep.join(path for path in sys.path if path)

app = importlib.import_module("web_hosted").app
