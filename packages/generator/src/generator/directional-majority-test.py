"""Directional runs and majority counts, with independent finite references."""

from dataclasses import replace
import importlib
from itertools import product
import json
from pathlib import Path
from typing import Any

import pytest

from puzzle import at_least_one, unique
from puzzle_defs import BlackCount, DirectionalRunLimit, RoomBlackCount, RoomMajorityCount, ShadingRecipe

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
    p=recipe.create_empty();answers=set()
    while (s:=p.solve(seed=0)) is not None:
        bits=tuple(v for row in p.result(s) for v in row)
        assert bits not in answers
        answers.add(bits)
        p.add(at_least_one(p.black[c]!=s.value(p.black[c]) for c in p.board.cells))
    return answers


def reference(rule,bits,rows,cols):
    if type(rule) is DirectionalRunLimit:
        # Walk backward from each cell along both axes. This checks maximal run
        # lengths without the encoder's windows or the finite checker's groupby.
        for r in range(rows):
            for c in range(cols):
                horizontal = bits[r*cols+c] == int(rule.horizontal_black)
                dr,dc = (1,0) if horizontal else (0,1)
                length,s,t = 0,r,c
                while s >= 0 and t >= 0 and bits[s*cols+t] == bits[r*cols+c]:
                    length += 1;s-=dr;t-=dc
                if length > rule.max_length:
                    return False
        return True
    if type(rule) is RoomMajorityCount:
        hist={label:[0,0] for row in rule.rooms for label in row}
        for r in range(rows):
            for c in range(cols):
                hist[rule.rooms[r][c]][bits[r*cols+c]] += 1
        # An absolute-difference identity, not encoder cases or max(counts).
        return all(a+b+abs(a-b) == 2*rule.count for a,b in hist.values())
    return sum(bits) == rule.count


@pytest.mark.parametrize("rows,cols",[(1,1),(1,3),(3,1),(2,3),(3,2),(3,3)])
@pytest.mark.parametrize("maximum,horizontal_black",product((1,2),(False,True)))
def test_every_binary_board_matches_direction_reference_and_csp(rows,cols,maximum,horizontal_black):
    rule=DirectionalRunLimit(maximum,horizontal_black)
    boards=list(product((0,1),repeat=rows*cols))
    expected={b for b in boards if reference(rule,b,rows,cols)}
    assert {b for b in boards if oracle.accepts(rule,b,rows,cols)} == expected
    assert all_answers(ShadingRecipe(rows,cols,(rule,))) == expected


@pytest.mark.parametrize("rooms,count",[
    (((0,),),0),(((0,),),1),(((0,0,0),),1),(((0,0,0),),2),(((0,0,0),),3),
    (((0,0),(0,0)),1),(((0,0),(0,0)),2),(((0,0),(0,0)),3),(((0,0),(0,0)),4),
    (((0,0,1,1),),2),(((0,0,1),(0,0,1),(2,2,1)),2),
    (((0,0,1),(0,0,1),(2,2,1)),3),
])
def test_majority_including_ties_uses_each_room_not_the_whole_board(rooms,count):
    rule=RoomMajorityCount(rooms,count)
    rows,cols=len(rooms),len(rooms[0]);boards=list(product((0,1),repeat=rows*cols))
    expected={b for b in boards if reference(rule,b,rows,cols)}
    assert {b for b in boards if oracle.accepts(rule,b,rows,cols)} == expected
    assert all_answers(ShadingRecipe(rows,cols,(rule,))) == expected


def test_ties_are_allowed_and_majority_colors_vary_between_rooms():
    assert all_answers(ShadingRecipe(1,4,(RoomMajorityCount(((0,0,1,1),),2),))) == {
        (0,0,0,0),(0,0,1,1),(1,1,0,0),(1,1,1,1)}
    # The two cases of a tied majority coincide; an unconditional XOR is wrong.
    assert all_answers(ShadingRecipe(1,2,(RoomMajorityCount(((0,0),),1),))) == {(0,1),(1,0)}


def test_parallel_runs_are_free_but_perpendicular_runs_are_limited_and_swappable():
    black=BlackCount(3)
    assert all_answers(ShadingRecipe(1,3,(DirectionalRunLimit(),black))) == {(1,1,1)}
    assert not all_answers(ShadingRecipe(3,1,(DirectionalRunLimit(),black)))
    assert all_answers(ShadingRecipe(3,1,(DirectionalRunLimit(horizontal_black=False),black))) == {(1,1,1)}
    # A room boundary does not interrupt a global straight run.
    rooms=RoomBlackCount(((0,0,1),),0)
    assert not all_answers(ShadingRecipe(1,3,(DirectionalRunLimit(),rooms)))
    for horizontal in (False,True):
        recipe=ShadingRecipe(1,3,(DirectionalRunLimit(10**100,horizontal),BlackCount(0)))
        assert all_answers(recipe) == {(0,0,0)}  # Huge redundant bounds never reach CP-SAT.


@pytest.mark.parametrize("bad",[0,-1,True,1.0,"2",None])
def test_run_limit_is_a_strict_positive_integer(bad):
    with pytest.raises(ValueError): DirectionalRunLimit(bad)
    with pytest.raises(ValueError): codec.read_rule({"type":"directional-run-limit","max_length":bad,"horizontal_black":True})


@pytest.mark.parametrize("bad",[0,1,None,"black"])
def test_direction_is_a_strict_boolean(bad):
    with pytest.raises(ValueError): DirectionalRunLimit(horizontal_black=bad)


@pytest.mark.parametrize("bad",[-1,True,1.0,"2",None,10**100])
def test_majority_is_a_strict_bounded_nonnegative_count(bad):
    with pytest.raises(ValueError): RoomMajorityCount(((0,0),),bad)
    with pytest.raises(ValueError): codec.read_rule({"type":"room-majority-count","rooms":[[0,0]],"count":bad})


def test_exact_immutable_codecs_dimensions_and_shared_room_compatibility():
    raw:Any=[[5,5,5],[5,5,5]]
    majority=RoomMajorityCount(raw,3);raw[0][0]=1
    assert majority.rooms == ((0,0,0),(0,0,0))
    for rule in [majority,DirectionalRunLimit(3,False)]:
        record=codec.rule_record(rule)
        assert codec.read_rule(json.loads(json.dumps(record))) == rule
        for broken in [{**record,"extra":0},*[{k:v for k,v in record.items() if k != missing} for missing in record]]:
            with pytest.raises(ValueError): codec.read_rule(broken)
        changed=type("Changed",(type(rule),),{})(**{k:v for k,v in record.items() if k != "type"})
        with pytest.raises(ValueError,match="exact built-in"): codec.rule_record(changed)
    for bad in [{},[],[{}],[[0,1],[1,0]]]:
        with pytest.raises(ValueError): codec.read_rule({"type":"room-majority-count","rooms":bad,"count":1})
    with pytest.raises(ValueError,match="dimensions"): ShadingRecipe(3,2,(majority,)).create_empty()
    recipe=ShadingRecipe(2,3,(majority,RoomBlackCount(((0,0,0),(1,1,1)),1)))
    with pytest.raises(ValueError,match="same partition"): codec.recipe_record(recipe)
    with pytest.raises(ValueError,match="same partition"): api.read_request(request(recipe))


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_three_rule_example_contributes_generates_and_checks_with_existing_ui():
    recipe=codec.load_recipe(EXAMPLES/"shading-directional-majority-recipe.json")
    expected={(0,1,0,0,1,0,0,0,1),(0,1,0,1,0,0,0,0,1),
              (1,0,0,0,1,0,0,0,1),(1,0,0,1,0,0,0,0,1)}
    assert all_answers(recipe) == expected and oracle.analyze(recipe)["completion_count"] == 4
    for omit,count in [(0,18),(1,24),(2,32)]:
        subset=replace(recipe,rules=tuple(r for i,r in enumerate(recipe.rules) if i != omit))
        boards={b for b in product((0,1),repeat=9) if all(reference(r,b,3,3) for r in subset.rules)}
        assert len(boards) == count and all_answers(subset) == boards
    result=worker.generate_request(request(recipe))
    assert result["status"] == "ok" and len(result["clues"]) == 2
    bits=tuple(v for row in result["record"]["solution"] for v in row)
    assert bits in expected and saved.verify(result["record"])["unique"]
    assert "parallel runs are unrestricted" in saved.show(result["record"])
    assert "Ties are allowed" in saved.show(result["record"])
    assert deductions.explain_puzzle(result["record"])["rules_without_deductions"] == [1,2]
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":result["clues"],
                               "answer":list(bits)}) == {"status":"ok","correct":True}
    p=recipe.build_from_clues(saved._read_record(result["record"])[1])
    assert p.solution_vars is not None and len(p.solution_vars) == 9
    p.add(unique());assert p.solve() is not None
    plan=api.read_request(request(recipe)).plan
    assert plan["rooms"] == [[0,0,1],[0,0,1],[2,2,1]]
    assert {c["kind"] for c in plan["requirements"]["channels"]} == {"binary-cells","cell-regions","cell-givens"}
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**request(recipe),"family":family})


def test_existing_file_and_web_bounds_and_oversized_majority_before_display():
    recipe=ShadingRecipe(5,5,(RoomMajorityCount(((0,)*5,)*5,13),DirectionalRunLimit()))
    assert codec.read_recipe(codec.recipe_record(recipe)) == recipe
    with pytest.raises(ValueError,match="at most 9"): api.read_request(request(recipe))
    with pytest.raises(ValueError,match="at most 9"): oracle.analyze(recipe)
    with pytest.raises(ValueError,match="at most 25"):
        codec.recipe_record(ShadingRecipe(6,5,(DirectionalRunLimit(),)))
    record={"format":saved.FORMAT,"rows":1,"cols":2,"rules":[{
        "type":"room-majority-count","rooms":[[0,0]],"count":10**100}],"clues":[],"solution":[[0,0]]}
    with pytest.raises(ValueError,match="cannot exceed"): saved.show(record)
