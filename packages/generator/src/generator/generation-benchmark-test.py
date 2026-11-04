import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.syspath_prepend(str(EXAMPLES))
    return importlib.import_module("benchmark_generation")


@pytest.mark.parametrize("option,value", [
    ("phase_seconds", 0), ("phase_seconds", -1), ("phase_seconds", float("nan")),
    ("phase_seconds", float("inf")), ("phase_seconds", True), ("phase_seconds", 301),
    ("total_seconds", 0), ("total_seconds", float("nan")), ("total_seconds", 3601),
])
def test_invalid_budget_has_no_files_or_workers(app, monkeypatch, tmp_path, option, value):
    monkeypatch.setattr(app, "_environment", lambda: pytest.fail("validation must precede work"))
    with pytest.raises(ValueError, match="seconds"):
        app.benchmark(["shading-3x3"], [0], tmp_path / "new", **{option: value})
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("seeds", [[], [True], [-1], [2**31], [1, 1], list(range(9))])
def test_invalid_seeds(app, tmp_path, seeds):
    with pytest.raises(ValueError, match="seeds"):
        app.benchmark(["shading-3x3"], seeds, tmp_path / "new")
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("selected", [[], ["unknown"], ["shading-3x3", "shading-3x3"]])
def test_invalid_cases(app, tmp_path, selected):
    with pytest.raises(ValueError, match="case"):
        app.benchmark(selected, [0], tmp_path / "new")


def test_existing_output_is_preserved(app, monkeypatch, tmp_path):
    (tmp_path / "report.json").write_text("existing", encoding="utf-8")
    monkeypatch.setattr(app, "_environment", lambda: {})
    monkeypatch.setattr(app, "_phase", lambda *a, **k: pytest.fail("must not launch"))
    with pytest.raises(FileExistsError):
        app.benchmark(["shading-3x3"], [0], tmp_path)
    assert (tmp_path / "report.json").read_text(encoding="utf-8") == "existing"
    assert len(list(tmp_path.iterdir())) == 1


def test_timeout_reaps_the_real_worker(app, monkeypatch):
    original = subprocess.Popen
    workers = []

    def capture(*args, **kwargs):
        worker = original(*args, **kwargs)
        workers.append(worker)
        return worker

    monkeypatch.setattr(subprocess, "Popen", capture)
    result = app._phase([sys.executable, "-c", "import time; time.sleep(30)"],
                        phase_seconds=0.1, deadline=time.monotonic() + 60)
    assert result["status"] == "timeout"
    assert result["reason"] == "phase_budget"
    assert len(workers) == 1 and workers[0].poll() is not None


def test_total_budget_limits_next_worker_and_then_skips(app, monkeypatch):
    monkeypatch.setattr(app.time, "monotonic", lambda: 10)
    timeouts = []

    def expire(command, **kwargs):
        timeouts.append(kwargs["timeout"])
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(app.subprocess, "run", expire)
    result = app._phase(["unused"], phase_seconds=15, deadline=10.25)
    assert result["status"] == "timeout" and result["reason"] == "total_budget"
    assert timeouts == [0.25]
    result = app._phase(["unused"], phase_seconds=15, deadline=10)
    assert result["status"] == "not_started"
    assert timeouts == [0.25]


def test_worker_launch_failure_is_a_recorded_failure(app, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("cannot launch")

    monkeypatch.setattr(app.subprocess, "run", fail)
    result = app._phase(["unused"], phase_seconds=1, deadline=time.monotonic() + 10)
    assert result["status"] == "failed" and result["reason"] == "launch_error"
    assert result["stderr"] == "cannot launch"


@pytest.mark.parametrize("failure", ["timeout", "failed", "not_started", "false", "malformed", "count"])
def test_unverified_artifact_is_not_published(app, monkeypatch, tmp_path, failure):
    monkeypatch.setattr(app, "_environment", lambda: {})

    def phase(command, **kwargs):
        if "generate" in command:
            Path(command[command.index("--output") + 1]).write_text('{"clues": []}', encoding="utf-8")
            return {"status": "ok", "seconds": 0.1}
        verified = {"valid": True, "unique": failure != "false", "irreducible": True,
                    "clue_count": 1 if failure == "count" else 0}
        return {"status": failure if failure in ("timeout", "failed", "not_started") else "ok",
                "seconds": 0.1, "stdout": "{" if failure == "malformed" else json.dumps(verified)}

    monkeypatch.setattr(app, "_phase", phase)
    output = tmp_path / "new"
    report = app.benchmark(["shading-3x3"], [0], output)
    assert report["complete"] is True
    assert report["runs"][0]["status"] != "verified"
    assert list(output.iterdir()) == [output / "report.json"]


def test_generation_failure_is_recorded_and_next_seed_runs(app, monkeypatch, tmp_path):
    monkeypatch.setattr(app, "_environment", lambda: {})
    commands = []

    def fail(command, **kwargs):
        commands.append(command)
        return {"status": "failed", "seconds": 0.1, "stderr": "inconsistent"}

    monkeypatch.setattr(app, "_phase", fail)
    report = app.benchmark(["shading-inconsistent"], [0, 1], tmp_path / "new")
    assert report["counts"] == {"generation_failed": 2}
    assert len(commands) == 2 and all("generate" in c for c in commands)
    assert all(r["verification"]["reason"] == "generation_incomplete" for r in report["runs"])


def test_three_real_recipe_types_and_failure_controls(tmp_path):
    output = tmp_path / "results"
    process = subprocess.run([
        sys.executable, str(EXAMPLES / "benchmark_generation.py"), "--output", str(output),
        "--cases", "shading-3x3", "slitherlink-2x2", "yajilin-2x3",
        "shading-insufficient-hints", "shading-inconsistent", "--seeds", "0",
        "--phase-seconds", "30", "--total-seconds", "180",
    ], capture_output=True, text=True, timeout=190)
    assert process.returncode == 1, process.stderr
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["complete"] is True
    assert report["counts"] == {"verified": 3, "generation_failed": 2}
    for run in report["runs"][:3]:
        content = (output / run["artifact"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == run["sha256"]
        assert run["generation"]["status"] == run["verification"]["status"] == "ok"
        assert run["verification_result"]["unique"] is True
        assert run["verification_result"]["clue_count"] == len(json.loads(content)["clues"])
    assert "uniqu" in report["runs"][3]["generation"]["stderr"].lower()
    assert "Failed to generate" in report["runs"][4]["generation"]["stderr"]
    assert len(list(output.iterdir())) == 4


def test_cli_timeout_and_no_unverified_files(tmp_path):
    output = tmp_path / "results"
    process = subprocess.run([
        sys.executable, str(EXAMPLES / "benchmark_generation.py"), "--output", str(output),
        "--cases", "shading-3x3", "--seeds", "0", "1", "--phase-seconds", "0.000001",
        "--total-seconds", "0.000001",
    ], capture_output=True, text=True, timeout=10)
    assert process.returncode == 1, process.stderr
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert len(report["runs"]) == 2
    assert all(r["status"] in ("generation_timeout", "budget_exhausted") for r in report["runs"])
    assert list(output.iterdir()) == [output / "report.json"]
