"""Fixed numbers, independent line uniqueness, and simultaneous room rendering."""

import importlib
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from generator import with_constraints
from puzzle import at_least_one
from puzzle_defs import (ConnectedWhite, DistinctWhiteNumbers, HitoriPuzzle,
                         NonTouchingBlack, RoomBlackCount, ShadingRecipe)
from puzzle_defs.number_layout import DEFAULT_NUMBERS, number_grid

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


def all_answers(puzzle):
    answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(int(v) for row in puzzle.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(puzzle.black[c] != solution.value(puzzle.black[c]) for c in puzzle.board.cells))
    return answers


@pytest.mark.parametrize("numbers", [((0,),), ((99,99,0),), DEFAULT_NUMBERS,
    ((1,2),(2,1)), ((1,1,1),(1,1,1),(1,1,1)), ((1,2,3),(1,3,2),(2,1,3))])
def test_all_dsl_answers_match_independent_white_number_sets(numbers):
    rows,cols = len(numbers),len(numbers[0])
    rule = DistinctWhiteNumbers(numbers)
    expected = {bits for bits in product((0,1),repeat=rows*cols) if oracle.accepts(rule,bits,rows,cols)}
    assert all_answers(ShadingRecipe(rows,cols,(rule,)).create_empty()) == expected


@pytest.mark.parametrize("numbers", [DEFAULT_NUMBERS, ((1,1),(2,1)), ((1,2),(3,4))])
def test_shared_pair_finder_preserves_dedicated_hitori_answers(numbers):
    recipe = ShadingRecipe(len(numbers),len(numbers[0]),
                           (DistinctWhiteNumbers(numbers),NonTouchingBlack(),ConnectedWhite(False)))
    assert all_answers(recipe.create_empty()) == all_answers(HitoriPuzzle([list(row) for row in numbers]))


@pytest.mark.parametrize("numbers", [{}, [], [[]], [[1],[1,2]], [[True]], [[1.0]], [[-1]], [[100]], [["1"]]])
def test_fixed_numbers_are_strict_bounded_arrays(numbers):
    with pytest.raises(ValueError): number_grid(numbers)
    with pytest.raises(ValueError): codec.read_rule({"type":"distinct-white-numbers","numbers":numbers})


def test_labels_are_preserved_immutable_and_not_answer_variables():
    raw: Any = [[99,99,0],[0,1,0]]
    rule = DistinctWhiteNumbers(raw)
    assert rule.numbers == ((99,99,0),(0,1,0))
    raw[0][0] = 3
    assert rule.numbers[0][0] == 99
    puzzle = ShadingRecipe(2,3,(rule,)).create_empty()
    assert puzzle.solution_vars is not None and len(puzzle.solution_vars) == 6
    with pytest.raises(ValueError, match="dimensions"): ShadingRecipe(3,2,(rule,)).create_empty()
    assert codec.read_rule(codec.rule_record(rule)) == rule
    with pytest.raises(ValueError): codec.read_rule({**codec.rule_record(rule),"extra":0})
    with pytest.raises(ValueError, match="exact built-in"):
        codec.rule_record(type("Changed",(DistinctWhiteNumbers,),{})(DEFAULT_NUMBERS))


def test_different_number_payloads_cannot_share_a_saved_drawing():
    recipe = ShadingRecipe(2,3,(DistinctWhiteNumbers(DEFAULT_NUMBERS),DistinctWhiteNumbers(((0,0,0),(0,0,0)))))
    with pytest.raises(ValueError, match="same fixed numbers"): codec.recipe_record(recipe)
    with pytest.raises(ValueError, match="same fixed numbers"): saved.puzzle_record(recipe,[],seed=0)


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


@pytest.mark.parametrize("name", ["hitori","number-rooms"])
def test_saved_examples_generate_and_keep_fixed_data_with_no_extra_hints(name):
    recipe = codec.load_recipe(EXAMPLES / f"shading-{name}-recipe.json")
    result = worker.generate_request(request(recipe))
    assert result == worker.generate_request(request(recipe)) and result["status"] == "ok"
    assert result["clues"] == [] and saved.verify(result["record"])["unique"]
    assert set(finite.identifiable_completions(recipe)) == {(1,0,0,0,0,1)}
    assert "1 1 2\n2 3 2" in saved.show(result["record"])
    assert 1 in deductions.explain_puzzle(result["record"])["rules_without_deductions"]
    answer = [v for row in result["record"]["solution"] for v in row]
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":[],"answer":answer}) == {"status":"ok","correct":True}
    if name == "number-rooms":
        assert "0 0 0\n1 1 1" in saved.show(result["record"])
        configured = with_constraints(recipe,composed.CellCount("black",2))
        record = composed_saved.generate_record(composed.recipe_record(configured),seed=0)
        assert "1 1 2\n2 3 2" in composed_saved.show(record)
        assert "0 0 0\n1 1 1" in composed_saved.show(record)


def test_ui_merges_number_and_room_channels_without_renaming_numeric_values():
    recipe = codec.load_recipe(EXAMPLES / "shading-number-rooms-recipe.json")
    data = request(recipe); data["rules"][0]["parameters"]["numbers"] = [[99,99,0],[0,1,0]]
    plan = api.read_request(data).plan
    assert plan["numbers"] == [[99,99,0],[0,1,0]] and plan["rooms"] == [[0,0,0],[1,1,1]]
    assert {c["name"] for c in plan["requirements"]["channels"]} == {"answer","givens","rooms","numbers"}
    for invalid in [{}, [[0]], [[100]*3]*2, [[False]*3]*2]:
        broken = request(recipe); broken["rules"][0]["parameters"]["numbers"] = invalid
        with pytest.raises(ValueError): api.read_request(broken)
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**data,"family":family})
