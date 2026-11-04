"""Bootstrap only the curated local sources shipped by prepare_vercel.py."""

import os
import importlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PATHS = [ROOT, ROOT / "examples", *(ROOT / "packages" / name / "src" for name in ("puzzle", "puzzle-defs", "generator"))]
sys.path[:0] = [str(path) for path in PATHS]
# The bounded child process needs the same local packages; do not depend on an
# editable install or paths from the developer's machine.
os.environ["PYTHONPATH"] = os.pathsep.join(map(str, PATHS))

app = importlib.import_module("web_hosted").app
