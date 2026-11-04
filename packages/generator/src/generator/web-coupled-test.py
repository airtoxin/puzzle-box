"""Joint Web answers, distinct edge topology, and independent small-board evidence."""

from copy import deepcopy
from dataclasses import fields, replace
import importlib
from itertools import product
from pathlib import Path

import pytest
from puzzle import Cell, Edge, Puzzle, Vertex, at_least_one
from puzzle_defs import BlackCellClue, BlackCount, EdgeStateClue, ShadingRecipe, SlitherlinkRecipe, YajilinAnswer, YajilinRecipe
from puzzle_defs.ui import UiRequirements, merge_requirements

with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(Path(__file__).resolve().parents[4] / "examples"))
    api = importlib.import_module("web_catalog")
    worker = importlib.import_module("web_worker")
    coupled = importlib.import_module("web_coupled")
    checks = importlib.import_module("web_answers")
    saved = importlib.import_module("generate_yajilin")


def request():
    return {"format": api.PROFILE_FORMAT, "family": "coupled", "rows": 3, "cols": 3,
            "rules": [{"id": r.identifier, "parameters": {}} for r in YajilinRecipe.rule_ui],
            "clue_kinds": ["black", "edge"], "seed": 0, "budget_seconds": 10}


def test_ui_merges_two_answer_channels_without_confusing_corner_and_center_edges():
    assert {f.name for f in fields(YajilinRecipe)} == {"rows", "cols", "arrow_sites", "clue_kinds"}
    assert {f.name for f in fields(BlackCellClue)} == {"cell", "black"}
    assert all(r.required for r in YajilinRecipe.rule_ui)
    plan = api.read_request(request()).plan
    assert plan["requirements"]["topology"] == "rectangular-cell-centers"
    assert {c["name"]: c["kind"] for c in plan["requirements"]["channels"]} == api.COUPLED_RENDERERS
    fewer = api.read_request({**request(), "clue_kinds": []}).plan
    assert {c["name"] for c in fewer["requirements"]["channels"]} == {"answer-cells", "answer-edges"}
    for requirements in ([SlitherlinkRecipe.ui, YajilinRecipe.ui], [YajilinRecipe.ui]):
        with pytest.raises(ValueError, match="topolog"):
            merge_requirements(requirements, supported=api.COUPLED_RENDERERS)
    merged = merge_requirements([UiRequirements(min_rows=2), UiRequirements(min_cols=3, max_cells=6)],
                                supported=api.RENDERERS)
    assert (merged.min_rows, merged.min_cols, merged.max_cells) == (2, 3, 6)
    with pytest.raises(ValueError, match="dimension"):
        merge_requirements([replace(merged, min_rows=3)], supported=api.RENDERERS)
    with pytest.raises(ValueError, match="positive"):
        merge_requirements([UiRequirements(min_cols=True)], supported=api.RENDERERS)


@pytest.mark.parametrize("field,value", [
    ("rows", 1), ("cols", True), ("rows", 4), ("rules", []), ("rules", {}),
    ("rules", [{"id": "count", "parameters": {}}]*3), ("clue_kinds", ["arrow"]),
    ("clue_kinds", ["black", "black"]), ("clue_kinds", {}), ("arrow_sites", []),
    ("requirements", {"topology": "rectangular-cells"}), ("module", "payload"),
])
def test_unsupported_shapes_rules_hints_and_untrusted_ui_are_rejected(field, value):
    with pytest.raises(ValueError): api.read_request({**request(), field: value})


def test_no_rule_is_optional_and_parameters_cannot_extend_the_fixed_profile():
    for i in range(3):
        data = request(); data["rules"].pop(i)
        with pytest.raises(ValueError): api.read_request(data)
    for params in ({"enabled": False}, [], None):
        data = request(); data["rules"][0]["parameters"] = params
        with pytest.raises(ValueError): api.read_request(data)
    data = request(); data["rules"][1] = data["rules"][0]
    with pytest.raises(ValueError): api.read_request(data)


def test_real_cell_and_edge_declarations_do_not_imply_cross_profile_compatibility():
    # The shared word "answer" does not make black cells and corner edges equal.
    with pytest.raises(ValueError, match="Conflicting UI channel"):
        merge_requirements([ShadingRecipe.ui, SlitherlinkRecipe.ui], supported=api.RENDERERS)
    # Even known cell-count rules and fixed-edge hints need an explicit binding
    # to cell centers, plus matching generation/serialization semantics.
    for declaration in (BlackCount.ui.requirements, EdgeStateClue.ui.requirements):
        with pytest.raises(ValueError, match="topolog"):
            merge_requirements([YajilinRecipe.ui, declaration], supported=api.COUPLED_RENDERERS,
                               supported_topology=YajilinRecipe.ui.topology)
    for identifier, parameters in (("count", {"count": 1}), ("single-loop", {}),
                                    ("loop-length", {"length": 8})):
        data = request(); data["rules"][0] = {"id": identifier, "parameters": parameters}
        with pytest.raises(ValueError, match="Unknown"):
            api.read_request(data)
    # Known hints from the corner-edge profile cannot be reinterpreted as
    # counts around a cell in the center-edge profile.
    with pytest.raises(ValueError): api.read_request({**request(), "clue_kinds": ["cell-count"]})


def independent_answers(rows, cols):
    # Different enumeration: boundaries of connected face subsets, then every
    # black-cell assignment. On these <=2x2/strip face grids no hole can occur.
    faces = [Cell(r, c) for r in range(rows-1) for c in range(cols-1)]
    cells = [Cell(r, c) for r in range(rows) for c in range(cols)]
    answers = set()
    for flags in product((0, 1), repeat=len(faces)):
        selected = {c for c, bit in zip(faces, flags) if bit}
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
        degrees = {cell: sum(Vertex(*cell) in edge for edge in boundary) for cell in cells}
        for bits in product((0, 1), repeat=len(cells)):
            black = frozenset(c for c, bit in zip(cells, bits) if bit)
            if any(degrees[c] != (0 if c in black else 2) for c in cells): continue
            if any(Cell(c.row+dr, c.col+dc) in black for c in black for dr, dc in ((1,0),(0,1))): continue
            answers.add(YajilinAnswer(black, frozenset(boundary)))
    return answers


@pytest.mark.parametrize("rows,cols", [(2,2), (2,3), (3,2), (2,4), (4,2), (3,3)])
def test_every_supported_shape_matches_independent_joint_enumeration_and_dsl(rows, cols):
    recipe = YajilinRecipe(rows, cols, clue_kinds=("black", "edge"))
    cells, edges, finite = coupled.completions(recipe)
    assert set(finite) == independent_answers(rows, cols)
    puzzle = recipe.create_empty()
    variables = [puzzle.is_black[c] for c in cells] + [puzzle.edge_on[e] for e in edges]
    assert puzzle.solution_vars is not None
    assert {id(v) for v in puzzle.solution_vars} == {id(v) for v in variables}
    actual = set()
    for _ in range(len(finite)+1):
        solution = puzzle.solve(seed=0)
        if solution is None: break
        actual.add(recipe.answer(solution, puzzle))
        puzzle.add(at_least_one(v != solution.value(v) for v in variables))
    else: pytest.fail("DSL admits more joint answers than the independent oracle")
    assert actual == set(finite)
    if rows == cols == 3:
        assert {a.black_cells for a in finite} == {frozenset([Cell(r,c)]) for r,c in ((0,0),(0,2),(1,1),(2,0),(2,2))}


@pytest.mark.parametrize("hints", [["black"], ["edge"], ["black", "edge"]])
def test_generation_is_repeatable_joint_unique_irreducible_and_saved_cli_compatible(hints):
    data = {**request(), "clue_kinds": hints}; before = deepcopy(data)
    result = worker.generate_request(data)
    assert result == worker.generate_request(data) and data == before and result["status"] == "ok"
    assert saved.verify(result["record"])["irreducible"]
    recipe, clues, answer = saved.read_record(result["record"])
    cells, edges, _ = coupled.completions(recipe)
    matches = lambda hints: [a for a in independent_answers(3,3) if set(hints) <= set(coupled.full_clues(recipe, a, cells, edges))]
    assert matches(clues) == [answer]
    for i in range(len(clues)): assert len(matches(clues[:i]+clues[i+1:])) > 1
    assert result["evidence"] == {"enumerated_boards": 4096, "completion_count": 5, "unique": True, "irreducible": True}


def test_insufficient_hints_and_the_degenerate_unique_two_by_two():
    assert worker.generate_request({**request(), "clue_kinds": []})["status"] == "insufficient_hints"
    result = worker.generate_request({**request(), "rows": 2, "cols": 2, "clue_kinds": []})
    assert result["status"] == "ok" and result["clues"] == []
    assert saved.verify(result["record"])["unique"]


def candidate(result):
    return {"format": checks.JOINT_FORMAT, "request": result["request"], "clues": result["clues"],
            "answer": {"cells": [int(c in result["record"]["solution"]["black_cells"]) for c in result["cells"]],
                       "edges": [int(e in result["record"]["solution"]["loop_edges"]) for e in result["edges"]]}}


def test_check_requires_both_channels_and_checks_hints_instead_of_trusting_an_answer():
    result = worker.generate_request(request()); data = candidate(result)
    assert checks.check_answer(data) == {"status": "ok", "correct": True}
    for channel in ("cells", "edges"):
        changed = deepcopy(data); changed["answer"][channel][0] ^= 1
        assert checks.check_answer(changed) == {"status": "ok", "correct": False}
    other = next(a for a in independent_answers(3,3) if [list(c) for c in a.black_cells] != result["record"]["solution"]["black_cells"])
    changed = deepcopy(data)
    changed["answer"] = {"cells": [int(Cell(*c) in other.black_cells) for c in result["cells"]],
                         "edges": [int(Edge(Vertex(*e[:2]),Vertex(*e[2:])) in other.loop_edges) for e in result["edges"]]}
    assert checks.check_answer(changed) == {"status": "ok", "correct": False}
    assert checks.check_answer({**changed, "clues": []}) == {"status": "ok", "correct": True}
    for answer in (data["answer"]["cells"], {"cells": [0]*9}, {"cells": [0]*9, "edges": [0]*11},
                   {"cells": [True]*9, "edges": [0]*12}, {**data["answer"], "solution": []}):
        with pytest.raises(ValueError): checks.read_check({**data, "answer": answer})
    for damaged in ({**data, "format": checks.FORMAT}, {**data, "solution": []},
                    {**data, "clues": result["clues"]*2},
                    {**data, "clues": [{"type": "edge", "edge": [0,0,0,3], "used": 1}]},
                    {**data, "clues": [{"type": "black", "cell": [3,0], "black": 1}]},
                    {**data, "clues": [{"type": "arrow", "cell": [0,0], "count": 0}]}):
        with pytest.raises(ValueError): checks.read_check(damaged)


def test_solver_nonconfirmation_is_not_a_wrong_answer(monkeypatch):
    result = worker.generate_request({**request(), "rows": 2, "cols": 2, "clue_kinds": []})
    monkeypatch.setattr(Puzzle, "solve", lambda *args, **kwargs: None)
    assert checks.check_answer(candidate(result)) == {"status": "unconfirmed"}
