"""Compare bounded deduction progress on saved generated shading candidates."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
from typing import Any

EXPLAINER = Path(__file__).with_name("explain_shading.py")
MAX_BYTES = 65536


def _budget(value: float, maximum: int) -> None:
    if (type(value) not in (int, float) or not 0 < value <= maximum
            or not math.isfinite(value)):
        raise ValueError(f"Time budget must be finite, positive and at most {maximum} seconds")


def _summarize(trace: dict[str, Any], returncode: int) -> dict[str, Any]:
    if (trace.get("format") != "puzzle-box/shading-deduction-trace-v1"
            or trace.get("status") not in ("solved", "stalled")
            or returncode != (0 if trace["status"] == "solved" else 1)
            or any(trace["artifact_verification"].get(k) is not True for k in ("valid", "unique", "irreducible"))):
        raise ValueError("Worker did not return a verified deduction result")
    given = len({tuple(g["cell"]) for g in trace["givens"]})
    inferred, unresolved = len(trace["steps"]), len(trace["unresolved_cells"])
    if (given + inferred + unresolved != trace["rows"] * trace["cols"]
            or (unresolved == 0) != (trace["status"] == "solved")
            or sum(v is None for row in trace["cells"] for v in row) != unresolved):
        raise ValueError("Worker counts do not agree with its final state")
    return {"status": trace["status"], "clue_count": trace["artifact_verification"]["clue_count"],
            "given_cells": given, "inferred_cells": inferred, "unresolved_cells": unresolved,
            "techniques": dict(Counter(s["technique"] for s in trace["steps"])),
            "rules_without_deductions": trace["rules_without_deductions"], "trace": trace}


def compare(paths: list[Path], *, phase_seconds: float = 15, total_seconds: float = 120) -> dict[str, Any]:
    if not 1 <= len(paths) <= 8:
        raise ValueError("Compare 1..8 saved puzzle files")
    _budget(phase_seconds, 300)
    _budget(total_seconds, 3600)
    environment = {"python": platform.python_version(), "ortools": importlib.metadata.version("ortools"),
                   "deduction_sha256": hashlib.sha256(EXPLAINER.read_bytes()).hexdigest()}
    start = time.monotonic()
    deadline = start + total_seconds
    attempts, groups = [], []
    group_keys: dict[str, int] = {}
    for index, path in enumerate(paths, 1):
        attempt: dict[str, Any] = {"index": index, "file": path.name, "status": "not_started",
                                   "reason": "total_budget", "seconds": 0.0}
        attempts.append(attempt)
        if time.monotonic() >= deadline:
            continue
        attempt_start = time.monotonic()
        try:
            # Snapshot bounded input, so edits to an original file during a worker
            # run cannot change the bytes described by this attempt's hash.
            with path.open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("Puzzle file must be at most 65536 bytes")
            attempt["sha256"] = hashlib.sha256(raw).hexdigest()
        except (OSError, ValueError) as exc:
            attempt.update(status="rejected", reason=str(exc), seconds=time.monotonic() - attempt_start)
            continue
        with tempfile.TemporaryDirectory(prefix="puzzle-box-deductions-") as temporary:
            snapshot = Path(temporary) / "candidate.json"
            snapshot.write_bytes(raw)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                attempt["seconds"] = time.monotonic() - attempt_start
                continue
            timeout = min(phase_seconds, remaining)
            attempt["timeout_seconds"] = timeout
            try:
                worker = subprocess.run([sys.executable, str(EXPLAINER), str(snapshot), "--json"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                    env=dict(os.environ, PYTHONHASHSEED="0", PYTHONIOENCODING="utf-8"))
            except subprocess.TimeoutExpired:
                # The bundled explainer does not spawn children. run() kills and
                # waits for this worker; no partial trace is used as a result.
                attempt.update(status="timeout", reason="total_budget" if remaining <= phase_seconds else "phase_budget")
            except OSError as exc:
                attempt.update(status="error", reason=str(exc))
            else:
                if worker.returncode not in (0, 1):
                    attempt.update(status="rejected" if worker.returncode == 2 else "error",
                                   reason=worker.stderr[-4096:] or f"Worker exited with code {worker.returncode}",
                                   returncode=worker.returncode)
                else:
                    try:
                        summary = _summarize(json.loads(worker.stdout), worker.returncode)
                        # The explainer has strictly validated these snapshot bytes.
                        data = json.loads(raw)
                        recipe = {k: data[k] for k in ("rows", "cols", "rules")}
                        recipe["clue_kinds"] = data.get("clue_kinds", ["cell"])
                        key = json.dumps(recipe, sort_keys=True)
                        if key not in group_keys:
                            group_keys[key] = len(groups) + 1
                            groups.append({"id": group_keys[key], "recipe": recipe})
                        attempt.update(summary, recipe_group=group_keys[key], reason=None)
                    except (ValueError, TypeError, KeyError, AttributeError) as exc:
                        attempt.update(status="error", reason=f"Invalid worker result: {exc}")
        attempt["seconds"] = time.monotonic() - attempt_start
    return {"format": "puzzle-box/shading-deduction-comparison-v1", "environment": environment,
            "phase_seconds": phase_seconds, "total_seconds": total_seconds,
            "seconds": time.monotonic() - start, "attempts": attempts, "recipe_groups": groups,
            "counts": dict(Counter(a["status"] for a in attempts))}


def explain(report: dict[str, Any]) -> str:
    lines = ["Limited deductions on saved candidates (no guesses; not human difficulty).",
             "Recipe groups share dimensions, ordered rules and candidate hint kinds; techniques are incomplete.",
             "# | File | Group | Clues | Given cells | Inferred cells | Unresolved | Status"]
    for a in report["attempts"]:
        values = [a["index"], a["file"], a.get("recipe_group", "-"), a.get("clue_count", "-"),
                  a.get("given_cells", "-"), a.get("inferred_cells", "-"), a.get("unresolved_cells", "-"), a["status"]]
        lines.append(" | ".join(map(str, values)))
        if a.get("reason"):
            lines.append("  " + str(a["reason"]).strip())
        elif a.get("rules_without_deductions"):
            lines.append(f"  Rule indices without deductions: {a['rules_without_deductions']}")
    lines.extend(["", "Only solved/stalled rows passed unique-answer and irreducible-clue verification.",
                  "Stalled means these techniques stopped; timeout/not_started/rejected/error are not deduction results.",
                  "A supported rule type does not mean every deduction for it is implemented.",
                  "No ranking is computed. --json reveals traces, including deduced cell values."])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--phase-seconds", type=float, default=15,
                        help="Per-candidate worker budget, including verification and deductions")
    parser.add_argument("--total-seconds", type=float, default=120)
    parser.add_argument("--json", action="store_true", help="Reveal full deduction traces")
    args = parser.parse_args()
    try:
        report = compare(args.files, phase_seconds=args.phase_seconds, total_seconds=args.total_seconds)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else explain(report))
    return 0 if all(a["status"] == "solved" for a in report["attempts"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
