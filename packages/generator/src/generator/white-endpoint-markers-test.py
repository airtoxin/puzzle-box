"""Endpoint positions versus independent pairwise degrees on every 2x3 board."""

from dataclasses import replace
import importlib
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from puzzle import Cell, at_least_one, unique
from puzzle_defs import ColorEndpointCount, ShadingRecipe, WhiteEndpointMarkers
from puzzle_defs.marker_layout import DEFAULT_ENDPOINT_MARKERS

EXAMPLES=Path(__file__).resolve().parents[4]/"examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    oracle=importlib.import_module("analyze_shading")
    codec=importlib.import_module("shading_recipe")
    saved=importlib.import_module("generate_shading")
    composed=importlib.import_module("composed_shading_recipe")
    composed_saved=importlib.import_module("generate_composed_shading")
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


def pairwise_markers(bits,rows,cols):
    white={(r,c) for r in range(rows) for c in range(cols) if not bits[r*cols+c]}
    endpoints={p for p in white if sum(abs(p[0]-q[0])+abs(p[1]-q[1]) == 1 for q in white) == 1}
    return tuple(tuple(int((r,c) in endpoints) for c in range(cols)) for r in range(rows))


def test_every_two_by_three_marker_layout_matches_both_independent_references():
    boards=list(product((0,1),repeat=6))
    grouped={}
    for bits in boards:
        grouped.setdefault(pairwise_markers(bits,2,3),set()).add(bits)
    for flags in product((0,1),repeat=6):
        markers=(flags[:3],flags[3:])
        rule=WhiteEndpointMarkers(markers)
        expected=grouped.get(markers,set())
        assert {b for b in boards if oracle.accepts(rule,b,2,3)} == expected
        assert all_answers(ShadingRecipe(2,3,(rule,))) == expected


def fixed(rows,cols,markers,white):
    return ShadingRecipe(rows,cols,(WhiteEndpointMarkers(markers),)).build_from_clues(
        [(Cell(r,c),int((r,c) not in white)) for r in range(rows) for c in range(cols)])


def test_markers_are_exact_locations_not_only_a_count_and_both_implications_hold():
    assert all_answers(ShadingRecipe(1,2,(WhiteEndpointMarkers(((1,1),)),))) == {(0,0)}
    assert not all_answers(ShadingRecipe(1,2,(WhiteEndpointMarkers(((1,0),)),)))
    assert all_answers(ShadingRecipe(1,2,(WhiteEndpointMarkers(((0,0),)),))) == {(1,1),(0,1),(1,0)}
    assert all_answers(ShadingRecipe(1,1,(WhiteEndpointMarkers(((0,),)),))) == {(0,),(1,)}
    assert not all_answers(ShadingRecipe(1,1,(WhiteEndpointMarkers(((1,),)),)))
    markers=((1,0,0),(0,0,1))
    wrong=((0,0,1),(1,0,0))
    white={(0,0),(0,1),(0,2),(1,2)}
    assert fixed(2,3,markers,white).solve() is not None
    assert fixed(2,3,wrong,white).solve() is None  # Same endpoint count, different positions.


def test_cycles_branches_absence_and_isolated_whites_are_not_additional_conditions():
    ring={(r,c) for r in range(3) for c in range(3)}-{(1,1)}
    assert fixed(3,3,((0,)*3,)*3,ring).solve() is not None
    tee={(0,1),(1,0),(1,1),(1,2)}
    markers=((0,1,0),(1,0,1),(0,0,0))
    assert fixed(3,3,markers,tee).solve() is not None
    assert fixed(1,3,((0,0,0),),{(0,0),(0,2)}).solve() is not None
    assert fixed(1,3,((0,0,0),),set()).solve() is not None


@pytest.mark.parametrize("bad", [{},[],[[]],[[1],[0,0]],[[None]],[[True]],[[1.0]],[[2]],[[-1]]])
def test_marker_schema_and_ui_parameter_validate_the_same_binary_domain(bad):
    with pytest.raises(ValueError): WhiteEndpointMarkers(bad)
    with pytest.raises(ValueError): codec.read_rule({"type":"white-endpoint-markers","markers":bad})
    with pytest.raises(ValueError):
        WhiteEndpointMarkers.ui.parameters[0].validate(bad,area=1,rows=1,cols=1)


def test_copy_exact_codec_dimensions_shared_layout_and_visible_projection():
    raw: Any=[[1,0,0],[0,0,1]]
    rule=WhiteEndpointMarkers(raw)
    raw[0][0]=0
    assert rule.markers == DEFAULT_ENDPOINT_MARKERS and codec.read_rule(codec.rule_record(rule)) == rule
    with pytest.raises(ValueError): codec.read_rule({**codec.rule_record(rule),"extra":0})
    with pytest.raises(ValueError,match="exact built-in"): codec.rule_record(type("Changed",(WhiteEndpointMarkers,),{})(rule.markers))
    with pytest.raises(ValueError,match="dimensions"): ShadingRecipe(3,2,(rule,)).create_empty()
    conflicting=ShadingRecipe(2,3,(rule,WhiteEndpointMarkers(((0,)*3,)*2)))
    with pytest.raises(ValueError,match="same markers"): codec.recipe_record(conflicting)
    with pytest.raises(ValueError,match="same markers"): saved.puzzle_record(conflicting,[],seed=0)
    p=fixed(1,2,((1,1),),{(0,0),(0,1)})
    assert p.solution_vars is not None and len(p.solution_vars) == 2
    p.add(unique())
    assert p.solve() is not None


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_example_retains_needed_hints_and_checks_with_new_marker_ui():
    recipe=codec.load_recipe(EXAMPLES/"shading-nurimisaki-recipe.json")
    answers={(0,0,0,1,1,0),(0,1,1,0,0,0),(0,0,1,1,0,0)}
    assert all_answers(recipe) == answers
    assert oracle.analyze(recipe)["completion_count"] == 3
    assert all_answers(replace(recipe,rules=(*recipe.rules,ColorEndpointCount(2,False)))) == answers
    result=worker.generate_request(request(recipe))
    assert result["status"] == "ok" and result["clues"]
    assert saved.verify(result["record"])["unique"]
    text=saved.show(result["record"])
    assert "o . .\n. . o" in text and "no other white cell" in text
    assert 1 in deductions.explain_puzzle(result["record"])["rules_without_deductions"]
    answer=[v for row in result["record"]["solution"] for v in row]
    assert tuple(answer) in answers
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":result["clues"],
                               "answer":answer}) == {"status":"ok","correct":True}
    configured=composed.with_constraints(recipe,composed.CellCount("black",2))
    record=composed_saved.generate_record(composed.recipe_record(configured),seed=0)
    assert "o . .\n. . o" in composed_saved.show(record)
    plan=api.read_request(request(recipe)).plan
    assert plan["endpoint_markers"] == [[1,0,0],[0,0,1]]
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**request(recipe),"family":family})
