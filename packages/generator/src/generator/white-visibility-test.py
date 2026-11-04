"""Sight prefixes versus independent white-run lengths and end-to-end recipes."""

import importlib
from itertools import groupby, product
from pathlib import Path
from typing import Any

import pytest

from generator import with_constraints
from puzzle import Cell, at_least_one
from puzzle_defs import DistinctWhiteNumbers, ShadingRecipe, WhiteVisibilityCounts
from puzzle_defs.number_layout import DEFAULT_NUMBERS
from puzzle_defs.puzzles.white_visibility import DEFAULT_SIGHT_COUNTS

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    oracle = importlib.import_module("analyze_shading")
    codec = importlib.import_module("shading_recipe")
    saved = importlib.import_module("generate_shading")
    composed = importlib.import_module("composed_shading_recipe")
    composed_saved = importlib.import_module("generate_composed_shading")
    deductions = importlib.import_module("explain_shading")
    api = importlib.import_module("web_catalog")
    worker = importlib.import_module("web_worker")
    checks = importlib.import_module("web_answers")


def run_length(line, origin):
    for color, group in groupby(enumerate(line), key=lambda item: item[1]):
        indices = [i for i, _ in group]
        if origin in indices:
            return len(indices) if color == 0 else 0
    raise AssertionError("Origin outside line")


def accepts_counts(counts, bits):
    rows, cols = len(counts), len(counts[0])
    for r in range(rows):
        for c in range(cols):
            count = counts[r][c]
            if count == 0:
                continue
            if bits[r*cols+c]:
                return False
            row = bits[r*cols:(r+1)*cols]
            column = tuple(bits[s*cols+c] for s in range(rows))
            if run_length(row, c) + run_length(column, r) - 1 != count:
                return False
    return True


def all_answers(recipe):
    puzzle = recipe.create_empty()
    answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(puzzle.black[c] != solution.value(puzzle.black[c]) for c in puzzle.board.cells))
    return answers


@pytest.mark.parametrize("counts", [((0,),), ((1,),), ((2,),), ((0,0,0,0),),
    ((1,0,0,0,0),), ((0,0,3,0,0),), ((0,),(0,),(3,),(0,),(0,)),
    DEFAULT_SIGHT_COUNTS, ((0,0,0),(0,5,0),(0,0,0)), ((99,0),(0,0))])
def test_all_visible_answers_match_independent_white_run_lengths_and_ray_checker(counts):
    rows, cols = len(counts), len(counts[0])
    rule = WhiteVisibilityCounts(counts)
    masks = list(product((0,1), repeat=rows*cols))
    expected = {bits for bits in masks if accepts_counts(counts, bits)}
    assert {bits for bits in masks if oracle.accepts(rule, bits, rows, cols)} == expected
    assert all_answers(ShadingRecipe(rows, cols, (rule,))) == expected


def test_white_beyond_blocker_is_not_counted_and_origin_must_be_white():
    recipe = ShadingRecipe(1,5,(WhiteVisibilityCounts(((1,0,0,0,0),)),))
    def fixed(bits):
        return recipe.build_from_clues([(Cell(0,c), b) for c,b in enumerate(bits)]).solve()
    assert fixed((0,1,0,0,0)) is not None
    assert fixed((0,0,0,0,0)) is None  # Cannot hide prefix witnesses.
    assert fixed((1,1,0,0,0)) is None


@pytest.mark.parametrize("bad", [{}, [], [[]], [[1],[2,3]], [[True]], [[1.0]], [[-1]], [[100]], [["1"]]])
def test_counts_are_strict_bounded_arrays(bad):
    with pytest.raises(ValueError): WhiteVisibilityCounts(bad)
    with pytest.raises(ValueError): codec.read_rule({"type":"white-visibility-counts","counts":bad})


def test_data_is_immutable_exact_and_dimension_checked():
    raw: Any = [[0,3,2],[0,0,0]]
    rule = WhiteVisibilityCounts(raw)
    raw[0][1] = 99
    assert rule.counts == DEFAULT_SIGHT_COUNTS
    assert codec.read_rule(codec.rule_record(rule)) == rule
    with pytest.raises(ValueError): codec.read_rule({**codec.rule_record(rule),"extra":0})
    with pytest.raises(ValueError,match="exact built-in"):
        codec.rule_record(type("Changed",(WhiteVisibilityCounts,),{})(DEFAULT_SIGHT_COUNTS))
    with pytest.raises(ValueError,match="dimensions"): ShadingRecipe(3,2,(rule,)).create_empty()
    with pytest.raises(ValueError,match="25 board cells"):
        ShadingRecipe(5,6,(WhiteVisibilityCounts(((0,)*6,)*5),)).create_empty()
    recipe = ShadingRecipe(2,3,(rule,WhiteVisibilityCounts(((0,0,0),(0,0,0)))))
    with pytest.raises(ValueError,match="same sight counts"): codec.recipe_record(recipe)
    with pytest.raises(ValueError,match="same sight counts"): saved.puzzle_record(recipe,[],seed=0)


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_kuromasu_composition_generates_unique_without_removing_fixed_numbers():
    recipe = codec.load_recipe(EXAMPLES / "shading-kuromasu-recipe.json")
    result = worker.generate_request(request(recipe))
    assert result["status"] == "ok" and result["clues"] == []
    assert result == worker.generate_request(request(recipe))
    assert saved.verify(result["record"])["unique"]
    assert all_answers(recipe) == {(1,0,0,0,0,1)}
    assert "0 3 2" not in saved.show(result["record"])
    assert ". 3 2\n. . ." in saved.show(result["record"])
    assert "Answer template: ?../???" in saved.show(result["record"])
    assert 1 in deductions.explain_puzzle(result["record"])["rules_without_deductions"]
    answer = [v for row in result["record"]["solution"] for v in row]
    checked = {"format":checks.FORMAT,"request":result["request"],"clues":[],"answer":answer}
    assert checks.check_answer(checked) == {"status":"ok","correct":True}
    assert checks.check_answer({**checked,"answer":[0]*6}) == {"status":"ok","correct":False}
    puzzle = recipe.create_empty()
    assert puzzle.solution_vars is not None and len(puzzle.solution_vars) == 6
    configured = with_constraints(recipe, composed.CellCount("black",2))
    record = composed_saved.generate_record(composed.recipe_record(configured),seed=0)
    assert ". 3 2\n. . ." in composed_saved.show(record)


def test_numeric_labels_and_visibility_data_have_separate_channels_and_values():
    recipe = codec.load_recipe(EXAMPLES / "shading-kuromasu-recipe.json")
    hybrid = ShadingRecipe(2,3,(*recipe.rules,DistinctWhiteNumbers(DEFAULT_NUMBERS)))
    data = request(hybrid)
    plan = api.read_request(data).plan
    assert plan["numbers"] == [list(row) for row in DEFAULT_NUMBERS]
    assert plan["sight_counts"] == [list(row) for row in DEFAULT_SIGHT_COUNTS]
    assert {c["name"] for c in plan["requirements"]["channels"]} == {"answer","givens","numbers","sight-counts"}
    assert all_answers(hybrid) == {(1,0,0,0,0,1)}
    for invalid in [{}, [[0]], [[False]*3]*2, [[100]*3]*2]:
        broken = request(recipe)
        broken["rules"][0]["parameters"]["counts"] = invalid
        with pytest.raises(ValueError): api.read_request(broken)
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**data,"family":family})
