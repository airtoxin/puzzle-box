import hashlib
import importlib
from itertools import product
import json
from pathlib import Path
import subprocess
import sys

import pytest

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.syspath_prepend(str(EXAMPLES))
    return importlib.import_module("compare_shading_deductions")


@pytest.mark.parametrize("option,value", [
    ("phase_seconds", 0), ("phase_seconds", True), ("phase_seconds", float("nan")),
    ("phase_seconds", float("inf")), ("phase_seconds", 301),
    ("total_seconds", -1), ("total_seconds", 3601),
])
def test_invalid_budgets_precede_workers(app, monkeypatch, option, value):
    monkeypatch.setattr(app.subprocess, "run", lambda *a, **k: pytest.fail("No worker"))
    with pytest.raises(ValueError, match="budget"):
        app.compare([EXAMPLES / "shading-connector-sample.json"], **{option: value})


@pytest.mark.parametrize("count", [0, 9])
def test_candidate_limit(app, count):
    with pytest.raises(ValueError, match="1..8"):
        app.compare([EXAMPLES / "shading-connector-sample.json"] * count)


def test_timeout_kills_and_reaps_each_worker(app, monkeypatch, tmp_path):
    slow = tmp_path / "slow.py"
    slow.write_text("import time; time.sleep(30)", encoding="utf-8")
    monkeypatch.setattr(app, "EXPLAINER", slow)
    original = subprocess.Popen
    workers = []

    def launch(*args, **kwargs):
        worker = original(*args, **kwargs)
        workers.append(worker)
        return worker

    monkeypatch.setattr(app.subprocess, "Popen", launch)
    sample = EXAMPLES / "shading-connector-sample.json"
    report = app.compare([sample, sample], phase_seconds=0.05, total_seconds=5)
    assert report["counts"] == {"timeout": 2}
    assert len(workers) == 2 and all(w.poll() is not None for w in workers)
    assert all(a["reason"] == "phase_budget" and "trace" not in a for a in report["attempts"])


def test_total_budget_clamps_worker_then_skips_remaining(app, monkeypatch):
    clock = [0.0]
    timeouts = []
    monkeypatch.setattr(app.time, "monotonic", lambda: clock[0])

    def expire(command, **kwargs):
        timeouts.append(kwargs["timeout"])
        clock[0] = 2.0
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(app.subprocess, "run", expire)
    sample = EXAMPLES / "shading-connector-sample.json"
    report = app.compare([sample, sample], phase_seconds=15, total_seconds=1)
    assert timeouts == [1]
    assert report["counts"] == {"timeout": 1, "not_started": 1}
    assert report["attempts"][0]["reason"] == "total_budget"
    assert all("trace" not in a for a in report["attempts"])


def test_oversize_input_never_reaches_worker(app, monkeypatch, tmp_path):
    oversized = tmp_path / "large.json"
    oversized.write_bytes(b"x" * 65537)
    monkeypatch.setattr(app.subprocess, "run", lambda *a, **k: pytest.fail("No worker"))
    result = app.compare([oversized])["attempts"][0]
    assert result["status"] == "rejected" and "65536" in result["reason"]


@pytest.mark.parametrize("fault", ["json", "unverified", "counts", "exit", "launch", "crash"])
def test_bad_worker_result_is_not_a_deduction_result(app, monkeypatch, fault):
    deduction = importlib.import_module("explain_shading")
    sample = EXAMPLES / "shading-connector-sample.json"
    trace = deduction.explain_puzzle(json.loads(sample.read_text()))
    if fault == "unverified":
        trace["artifact_verification"]["unique"] = False
    if fault == "counts":
        trace["unresolved_cells"] = [[0, 0]]

    def run(command, **kwargs):
        if fault == "launch":
            raise OSError("cannot launch")
        if fault == "crash":
            return subprocess.CompletedProcess(command, -9, "", "Worker crashed")
        return subprocess.CompletedProcess(command, 1 if fault == "exit" else 0,
            "{" if fault == "json" else json.dumps(trace), "")

    monkeypatch.setattr(app.subprocess, "run", run)
    result = app.compare([sample])["attempts"][0]
    assert result["status"] == "error"
    assert "trace" not in result and "inferred_cells" not in result


@pytest.mark.parametrize("fault", ["disagreement", "contradiction"])
def test_real_worker_distinguishes_internal_deductions_from_invalid_candidates(app, monkeypatch, tmp_path, fault):
    proxy = tmp_path / "worker.py"
    body = ('return {"cells": [[1, None, None], [None, None, None]]}' if fault == "disagreement"
            else 'raise ValueError("injected contradictory deduction")')
    proxy.write_text(
        f"import sys\nsys.path.insert(0, {str(EXAMPLES)!r})\nimport explain_shading as d\n"
        f"def fail(*args):\n    {body}\nd._propagate = fail\nraise SystemExit(d.main())\n", encoding="utf-8")
    monkeypatch.setattr(app, "EXPLAINER", proxy)
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"format": "unsupported"}', encoding="utf-8")
    report = app.compare([EXAMPLES / "shading-connector-sample.json", invalid],
                         phase_seconds=30, total_seconds=90)
    assert report["counts"] == {"error": 1, "rejected": 1}
    internal, rejected = report["attempts"]
    assert internal["returncode"] == 3 and "Internal error:" in internal["reason"]
    assert ("disagrees" if fault == "disagreement" else "after puzzle verification") in internal["reason"]
    assert rejected["returncode"] == 2
    assert all("trace" not in a and "inferred_cells" not in a for a in report["attempts"])


def _accepts(bits, clues):
    # Independent tiny-board oracle: explicit 2x3 adjacency, no DSL or explainer.
    white = {i for i, bit in enumerate(bits) if bit == 0}
    seen, todo = set(), list(white)[:1]
    while todo:
        i = todo.pop()
        if i not in seen:
            seen.add(i)
            todo.extend(j for j in white - seen if abs(i // 3 - j // 3) + abs(i % 3 - j % 3) == 1)
    return (bool(white) and seen == white
            and any(bits[i] for i in (0, 1, 3, 4)) and any(bits[i] for i in (1, 2, 4, 5))
            and all(bits[r * 3 + c] == value for r, c, value in clues))


def test_saved_generated_candidates_are_independently_unique_and_keep_exact_traces(app):
    deduction = importlib.import_module("explain_shading")
    paths = [EXAMPLES / "shading-deduction-candidate-stalled.json", EXAMPLES / "shading-connector-sample.json"]
    originals = [p.read_bytes() for p in paths]
    report = app.compare(paths, phase_seconds=30, total_seconds=90)
    assert report["counts"] == {"stalled": 1, "solved": 1}
    assert len(report["recipe_groups"]) == 1
    for raw, attempt in zip(originals, report["attempts"]):
        data = json.loads(raw)
        answers = [bits for bits in product((0, 1), repeat=6) if _accepts(bits, data["clues"])]
        assert answers == [tuple(v for row in data["solution"] for v in row)]
        for i in range(len(data["clues"])):
            assert sum(_accepts(bits, data["clues"][:i] + data["clues"][i+1:]) for bits in product((0, 1), repeat=6)) > 1
        assert attempt["trace"] == deduction.explain_puzzle(data)
        assert attempt["sha256"] == hashlib.sha256(raw).hexdigest()
        assert attempt["given_cells"] == 4 and attempt["recipe_group"] == 1
        assert attempt["given_cells"] + attempt["inferred_cells"] + attempt["unresolved_cells"] == 6
    assert [(a["inferred_cells"], a["unresolved_cells"]) for a in report["attempts"]] == [(1, 1), (2, 0)]
    assert [p.read_bytes() for p in paths] == originals
    text = app.explain(report)
    assert "not human difficulty" in text and "incomplete" in text
    assert "State:" not in text and "white-connector" not in text  # Summary does not print inferred values/steps.


def test_cli_mixed_clues_unsupported_format_and_other_recipe(tmp_path):
    script = EXAMPLES / "compare_shading_deductions.py"
    large = json.loads((EXAMPLES / "shading-connector-sample.json").read_text())
    large.update(rows=4, cols=4)
    unsupported_size = tmp_path / "large.json"
    unsupported_size.write_text(json.dumps(large), encoding="utf-8")
    command = [sys.executable, str(script), str(EXAMPLES / "slitherlink-sample.json"),
               str(EXAMPLES / "shading-deduction-stalled.json"), str(EXAMPLES / "shading-connector-sample.json"),
               str(unsupported_size),
               "--phase-seconds", "30", "--total-seconds", "90", "--json"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=100)
    assert result.returncode == 1, result.stderr
    report = json.loads(result.stdout)
    assert report["counts"] == {"rejected": 2, "stalled": 1, "solved": 1}
    assert len(report["recipe_groups"]) == 2
    unsupported, mixed, _, large_result = report["attempts"]
    assert "shading-v1 or shading-v2" in unsupported["reason"]
    assert "trace" not in unsupported
    assert "at most 9 cells" in large_result["reason"] and "trace" not in large_result
    assert (mixed["clue_count"], mixed["given_cells"], mixed["inferred_cells"], mixed["unresolved_cells"]) == (3, 0, 3, 6)
