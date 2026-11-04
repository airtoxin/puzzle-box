"""Chained row representatives versus explicit per-room water-height choices."""

from dataclasses import replace
import importlib
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from puzzle import Cell, at_least_one, unique
from puzzle_defs import (BlackCount, ConnectedBlack, RoomBlackCount, RoomConnectedBlack,
                         RoomFillLevels, ShadingRecipe, UniformRooms)

EXAMPLES = Path(__file__).resolve().parents[4]/"examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    oracle = importlib.import_module("analyze_shading")
    codec = importlib.import_module("shading_recipe")
    saved = importlib.import_module("generate_shading")
    deductions = importlib.import_module("explain_shading")
    api = importlib.import_module("web_catalog")
    worker = importlib.import_module("web_worker")
    checks = importlib.import_module("web_answers")


def all_answers(recipe):
    puzzle = recipe.create_empty()
    answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(puzzle.black[c] != solution.value(puzzle.black[c]) for c in puzzle.board.cells))
    return answers


def height_reference(rooms, black):
    # Construct boards from all possible physical water heights; neither the
    # encoder's row-chain constraints nor the finite checker's implications.
    rows, cols = len(rooms), len(rooms[0])
    labels = sorted({n for row in rooms for n in row})
    return {tuple(int(black if r >= heights[rooms[r][c]] else not black)
                  for r in range(rows) for c in range(cols))
            for values in product(range(rows+1), repeat=len(labels))
            for heights in [dict(zip(labels, values))]}


@pytest.mark.parametrize("rooms", [((0,),), ((0,0,1),), ((0,),(0,),(0,)),
    ((0,0,1),(0,1,1)), ((0,1,2),(3,4,5)),
    ((0,1,0),(0,1,0),(0,0,0)), ((0,0,0),(0,1,0),(0,1,0))])
@pytest.mark.parametrize("black", [True, False])
def test_complete_boards_match_independent_height_choices(rooms, black):
    rows, cols = len(rooms), len(rooms[0])
    rule = RoomFillLevels(rooms, black)
    expected = height_reference(rule.rooms, black)
    assert all_answers(ShadingRecipe(rows,cols,(rule,))) == expected
    assert {b for b in product((0,1),repeat=rows*cols) if oracle.accepts(rule,b,rows,cols)} == expected


def fixed(rooms, black_cells, *extra):
    rows, cols = len(rooms), len(rooms[0])
    return ShadingRecipe(rows,cols,(RoomFillLevels(rooms),*extra)).build_from_clues(
        [(Cell(r,c),int((r,c) in black_cells)) for r in range(rows) for c in range(cols)])


def test_separated_segments_share_level_and_water_neither_floats_nor_needs_connectivity():
    u = ((0,1,0),(0,1,0),(0,0,0))
    # Filling just one arm at a height would pass vertical-only gravity.
    bottom = {(2,0),(2,1),(2,2)}
    assert fixed(u,bottom|{(1,0)}).solve() is None
    assert fixed(u,bottom|{(1,0),(1,2)}).solve() is not None
    assert fixed(u,{(0,1)}).solve() is None  # room 1 water cannot float
    assert fixed(u,{(1,1)}).solve() is not None  # room 0 may be empty
    cap = ((0,0,0),(0,1,0),(0,1,0))
    split = {(2,0),(2,2)}
    assert fixed(cap,split).solve() is not None
    assert fixed(cap,split,RoomConnectedBlack(cap,nonempty=False)).solve() is None
    for cells in [set(), {(r,c) for r in range(3) for c in range(3)}]:
        p = fixed(u,cells)
        assert p.solution_vars is not None and len(p.solution_vars) == 9
        p.add(unique())
        assert p.solve() is not None


@pytest.mark.parametrize("bad", [0,1,None,"black"])
def test_color_is_strict_boolean(bad):
    with pytest.raises(ValueError): RoomFillLevels(((0,),),bad)
    with pytest.raises(ValueError): codec.read_rule({"type":"room-fill-levels","rooms":[[0]],"black":bad})


@pytest.mark.parametrize("bad", [{},[],[[]],[[0],[1,2]],[[True]],[[1.0]],[[0,1],[1,0]]])
def test_rooms_are_strict_connected_partitions(bad):
    with pytest.raises(ValueError): RoomFillLevels(bad)
    with pytest.raises(ValueError): codec.read_rule({"type":"room-fill-levels","rooms":bad,"black":True})


def test_copy_normalization_codec_and_existing_room_contracts():
    raw: Any = [[4,4,1],[4,1,1]]
    rule = RoomFillLevels(raw)
    raw[0][0] = 0
    assert rule.rooms == ((0,0,1),(0,1,1))
    for r in [rule, replace(rule,black=False)]:
        assert codec.read_rule(codec.rule_record(r)) == r
        with pytest.raises(ValueError): codec.read_rule({**codec.rule_record(r),"extra":0})
        with pytest.raises(ValueError): codec.read_rule({"type":"room-fill-levels","rooms":[[0]]})
        with pytest.raises(ValueError,match="exact built-in"):
            codec.rule_record(type("Changed",(RoomFillLevels,),{})(r.rooms))
    with pytest.raises(ValueError,match="dimensions"): ShadingRecipe(3,2,(rule,)).create_empty()
    same = ShadingRecipe(2,3,(rule,RoomBlackCount(((3,3,0),(3,0,0)),1)))
    assert codec.read_recipe(codec.recipe_record(same)) == same
    with pytest.raises(ValueError,match="same partition"):
        codec.recipe_record(replace(same,rules=(rule,UniformRooms(((0,0,0),(1,1,1))))))
    # Count and level constraints can be jointly contradictory without UI conflict.
    u = ((0,1,0),(0,1,0),(0,0,0))
    assert not all_answers(ShadingRecipe(3,3,(RoomFillLevels(u),RoomBlackCount(u,1))))
    assert all_answers(ShadingRecipe(3,3,(RoomFillLevels(u),BlackCount(4)))) == {(0,0,0,0,1,0,1,1,1)}


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_aquarium_uses_count_hints_and_existing_generation_display_and_answer_paths():
    recipe = codec.load_recipe(EXAMPLES/"shading-aquarium-recipe.json")
    assert len(all_answers(recipe)) == oracle.analyze(recipe)["completion_count"] == 12
    result = worker.generate_request(request(recipe))
    assert result["status"] == "ok" and result["clues"]
    assert all(c["type"] in ("row-count","column-count") for c in result["clues"])
    assert saved.verify(result["record"])["unique"]
    text = saved.show(result["record"])
    assert "bottom-up" in text and "Fixed rooms" in text
    assert deductions.explain_puzzle(result["record"])["rules_without_deductions"] == [1]
    answer = [v for row in result["record"]["solution"] for v in row]
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":result["clues"],
                               "answer":answer}) == {"status":"ok","correct":True}
    plan = api.read_request(request(recipe)).plan
    assert plan["rooms"] == [[0,1,0],[0,1,0],[0,0,0]]
    hybrid = replace(recipe,rules=(*recipe.rules,ConnectedBlack()))
    assert oracle.analyze(hybrid)["completion_count"] == 11
    assert worker.generate_request(request(hybrid))["status"] == "ok"
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**request(recipe),"family":family})
