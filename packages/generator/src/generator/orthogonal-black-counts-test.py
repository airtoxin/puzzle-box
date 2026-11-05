"""Color-free neighbor numbers, from Paint Area; zero is not absence."""

from dataclasses import replace
import importlib
from itertools import product
import json
from pathlib import Path
from typing import Any

import pytest

from puzzle import at_least_one, unique
from puzzle_defs import (AdjacentBlackCounts, ComponentAreaClues, OrthogonalBlackCounts,
                         ShadingRecipe, UniformRooms)

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
    p=recipe.create_empty();answers=set()
    while (s:=p.solve(seed=0)) is not None:
        bits=tuple(v for row in p.result(s) for v in row)
        assert bits not in answers
        answers.add(bits)
        p.add(at_least_one(p.black[c]!=s.value(p.black[c]) for c in p.board.cells))
    return answers


def bit_reference(counts,bits):
    rows,cols=len(counts),len(counts[0]);mines=sum(b<<i for i,b in enumerate(bits))
    for r,row in enumerate(counts):
        for c,n in enumerate(row):
            if n is None:
                continue
            mask=sum(1<<(s*cols+t) for s,t in ((r-1,c),(r+1,c),(r,c-1),(r,c+1))
                     if 0<=s<rows and 0<=t<cols)
            if (mines & mask).bit_count()!=n:
                return False
    return True


@pytest.mark.parametrize("counts",[
    ((None,),),((0,),),((1,),),((0,None),),((0,0),),((1,1),),
    ((2,None,None),(None,None,None)),((None,1,None),(None,None,0)),
    ((None,None,None),(None,4,None),(None,None,None)),
    ((1,None,None),(None,0,None),(None,None,1)),
])
def test_all_binary_answers_match_independent_bit_and_distance_references(counts):
    rule=OrthogonalBlackCounts(counts);rows,cols=len(counts),len(counts[0])
    boards=list(product((0,1),repeat=rows*cols))
    expected={b for b in boards if bit_reference(counts,b)}
    assert {b for b in boards if oracle.accepts(rule,b,rows,cols)} == expected
    assert all_answers(ShadingRecipe(rows,cols,(rule,))) == expected


def test_zero_does_not_set_its_own_color_and_white_number_counts_keep_their_contract():
    assert all_answers(ShadingRecipe(1,1,(OrthogonalBlackCounts(((0,),)),))) == {(0,),(1,)}
    assert all_answers(ShadingRecipe(1,1,(AdjacentBlackCounts(((0,),),False),))) == {(0,)}
    assert all_answers(ShadingRecipe(1,2,(OrthogonalBlackCounts(((1,1),)),))) == {(1,1)}
    assert not all_answers(ShadingRecipe(1,2,(AdjacentBlackCounts(((1,1),),False),)))


@pytest.mark.parametrize("bad",[{},[],[[]],[[0],[1,2]],[[True]],[[1.0]],[[-1]],[[5]],[["."]]])
def test_strict_nullable_count_grids(bad):
    with pytest.raises(ValueError): OrthogonalBlackCounts(bad)
    with pytest.raises(ValueError): codec.read_rule({"type":"orthogonal-black-counts","orthogonal_counts":bad})


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],"parameters":{k:v for k,v in r.items() if k!="type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_immutable_exact_codecs_separate_shared_grids_and_server_validation():
    raw:Any=[[2,None,None],[None,None,None]]
    rule=OrthogonalBlackCounts(raw);raw[0][0]=None
    assert rule.orthogonal_counts == ((2,None,None),(None,None,None))
    record=codec.rule_record(rule)
    assert codec.read_rule(json.loads(json.dumps(record))) == rule
    for broken in [{**record,"extra":0},{"type":rule.ui.identifier},{**record,"orthogonal_counts":rule.orthogonal_counts}]:
        with pytest.raises(ValueError): codec.read_rule(broken)
    with pytest.raises(ValueError,match="exact built-in"):
        codec.rule_record(type("Changed",(OrthogonalBlackCounts,),{})(rule.orthogonal_counts))
    with pytest.raises(ValueError,match="dimensions"): ShadingRecipe(3,2,(rule,)).create_empty()
    same=ShadingRecipe(2,3,(rule,rule))
    assert codec.read_recipe(codec.recipe_record(same)) == same
    conflict=replace(same,rules=(rule,OrthogonalBlackCounts(((None,)*3,)*2)))
    with pytest.raises(ValueError,match="same counts"): codec.recipe_record(conflict)
    with pytest.raises(ValueError,match="same counts"): saved.puzzle_record(conflict,[],seed=0)
    # These are distinct channels, not two encodings of the same white clue.
    recipe=ShadingRecipe(2,3,(rule,AdjacentBlackCounts(((None,None,1),(None,None,None)),False),
                              ComponentAreaClues(((3,0,0),(0,0,0)))))
    plan=api.read_request(request(recipe)).plan
    assert plan["orthogonal_counts"] == [[2,None,None],[None,None,None]]
    assert plan["neighbor_counts"] == [[None,None,1],[None,None,None]]
    assert plan["component_areas"] == [[3,0,0],[0,0,0]]
    for bad in [{},[[None]],[[False]*3]*2,[[5]*3]*2]:
        broken=request(ShadingRecipe(2,3,(rule,)));broken["rules"][0]["parameters"]["orthogonal_counts"]=bad
        with pytest.raises(ValueError): api.read_request(broken)


def test_five_rule_paint_area_example_has_an_editable_black_number_and_no_extra_hints():
    recipe=codec.load_recipe(EXAMPLES/"shading-paint-area-recipe.json")
    assert len(recipe.rules) == 5 and all_answers(recipe) == {(1,1,0,1,0,0)}
    # Some standard conditions are redundant on this particular tiny example.
    for omitted,count in enumerate([2,6,1,2,1]):
        subset=replace(recipe,rules=tuple(r for i,r in enumerate(recipe.rules) if i!=omitted))
        expected={b for b in product((0,1),repeat=6) if all(oracle.accepts(r,b,2,3) for r in subset.rules)}
        assert len(expected)==count and all_answers(subset)==expected
    assert oracle.analyze(recipe)["completion_count"] == 1
    result=worker.generate_request(request(recipe))
    assert result["status"] == "ok" and result["clues"] == []
    assert result["record"]["solution"] == [[1,1,0],[1,0,0]]
    assert saved.verify(result["record"])["unique"]
    shown=saved.show(result["record"])
    assert "clue colors remain free" in shown and "Answer template: ???/???" in shown
    assert "2 . .\n. . ." in shown
    assert 1 in deductions.explain_puzzle(result["record"])["rules_without_deductions"]
    answer=[1,1,0,1,0,0]
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":[],"answer":answer}) == {"status":"ok","correct":True}
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":[],"answer":[0,1,0,1,0,0]}) == {"status":"ok","correct":False}
    white=replace(recipe,rules=(AdjacentBlackCounts(recipe.rules[0].orthogonal_counts,False),*recipe.rules[1:]))
    assert worker.generate_request(request(white))["status"] == "unsatisfiable"
    plan=api.read_request(request(recipe)).plan
    assert {c["kind"] for c in plan["requirements"]["channels"]} == {"binary-cells","cell-orthogonal-counts","cell-regions","cell-givens"}
    p=recipe.create_empty();assert p.solution_vars is not None and len(p.solution_vars)==6
    p.add(unique());assert p.solve() is not None
    configured=composed.with_constraints(recipe,composed.CellCount("black",3))
    artifact=composed_saved.generate_record(composed.recipe_record(configured),seed=0)
    assert "clue colors remain free" in composed_saved.show(artifact)
    assert "Answer template: ???/???" in composed_saved.show(artifact)
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**request(recipe),"family":family})


def test_only_existing_resource_limits_apply():
    recipe=ShadingRecipe(5,5,(OrthogonalBlackCounts(((None,)*5,)*5),))
    assert codec.read_recipe(codec.recipe_record(recipe)) == recipe
    with pytest.raises(ValueError,match="at most 9"): api.read_request(request(recipe))
    with pytest.raises(ValueError,match="at most 9"): oracle.analyze(recipe)
    with pytest.raises(ValueError,match="at most 25"):
        codec.recipe_record(ShadingRecipe(6,5,(OrthogonalBlackCounts(((None,)*5,)*6),)))
