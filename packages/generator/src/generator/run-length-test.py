"""Run grouping versus window encoding, including the legacy fixed-three rule."""

import importlib
from itertools import product
from pathlib import Path

import pytest

from puzzle import at_least_one
from puzzle_defs import NoThreeConsecutive, RunLengthLimit, ShadingRecipe

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


@pytest.mark.parametrize("rows,cols,maximum", [
    (rows,cols,maximum) for rows,cols in [(1,1),(1,4),(4,1),(2,4),(3,3)]
    for maximum in [1,2,3,6] if rows*cols <= 4 or maximum < max(rows,cols)
])
def test_all_solver_answers_match_independent_group_lengths(rows, cols, maximum):
    rule = RunLengthLimit(maximum)
    expected = {bits for bits in product((0,1),repeat=rows*cols) if oracle.accepts(rule,bits,rows,cols)}
    assert all_answers(ShadingRecipe(rows,cols,(rule,))) == expected
    if maximum == 2:
        assert expected == {bits for bits in product((0,1),repeat=rows*cols)
                            if oracle.accepts(NoThreeConsecutive(),bits,rows,cols)}


@pytest.mark.parametrize("value", [0,-1,True,1.5,"3"])
def test_limits_are_positive_exact_integers(value):
    with pytest.raises(ValueError): RunLengthLimit(value)
    with pytest.raises(ValueError): codec.read_rule({"type":"run-length-limit","max_length":value})


def test_codec_legacy_contract_and_large_redundant_limit():
    assert codec.rule_record(NoThreeConsecutive()) == {"type":"no-three-consecutive"}
    assert codec.read_rule({"type":"no-three-consecutive"}) == NoThreeConsecutive()
    rule = RunLengthLimit(2**100)
    assert codec.read_rule(codec.rule_record(rule)) == rule
    assert all_answers(ShadingRecipe(1,3,(rule,))) == set(product((0,1),repeat=3))
    with pytest.raises(ValueError): codec.read_rule({**codec.rule_record(rule),"extra":0})
    with pytest.raises(ValueError, match="exact built-in"):
        codec.rule_record(type("Changed",(RunLengthLimit,),{})(3))


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_aqre_fragment_removes_edge_blocks_and_is_not_the_stricter_binary_rule():
    recipe = codec.load_recipe(EXAMPLES / "shading-aqre-fragment-recipe.json")
    base = ShadingRecipe(1,6,recipe.rules[:-1])
    assert len(all_answers(base)) == 5
    expected = {(0,1,1,0,0,0),(0,0,1,1,0,0),(0,0,0,1,1,0)}
    assert all_answers(recipe) == set(finite.identifiable_completions(recipe)) == expected
    assert all_answers(ShadingRecipe(1,6,(*base.rules,NoThreeConsecutive()))) == {(0,0,1,1,0,0)}
    assert not all_answers(ShadingRecipe(1,6,(*base.rules,RunLengthLimit(1))))
    result = worker.generate_request(request(recipe))
    assert result == worker.generate_request(request(recipe)) and result["status"] == "ok"
    assert result["clues"] and saved.verify(result["record"])["unique"]
    assert "length at most 3" in saved.show(result["record"])
    assert "0 0 0 0 0 0" in saved.show(result["record"])
    assert deductions.explain_puzzle(result["record"])["rules_without_deductions"] == [1,2,3]


def test_web_bound_is_explicit_and_other_families_reject_the_rule():
    data = request(ShadingRecipe(2,3,(RunLengthLimit(25),)))
    assert api.read_request(data).recipe.rules == (RunLengthLimit(25),)
    data["rules"][0]["parameters"]["max_length"] = 26
    with pytest.raises(ValueError): api.read_request(data)
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**data,"family":family})
