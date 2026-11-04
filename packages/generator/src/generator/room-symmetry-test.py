"""Room-local half turns versus independently rotated black sets."""

import importlib
from itertools import product
from pathlib import Path

import pytest

from puzzle import Cell, at_least_one
from puzzle_defs import RoomBlackCount, RoomRotationalSymmetry, ShadingRecipe
from puzzle_defs.room_layout import DEFAULT_ROOMS

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    oracle = importlib.import_module("analyze_shading")
    codec = importlib.import_module("shading_recipe")
    saved = importlib.import_module("generate_shading")
    finite = importlib.import_module("finite_shading")
    deductions = importlib.import_module("explain_shading")
    api = importlib.import_module("web_catalog")
    worker = importlib.import_module("web_worker")


def all_answers(recipe):
    puzzle = recipe.create_empty(); answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(puzzle.black[c] != solution.value(puzzle.black[c]) for c in puzzle.board.cells))
    return answers


@pytest.mark.parametrize("rooms", [((0,),), ((0,0,0),), ((0,0,0,0),), ((0,0,0),(0,0,0)),
    ((0,0,0),(0,0,0),(0,0,0)), DEFAULT_ROOMS, ((0,0,0),(0,1,0)), ((0,0,1,1,1),)])
def test_all_dsl_answers_match_rotated_sets_at_integer_half_and_offset_centers(rooms):
    rows,cols = len(rooms),len(rooms[0]); rule = RoomRotationalSymmetry(rooms)
    expected = {bits for bits in product((0,1),repeat=rows*cols) if oracle.accepts(rule,bits,rows,cols)}
    assert all_answers(ShadingRecipe(rows,cols,(rule,))) == expected
    assert (0,)*(rows*cols) in expected


def test_mapping_into_another_room_is_not_rescued_by_that_rooms_black_cell():
    rule = RoomRotationalSymmetry(DEFAULT_ROOMS)
    puzzle = ShadingRecipe(2,3,(rule,)).create_empty()
    puzzle.add(puzzle.black[Cell(0,0)] == 1)
    puzzle.add(puzzle.black[Cell(1,1)] == 1)  # rotation of (0,0), but in a different room
    assert puzzle.solve() is None


def test_odd_counts_need_a_fixed_cell_at_the_center():
    even = ((0,0),(0,0))
    assert not all_answers(ShadingRecipe(2,2,(RoomBlackCount(even,1),RoomRotationalSymmetry(even))))
    odd = ((0,0,0),)
    assert all_answers(ShadingRecipe(1,3,(RoomBlackCount(odd,1),RoomRotationalSymmetry(odd)))) == {(0,1,0)}


def test_strict_codec_canonical_geometry_and_shared_partition_contract():
    rule = codec.read_rule({"type":"room-rotational-symmetry","rooms":[[5,5,3],[5,3,3]]})
    assert rule == RoomRotationalSymmetry(DEFAULT_ROOMS)
    assert codec.read_rule(codec.rule_record(rule)) == rule
    assert {p.name for p in rule.ui.parameters} == {"rooms"}
    for bad in [{}, [], [[0]], [[False]], [[0,1,0]]]:
        # [[0]] is valid by itself, but cannot be used on this 2x3 board.
        with pytest.raises(ValueError):
            ShadingRecipe(2,3,(codec.read_rule({"type":"room-rotational-symmetry","rooms":bad}),)).create_empty()
    with pytest.raises(ValueError): codec.read_rule({**codec.rule_record(rule),"extra":0})
    with pytest.raises(ValueError, match="exact built-in"):
        codec.rule_record(type("Changed",(RoomRotationalSymmetry,),{})(DEFAULT_ROOMS))
    conflicting = ShadingRecipe(2,3,(rule,RoomBlackCount(((0,0,0),(1,1,1)),2)))
    with pytest.raises(ValueError, match="same partition"): codec.recipe_record(conflicting)


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_symmetry_selects_one_of_three_aqre_completions_without_cell_clues():
    recipe = codec.load_recipe(EXAMPLES / "shading-aqre-symmetry-recipe.json")
    base = ShadingRecipe(1,6,recipe.rules[:-1]); assert len(all_answers(base)) == 3
    assert all_answers(recipe) == set(finite.identifiable_completions(recipe)) == {(0,0,1,1,0,0)}
    result = worker.generate_request(request(recipe))
    assert result == worker.generate_request(request(recipe)) and result["status"] == "ok"
    assert result["clues"] == [] and saved.verify(result["record"])["unique"]
    assert "180-degree symmetry" in saved.show(result["record"])
    assert deductions.explain_puzzle(result["record"])["rules_without_deductions"] == [1,2,3,4]
    plan = api.read_request(request(recipe)).plan
    assert [c["name"] for c in plan["requirements"]["channels"]].count("rooms") == 1
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**request(recipe),"family":family})
