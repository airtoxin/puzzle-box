"""Maximal component predicates versus color-neutral union-find areas."""

from dataclasses import replace
import importlib
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from puzzle import Cell, at_least_one, unique
from puzzle_defs import ComponentAreaClues, ShadingRecipe, WhiteIslandAreas

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


def areas(bits,rows,cols):
    parent=list(range(rows*cols))
    def root(i):
        while parent[i]!=i:i=parent[i]
        return i
    for i in range(rows*cols):
        for j in range(i):
            if bits[i]==bits[j] and abs(i//cols-j//cols)+abs(i%cols-j%cols)==1:
                parent[root(i)]=root(j)
    return tuple(sum(root(j)==root(i) for j in range(rows*cols)) for i in range(rows*cols))


def all_answers(recipe):
    p=recipe.create_empty();answers=set()
    while (solution:=p.solve(seed=0)) is not None:
        bits=tuple(v for row in p.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        p.add(at_least_one(p.black[c]!=solution.value(p.black[c]) for c in p.board.cells))
    return answers


@pytest.mark.parametrize("rows,cols,origin",[(1,1,0),(1,4,1),(2,3,0),(2,3,1)])
def test_complete_answers_match_union_find_and_floods_for_each_clue_size(rows,cols,origin):
    boards=list(product((0,1),repeat=rows*cols))
    measured={bits:areas(bits,rows,cols) for bits in boards}
    for n in range(rows*cols+2):
        grid=tuple(tuple(n if r*cols+c==origin else 0 for c in range(cols)) for r in range(rows))
        rule=ComponentAreaClues(grid)
        expected={b for b in boards if n==0 or measured[b][origin]==n}
        assert {b for b in boards if oracle.accepts(rule,b,rows,cols)}==expected
        assert all_answers(ShadingRecipe(rows,cols,(rule,)))==expected


def test_three_by_three_dense_clues_match_both_independent_algorithms():
    for bits in product((0,1),repeat=9):
        measured=areas(bits,3,3)
        grid=tuple(tuple(measured[r*3+c] for c in range(3)) for r in range(3))
        assert oracle.accepts(ComponentAreaClues(grid),bits,3,3)
        changed=[list(row) for row in grid];changed[1][1]=measured[4]%9+1
        assert not oracle.accepts(ComponentAreaClues(tuple(tuple(row) for row in changed)),bits,3,3)


def test_color_freedom_absence_repeated_clues_and_unnumbered_components():
    for grid in [((0,),),((1,),)]:
        assert all_answers(ShadingRecipe(1,1,(ComponentAreaClues(grid),)))=={(0,),(1,)}
    assert all_answers(ShadingRecipe(1,3,(ComponentAreaClues(((3,3,3),)),)))=={(0,0,0),(1,1,1)}
    assert all_answers(ShadingRecipe(1,3,(ComponentAreaClues(((2,0,0),)),)))=={(0,0,1),(1,1,0)}
    assert not all_answers(ShadingRecipe(1,3,(ComponentAreaClues(((2,3,0),)),)))
    assert not all_answers(ShadingRecipe(1,1,(ComponentAreaClues(((99,),)),)))
    rule=ComponentAreaClues(((9,0,0),(0,0,0),(0,0,0)))
    for color in (0,1):
        p=ShadingRecipe(3,3,(rule,rule)).build_from_clues([(Cell(r,c),color) for r,c in product(range(3),repeat=2)])
        assert p.solution_vars is not None and len(p.solution_vars)==9
        p.add(unique());assert p.solve() is not None


@pytest.mark.parametrize("bad",[{},[],[[]],[[None]],[[True]],[[1.0]],[[-1]],[[100]],[[0],[0,0]],[[0]*5,[0]*5]])
def test_strict_numeric_grids_and_resource_bound(bad):
    with pytest.raises(ValueError):ComponentAreaClues(bad)
    with pytest.raises(ValueError):codec.read_rule({"type":"component-area-clues","component_areas":bad})


def test_immutable_codec_shared_layout_and_different_numeric_meanings():
    raw: Any=[[1,0,0],[0,0,4]]
    rule=ComponentAreaClues(raw);raw[0][0]=8
    assert rule.component_areas==((1,0,0),(0,0,4))
    assert codec.read_rule(codec.rule_record(rule))==rule
    with pytest.raises(ValueError):codec.read_rule({**codec.rule_record(rule),"extra":0})
    with pytest.raises(ValueError):codec.read_rule({"type":"component-area-clues","component_areas":rule.component_areas})
    with pytest.raises(ValueError,match="exact built-in"):codec.rule_record(type("Changed",(ComponentAreaClues,),{})(rule.component_areas))
    with pytest.raises(ValueError,match="dimensions"):ShadingRecipe(3,2,(rule,)).create_empty()
    same=ShadingRecipe(2,3,(rule,rule))
    assert codec.read_recipe(codec.recipe_record(same))==same
    conflict=replace(same,rules=(rule,ComponentAreaClues(((0,0,1),(4,0,0)))))
    with pytest.raises(ValueError,match="same numbers"):codec.recipe_record(conflict)
    with pytest.raises(ValueError,match="same numbers"):saved.puzzle_record(conflict,[],seed=0)
    separate=ShadingRecipe(2,3,(rule,WhiteIslandAreas(((0,0,0),(0,0,4)))))
    plan=api.read_request(request(separate)).plan
    assert plan["component_areas"]==[[1,0,0],[0,0,4]]
    assert plan["island_areas"]==[[0,0,0],[0,0,4]]


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],"parameters":{k:v for k,v in r.items() if k!="type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_choco_banana_uses_black_and_white_numbered_cells_without_forcing_color():
    recipe=codec.load_recipe(EXAMPLES/"shading-choco-banana-recipe.json")
    expected={(1,0,1,0,0,0)}
    assert all_answers(recipe)==expected
    assert oracle.analyze(recipe)["completion_count"]==1
    result=worker.generate_request(request(recipe))
    assert result["status"]=="ok" and result["clues"]==[]
    assert saved.verify(result["record"])["unique"]
    text=saved.show(result["record"])
    assert "Answer template: ???/???" in text and "clue colors remain free" in text
    assert "1 0 0\n0 0 4" in text
    assert deductions.explain_puzzle(result["record"])["rules_without_deductions"]==[1,2,3]
    answer=[v for row in result["record"]["solution"] for v in row]
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":result["clues"],"answer":answer})=={"status":"ok","correct":True}
    wrong=list(answer);wrong[0]=0
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":result["clues"],"answer":wrong})=={"status":"ok","correct":False}
    combined=composed.with_constraints(recipe,composed.CellCount("black",2))
    record=composed_saved.generate_record(composed.recipe_record(combined),seed=0)
    assert "Fixed containing-component areas" in composed_saved.show(record)
    plan=api.read_request(request(recipe)).plan
    assert plan["component_areas"]==[[1,0,0],[0,0,4]]
    p=recipe.create_empty();assert p.solution_vars is not None and len(p.solution_vars)==6
    for family in ("slitherlink","coupled"):
        with pytest.raises(ValueError):api.read_request({**request(recipe),"family":family})
    broken={**result["record"],"rows":2,"cols":5,"solution":[[0]*5,[0]*5],
            "rules":[{"type":"component-area-clues","component_areas":[[0]*5,[0]*5]}]}
    with pytest.raises(ValueError,match="at most 9"):saved.show(broken)
