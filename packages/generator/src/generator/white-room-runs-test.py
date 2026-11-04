"""White runs, independent room-entry scans, and shared geometry integration."""

import importlib
from itertools import product
from pathlib import Path

import pytest

from generator import InitialCluesNotUniqueError
from puzzle import at_least_one
from puzzle_defs import (BlackCount, ConnectedWhite, NoWhiteAcrossThreeRooms,
                         NonTouchingBlack, RoomBlackCount, ShadingRecipe)

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
    checks = importlib.import_module("web_answers")

COLUMNS = ((0,1,2),(0,1,2))


def all_answers(recipe):
    puzzle = recipe.create_empty()
    answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(puzzle.black[c] != solution.value(puzzle.black[c]) for c in puzzle.board.cells))
    return answers


@pytest.mark.parametrize("layout", [((0,),), ((0,0,1),), ((0,1,2),),
    ((0,0,1,1,1,2,2),), COLUMNS, ((0,0,0),(0,1,0)),
    ((0,0,0),(1,1,1),(2,2,2)), ((0,1,2),(3,4,5),(6,7,8))])
def test_short_boundary_intervals_match_independent_scans_of_all_white_runs(layout):
    rows,cols = len(layout),len(layout[0])
    rule = NoWhiteAcrossThreeRooms(layout)
    expected = {bits for bits in product((0,1),repeat=rows*cols) if oracle.accepts(rule,bits,rows,cols)}
    assert all_answers(ShadingRecipe(rows,cols,(rule,))) == expected


def test_two_rooms_allow_arbitrarily_long_white_runs_and_black_interrupts_three_rooms():
    two = NoWhiteAcrossThreeRooms(((0,0,0,1,1,1),))
    assert oracle.accepts(two,(0,)*6,1,6)
    three = NoWhiteAcrossThreeRooms(((0,0,1,1,1,2,2),))
    assert not oracle.accepts(three,(0,)*7,1,7)
    for position in range(7):
        bits = tuple(int(i == position) for i in range(7))
        assert oracle.accepts(three,bits,1,7) == (1 <= position <= 5)


def test_reentering_an_irregular_room_counts_as_another_segment():
    layout = ((0,0,0),(0,1,0))
    rule = NoWhiteAcrossThreeRooms(layout)
    assert not oracle.accepts(rule,(0,0,0,0,0,0),2,3)
    assert oracle.accepts(rule,(0,0,0,0,1,0),2,3)
    # Top white cells connect the bottom ends, but a bent path is not a straight run.
    assert (0,0,0,0,1,0) in all_answers(ShadingRecipe(2,3,(rule,)))


@pytest.mark.parametrize("rooms", [{}, [], [[0,1,0]], [[True]], [[0],[0,1]]])
def test_invalid_room_data_is_rejected(rooms):
    with pytest.raises(ValueError): codec.read_rule({"type":"no-white-across-three-rooms","rooms":rooms})


def test_exact_codec_dimensions_and_same_partition_contract():
    rule = NoWhiteAcrossThreeRooms(COLUMNS)
    assert codec.read_rule(codec.rule_record(rule)) == rule
    assert {p.name for p in rule.ui.parameters} == {"rooms"}
    with pytest.raises(ValueError): codec.read_rule({**codec.rule_record(rule),"extra":0})
    with pytest.raises(ValueError, match="exact built-in"):
        codec.rule_record(type("Changed",(NoWhiteAcrossThreeRooms,),{})(COLUMNS))
    with pytest.raises(ValueError, match="dimensions"): ShadingRecipe(3,2,(rule,)).create_empty()
    conflicting = ShadingRecipe(2,3,(rule,RoomBlackCount(((0,0,0),(1,1,1)),1)))
    with pytest.raises(ValueError, match="same partition"): codec.recipe_record(conflicting)
    with pytest.raises(ValueError, match="same partition"): saved.puzzle_record(conflicting,[],seed=0)


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_relabelled_maps_share_one_channel_and_different_geometry_is_rejected():
    recipe = ShadingRecipe(2,3,(NoWhiteAcrossThreeRooms(COLUMNS),RoomBlackCount(COLUMNS,1)))
    data = request(recipe); data["rules"][0]["parameters"]["rooms"] = [[5,4,3],[5,4,3]]
    plan = api.read_request(data).plan
    assert plan["rooms"] == [list(row) for row in COLUMNS]
    assert [c["name"] for c in plan["requirements"]["channels"]].count("rooms") == 1
    data["rules"][0]["parameters"]["rooms"] = [[0,0,0],[1,1,1]]
    with pytest.raises(ValueError, match="same partition"): api.read_request(data)
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**request(recipe),"family":family})


def test_documented_recipe_has_two_answers_before_clues_and_generates_verified_puzzle():
    recipe = codec.load_recipe(EXAMPLES / "shading-room-runs-recipe.json")
    expected = {(0,0,1,1,0,0),(1,0,0,0,0,1)}
    assert all_answers(recipe) == set(finite.identifiable_completions(recipe)) == expected
    result = worker.generate_request(request(recipe))
    assert result == worker.generate_request(request(recipe)) and result["status"] == "ok"
    assert result["clues"] and saved.verify(result["record"])["unique"]
    assert "cannot cross two room boundaries" in saved.show(result["record"])
    assert "0 1 2\n0 1 2" in saved.show(result["record"])
    assert deductions.explain_puzzle(result["record"])["rules_without_deductions"] == [1]
    answer = [v for row in result["record"]["solution"] for v in row]
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":result["clues"],
                               "answer":answer}) == {"status":"ok","correct":True}


def test_row_and_column_counts_cannot_distinguish_the_two_example_completions():
    recipe = codec.load_recipe(EXAMPLES / "shading-room-runs-recipe.json")
    counts_only = ShadingRecipe(2,3,recipe.rules,("row-count","column-count"))
    with pytest.raises(InitialCluesNotUniqueError): finite.identifiable_completions(counts_only)


def test_rule_is_not_redundant_with_global_white_connectivity_and_black_noncontact():
    base = (NonTouchingBlack(),ConnectedWhite(),BlackCount(1))
    assert all_answers(ShadingRecipe(2,3,base))
    assert not all_answers(ShadingRecipe(2,3,(*base,NoWhiteAcrossThreeRooms(COLUMNS))))
