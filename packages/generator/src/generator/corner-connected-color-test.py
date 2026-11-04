"""Eight-neighbor color connectivity composed with orthogonal shapes."""

from dataclasses import replace
import importlib
from itertools import product
from pathlib import Path

import pytest

from puzzle import Cell, at_least_one, unique
from puzzle_defs import (ConnectedWhite, CornerConnectedColor, NoBlack2x2, RectangularComponents,
                         ShadingRecipe, WhiteIslandAreas)

EXAMPLES=Path(__file__).resolve().parents[4]/"examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    oracle=importlib.import_module("analyze_shading")
    codec=importlib.import_module("shading_recipe")
    saved=importlib.import_module("generate_shading")
    deductions=importlib.import_module("explain_shading")
    api=importlib.import_module("web_catalog")
    worker=importlib.import_module("web_worker")
    checks=importlib.import_module("web_answers")


def all_answers(recipe):
    p=recipe.create_empty()
    answers=set()
    while (solution:=p.solve(seed=0)) is not None:
        bits=tuple(v for row in p.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        p.add(at_least_one(p.black[c] != solution.value(p.black[c]) for c in p.board.cells))
    return answers


@pytest.mark.parametrize("black,nonempty", product((False,True),repeat=2))
def test_both_colors_and_empty_policies_match_finite_checker(black,nonempty):
    rule=CornerConnectedColor(black,nonempty)
    expected={b for b in product((0,1),repeat=6) if oracle.accepts(rule,b,2,3)}
    assert all_answers(ShadingRecipe(2,3,(rule,))) == expected
    empty=(int(not black),)*6
    assert (empty in expected) == (not nonempty)


def test_corner_contact_does_not_merge_orthogonal_components_or_area_numbers():
    # Two numbered singleton rectangles meet only at a corner.
    areas=WhiteIslandAreas(((1,0),(0,1)))
    recipe=ShadingRecipe(2,2,(areas,RectangularComponents(False),NoBlack2x2(),CornerConnectedColor()))
    assert all_answers(recipe) == {(0,1,1,0)}
    assert not all_answers(replace(recipe,rules=(*recipe.rules,ConnectedWhite())))
    puzzle=recipe.create_empty()
    assert puzzle.solution_vars is not None and len(puzzle.solution_vars) == 4
    puzzle.add(unique())
    assert puzzle.solve() is not None


def test_edges_are_still_connections_but_a_whole_cell_gap_is_not():
    rules=(CornerConnectedColor(),RectangularComponents(False))
    assert (0,0,0,1,1,1) in all_answers(ShadingRecipe(2,3,rules))
    # Left vertical domino and right singleton cannot jump a black column.
    assert (0,1,0,0,1,1) not in all_answers(ShadingRecipe(2,3,rules))
    # Three diagonal singleton rectangles form an eight-neighbor chain.
    assert (0,1,0,1,0,1) in all_answers(ShadingRecipe(2,3,rules))


@pytest.mark.parametrize("bad", [0,1,None,"white"])
def test_parameters_are_strict_booleans(bad):
    with pytest.raises(ValueError): CornerConnectedColor(bad)
    with pytest.raises(ValueError): CornerConnectedColor(False,bad)
    with pytest.raises(ValueError): codec.read_rule({"type":"corner-connected-color","black":bad,"nonempty":True})


def test_exact_codecs_and_missing_unknown_parameters():
    for black,nonempty in product((False,True),repeat=2):
        rule=CornerConnectedColor(black,nonempty)
        record=codec.rule_record(rule)
        assert codec.read_rule(record) == rule
        with pytest.raises(ValueError): codec.read_rule({**record,"diagonal":False})
        with pytest.raises(ValueError): codec.read_rule({k:v for k,v in record.items() if k != "nonempty"})
    with pytest.raises(ValueError,match="exact built-in"):
        codec.rule_record(type("Changed",(CornerConnectedColor,),{})())


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_shape_example_generates_and_checks_with_existing_renderers():
    recipe=codec.load_recipe(EXAMPLES/"shading-corner-rectangles-recipe.json")
    report=oracle.analyze(recipe)
    assert report["completion_count"] == len(all_answers(recipe)) > 1
    result=worker.generate_request(request(recipe))
    assert result["status"] == "ok" and result["clues"]
    assert saved.verify(result["record"])["unique"]
    assert "edges or corners (eight neighbors)" in saved.show(result["record"])
    assert 1 in deductions.explain_puzzle(result["record"])["rules_without_deductions"]
    answer=[v for row in result["record"]["solution"] for v in row]
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":result["clues"],
                               "answer":answer}) == {"status":"ok","correct":True}
    plan=api.read_request(request(recipe)).plan
    assert {c["kind"] for c in plan["requirements"]["channels"]} == {"binary-cells","cell-givens"}
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**request(recipe),"family":family})
