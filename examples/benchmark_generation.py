"""Measure fixed small recipes with separate generation/verification time budgets."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
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

ROOT = Path(__file__).resolve().parents[1]
FORMAT = "puzzle-box/generation-benchmark-v1"


def cases() -> dict[str, tuple[str, list[str]]]:
    """Explicit CLI arguments are part of the reproducible benchmark definition."""
    result = {}
    for size, count in ((3, 3), (4, 5), (5, 8)):
        args = ["--rows", str(size), "--cols", str(size), "--black-count", str(count),
                "--rules", "count", "non-touching", "connected-white", "no-white-2x2",
                "--hints", "cell", "row-count", "column-count"]
        result[f"shading-{size}x{size}"] = ("shading", args + ["--selection", "solver"])
        if size == 3:
            result["shading-finite-3x3"] = ("shading", args + ["--selection", "finite"])
    for rows, cols in ((2, 2), (2, 3), (3, 3)):
        result[f"slitherlink-{rows}x{cols}"] = (
            "slitherlink", ["--rows", str(rows), "--cols", str(cols), "--hints", "cell-count", "edge"])
    for rows, cols in ((2, 3), (3, 3), (3, 4)):
        result[f"yajilin-{rows}x{cols}"] = (
            "yajilin", ["--rows", str(rows), "--cols", str(cols), "--arrow", "1", "0", "right",
                        "--hints", "arrow", "edge", "--attempts", "1"])
    result["shading-insufficient-hints"] = (
        "shading", ["--rows", "2", "--cols", "2", "--rules", "count", "--black-count", "1",
                    "--hints", "row-count", "--selection", "solver"])
    result["shading-inconsistent"] = (
        "shading", ["--rows", "2", "--cols", "2", "--rules", "count", "non-touching",
                    "--black-count", "4", "--hints", "cell", "--selection", "solver"])
    return result


def _seconds(value: float, name: str, maximum: int) -> None:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
        raise ValueError(f"{name} must be finite, greater than zero and at most {maximum} seconds")


def _phase(command: list[str], *, phase_seconds: float, deadline: float) -> dict[str, Any]:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return {"status": "not_started", "reason": "total_budget", "seconds": 0.0}
    timeout = min(phase_seconds, remaining)
    limit = "total_budget" if remaining <= phase_seconds else "phase_budget"
    start = time.monotonic()
    try:
        # Only the three bundled Python CLIs run here. They do not spawn child
        # processes; run() kills and waits for this worker on TimeoutExpired.
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=timeout,
                                 env=dict(os.environ, PYTHONHASHSEED="0", PYTHONIOENCODING="utf-8"))
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "reason": limit, "seconds": time.monotonic() - start,
                "timeout_seconds": timeout}
    except OSError as exc:
        return {"status": "failed", "reason": "launch_error", "seconds": time.monotonic() - start,
                "stderr": str(exc)}
    return {"status": "ok" if process.returncode == 0 else "failed",
            "seconds": time.monotonic() - start, "timeout_seconds": timeout,
            "returncode": process.returncode, "stdout": process.stdout[-4096:],
            "stderr": process.stderr[-4096:]}


def _environment() -> dict[str, Any]:
    result: dict[str, Any] = {"python": platform.python_version(),
                              "ortools": importlib.metadata.version("ortools"),
                              "platform": platform.platform(), "machine": platform.machine(),
                              "logical_cpus": os.cpu_count(), "python_hash_seed": "0",
                              "benchmark_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                              "seeded_search_workers": 1, "unseeded_search_workers": "solver default"}
    # Git is optional for installed source archives. No remotes, paths or secrets.
    for key, args in (("git_commit", ["rev-parse", "HEAD"]),
                      ("git_tracked_dirty", ["status", "--porcelain", "--untracked-files=no"])):
        try:
            p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=2)
            result[key] = (bool(p.stdout.strip()) if key.endswith("dirty") else p.stdout.strip()) if p.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            result[key] = None
    return result


def benchmark(selected: list[str], seeds: list[int], output: Path, *,
              phase_seconds: float = 15, total_seconds: float = 120) -> dict[str, Any]:
    catalog = cases()
    if not selected or len(selected) != len(set(selected)) or any(c not in catalog for c in selected):
        raise ValueError("Choose distinct case names from the fixed catalog")
    if (not 1 <= len(seeds) <= 8 or any(type(s) is not int or not 0 <= s <= 2**31 - 1 for s in seeds)
            or len(set(seeds)) != len(seeds)):
        raise ValueError("Choose 1..8 distinct integer seeds between 0 and 2147483647")
    _seconds(phase_seconds, "phase_seconds", 300)
    _seconds(total_seconds, "total_seconds", 3600)
    environment = _environment()
    output.mkdir()  # Refuse any existing directory or file, including symlinks.
    report: dict[str, Any] = {
        "format": FORMAT, "started_utc": datetime.now(timezone.utc).isoformat(),
        "environment": environment, "phase_seconds": phase_seconds, "total_seconds": total_seconds,
        "cases": selected, "seeds": seeds, "runs": [], "complete": False,
    }
    start = time.monotonic()
    deadline = start + total_seconds

    def save() -> None:
        report["seconds"] = time.monotonic() - start
        report["counts"] = dict(Counter(run["status"] for run in report["runs"]))
        # In our newly created directory only. Keep the last complete report if
        # interrupted while writing the next checkpoint.
        staging = output / "report.tmp"
        staging.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        staging.replace(output / "report.json")

    save()
    for name in selected:
        kind, arguments = catalog[name]
        script = f"examples/generate_{kind}.py"
        for seed in seeds:
            filename = f"{name}-seed-{seed}.json"
            generation_args = [script, "generate", *arguments, "--seed", str(seed)]
            run: dict[str, Any] = {"case": name, "seed": seed,
                                   "generate_arguments": generation_args,
                                   "verify_arguments": [script, "verify", filename]}
            with tempfile.TemporaryDirectory(prefix=".worker-", dir=output) as temporary:
                artifact = Path(temporary) / filename
                generation = _phase([sys.executable, *generation_args, "--output", str(artifact.resolve()), "--quiet"],
                                    phase_seconds=phase_seconds, deadline=deadline)
                run["generation"] = generation
                run["verification"] = {"status": "not_started", "reason": "generation_incomplete", "seconds": 0.0}
                run["status"] = "budget_exhausted" if generation["status"] == "not_started" else "generation_" + generation["status"]
                if generation["status"] == "ok":
                    verification = _phase([sys.executable, script, "verify", str(artifact.resolve())],
                                          phase_seconds=phase_seconds, deadline=deadline)
                    run["verification"] = verification
                    run["status"] = "budget_exhausted" if verification["status"] == "not_started" else "verification_" + verification["status"]
                    if verification["status"] == "ok":
                        try:
                            verified = json.loads(verification["stdout"])
                            if not isinstance(verified, dict) or any(verified.get(k) is not True for k in ("valid", "unique", "irreducible")):
                                raise ValueError("Verifier did not confirm valid, unique and irreducible")
                            content = artifact.read_bytes()
                            record = json.loads(content)
                            if (type(verified.get("clue_count")) is not int
                                    or verified["clue_count"] != len(record["clues"])):
                                raise ValueError("Verifier clue count does not match the artifact")
                            destination = output / filename
                            target = destination.open("xb")
                            try:
                                with target:
                                    target.write(content)
                            except BaseException:
                                # Exclusive creation succeeded: this attempt owns
                                # the file. A failed open must never enter cleanup.
                                destination.unlink()
                                raise
                            run.update(status="verified", artifact=filename,
                                       sha256=hashlib.sha256(content).hexdigest(), verification_result=verified)
                        except (ValueError, KeyError, TypeError, OSError) as exc:
                            run["status"] = "artifact_failed"
                            run["error"] = str(exc)
            report["runs"].append(run)
            save()
    report["complete"] = True
    save()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", choices=cases(), default=list(cases()))
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1])
    parser.add_argument("--phase-seconds", type=float, default=15)
    parser.add_argument("--total-seconds", type=float, default=120)
    parser.add_argument("--output", type=Path, required=True, help="New directory for report and verified puzzles")
    args = parser.parse_args()
    try:
        report = benchmark(args.cases, args.seeds, args.output,
                           phase_seconds=args.phase_seconds, total_seconds=args.total_seconds)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({"counts": report["counts"], "seconds": report["seconds"]}, sort_keys=True))
    return 0 if all(r["status"] == "verified" for r in report["runs"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
