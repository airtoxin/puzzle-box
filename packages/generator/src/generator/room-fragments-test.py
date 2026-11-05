"""Fixed partitions, independent room semantics, and end-to-end interchange."""

from dataclasses import fields
import importlib
from itertools import permutations, product
from pathlib import Path
from typing import Any

import pytest

from generator import generate, with_constraints
from puzzle import Puzzle, at_least_one
from puzzle_defs import (BlackDominoes, ConnectedBlack, LineBlackCount, NonTouchingBlack,
                         RoomBlackCount, RoomConnectedBlack, ShadingRecipe)
from puzzle_defs.room_layout import DEFAULT_ROOMS, room_map

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    oracle = importlib.import_module("analyze_shading")
    codec = importlib.import_module("shading_recipe")
    saved = importlib.import_module("generate_shading")
    composed = importlib.import_module("composed_shading_recipe")
    composed_saved = importlib.import_module("generate_composed_shading")
    finite = importlib.import_module("finite_shading")
    deductions = importlib.import_module("explain_shading")
    api = importlib.import_module("web_catalog")
    worker = importlib.import_module("web_worker")
    checks = importlib.import_module("web_answers")

STRIPES = ((0, 0, 0), (1, 1, 1))


def all_answers(recipe):
    puzzle = recipe.create_empty()
    answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(puzzle.black[c] != solution.value(puzzle.black[c]) for c in puzzle.board.cells))
    return answers


@pytest.mark.parametrize("layout", [((0,),), ((0, 0, 0),), DEFAULT_ROOMS, STRIPES, ((0, 0, 0), (0, 1, 0))])
@pytest.mark.parametrize("kind,parameter", [(RoomBlackCount, 0), (RoomBlackCount, 2),
                                           (RoomConnectedBlack, True), (RoomConnectedBlack, False)])
def test_each_room_rule_matches_every_independent_small_board(layout, kind, parameter):
    rule = kind(layout, parameter)
    rows, cols = len(layout), len(layout[0])
    if kind is RoomBlackCount and parameter > rows * cols:
        with pytest.raises(ValueError, match="board area"):
            ShadingRecipe(rows, cols, (rule,)).create_empty()
        return
    expected = {bits for bits in product((0, 1), repeat=rows*cols) if oracle.accepts(rule, bits, rows, cols)}
    assert all_answers(ShadingRecipe(rows, cols, (rule,))) == expected


@pytest.mark.parametrize("rows,cols", [(1, 1), (1, 3), (2, 2), (2, 3), (3, 3)])
@pytest.mark.parametrize("count", [0, 1, 2])
def test_line_counts_match_finite_rows_and_columns(rows, cols, count):
    rule = LineBlackCount(count)
    if count > rows * cols:
        with pytest.raises(ValueError, match="board area"):
            ShadingRecipe(rows, cols, (rule,)).create_empty()
        return
    expected = {bits for bits in product((0, 1), repeat=rows*cols) if oracle.accepts(rule, bits, rows, cols)}
    assert all_answers(ShadingRecipe(rows, cols, (rule,))) == expected


def test_room_connection_cannot_use_a_path_outside_the_room():
    layout = ((0, 0, 0), (0, 1, 0))
    bits = (0, 0, 0, 1, 1, 1)
    assert oracle.accepts(ConnectedBlack(), bits, 2, 3)
    assert not oracle.accepts(RoomConnectedBlack(layout), bits, 2, 3)
    assert bits not in all_answers(ShadingRecipe(2, 3, (RoomConnectedBlack(layout),)))


def test_norinori_pairs_may_cross_rooms_and_extra_room_connectivity_changes_the_problem():
    rules = (RoomBlackCount(STRIPES, 2), BlackDominoes())
    assert all_answers(ShadingRecipe(2, 3, rules)) == {(1, 0, 1, 1, 0, 1)}
    assert not all_answers(ShadingRecipe(2, 3, (*rules, RoomConnectedBlack(STRIPES))))


@pytest.mark.parametrize("layout", [[], {}, [[]], [[0], [0, 1]], [[True]], [[0.0]], [[-1]], [[1]],
                                    [[0, 1], [1, 0]], [[0, 1, 0]]])
def test_invalid_or_disconnected_partitions_fail_explicitly(layout):
    with pytest.raises(ValueError): room_map(layout)


def test_room_labels_are_canonical_immutable_and_not_answer_variables():
    raw: Any = [[5, 5, 3], [5, 3, 3]]
    rule = RoomBlackCount(raw, 2)
    assert rule.rooms == DEFAULT_ROOMS and raw == [[5, 5, 3], [5, 3, 3]]
    raw[0][0] = 4
    assert rule.rooms == DEFAULT_ROOMS
    puzzle = ShadingRecipe(2, 3, (rule,)).create_empty()
    assert puzzle.solution_vars is not None
    assert {id(v) for v in puzzle.solution_vars} == {id(puzzle.black[c]) for c in puzzle.board.cells}
    with pytest.raises(ValueError, match="dimensions"):
        ShadingRecipe(3, 2, (rule,)).create_empty()


@pytest.mark.parametrize("rule", [RoomBlackCount(DEFAULT_ROOMS), RoomConnectedBlack(DEFAULT_ROOMS), LineBlackCount()])
def test_closed_codecs_and_ui_declarations_preserve_rules(rule):
    record = codec.rule_record(rule)
    assert codec.read_rule(record) == rule
    assert {p.name for p in rule.ui.parameters} == {f.name for f in fields(rule)}
    with pytest.raises(ValueError): codec.read_rule({**record, "import": "payload"})
    subtype = type("ChangedMeaning", (type(rule),), {})
    changed = subtype(DEFAULT_ROOMS) if hasattr(rule, "rooms") else subtype()
    with pytest.raises(ValueError, match="exact built-in"): codec.rule_record(changed)


@pytest.mark.parametrize("record", [
    {"type": "room-black-count", "rooms": {}, "count": 2},
    {"type": "room-black-count", "rooms": [[0]], "count": True},
    {"type": "room-connected-black", "rooms": [[0]], "nonempty": 1},
    {"type": "line-black-count", "count": -1},
])
def test_invalid_rule_parameters_are_not_coerced(record):
    with pytest.raises(ValueError): codec.read_rule(record)


@pytest.mark.parametrize("rule", [RoomBlackCount(DEFAULT_ROOMS, 2**100), LineBlackCount(2**100)])
def test_oversized_counts_fail_before_encoding_and_cannot_be_exported(rule):
    recipe = ShadingRecipe(2, 3, (rule,))
    with pytest.raises(ValueError, match="board area"): recipe.create_empty()
    with pytest.raises(ValueError, match="board area"): codec.recipe_record(recipe)
    with pytest.raises(ValueError): api.read_request(request(recipe))


def test_conflicting_room_drawings_are_rejected_before_solve(monkeypatch):
    recipe = ShadingRecipe(2, 3, (RoomBlackCount(DEFAULT_ROOMS), RoomConnectedBlack(STRIPES)))
    monkeypatch.setattr(Puzzle, "solve", lambda *a, **k: pytest.fail("Reject conflicting drawings before solving"))
    with pytest.raises(ValueError, match="same partition"): codec.recipe_record(recipe)
    with pytest.raises(ValueError, match="same partition"): saved.puzzle_record(recipe, [], seed=0)
    data = {"format": saved.FORMAT, "rows": 2, "cols": 3, "rules": [codec.rule_record(r) for r in recipe.rules],
            "clues": [], "solution": [[0, 0, 0], [0, 0, 0]]}
    with pytest.raises(ValueError, match="same partition"): saved.verify(data)


def request(recipe):
    return {"format": api.PROFILE_FORMAT, "family": "shading", "rows": recipe.rows, "cols": recipe.cols,
            "rules": [{"id": (record := codec.rule_record(rule))["type"],
                       "parameters": {k: v for k, v in record.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds": list(recipe.clue_kinds), "seed": 0, "budget_seconds": 10}


def test_two_room_rules_share_one_canonical_plan_and_disagreement_is_rejected():
    recipe = ShadingRecipe(2, 3, (RoomBlackCount(DEFAULT_ROOMS), RoomConnectedBlack(DEFAULT_ROOMS)))
    data = request(recipe); data["rules"][1]["parameters"]["rooms"] = [[5, 5, 3], [5, 3, 3]]
    plan = api.read_request(data).plan
    assert plan["rooms"] == [[0, 0, 1], [0, 1, 1]]
    assert [c["name"] for c in plan["requirements"]["channels"]].count("rooms") == 1
    data["rules"][1]["parameters"]["rooms"] = [list(row) for row in STRIPES]
    with pytest.raises(ValueError, match="same partition"): api.read_request(data)
    for family in ("slitherlink", "coupled"):
        with pytest.raises(ValueError): api.read_request({**data, "family": family})


@pytest.mark.parametrize("layout", [{}, [[0]], [[0, 1, 0], [0, 1, 0]], [[False]*3]*2, [list(range(10))]*2])
def test_web_rejects_invalid_matrix_before_worker(layout):
    data = request(ShadingRecipe(2, 3, (RoomBlackCount(DEFAULT_ROOMS),)))
    data["rules"][0]["parameters"]["rooms"] = layout
    with pytest.raises(ValueError): api.read_request(data)


def test_generation_saved_display_composed_display_and_answer_check_keep_rooms():
    recipe = ShadingRecipe(2, 3, (RoomBlackCount(STRIPES), BlackDominoes()))
    result = worker.generate_request(request(recipe))
    assert result == worker.generate_request(request(recipe)) and result["status"] == "ok"
    assert result["clues"] == [] and saved.verify(result["record"])["unique"]
    assert "0 0 0\n1 1 1" in saved.show(result["record"])
    trace = deductions.explain_puzzle(result["record"])
    assert trace["status"] == "stalled" and trace["rules_without_deductions"] == [1, 2]
    assert checks.check_answer({"format": checks.FORMAT, "request": result["request"], "clues": [],
                               "answer": [1, 0, 1, 1, 0, 1]}) == {"status": "ok", "correct": True}
    assert checks.check_answer({"format": checks.FORMAT, "request": result["request"], "clues": [],
                               "answer": [0]*6}) == {"status": "ok", "correct": False}
    configured = with_constraints(recipe, composed.CellCount("black", 4))
    record = composed_saved.generate_record(composed.recipe_record(configured), seed=0)
    assert "0 0 0\n1 1 1" in composed_saved.show(record)


STAR_ROOMS = ((0, 0, 1, 1), (1, 1, 1, 1), (2, 2, 2, 2), (3, 3, 3, 3))


def test_one_star_example_matches_independent_permutations_and_needs_no_cell_clues():
    expected = set()
    # Exactly one per line means a column permutation. Reject adjacent stars,
    # then count the fixed-room labels, without the DSL or production oracle.
    for columns in permutations(range(4)):
        if any(abs(columns[r]-columns[r+1]) <= 1 for r in range(3)): continue
        if sorted(STAR_ROOMS[r][c] for r, c in enumerate(columns)) != [0, 1, 2, 3]: continue
        expected.add(tuple(int(c == columns[r]) for r in range(4) for c in range(4)))
    recipe = ShadingRecipe(4, 4, (LineBlackCount(1), RoomBlackCount(STAR_ROOMS, 1), NonTouchingBlack(True)))
    assert len(expected) == 1 and all_answers(recipe) == expected
    clues = generate(recipe, seed=0)
    assert clues == [] and saved.verify(saved.puzzle_record(recipe, clues, seed=0))["unique"]
    assert api.read_request(request(recipe)).recipe == recipe


@pytest.mark.parametrize("name", ["norinori", "room-connection", "star"])
def test_documented_room_recipes_generate_round_trip_and_preserve_fixed_geometry(name):
    recipe = codec.load_recipe(EXAMPLES / f"shading-{name}-recipe.json")
    clues = generate(recipe, seed=0)
    record = saved.puzzle_record(recipe, clues, seed=0)
    assert saved.verify(record)["unique"]
    assert codec.read_recipe(codec.recipe_record(recipe)) == recipe
    layout = codec.shared_rooms(recipe)
    assert layout is not None
    assert "\n".join(" ".join(map(str, row)) for row in layout) in saved.show(record)
