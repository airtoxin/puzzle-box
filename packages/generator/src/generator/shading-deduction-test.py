"""Check each local inference against all assignments of its cited constraint."""

from copy import deepcopy
import importlib
from itertools import product
import json
from pathlib import Path
import subprocess
import sys

import pytest

from puzzle import Cell, at_least_one
from puzzle_defs import BlackCount, ColumnCountClue, ConnectedWhite, NonTouchingBlack, NoWhite2x2, RowCountClue, ShadingPuzzle, ShadingRecipe

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    deduction = importlib.import_module("explain_shading")
    oracle = importlib.import_module("analyze_shading")
    display = importlib.import_module("generate_shading")


def _load(name):
    return json.loads((EXAMPLES / f"shading-deduction-{name}.json").read_text())


def _replay_and_prove(recipe, clues, trace):
    known, origins = {}, {}
    for index, clue in enumerate(clues, 1):
        if isinstance(clue, tuple):
            cell, value = clue
            known[(cell.row, cell.col)] = value
            origins.setdefault((cell.row, cell.col), {"kind": "given", "index": index})
    for number, step in enumerate(trace["steps"], 1):
        assert step["number"] == number
        cell = tuple(step["cell"])
        assert cell not in known
        constraint = step["constraint"]
        scope = [tuple(c) for c in constraint["scope"]]
        source = constraint["source"]
        original = recipe.rules[source["index"]-1] if source["kind"] == "rule" else clues[source["index"]-1]
        # Check that the certificate's scope and relation really come from the cited source.
        if isinstance(original, (BlackCount, RowCountClue, ColumnCountClue)):
            expected = ([(original.row, c) for c in range(recipe.cols)] if isinstance(original, RowCountClue)
                        else [(r, original.col) for r in range(recipe.rows)] if isinstance(original, ColumnCountClue)
                        else [(r, c) for r in range(recipe.rows) for c in range(recipe.cols)])
            assert scope == expected and constraint["kind"] == "count" and constraint["target"] == original.count
            relation = lambda values: sum(values) == original.count
        elif isinstance(original, NonTouchingBlack):
            assert len(scope) == 2 and constraint["kind"] == "non-touching"
            a, b = scope
            dr, dc = abs(a[0]-b[0]), abs(a[1]-b[1])
            assert (max(dr, dc) if original.diagonal else dr+dc) == 1
            relation = lambda values: sum(values) <= 1
        else:
            assert type(original) is NoWhite2x2 and constraint["kind"] == "has-black"
            r, c = min(scope)
            assert scope == [(r, c), (r, c+1), (r+1, c), (r+1, c+1)]
            relation = lambda values: sum(values) >= 1
        assert step["premises"] == [{"cell": list(c), "value": known[c], "origin": origins[c]} for c in scope if c in known]
        assert step["unknown_cells"] == [list(c) for c in scope if c not in known]
        # Prove the step from ONLY its cited local constraint and listed premises.
        # Using the full unique solution here would also approve unsupported guesses.
        local_answers = [values for values in product((0, 1), repeat=len(scope))
                         if relation(values) and all(values[i] == known[c] for i, c in enumerate(scope) if c in known)]
        assert local_answers
        assert {values[scope.index(cell)] for values in local_answers} == {step["value"]}
        known[cell] = step["value"]
        origins[cell] = {"kind": "step", "index": number}
    assert trace["cells"] == [[known.get((r, c)) for c in range(recipe.cols)] for r in range(recipe.rows)]
    assert len(trace["steps"]) <= recipe.rows * recipe.cols


@pytest.mark.parametrize("rules", [(BlackCount(2),), (NonTouchingBlack(),), (NonTouchingBlack(True),),
    (NoWhite2x2(),), (BlackCount(2), NonTouchingBlack()), (BlackCount(1), ConnectedWhite())])
def test_all_feasible_partial_2x2_boards_have_sound_local_certificates(rules, monkeypatch):
    recipe = ShadingRecipe(2, 2, rules)
    boards = [bits for bits in product((0, 1), repeat=4) if all(oracle.accepts(rule, bits, 2, 2) for rule in rules)]
    monkeypatch.setattr(ShadingPuzzle, "solve", lambda *a, **k: pytest.fail("Propagation must not consult the solver"))
    for partial in product((None, 0, 1), repeat=4):
        answers = [bits for bits in boards if all(value is None or bits[i] == value for i, value in enumerate(partial))]
        if not answers:
            continue
        clues = [(Cell(i//2, i % 2), value) for i, value in enumerate(partial) if value is not None]
        trace = deduction._propagate(recipe, clues)
        _replay_and_prove(recipe, clues, trace)
        for step in trace["steps"]:
            r, c = step["cell"]
            assert {bits[r*2+c] for bits in answers} == {step["value"]}


@pytest.mark.parametrize("kind", ["row", "column"])
@pytest.mark.parametrize("count", [0, 1, 2])
def test_count_clues_and_partial_cells_are_sound(kind, count):
    recipe = ShadingRecipe(2, 2, (), ("cell", "row-count", "column-count"))
    count_clue = RowCountClue(0, count) if kind == "row" else ColumnCountClue(0, count)
    for partial in product((None, 0, 1), repeat=4):
        clues = [count_clue] + [(Cell(i//2, i % 2), value) for i, value in enumerate(partial) if value is not None]
        answers = [bits for bits in product((0, 1), repeat=4)
                   if set(clues) <= set(oracle.full_clues(recipe, bits))]
        if answers:
            trace = deduction._propagate(recipe, clues)
            _replay_and_prove(recipe, clues, trace)


@pytest.mark.parametrize("name,status,remaining", [("solved", "solved", 0), ("stalled", "stalled", 6)])
def test_examples_separate_unique_answers_from_supported_deductions(name, status, remaining):
    data = _load(name)
    before = deepcopy(data)
    report = deduction.explain_puzzle(data)
    recipe, clues, answer = display._read_record(data)
    assert report["status"] == status and len(report["unresolved_cells"]) == remaining
    assert report["artifact_verification"] == {"valid": True, "unique": True, "irreducible": True, "clue_count": len(clues)}
    _replay_and_prove(recipe, clues, report)
    independent = [bits for bits in product((0, 1), repeat=recipe.rows*recipe.cols)
                   if all(oracle.accepts(rule, bits, recipe.rows, recipe.cols) for rule in recipe.rules)
                   and set(clues) <= set(oracle.full_clues(recipe, bits))]
    assert independent == [tuple(v for row in answer for v in row)]
    puzzle = recipe.build_from_clues(clues)
    solution = puzzle.solve(seed=0)
    assert solution is not None
    puzzle.add(at_least_one(puzzle.black[c] != solution.value(puzzle.black[c]) for c in puzzle.board.cells))
    assert puzzle.solve(seed=0) is None
    assert data == before
    if status == "stalled":
        assert report["cells"] == [[None, 0, None]] * 3
        assert report["rules_without_deductions"] == []  # Incomplete even with supported rule types.
        assert "solution" not in report
        assert "no guesses" in deduction.explain(report)


def test_unimplemented_connectivity_is_reported_and_cannot_fill_a_unique_cell():
    data = {"format": display.FORMAT, "rows": 1, "cols": 1,
            "rules": [{"type": "connected-white", "nonempty": True}], "clues": [], "solution": [[0]]}
    report = deduction.explain_puzzle(data)
    assert report["artifact_verification"]["unique"] is True
    assert report["status"] == "stalled" and report["cells"] == [[None]] and report["steps"] == []
    assert report["rules_without_deductions"] == [1]


@pytest.mark.parametrize("damage", ["wrong-answer", "ambiguous", "contradictory", "redundant", "unknown-field", "recipe"])
def test_invalid_artifacts_never_start_a_trace(damage, monkeypatch):
    data = _load("solved")
    if damage == "wrong-answer":
        data["solution"][0][0] = 0
    elif damage == "ambiguous":
        data["clues"] = []
    elif damage == "contradictory":
        data["clues"].append({"type": "cell", "row": 1, "col": 1, "value": 0})
    elif damage == "redundant":
        data["clues"].append(deepcopy(data["clues"][0]))
    elif damage == "unknown-field":
        data["extra"] = True
    else:
        data["format"] = "puzzle-box/shading-recipe-v1"
    monkeypatch.setattr(deduction, "_propagate", lambda *a: pytest.fail("Verify artifacts first"))
    with pytest.raises(ValueError):
        deduction.explain_puzzle(data)


def test_disagreement_is_an_error_not_a_guessed_correction(monkeypatch):
    monkeypatch.setattr(deduction, "_propagate", lambda *a: {"cells": [[0, None], [None, None]]})
    with pytest.raises(RuntimeError, match="disagrees"):
        deduction.explain_puzzle(_load("solved"))


@pytest.mark.parametrize("name,expected", [("solved", 0), ("stalled", 1)])
def test_cli_reports_honest_exit_status_and_preserves_source(tmp_path, name, expected):
    source = tmp_path / "puzzle.json"
    source.write_text(json.dumps(_load(name)))
    before = source.read_bytes()
    for flags in ([], ["--json"]):
        result = subprocess.run([sys.executable, str(EXAMPLES / "explain_shading.py"), str(source), *flags],
                                capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert result.returncode == expected, result.stderr
        if flags:
            assert json.loads(result.stdout)["status"] == ("solved" if expected == 0 else "stalled")
        else:
            assert "Solved by" in result.stdout if expected == 0 else "Unresolved: 6 cells" in result.stdout
    assert source.read_bytes() == before


@pytest.mark.parametrize("raw", ["{", '{"format":1,"format":2}', " " * 65537,
    json.dumps({"format": "puzzle-box/shading-v1", "rows": 2, "cols": 5, "rules": [], "clues": [], "solution": [[0]*5]*2})],
    ids=["malformed-json", "duplicate-key", "oversized-input", "oversized-board"])
def test_cli_rejects_malformed_or_out_of_scope_input_without_writing(tmp_path, raw):
    source = tmp_path / "bad.json"
    source.write_text(raw)
    before = source.read_bytes()
    result = subprocess.run([sys.executable, str(EXAMPLES / "explain_shading.py"), str(source)],
                            capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert result.returncode == 2 and not result.stdout
    assert source.read_bytes() == before
