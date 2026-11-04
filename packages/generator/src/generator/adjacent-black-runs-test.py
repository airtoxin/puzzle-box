"""Cyclic mask clauses versus rotated linear runs and ring-component floods."""

from dataclasses import replace
import importlib
from itertools import groupby, product
from pathlib import Path
from typing import Any

import pytest

from puzzle import Cell, at_least_one, unique
from puzzle_defs import AdjacentBlackRuns, ConnectedBlack, ShadingRecipe

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


def signature(bits,rows,cols,r,c):
    # Start at NW, rotate at a white gap, and use linear groups. No production
    # bit-mask helper or finite checker's cycle-component traversal is used.
    ring=[bits[s*cols+t] if 0<=s<rows and 0<=t<cols else 0
          for s,t in [(r-1,c-1),(r-1,c),(r-1,c+1),(r,c+1),(r+1,c+1),(r+1,c),(r+1,c-1),(r,c-1)]]
    if all(ring): return (8,)
    gap=ring.index(0)
    ring=ring[gap:]+ring[:gap]
    lengths=tuple(sorted(sum(1 for _ in g) for v,g in groupby(ring) if v))
    return lengths or (0,)


def all_answers(recipe):
    p=recipe.create_empty()
    answers=set()
    while (solution:=p.solve(seed=0)) is not None:
        bits=tuple(v for row in p.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        p.add(at_least_one(p.black[c] != solution.value(p.black[c]) for c in p.board.cells))
    return answers


@pytest.mark.parametrize("rows,cols,r,c", [(3,3,1,1),(2,3,0,0),(2,3,0,1),(2,3,1,2)])
def test_complete_answer_sets_match_two_independent_run_checkers(rows,cols,r,c):
    boards=list(product((0,1),repeat=rows*cols))
    grouped={}
    for b in boards:
        if not b[r*cols+c]: grouped.setdefault(signature(b,rows,cols,r,c),set()).add(b)
    for clue,expected in grouped.items():
        grid=tuple(tuple(clue if (s,t)==(r,c) else None for t in range(cols)) for s in range(rows))
        rule=AdjacentBlackRuns(grid)
        assert {b for b in boards if oracle.accepts(rule,b,rows,cols)} == expected
        assert all_answers(ShadingRecipe(rows,cols,(rule,))) == expected


def fixed(clue,black,origin=(1,1),size=(3,3)):
    rows,cols=size
    grid=tuple(tuple(clue if (r,c)==origin else None for c in range(cols)) for r in range(rows))
    return ShadingRecipe(rows,cols,(AdjacentBlackRuns(grid),)).build_from_clues(
        [(Cell(r,c),int((r,c) in black)) for r in range(rows) for c in range(cols)])


def test_wraparound_runs_and_outside_gaps_are_not_lost():
    # NW and N touch across the producer's indexing boundary: one length-2 run.
    black={(0,0),(0,1)}
    assert fixed((2,),black).solve() is not None
    assert fixed((1,1),black).solve() is None
    assert fixed((8,),{(r,c) for r in range(3) for c in range(3)}-{(1,1)}).solve() is not None
    # On a corner, E and S remain separated by SE and the outside white gap.
    assert fixed((1,1),{(0,1),(1,0)},origin=(0,0),size=(2,2)).solve() is not None
    assert fixed((2,),{(0,1),(1,0)},origin=(0,0),size=(2,2)).solve() is None
    assert not all_answers(ShadingRecipe(1,1,(AdjacentBlackRuns((((1,),),)),)))


def test_zero_absence_and_multiple_components_have_distinct_meanings():
    assert all_answers(ShadingRecipe(1,1,(AdjacentBlackRuns(((None,),)),))) == {(0,),(1,)}
    p=ShadingRecipe(1,1,(AdjacentBlackRuns((((0,),),)),)).create_empty()
    p.add(unique())
    assert p.solve() is not None
    assert all_answers(ShadingRecipe(1,1,(AdjacentBlackRuns((((0,),),)),))) == {(0,)}
    grid=((None,None,None),(None,(1,1,1,1),None),(None,None,None))
    recipe=ShadingRecipe(3,3,(AdjacentBlackRuns(grid),))
    assert len(all_answers(recipe)) == 2
    assert not all_answers(replace(recipe,rules=(*recipe.rules,ConnectedBlack())))


@pytest.mark.parametrize("bad", [{},[],[[]],[[{}]],[[[]]],[[0]],[["1,2"]],[[[True]]],[[[1.0]]],
    [[[-1]]],[[[9]]],[[[0,1]]],[[[1,7]]],[[[1,1,1,1,1]]],[[None],[None,None]]])
def test_schema_is_strict_without_executable_or_unknown_clues(bad):
    with pytest.raises(ValueError): AdjacentBlackRuns(bad)
    with pytest.raises(ValueError): codec.read_rule({"type":"adjacent-black-runs","run_clues":bad})
    with pytest.raises(ValueError): AdjacentBlackRuns.ui.parameters[0].validate(bad,area=1,rows=1,cols=1)


def test_unordered_immutable_clues_round_trip_and_share_only_equal_multisets():
    raw: Any=[[[2,1],None],[None,None]]
    rule=AdjacentBlackRuns(raw)
    raw[0][0][0]=8
    assert rule.run_clues == (((1,2),None),(None,None))
    assert codec.read_rule(codec.rule_record(rule)) == rule
    with pytest.raises(ValueError): codec.read_rule({**codec.rule_record(rule),"extra":0})
    with pytest.raises(ValueError): codec.read_rule({"type":"adjacent-black-runs","run_clues":[[(1,2)]]})
    with pytest.raises(ValueError,match="exact built-in"): codec.rule_record(type("Changed",(AdjacentBlackRuns,),{})(rule.run_clues))
    with pytest.raises(ValueError,match="dimensions"): ShadingRecipe(1,4,(rule,)).create_empty()
    same=ShadingRecipe(2,2,(rule,AdjacentBlackRuns((((2,1),None),(None,None)))))
    assert codec.read_recipe(codec.recipe_record(same)) == same
    conflict=replace(same,rules=(rule,AdjacentBlackRuns((((3,),None),(None,None)))))
    with pytest.raises(ValueError,match="same clues"): codec.recipe_record(conflict)
    with pytest.raises(ValueError,match="same clues"): saved.puzzle_record(conflict,[],seed=0)


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_tapa_example_generates_checks_and_keeps_its_fixed_patterns():
    recipe=codec.load_recipe(EXAMPLES/"shading-tapa-recipe.json")
    assert all_answers(recipe) == {(1,0,0,1,0,1,1,1,1),(0,0,1,1,0,1,1,1,1)}
    assert oracle.analyze(recipe)["completion_count"] == 2
    result=worker.generate_request(request(recipe))
    assert result["status"] == "ok" and len(result["clues"]) == 1
    assert saved.verify(result["record"])["unique"]
    text=saved.show(result["record"])
    assert ". 1,2 .\n. 6 .\n. . ." in text and "cyclic eight-neighbor" in text
    assert 1 in deductions.explain_puzzle(result["record"])["rules_without_deductions"]
    answer=[v for row in result["record"]["solution"] for v in row]
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":result["clues"],
                               "answer":answer}) == {"status":"ok","correct":True}
    composed_recipe=composed.with_constraints(recipe,composed.CellCount("black",6))
    record=composed_saved.generate_record(composed.recipe_record(composed_recipe),seed=0)
    assert ". 1,2 .\n. 6 .\n. . ." in composed_saved.show(record)
    plan=api.read_request(request(recipe)).plan
    assert plan["black_run_clues"] == [[None,[1,2],None],[None,[6],None],[None,None,None]]
    puzzle=recipe.create_empty()
    assert puzzle.solution_vars is not None and len(puzzle.solution_vars) == 9
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**request(recipe),"family":family})
