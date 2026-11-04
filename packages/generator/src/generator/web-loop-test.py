"""Loop UI compatibility, finite evidence, and untrusted answer boundaries."""

from copy import deepcopy
from dataclasses import fields
import importlib
from itertools import product
from pathlib import Path

import pytest
from puzzle import Cell, Edge, Puzzle, Vertex
from puzzle_defs import SlitherlinkRecipe, ShadingRecipe
from puzzle_defs.ui import UiParameter, merge_requirements

with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(Path(__file__).resolve().parents[4] / "examples"))
    api = importlib.import_module("web_catalog")
    worker = importlib.import_module("web_worker")
    loop = importlib.import_module("web_loop")
    checks = importlib.import_module("web_answers")
    saved = importlib.import_module("generate_slitherlink")


def request():
    return {"format": api.PROFILE_FORMAT, "family": "slitherlink", "rows": 2, "cols": 2,
            "rules": [{"id": "single-loop", "parameters": {}}, {"id": "loop-length", "parameters": {"length": 8}}],
            "clue_kinds": ["cell-count", "edge"], "seed": 2, "budget_seconds": 10}


def test_existing_recipe_declares_required_and_optional_rules_without_dataclass_changes():
    assert {f.name for f in fields(SlitherlinkRecipe)} == {"rows", "cols", "loop_length", "clue_kinds"}
    assert [r.required for r in SlitherlinkRecipe.rule_ui] == [True, False]
    full = api.read_request(request()).plan
    assert {c["kind"] for c in full["requirements"]["channels"]} == set(api.LOOP_RENDERERS.values())
    fewer = api.read_request({**request(), "clue_kinds": ["cell-count"]}).plan
    assert {c["name"] for c in fewer["requirements"]["channels"]} == {"answer", "cell-counts"}
    with pytest.raises(ValueError, match="Conflicting"):
        merge_requirements([ShadingRecipe.ui, SlitherlinkRecipe.ui], supported=api.LOOP_RENDERERS)
    with pytest.raises(ValueError, match="edge bound"):
        UiParameter("n", "n", "integer", 4, maximum="edges").validate(4, area=4)


@pytest.mark.parametrize("field,value", [
    ("family", "yajilin"), ("family", {}), ("rows", 3), ("rules", []),
    ("rules", [{"id": "count", "parameters": {"count": 2}}]),
    ("rules", [{"id": "single-loop", "parameters": {"module": "os"}}]),
    ("clue_kinds", ["cell"]), ("clue_kinds", ["edge", "edge"]),
    ("clue_kinds", {}), ("requirements", {}),
])
def test_unknown_or_mixed_profiles_and_unsupported_requirements_are_rejected(field, value):
    with pytest.raises(ValueError): api.read_request({**request(), field: value})


@pytest.mark.parametrize("value", [True, 13, -1, "8"])
def test_loop_length_uses_actual_edge_bound_and_strict_integer(value):
    data = request(); data["rules"][1]["parameters"]["length"] = value
    with pytest.raises(ValueError): api.read_request(data)


def face_boundaries(rows, cols):
    # Independent oracle: on these grids (<=2x2 or a strip), a connected
    # nonempty subset of faces has one boundary and cannot contain a hole.
    cells = [Cell(r, c) for r in range(rows) for c in range(cols)]
    result = set()
    for bits in product((0, 1), repeat=len(cells)):
        selected = {c for c, bit in zip(cells, bits) if bit}
        if not selected: continue
        seen, todo = set(), [next(iter(selected))]
        while todo:
            cell = todo.pop()
            if cell in seen: continue
            seen.add(cell)
            todo.extend(c for c in selected if abs(c.row-cell.row)+abs(c.col-cell.col) == 1)
        if seen != selected: continue
        boundary = set()
        for r, c in selected:
            boundary.symmetric_difference_update({Edge(Vertex(r,c),Vertex(r,c+1)), Edge(Vertex(r+1,c),Vertex(r+1,c+1)),
                                                  Edge(Vertex(r,c),Vertex(r+1,c)), Edge(Vertex(r,c+1),Vertex(r+1,c+1))})
        result.add(frozenset(boundary))
    return result


@pytest.mark.parametrize("rows,cols,total", [(2, 2, 13), (1, 4, 10), (4, 1, 10)])
def test_edge_subsets_agree_with_independent_connected_face_boundaries(rows, cols, total):
    _, answers = loop.completions(SlitherlinkRecipe(rows, cols))
    assert len(answers) == total and set(answers) == face_boundaries(rows, cols)


@pytest.mark.parametrize("hints", [["cell-count"], ["edge"], ["cell-count", "edge"]])
def test_generated_loop_is_repeatable_unique_irreducible_and_cli_compatible(hints):
    data = {**request(), "clue_kinds": hints}; before = deepcopy(data)
    result = worker.generate_request(data)
    assert result == worker.generate_request(data) and data == before and result["status"] == "ok"
    assert saved.verify(result["record"])["irreducible"]
    recipe = api.read_request(data).recipe
    clues = [saved.read_clue(c) for c in result["clues"]]
    answers = [a for a in face_boundaries(2, 2) if len(a) == 8]
    matches = lambda hints: [a for a in answers if set(hints) <= set(loop.full_clues(recipe, a))]
    expected = frozenset(saved.read_edge(e) for e in result["record"]["solution"])
    assert matches(clues) == [expected]
    for i in range(len(clues)): assert len(matches(clues[:i]+clues[i+1:])) > 1
    assert result["evidence"]["enumerated_boards"] == 4096


def test_zero_odd_length_and_insufficient_hint_sets_are_proved_distinct():
    for length in (0, 5):
        data = request(); data["rules"][1]["parameters"]["length"] = length
        assert worker.generate_request(data)["status"] == "unsatisfiable"
    assert worker.generate_request({**request(), "clue_kinds": []})["status"] == "insufficient_hints"


def test_server_checks_rules_and_hints_without_trusting_a_stored_solution():
    result = worker.generate_request(request())
    data = {"format": checks.FORMAT, "request": request(), "clues": result["clues"],
            "answer": [int(e in result["record"]["solution"]) for e in result["edges"]]}
    assert checks.check_answer(data) == {"status": "ok", "correct": True}
    assert checks.check_answer({**data, "answer": [0]*12}) == {"status": "ok", "correct": False}
    alternate = next(a for a in face_boundaries(2, 2) if len(a) == 8 and a != frozenset(saved.read_edge(e) for e in result["record"]["solution"]))
    assert checks.check_answer({**data, "answer": [int(saved.read_edge(e) in alternate) for e in result["edges"]]})["correct"] is False
    for damaged in ({**data, "solution": []}, {**data, "answer": [True]*12}, {**data, "answer": [0]*11},
                    {**data, "clues": [{"type": "edge", "edge": [0,0,1,1], "used": 1}]},
                    {**data, "clues": [{"type": "cell-count", "row": 9, "col": 0, "count": 2}]},
                    {**data, "clues": result["clues"]*2}):
        with pytest.raises(ValueError): checks.read_check(damaged)


def test_solver_nonconfirmation_does_not_mark_a_valid_answer_wrong(monkeypatch):
    data = request(); data.update(rows=1, cols=1, rules=[data["rules"][0]], clue_kinds=[])
    candidate = {"format": checks.FORMAT, "request": data, "clues": [], "answer": [1]*4}
    monkeypatch.setattr(Puzzle, "solve", lambda *args, **kwargs: None)
    assert checks.check_answer(candidate) == {"status": "unconfirmed"}
