"""Saved-file boundaries must agree across play, verification and diagnostics."""
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
CASES = [
    ("generate_shading.py", "shading-sample.json", ["--answer", "..#/#../..#"]),
    ("generate_slitherlink.py", "slitherlink-sample.json", ["--answer", "?"]),
    ("generate_yajilin.py", "yajilin-sample.json", ["--cells", "?", "--edges", "?"]),
]


def _cli(script, command, path, *args):
    return subprocess.run([sys.executable, str(EXAMPLES / script), command, str(path), *args],
                          capture_output=True, text=True, encoding="utf-8", timeout=20)


@pytest.mark.parametrize("script,sample,answer", CASES)
@pytest.mark.parametrize("command", ["verify", "show", "check"])
def test_duplicate_version_is_rejected_before_any_puzzle_action(tmp_path, script, sample, answer, command):
    original = (EXAMPLES / sample).read_text(encoding="utf-8")
    raw = '{"format":"puzzle-box/future-v99",' + original.lstrip()[1:]
    path = tmp_path / "ambiguous.json"
    path.write_text(raw, encoding="utf-8")
    before = path.read_bytes()
    result = _cli(script, command, path, *(answer if command == "check" else []))
    assert result.returncode == 2
    assert "Duplicate JSON key: format" in result.stderr
    assert "Traceback" not in result.stderr and result.stdout == ""
    assert path.read_bytes() == before


@pytest.mark.parametrize("script,sample,answer", CASES)
@pytest.mark.parametrize("damage,expected", [
    ("nested-key", "Duplicate JSON key: note"),
    ("nan", "Non-finite"), ("overflow", "Non-finite"),
    ("large", "at most 65536 bytes"), ("deep", "nested too deeply"),
    ("future", "Unsupported"), ("encoding", "utf-8"), ("syntax", "property name"),
])
def test_invalid_saved_files_fail_cleanly(tmp_path, script, sample, answer, damage, expected):
    original = (EXAMPLES / sample).read_text(encoding="utf-8")
    if damage == "nested-key":
        raw = ('{"extra_metadata":{"note":1,"note":2},' + original.lstrip()[1:]).encode()
    elif damage in ("nan", "overflow"):
        value = "NaN" if damage == "nan" else "1e400"
        raw = ('{"extra_metadata":' + value + ',' + original.lstrip()[1:]).encode()
    elif damage == "large":
        encoded = original.encode()
        raw = encoded + b" " * (65537 - len(encoded))
    elif damage == "deep":
        raw = b"[" * 20000 + b"]" * 20000
    elif damage == "future":
        data = json.loads(original)
        data["format"] = data["format"].rsplit("-v", 1)[0] + "-v99"
        raw = json.dumps(data).encode()
    else:
        raw = b"\xff" if damage == "encoding" else b"{"
    path = tmp_path / "broken.json"
    path.write_bytes(raw)
    result = _cli(script, "verify", path)
    assert result.returncode == 2
    assert expected in result.stderr
    assert "Traceback" not in result.stderr and result.stdout == ""
    assert path.read_bytes() == raw


@pytest.mark.parametrize("script,sample", [(script, sample) for script, sample, _ in CASES] + [
    ("generate_shading.py", "shading-mixed-sample.json"),
])
@pytest.mark.parametrize("metadata", [None, {"ratio": 1.25, "label": "日本語"}],
                         ids=["no-metadata", "environment-metadata"])
def test_current_formats_and_exact_byte_limit_remain_compatible(tmp_path, script, sample, metadata):
    data = json.loads((EXAMPLES / sample).read_text(encoding="utf-8"))
    # Metadata is optional. Additional notes belong in the known metadata field,
    # not in unknown top-level fields which could instead represent new rules.
    data.pop("seed", None)
    data.pop("environment", None)
    if metadata is not None:
        data["environment"] = metadata
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    path = tmp_path / "boundary.json"
    padded = raw + b" " * (65536-len(raw))
    path.write_bytes(padded)
    result = _cli(script, "verify", path)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["valid"] and report["unique"] and report["irreducible"]
    assert path.read_bytes() == padded


@pytest.mark.parametrize("module,name", [("shading_recipe", "load_json"), ("coupled_records", "load_puzzle")])
@pytest.mark.parametrize("value", ["1e400", "-1e400", "NaN", "Infinity", "-Infinity"])
def test_existing_bounded_loaders_reject_all_nonfinite_numbers(tmp_path, monkeypatch, module, name, value):
    monkeypatch.syspath_prepend(str(EXAMPLES))
    loader = getattr(importlib.import_module(module), name)
    path = tmp_path / "number.json"
    path.write_text('{"metadata":' + value + '}', encoding="utf-8")
    with pytest.raises(ValueError, match="Non-finite"):
        loader(path)


@pytest.mark.parametrize("module", ["generate_shading", "generate_slitherlink", "generate_yajilin"])
@pytest.mark.parametrize("data", [None, [], {}, {"format": "puzzle-box/future-v99"}])
def test_record_readers_explain_missing_or_unsupported_versions(monkeypatch, module, data):
    monkeypatch.syspath_prepend(str(EXAMPLES))
    app = importlib.import_module(module)
    with pytest.raises(ValueError, match="Unsupported.*expected an object with format puzzle-box/"):
        app.verify(data)
