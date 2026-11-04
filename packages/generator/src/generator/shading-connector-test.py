"""Prove white-connector steps with exhaustive assignments and independent reachability."""

import importlib
from itertools import product
import json
from pathlib import Path
import subprocess
import sys

import pytest

from puzzle import Cell, at_least_one
from puzzle_defs import ConnectedWhite, ShadingPuzzle, ShadingRecipe

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    deduction = importlib.import_module("explain_shading")
    oracle = importlib.import_module("analyze_shading")
    display = importlib.import_module("generate_shading")


def _prove_cut(cells, known, candidate, witness):
    # Independently compute transitive closure, not the implementation's graph walk.
    allowed = sorted(c for c in cells if known.get(c) != 1 and c != candidate)
    links = [[a == b or abs(a[0]-b[0])+abs(a[1]-b[1]) == 1 for b in allowed] for a in allowed]
    for k in range(len(allowed)):
        for i in range(len(allowed)):
            for j in range(len(allowed)):
                links[i][j] |= links[i][k] and links[k][j]
    a, b = map(tuple, witness["terminals"])
    assert known[a] == known[b] == 0 and candidate not in known
    assert not links[allowed.index(a)][allowed.index(b)]
    reached = {c for j, c in enumerate(allowed) if links[allowed.index(a)][j]}
    assert reached == set(map(tuple, witness["reachable_without_cell"]))
    # Restoring the candidate must give the known white terminals a possible path.
    # Soundness below is also checked against all satisfying assignments.


@pytest.mark.parametrize("rows,cols", [(1, 3), (3, 1), (2, 2), (2, 3), (3, 2)])
@pytest.mark.parametrize("nonempty", [False, True])
def test_every_feasible_partial_board_has_sound_connector_certificates(rows, cols, nonempty, monkeypatch):
    rule = ConnectedWhite(nonempty)
    recipe = ShadingRecipe(rows, cols, (rule,))
    cells = [(r, c) for r in range(rows) for c in range(cols)]
    boards = [bits for bits in product((0, 1), repeat=len(cells)) if oracle.accepts(rule, bits, rows, cols)]
    monkeypatch.setattr(ShadingPuzzle, "solve", lambda *a, **k: pytest.fail("Do not consult a solver for deductions"))
    for partial in product((None, 0, 1), repeat=len(cells)):
        answers = [bits for bits in boards if all(v is None or bits[i] == v for i, v in enumerate(partial))]
        if not answers:
            continue
        known = {c: partial[i] for i, c in enumerate(cells) if partial[i] is not None}
        clues = [(Cell(*c), value) for c, value in known.items()]
        origins = {tuple((c.row, c.col)): {"kind": "given", "index": i} for i, (c, _) in enumerate(clues, 1)}
        trace = deduction._propagate(recipe, clues)
        for number, step in enumerate(trace["steps"], 1):
            candidate = tuple(step["cell"])
            assert step["technique"] == "white-connector" and step["value"] == 0
            assert step["constraint"] == {"kind": "connected-white", "scope": [list(c) for c in cells],
                                           "source": {"kind": "rule", "index": 1}, "target": None}
            assert step["premises"] == [{"cell": list(c), "value": known[c], "origin": origins[c]} for c in cells if c in known]
            assert step["unknown_cells"] == [list(c) for c in cells if c not in known]
            _prove_cut(cells, known, candidate, step["connectivity_witness"])
            # All answers satisfying ONLY the cited connectivity rule and the known
            # premises agree. No other puzzle rules, hints, or saved answer are used.
            consistent = [bits for bits in boards if all(bits[cells.index(c)] == value for c, value in known.items())]
            assert consistent and {bits[cells.index(candidate)] for bits in consistent} == {0}
            known[candidate] = 0
            origins[candidate] = {"kind": "step", "index": number}
        assert trace["cells"] == [[known.get((r, c)) for c in range(cols)] for r in range(rows)]


def test_alternative_paths_or_a_single_white_terminal_do_not_force_a_cell():
    square = [(0, 0), (0, 1), (1, 0), (1, 1)]
    assert deduction._white_connector(square, {(0, 0): 0, (1, 1): 0}) is None
    assert deduction._white_connector(square, {(0, 0): 0, (1, 0): 1}) is None
    assert deduction._white_connector(square, {}) is None
    with pytest.raises(ValueError, match="no possible orthogonal connection"):
        deduction._white_connector(square, {(0, 0): 0, (1, 1): 0, (0, 1): 1, (1, 0): 1})


def test_one_row_and_one_column_witnesses_are_axis_correct():
    for cells, known, middle in [([(0, c) for c in range(3)], {(0, 0): 0, (0, 2): 0}, (0, 1)),
                                 ([(r, 0) for r in range(3)], {(0, 0): 0, (2, 0): 0}, (1, 0))]:
        found = deduction._white_connector(cells, known)
        assert found is not None and found[0] == middle
        _prove_cut(cells, known, *found)


def test_saved_example_replays_the_cut_and_has_one_projected_dsl_answer():
    data = json.loads((EXAMPLES / "shading-connector-sample.json").read_text())
    report = deduction.explain_puzzle(data)
    assert report["status"] == "solved"
    assert [step["cell"] for step in report["steps"]] == [[0, 1], [0, 2]]
    assert all(step["technique"] == "white-connector" for step in report["steps"])
    recipe, clues, answer = display._read_record(data)
    puzzle = recipe.build_from_clues(clues)
    solution = puzzle.solve(seed=0)
    assert solution is not None and puzzle.result(solution) == answer
    puzzle.add(at_least_one(puzzle.black[c] != solution.value(puzzle.black[c]) for c in puzzle.board.cells))
    assert puzzle.solve(seed=0) is None
    # Check this generated fixture with the independent complete-board predicate too.
    valid = [bits for bits in product((0, 1), repeat=6)
             if all(oracle.accepts(r, bits, 2, 3) for r in recipe.rules)
             and set(clues) <= set(oracle.full_clues(recipe, bits))]
    assert valid == [tuple(v for row in answer for v in row)]


def test_connectivity_is_never_invented_for_a_recipe_without_that_rule():
    clues = [(Cell(0, 0), 0), (Cell(0, 2), 0)]
    trace = deduction._propagate(ShadingRecipe(1, 3, ()), clues)
    assert trace["cells"] == [[0, None, 0]] and trace["steps"] == []


def test_new_connector_deductions_can_still_leave_a_unique_puzzle_unresolved():
    data = {"format": display.FORMAT, "rows": 3, "cols": 3,
            "rules": [{"type": "count", "count": 3}, {"type": "non-touching", "diagonal": False},
                      {"type": "connected-white", "nonempty": True}, {"type": "no-white-2x2"}],
            "clues": [[0, 1, 1]], "solution": [[0, 1, 0], [0, 0, 0], [1, 0, 1]]}
    report = deduction.explain_puzzle(data)
    assert report["status"] == "stalled" and len(report["unresolved_cells"]) == 3
    assert sum(step["technique"] == "white-connector" for step in report["steps"]) == 2
    assert any(v is None for row in report["cells"] for v in row)
    known = {(0, 1): 1}
    cells = [(r, c) for r in range(3) for c in range(3)]
    for step in report["steps"]:
        cell = tuple(step["cell"])
        if step["technique"] == "white-connector":
            _prove_cut(cells, known, cell, step["connectivity_witness"])
            allowed = [bits for bits in product((0, 1), repeat=9)
                       if oracle.accepts(ConnectedWhite(), bits, 3, 3)
                       and all(bits[cells.index(c)] == value for c, value in known.items())]
            assert allowed and {bits[cells.index(cell)] for bits in allowed} == {0}
        known[cell] = step["value"]


def test_cli_exposes_replayable_witness_and_keeps_source_bytes(tmp_path):
    source = tmp_path / "puzzle.json"
    raw = (EXAMPLES / "shading-connector-sample.json").read_bytes()
    source.write_bytes(raw)
    for flags in ([], ["--json"]):
        p = subprocess.run([sys.executable, str(EXAMPLES / "explain_shading.py"), str(source), *flags],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert p.returncode == 0, p.stderr
        if flags:
            assert len(json.loads(p.stdout)["steps"]) == 2
        else:
            assert "Connectivity witness:" in p.stdout and "reachable_without_cell" in p.stdout
    assert source.read_bytes() == raw
