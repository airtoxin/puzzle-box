"""Saved JSON arrays must not be replaced by other iterable containers."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
EDGES = [[0, 0, 0, 1], [0, 1, 1, 1], [1, 0, 1, 1], [0, 0, 1, 0]]
RECORDS = {
    "shading-v1": {"format": "puzzle-box/shading-v1", "rows": 1, "cols": 1,
                   "rules": [], "clues": [[0, 0, 1]], "solution": [[1]]},
    "shading-v2": {"format": "puzzle-box/shading-v2", "rows": 1, "cols": 1,
                   "rules": [], "clue_kinds": ["cell"], "solution": [[1]],
                   "clues": [{"type": "cell", "row": 0, "col": 0, "value": 1}]},
    "slitherlink": {"format": "puzzle-box/slitherlink-v1", "rows": 1, "cols": 1,
                    "loop_length": None, "clue_kinds": ["cell-count", "edge"],
                    "clues": [], "solution": EDGES},
    "yajilin": {"format": "puzzle-box/yajilin-v1", "rows": 2, "cols": 2,
                "arrow_sites": [], "clue_kinds": ["arrow", "black", "edge"], "clues": [],
                "solution": {"black_cells": [], "loop_edges": EDGES}},
}
FIELDS = {
    "shading-v1": ("rules", "clues"),
    "shading-v2": ("rules", "clue_kinds", "clues"),
    "slitherlink": ("clue_kinds", "clues", "solution"),
    "yajilin": ("arrow_sites", "clue_kinds", "clues", "solution.black_cells", "solution.loop_edges"),
}


def _app(case, monkeypatch):
    monkeypatch.syspath_prepend(str(EXAMPLES))
    name = "shading" if case.startswith("shading") else case
    return importlib.import_module(f"generate_{name}")


def _reader(app):
    return app._read_record if app.__name__ == "generate_shading" else app.read_record


@pytest.mark.parametrize("case,field", [(c, f) for c, fields in FIELDS.items() for f in fields])
@pytest.mark.parametrize("value", [{}, "", None, False, ()], ids=["object", "string", "null", "bool", "tuple"])
def test_every_array_boundary_rejects_non_arrays_with_its_field_name(monkeypatch, case, field, value):
    record = deepcopy(RECORDS[case])
    target = record
    parts = field.split(".")
    for part in parts[:-1]:
        target = target[part]
    target[parts[-1]] = value
    with pytest.raises(ValueError, match=re.escape(field) + " must be an array"):
        _reader(_app(case, monkeypatch))(record)


@pytest.mark.parametrize("case", ["shading-v2", "slitherlink", "yajilin"])
def test_nonempty_object_keys_are_not_interpreted_as_enabled_hint_types(monkeypatch, case):
    record = deepcopy(RECORDS[case])
    record["clue_kinds"] = {kind: False for kind in record["clue_kinds"]}
    with pytest.raises(ValueError, match="clue_kinds must be an array"):
        _reader(_app(case, monkeypatch))(record)


@pytest.mark.parametrize("clue,kinds", [
    ({"type": "cell", "row": 0, "col": 0, "value": 1}, ["row-count"]),
    ({"type": "row-count", "row": 0, "count": 1}, ["cell"]),
    ({"type": "column-count", "col": 0, "count": 1}, ["cell"]),
])
def test_valid_arrays_still_reject_disabled_clue_types_before_solving(monkeypatch, clue, kinds):
    app = _app("shading-v2", monkeypatch)
    record = deepcopy(RECORDS["shading-v2"])
    record.update(clues=[clue], clue_kinds=kinds)
    monkeypatch.setattr(app.ShadingRecipe, "build_from_clues",
                        lambda *a, **k: pytest.fail("Reject disabled clues before solving"))
    with pytest.raises(ValueError, match="not enabled by clue_kinds"):
        app.verify(record)


@pytest.mark.parametrize("case", RECORDS)
def test_valid_arrays_and_allowed_empty_lists_keep_their_meaning(monkeypatch, case):
    record = json.loads(json.dumps(RECORDS[case]))
    before = deepcopy(record)
    result = _app(case, monkeypatch).verify(record)
    assert result["valid"] and result["unique"] and result["irreducible"]
    assert record == before


@pytest.mark.parametrize("value", [{}, "", None, (0, 0, 1), [], [0, 0], [0, 0, 1, 1]])
def test_legacy_cell_clue_requires_an_array_of_three_items(monkeypatch, value):
    app = _app("shading-v1", monkeypatch)
    with pytest.raises(ValueError, match="A v1 cell clue must be an array of row, column and value"):
        app.read_clue(value, legacy=True)


@pytest.mark.parametrize("command", ["verify", "show", "check"])
@pytest.mark.parametrize("case,field,args", [
    ("shading-v1", "rules", ["--answer", "#"]),
    ("slitherlink", "clues", ["--answer", "1/11/1"]),
    ("yajilin", "arrow_sites", ["--cells", "../..", "--edges", "1/11/1"]),
])
def test_previous_false_acceptances_fail_cleanly_in_all_cli_actions(tmp_path, case, field, args, command):
    record = deepcopy(RECORDS[case])
    record[field] = {}
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    before = path.read_bytes()
    name = "shading" if case.startswith("shading") else case
    result = subprocess.run([sys.executable, str(EXAMPLES / f"generate_{name}.py"), command, str(path),
                             *(args if command == "check" else [])],
                            capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert result.returncode == 2
    assert f"{field} must be an array" in result.stderr
    assert "Traceback" not in result.stderr and result.stdout == ""
    assert path.read_bytes() == before
