"""Existing marker and visibility rules versus direct endpoint-ray walks."""

import importlib
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from puzzle import Cell, at_least_one
from puzzle_defs import (ConnectedWhite, NoBlack2x2, NoWhite2x2, ShadingRecipe,
                         WhiteEndpointMarkers, WhiteVisibilityCounts, numbered_white_endpoints)

EXAMPLES=Path(__file__).resolve().parents[4]/"examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    oracle=importlib.import_module("analyze_shading")
    codec=importlib.import_module("shading_recipe")
    saved=importlib.import_module("generate_shading")
    api=importlib.import_module("web_catalog")
    worker=importlib.import_module("web_worker")
    checks=importlib.import_module("web_answers")
    deductions=importlib.import_module("explain_shading")


def reference(bits,rows,cols):
    white={(r,c) for r in range(rows) for c in range(cols) if not bits[r*cols+c]}
    lengths={}
    for p in white:
        adjacent=[q for q in white if abs(p[0]-q[0])+abs(p[1]-q[1]) == 1]
        if len(adjacent) != 1: continue
        q=adjacent[0]
        direction=(q[0]-p[0],q[1]-p[1])
        n=1  # Include the circled origin, not only its neighbor.
        while q in white:
            n+=1
            q=(q[0]+direction[0],q[1]+direction[1])
        lengths[p]=n
    markers=tuple(tuple(int((r,c) in lengths) for c in range(cols)) for r in range(rows))
    counts=tuple(tuple(lengths.get((r,c),0) for c in range(cols)) for r in range(rows))
    return markers,counts


def all_answers(recipe):
    p=recipe.create_empty()
    answers=set()
    while (solution:=p.solve(seed=0)) is not None:
        bits=tuple(v for row in p.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        p.add(at_least_one(p.black[c] != solution.value(p.black[c]) for c in p.board.cells))
    return answers


def test_every_derived_two_by_three_numeric_layout_matches_independent_direct_rays():
    boards=list(product((0,1),repeat=6))
    groups={}
    for bits in boards: groups.setdefault(reference(bits,2,3),set()).add(bits)
    for (markers,lengths),expected in groups.items():
        rules=numbered_white_endpoints(markers,lengths)
        assert {b for b in boards if all(oracle.accepts(r,b,2,3) for r in rules)} == expected
        assert all_answers(ShadingRecipe(2,3,rules)) == expected


def fixed(markers,lengths,white):
    rows,cols=len(markers),len(markers[0])
    return ShadingRecipe(rows,cols,numbered_white_endpoints(markers,lengths)).build_from_clues(
        [(Cell(r,c),int((r,c) not in white)) for r in range(rows) for c in range(cols)])


def test_origin_is_included_and_straight_lengths_never_follow_a_turn():
    assert all_answers(ShadingRecipe(1,2,numbered_white_endpoints(((1,1),),((2,2),)))) == {(0,0)}
    assert not all_answers(ShadingRecipe(1,2,numbered_white_endpoints(((1,1),),((1,0),))))
    markers=((1,0,0),(0,0,1))
    white={(0,0),(0,1),(0,2),(1,2)}
    assert fixed(markers,((3,0,0),(0,0,2)),white).solve() is not None
    assert fixed(markers,((4,0,0),(0,0,2)),white).solve() is None
    assert fixed(markers,((3,0,0),(0,0,3)),white).solve() is None
    assert fixed(((1,1,0,0),),((2,0,0,0),),{(0,0),(0,1),(0,3)}).solve() is not None
    assert fixed(((1,1,0,0),),((3,0,0,0),),{(0,0),(0,1),(0,3)}).solve() is None


def test_zero_means_unnumbered_and_classic_placement_does_not_restrict_generic_hybrids():
    markers=((1,0,0),(0,0,1))
    unnumbered=numbered_white_endpoints(markers,((0,0,0),(0,0,0)))
    assert all_answers(ShadingRecipe(2,3,unnumbered)) == all_answers(ShadingRecipe(2,3,(WhiteEndpointMarkers(markers),)))
    with pytest.raises(ValueError,match="marked circles"): numbered_white_endpoints(((0,),),((1,),))
    hybrid=ShadingRecipe(1,1,(WhiteEndpointMarkers(((0,),)),WhiteVisibilityCounts(((1,),))))
    assert all_answers(hybrid) == {(0,)}  # An independent sight number, not a numbered endpoint.


@pytest.mark.parametrize("bad", [{},[],[[None]],[[True]],[[1.5]],[[-1]],[[100]],[[2,0]]])
def test_invalid_lengths_are_rejected(bad):
    with pytest.raises(ValueError): numbered_white_endpoints(((1,),),bad)


def test_mutable_input_is_copied_and_serialization_uses_only_existing_rule_ids():
    markers: Any=[[1,1]]
    lengths: Any=[[2,0]]
    rules=numbered_white_endpoints(markers,lengths)
    markers[0][0]=0; lengths[0][0]=99
    assert rules == (WhiteEndpointMarkers(((1,1),)),WhiteVisibilityCounts(((2,0),)))
    recipe=ShadingRecipe(1,2,rules)
    record=codec.recipe_record(recipe)
    assert [r["type"] for r in record["rules"]] == ["white-endpoint-markers","white-visibility-counts"]
    assert codec.read_recipe(record) == recipe


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_numbered_example_is_unique_without_added_cell_clues_and_round_trips():
    recipe=codec.load_recipe(EXAMPLES/"shading-numbered-nurimisaki-recipe.json")
    built=ShadingRecipe(2,3,(*numbered_white_endpoints(((1,0,0),(0,0,1)),((3,0,0),(0,0,2))),
                            ConnectedWhite(),NoWhite2x2(),NoBlack2x2()))
    assert recipe == built and all_answers(recipe) == {(0,0,0,1,1,0)}
    result=worker.generate_request(request(recipe))
    assert result["status"] == "ok" and result["clues"] == []
    assert saved.verify(result["record"])["unique"]
    text=saved.show(result["record"])
    assert "3 . .\n. . 2" in text and "o . .\n. . o" in text and "unsupported" not in text.lower()
    assert {1,2} <= set(deductions.explain_puzzle(result["record"])["rules_without_deductions"])
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":[],
                               "answer":[0,0,0,1,1,0]}) == {"status":"ok","correct":True}
