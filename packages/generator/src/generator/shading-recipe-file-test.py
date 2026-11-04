"""Exercise recipe interchange through discovery, generation and verification."""

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from puzzle_defs import BlackCount, ConnectedWhite, NonTouchingBlack, NoWhite2x2, ShadingRecipe

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"


@pytest.fixture(scope="module")
def codec():
    sys.path.insert(0, str(EXAMPLES))
    try:
        yield importlib.import_module("shading_recipe")
    finally:
        sys.path.remove(str(EXAMPLES))


def _record():
    return {"format": "puzzle-box/shading-recipe-v1", "rows": 2, "cols": 2,
            "rules": [{"type": "count", "count": 1}, {"type": "non-touching", "diagonal": False}],
            "clue_kinds": ["cell", "row-count", "column-count"]}


def _save(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _cli(script, *args, hash_seed="0"):
    return subprocess.run([sys.executable, str(EXAMPLES / script), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8", timeout=60,
                          env={**os.environ, "PYTHONHASHSEED": hash_seed})


def test_round_trip_keeps_rule_occurrences_order_and_hint_order(codec, tmp_path):
    original = ShadingRecipe(2, 3, (BlackCount(2), NonTouchingBlack(True), ConnectedWhite(False),
                                    NoWhite2x2(), BlackCount(2)), ("column-count", "cell", "row-count"))
    record = codec.recipe_record(original)
    restored = codec.load_recipe(_save(tmp_path / "recipe.json", record))
    assert restored == original
    assert set(record) == {"format", "rows", "cols", "rules", "clue_kinds"}
    assert codec.recipe_record(restored) == record


@pytest.mark.parametrize("field,value", [
    ("format", "puzzle-box/shading-v2"), ("format", "puzzle-box/shading-recipe-v2"),
    ("rows", True), ("rows", 2.0), ("rows", 0), ("rows", 10**20),
    ("cols", "2"), ("cols", -1), ("cols", None),
    ("rules", {}), ("rules", [{"type": "no-white-2x2"}] * 9),
    ("rules", [None]), ("rules", ["count"]), ("rules", [{}]),
    ("rules", [{"type": "external-module", "path": "payload.py"}]),
    ("rules", [{"type": "count", "count": True}]),
    ("rules", [{"type": "count", "count": 1.0}]),
    ("rules", [{"type": "count", "count": -1}]),
    ("rules", [{"type": "count", "count": 5}]),
    ("rules", [{"type": "count", "count": 1, "extra": 0}]),
    ("rules", [{"type": "non-touching", "diagonal": 0}]),
    ("rules", [{"type": "connected-white", "nonempty": "false"}]),
    ("rules", [{"type": "no-white-2x2", "extra": 0}]),
    ("clue_kinds", "cell"), ("clue_kinds", {}), ("clue_kinds", [None]),
    ("clue_kinds", [{}]), ("clue_kinds", ["cell", "cell"]), ("clue_kinds", ["arrow"]),
])
def test_invalid_configuration_is_rejected(codec, field, value):
    record = _record()
    record[field] = value
    with pytest.raises(ValueError):
        codec.read_recipe(record)


@pytest.mark.parametrize("data", [None, [], "recipe", {}, {**_record(), "seed": 6},
                                  {**_record(), "solution": [[0, 1], [0, 0]]},
                                  {k: v for k, v in _record().items() if k != "clue_kinds"}])
def test_wrong_record_shape_is_rejected(codec, data):
    with pytest.raises(ValueError):
        codec.read_recipe(data)


@pytest.mark.parametrize("raw,pattern", [
    (b'{"rows": 2, "rows": 3}', "Duplicate JSON key"),
    (b'{"rules":[{"type":"count","count":1,"count":2}]}', "Duplicate JSON key"),
    (b'{"rows": NaN}', "Non-finite"), (b'{"rows": Infinity}', "Non-finite"),
    (b"[" * 2000 + b"]" * 2000, "nested too deeply|Recipe must contain"),
    (b" " * 65537, "at most 65536"), (b"\xff", "utf-8"), (b"{", "property name"),
], ids=["duplicate-field", "duplicate-rule-field", "nan", "infinity", "deep", "large", "encoding", "syntax"])
def test_invalid_file_encoding_and_json(codec, tmp_path, raw, pattern):
    path = tmp_path / "bad.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError, match=pattern):
        codec.load_recipe(path)


def test_byte_rule_and_cell_boundaries(codec, tmp_path):
    record = _record()
    record.update(rows=5, cols=5, rules=[{"type": "count", "count": 0}] * 8)
    raw = json.dumps(record).encode()
    path = tmp_path / "boundary.json"
    path.write_bytes(raw + b" " * (65536-len(raw)))
    assert codec.load_recipe(path).rows == 5
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="65536"):
        codec.load_recipe(path)


def test_subclass_cannot_silently_lose_its_semantics(codec):
    class ChangedCount(BlackCount):
        pass

    with pytest.raises(ValueError, match="subclasses"):
        codec.recipe_record(ShadingRecipe(1, 1, (ChangedCount(0),)))


def test_exploration_export_matches_direct_generation_and_is_reproducible(tmp_path):
    recipe = tmp_path / "chosen.json"
    report = tmp_path / "report.json"
    export = _cli("explore_shading.py", "--rows", 3, "--cols", 3, "--black-counts", 3,
                  "--candidates", "count", "non-touching", "--hints", "cell", "row-count", "column-count",
                  "--explain", 2, 1, "--export-recipe", recipe, "--output", report)
    assert export.returncode == 0, export.stderr
    data = json.loads(recipe.read_text())
    assert data["rules"] == [{"type": "count", "count": 3}, {"type": "non-touching", "diagonal": False}]
    assert json.loads(report.read_text())["format"] == "puzzle-box/shading-exploration-v1"
    first = _cli("generate_shading.py", "generate", "--recipe", recipe, "--seed", 6)
    again = _cli("generate_shading.py", "generate", "--recipe", recipe, "--seed", 6, hash_seed="73")
    direct = _cli("generate_shading.py", "generate", "--rows", 3, "--cols", 3, "--rules", "count", "non-touching",
                  "--black-count", 3, "--hints", "cell", "row-count", "column-count", "--seed", 6)
    assert first.returncode == again.returncode == direct.returncode == 0, first.stderr
    assert first.stdout == again.stdout == direct.stdout
    puzzle = json.loads(first.stdout)
    assert puzzle["format"] == "puzzle-box/shading-v2" and puzzle["seed"] == 6
    assert len(puzzle["clues"]) == 2
    verified = _cli("generate_shading.py", "verify", _save(tmp_path / "puzzle.json", puzzle))
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout) == {"valid": True, "unique": True, "irreducible": True, "clue_count": 2}


@pytest.mark.parametrize("options", [[], ["--hints"], ["--candidates", "count", "count", "--black-counts", "0"]])
def test_export_empty_and_duplicate_occurrences(tmp_path, options):
    path = tmp_path / "chosen.json"
    args = ["--rows", "1", "--cols", "1", "--black-counts", "0", *options]
    indices = [1, 2] if "count" in options else []
    result = _cli("explore_shading.py", *args, "--explain", *indices, "--export-recipe", path)
    assert result.returncode == 0, result.stderr
    recipe = json.loads(path.read_text())
    assert len(recipe["rules"]) == len(indices)
    assert recipe["clue_kinds"] == ([] if "--hints" in options else ["row-count", "column-count"])


@pytest.mark.parametrize("flag,values", [("--rows", [3]), ("--cols", [3]), ("--black-count", [3]),
    ("--rules", ["count"]), ("--hints", ["cell"]), ("--diagonal", []), ("--allow-empty-white", [])])
def test_explicit_recipe_override_options_fail_without_overwriting(tmp_path, flag, values):
    recipe = _save(tmp_path / "chosen.json", _record())
    output = tmp_path / "puzzle.json"
    output.write_text("keep")
    r = _cli("generate_shading.py", "generate", "--recipe", recipe, flag, *values, "--output", output)
    assert r.returncode == 2 and "Do not combine --recipe" in r.stderr
    assert output.read_text() == "keep"


def test_input_output_aliases_are_rejected_without_overwriting(tmp_path, codec):
    recipe = _save(tmp_path / "chosen.json", _record())
    before = recipe.read_bytes()
    r = _cli("generate_shading.py", "generate", "--recipe", recipe, "--output", recipe)
    assert r.returncode == 2 and "different files" in r.stderr
    assert recipe.read_bytes() == before
    r = _cli("explore_shading.py", "--explain", 1, "--export-recipe", recipe, "--output", recipe)
    assert r.returncode == 2 and "different files" in r.stderr
    assert recipe.read_bytes() == before


def test_hardlink_output_alias_is_rejected_when_supported(tmp_path, codec):
    recipe = _save(tmp_path / "chosen.json", _record())
    before = recipe.read_bytes()
    alias = tmp_path / "alias.json"
    try:
        alias.hardlink_to(recipe)
    except OSError as exc:
        pytest.skip(f"Filesystem does not allow hardlink creation: {exc}")
    with pytest.raises(ValueError, match="different files"):
        codec.check_distinct_paths(recipe, alias)
    r = _cli("explore_shading.py", "--explain", 1, "--export-recipe", recipe, "--output", alias)
    assert r.returncode == 2 and "different files" in r.stderr
    assert recipe.read_bytes() == before


@pytest.mark.parametrize("args", [[], ["--explain", 99], ["--explain", 1, 1], ["--explain", 1, "--json"]])
def test_invalid_export_selection_preserves_existing_file(tmp_path, args):
    output = tmp_path / "chosen.json"
    output.write_text("keep")
    r = _cli("explore_shading.py", *args, "--export-recipe", output)
    assert r.returncode == 2 and "Traceback" not in r.stderr
    assert output.read_text() == "keep"


@pytest.mark.parametrize("mode", ["infeasible", "ambiguous", "missing", "puzzle", "invalid-json"])
def test_generation_failures_do_not_write_output_or_add_hints(tmp_path, mode):
    record = _record()
    if mode == "infeasible":
        record["rules"] = [{"type": "count", "count": 0}, {"type": "count", "count": 1}]
    elif mode == "ambiguous":
        record["rules"][0]["count"] = 2
        record["clue_kinds"] = ["row-count", "column-count"]
    elif mode == "puzzle":
        record["format"] = "puzzle-box/shading-v2"
    recipe = _save(tmp_path / "chosen.json", record)
    if mode == "missing":
        recipe = tmp_path / "not-there.json"
    if mode == "invalid-json":
        recipe.write_text('{"rows":2,"rows":3}')
    output = tmp_path / "puzzle.json"
    output.write_text("keep")
    r = _cli("generate_shading.py", "generate", "--recipe", recipe, "--output", output)
    assert r.returncode == 2 and "Traceback" not in r.stderr
    assert output.read_text() == "keep"
    if mode == "ambiguous":
        assert "Initial clues" in r.stderr and "include cell in the recipe clue_kinds" in r.stderr
    if mode == "infeasible":
        assert "Failed to generate a random solution" in r.stderr


def test_legacy_format_and_zero_hint_recipe_still_work(tmp_path):
    record = _record()
    record.update(rows=1, cols=1, rules=[{"type": "count", "count": 0}], clue_kinds=["cell"])
    for kinds, expected in [(["cell"], "puzzle-box/shading-v1"), ([], "puzzle-box/shading-v2")]:
        record["clue_kinds"] = kinds
        recipe = _save(tmp_path / "chosen.json", record)
        r = _cli("generate_shading.py", "generate", "--recipe", recipe)
        assert r.returncode == 0, r.stderr
        artifact = json.loads(r.stdout)
        assert artifact["format"] == expected and artifact["clues"] == []
        assert artifact["solution"] == [[0]] and artifact["seed"] == 42
