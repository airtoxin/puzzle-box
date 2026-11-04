"""Optional numbers: candidate covers versus independent numbered-anchor floods."""

from dataclasses import replace
import importlib
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from puzzle import Cell, at_least_one
from puzzle_defs import ShadingRecipe, WhiteAreaClues, WhiteIslandAreas

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


def anchor_reference(areas,bits):
    rows,cols=len(areas),len(areas[0])
    white={(r,c) for r in range(rows) for c in range(cols) if not bits[r*cols+c]}
    for r in range(rows):
        for c in range(cols):
            if not areas[r][c]: continue
            if (r,c) not in white: return False
            reached,todo=set(),[(r,c)]
            while todo:
                p=todo.pop()
                if p not in white or p in reached: continue
                reached.add(p)
                s,t=p
                todo.extend([(s-1,t),(s+1,t),(s,t-1),(s,t+1)])
            if len(reached) != areas[r][c]: return False
            if any(areas[s][t] > 0 for s,t in reached-{(r,c)}): return False
    return True


def all_answers(recipe):
    p=recipe.create_empty()
    answers=set()
    while (solution:=p.solve(seed=0)) is not None:
        bits=tuple(v for row in p.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        p.add(at_least_one(p.black[c] != solution.value(p.black[c]) for c in p.board.cells))
    return answers


@pytest.mark.parametrize("areas", [((0,),),((1,),),((2,),),((0,0,0),(0,0,0)),
    ((1,0,0),(0,0,0)),((2,0,0),(0,0,0)),((1,0),(0,1)),((2,2),),((99,0),),
    ((0,0,0),(0,1,0),(0,0,0))])
def test_all_answers_match_anchor_flood_and_component_checker(areas):
    rows,cols=len(areas),len(areas[0])
    rule=WhiteAreaClues(areas)
    masks=list(product((0,1),repeat=rows*cols))
    expected={b for b in masks if anchor_reference(areas,b)}
    assert {b for b in masks if oracle.accepts(rule,b,rows,cols)} == expected
    assert all_answers(ShadingRecipe(rows,cols,(rule,))) == expected


def test_unnumbered_components_are_allowed_without_relaxing_number_cardinality():
    areas=((1,0),(0,0))
    optional=all_answers(ShadingRecipe(2,2,(WhiteAreaClues(areas),)))
    required=all_answers(ShadingRecipe(2,2,(WhiteIslandAreas(areas),)))
    assert optional == {(0,1,1,0),(0,1,1,1)} and required == {(0,1,1,1)}
    assert not all_answers(ShadingRecipe(1,2,(WhiteAreaClues(((2,2),)),)))
    assert all_answers(ShadingRecipe(1,2,(WhiteAreaClues(((2,0),)),))) == {(0,0)}
    assert all_answers(ShadingRecipe(1,2,(WhiteAreaClues(((0,0),)),))) == set(product((0,1),repeat=2))
    assert all_answers(ShadingRecipe(1,2,(WhiteIslandAreas(((0,0),)),))) == {(1,1)}


@pytest.mark.parametrize("bad", [{},[],[[]],[[1],[0,0]],[[False]],[[1.0]],[[None]],[[-1]],[[100]]])
def test_area_schema_is_strict(bad):
    with pytest.raises(ValueError): WhiteAreaClues(bad)
    with pytest.raises(ValueError): codec.read_rule({"type":"white-area-clues","areas":bad})


def test_copy_bounds_dimensions_exact_codec_and_shared_display_meaning(monkeypatch):
    raw: Any=[[1,0],[0,0]]
    rule=WhiteAreaClues(raw)
    raw[0][0]=2
    assert rule.areas == ((1,0),(0,0))
    assert codec.read_rule(codec.rule_record(rule)) == rule
    with pytest.raises(ValueError): codec.read_rule({**codec.rule_record(rule),"extra":0})
    with pytest.raises(ValueError,match="exact built-in"): codec.rule_record(type("Changed",(WhiteAreaClues,),{})(rule.areas))
    with pytest.raises(ValueError,match="dimensions"): ShadingRecipe(1,4,(rule,)).create_empty()
    both=ShadingRecipe(2,2,(rule,WhiteIslandAreas(rule.areas)))
    assert codec.read_recipe(codec.recipe_record(both)) == both
    assert all_answers(both) == {(0,1,1,1)}  # Conjunction still requires one number in every component.
    conflict=replace(both,rules=(rule,WhiteIslandAreas(((0,0),(0,0)))))
    with pytest.raises(ValueError,match="same areas"): codec.recipe_record(conflict)
    with pytest.raises(ValueError,match="same areas"): saved.puzzle_record(conflict,[],seed=0)
    module=importlib.import_module("puzzle_defs.puzzles.white_island_areas")
    monkeypatch.setattr(module,"enumerate_connected_regions",lambda *a,**k:pytest.fail("Must not enumerate"))
    with pytest.raises(ValueError,match="9 board cells"): WhiteAreaClues(((0,)*4,)*3)
    assert all_answers(ShadingRecipe(1,1,(WhiteAreaClues(((0,),)),))) == {(0,),(1,)}


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_mochikoro_composition_requires_unnumbered_components_and_retains_a_hint():
    recipe=codec.load_recipe(EXAMPLES/"shading-mochikoro-recipe.json")
    answers={(0,1,1,1,0,0),(0,1,0,1,0,1)}
    assert all_answers(recipe) == answers
    assert oracle.analyze(recipe)["completion_count"] == 2
    required=replace(recipe,rules=(WhiteIslandAreas(recipe.rules[0].areas),*recipe.rules[1:]))
    assert not all_answers(required)
    result=worker.generate_request(request(recipe))
    assert result["status"] == "ok" and len(result["clues"]) == 1
    assert saved.verify(result["record"])["unique"]
    assert "Unnumbered components are allowed" in saved.show(result["record"])
    assert "exactly one number per island" not in saved.show(result["record"])
    assert "Fixed white island areas" in saved.show(result["record"])
    assert 1 in deductions.explain_puzzle(result["record"])["rules_without_deductions"]
    answer=[v for row in result["record"]["solution"] for v in row]
    assert tuple(answer) in answers
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":result["clues"],
                               "answer":answer}) == {"status":"ok","correct":True}
    assert len(result["record"]["solution"]) == 2
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**request(recipe),"family":family})
