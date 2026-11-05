"""Per-room false counts: exact truth values, shared UI and answer projection."""

from dataclasses import replace
import importlib
from itertools import product
import json
from pathlib import Path
from typing import Any

import pytest

from puzzle import at_least_one, unique
from puzzle_defs import (AdjacentBlackCounts, ConnectedWhite, NonTouchingBlack,
                         OneFalseAdjacentCountPerRoom, RoomBlackCount, ShadingRecipe)

EXAMPLES = Path(__file__).resolve().parents[4]/"examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    oracle = importlib.import_module("analyze_shading")
    codec = importlib.import_module("shading_recipe")
    saved = importlib.import_module("generate_shading")
    deductions = importlib.import_module("explain_shading")
    api = importlib.import_module("web_catalog")
    worker = importlib.import_module("web_worker")
    checks = importlib.import_module("web_answers")


def bit_reference(rooms, counts, bits):
    rows, cols = len(rooms), len(rooms[0])
    mines = sum(b << i for i,b in enumerate(bits))
    # Independent bit masks, without board.neighbors or distance-based checks.
    mismatches = {label:[] for row in rooms for label in row}
    for r,row in enumerate(counts):
        for c,given in enumerate(row):
            if given is None:
                continue
            if bits[r*cols+c]:
                return False
            mask = sum(1 << (s*cols+t) for s,t in ((r-1,c),(r+1,c),(r,c-1),(r,c+1))
                       if 0 <= s < rows and 0 <= t < cols)
            mismatches[rooms[r][c]].append((mines & mask).bit_count() != given)
    return all(errors.count(True) == 1 for errors in mismatches.values())


def all_answers(recipe):
    p = recipe.create_empty()
    answers = set()
    while (s := p.solve(seed=0)) is not None:
        bits = tuple(v for row in p.result(s) for v in row)
        assert bits not in answers
        answers.add(bits)
        p.add(at_least_one(p.black[c] != s.value(p.black[c]) for c in p.board.cells))
    return answers


@pytest.mark.parametrize("rooms,counts", [
    (((0,),), ((None,),)), (((0,),), ((0,),)), (((0,),), ((1,),)),
    (((0,0,0),), ((0,None,0),)), (((0,0,0),), ((0,None,1),)),
    (((0,1,2),), ((0,0,0),)),
    (((0,0),(1,1)), ((0,None),(None,1))),
    (((0,0,1),(0,1,1)), ((0,None,1),(None,1,None))),
    (((0,0,0),(1,1,1)), ((0,None,1),(None,1,None))),
    (((0,0,0),(0,0,0)), ((0,None,1),(None,1,None))),
    (((0,0,0),(0,0,0),(0,0,0)), ((0,None,None),(None,4,None),(None,None,8))),
])
def test_all_projected_answers_match_bit_masks_and_finite_checker(rooms,counts):
    rule = OneFalseAdjacentCountPerRoom(rooms,counts)
    rows,cols = len(rooms),len(rooms[0])
    boards = list(product((0,1),repeat=rows*cols))
    expected = {b for b in boards if bit_reference(rooms,counts,b)}
    assert {b for b in boards if oracle.accepts(rule,b,rows,cols)} == expected
    assert all_answers(ShadingRecipe(rows,cols,(rule,))) == expected


def test_exactly_one_false_not_a_free_selector_and_not_one_per_board():
    rule = OneFalseAdjacentCountPerRoom(((0,0,0),),((0,None,0),))
    # Middle white -> zero false; middle black -> two false. Neither is valid.
    assert not all_answers(ShadingRecipe(1,3,(rule,)))
    rule = OneFalseAdjacentCountPerRoom(((0,1),),((1,1),))
    assert all_answers(ShadingRecipe(1,2,(rule,))) == {(0,0)}  # one false in EACH room
    assert all_answers(ShadingRecipe(1,1,(OneFalseAdjacentCountPerRoom(((0,),),((8,),)),))) == {(0,)}


def test_numbers_are_white_and_neighbors_across_room_borders_are_counted():
    rule = OneFalseAdjacentCountPerRoom(((0,0,1),(0,1,1)),((0,None,None),(None,None,None)))
    # The second room has no clues, irrespective of a valid false clue in room 0.
    assert not all_answers(ShadingRecipe(2,3,(rule,)))
    rule = OneFalseAdjacentCountPerRoom(((0,0,1),(0,1,1)),((0,None,0),(None,None,None)))
    assert (0,1,0,0,0,0) in all_answers(ShadingRecipe(2,3,(rule,)))
    # Top-middle is across the room boundary from the top-right zero clue.
    assert not oracle.accepts(rule,(0,0,0,0,0,0),2,3)


@pytest.mark.parametrize("bad", [{}, [], [[]], [[0],[1,2]], [[True]], [[1.0]], [[-1]], [[9]], [["."]]])
def test_invalid_counts_and_room_grids_are_rejected(bad):
    with pytest.raises(ValueError): OneFalseAdjacentCountPerRoom(((0,),),bad)
    with pytest.raises(ValueError): codec.read_rule({"type":"one-false-adjacent-count-per-room","rooms":[[0]],"neighbor_counts":bad})
    with pytest.raises(ValueError): OneFalseAdjacentCountPerRoom(bad,((0,),))


def test_canonical_immutable_exact_codecs_and_shared_input_contracts():
    rooms: Any = [[5,5,5],[5,5,5]]
    counts: Any = [[0,None,1],[None,1,None]]
    rule = OneFalseAdjacentCountPerRoom(rooms,counts)
    rooms[0][0]=1;counts[0][0]=None
    assert rule.rooms == ((0,0,0),(0,0,0)) and rule.neighbor_counts[0][0] == 0
    record = codec.rule_record(rule)
    assert codec.read_rule(json.loads(json.dumps(record))) == rule
    for broken in [{**record,"extra":0},{k:v for k,v in record.items() if k != "rooms"},
                   {**record,"rooms":{}},{**record,"neighbor_counts":[{}]}]:
        with pytest.raises(ValueError): codec.read_rule(broken)
    with pytest.raises(ValueError,match="exact built-in"):
        codec.rule_record(type("Changed",(OneFalseAdjacentCountPerRoom,),{})(rule.rooms,rule.neighbor_counts))
    with pytest.raises(ValueError,match="dimensions"): ShadingRecipe(3,2,(rule,)).create_empty()
    recipe = ShadingRecipe(2,3,(rule,RoomBlackCount(((0,0,0),(1,1,1)),1)))
    with pytest.raises(ValueError,match="same partition"): codec.recipe_record(recipe)
    recipe = ShadingRecipe(2,3,(rule,AdjacentBlackCounts(((None,)*3,)*2,False)))
    with pytest.raises(ValueError,match="same neighbor counts"): codec.recipe_record(recipe)
    with pytest.raises(ValueError,match="same neighbor counts"): api.read_request(request(recipe))


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_shared_numbers_can_be_false_for_four_neighbors_and_true_for_eight():
    counts=((1,None),(None,None))
    recipe=ShadingRecipe(2,2,(OneFalseAdjacentCountPerRoom(((0,0),(0,0)),counts),
                              AdjacentBlackCounts(counts,True)))
    assert api.read_request(request(recipe)).plan["neighbor_counts"] == [[1,None],[None,None]]
    assert all_answers(recipe) == {(0,0,0,1)}


def test_three_rule_example_generates_uniquely_without_extra_hints_and_checks():
    recipe = codec.load_recipe(EXAMPLES/"shading-usowan-recipe.json")
    assert {type(r) for r in recipe.rules} == {OneFalseAdjacentCountPerRoom,NonTouchingBlack,ConnectedWhite}
    assert all_answers(recipe) == {(0,1,0,0,0,0)}
    # Both independently reusable companions make a real difference here.
    for rules,count in [(recipe.rules[:1],8),(recipe.rules[:2],2),
                        ((recipe.rules[0],recipe.rules[2]),4)]:
        subset=replace(recipe,rules=rules)
        expected={b for b in product((0,1),repeat=6) if all(bit_reference(r.rooms,r.neighbor_counts,b)
                  if type(r) is OneFalseAdjacentCountPerRoom else oracle.accepts(r,b,2,3) for r in rules)}
        assert len(expected) == count and all_answers(subset) == expected
    assert oracle.analyze(recipe)["completion_count"] == 1
    result = worker.generate_request(request(recipe))
    assert result["status"] == "ok" and result["clues"] == []
    assert result["record"]["solution"] == [[0,1,0],[0,0,0]]
    assert saved.verify(result["record"]) == {"valid":True,"unique":True,"irreducible":True,"clue_count":0}
    shown = saved.show(result["record"])
    assert "exactly one given count differs" in shown and "Answer template: .??/.??" in shown
    assert "1 . .\n2 . ." in shown
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":[],
                               "answer":[0,1,0,0,0,0]}) == {"status":"ok","correct":True}
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":[],
                               "answer":[0,0,0,0,0,1]}) == {"status":"ok","correct":False}
    assert 1 in deductions.explain_puzzle(result["record"])["rules_without_deductions"]
    p = recipe.create_empty()
    assert p.solution_vars is not None and len(p.solution_vars) == 6
    p.add(unique());assert p.solve() is not None  # Witnesses do not alter visible uniqueness.
    plan = api.read_request(request(recipe)).plan
    assert plan["rooms"] == [[0,0,0],[0,0,0]] and plan["neighbor_counts"] == [[1,None,None],[2,None,None]]
    assert {c["kind"] for c in plan["requirements"]["channels"]} == {"binary-cells","cell-regions","cell-neighbor-counts","cell-givens"}
    truth = AdjacentBlackCounts(recipe.rules[0].neighbor_counts,False)
    # A known, renderable composition can be logically inconsistent.
    incompatible = replace(recipe,rules=(*recipe.rules,truth))
    assert worker.generate_request(request(incompatible))["status"] == "unsatisfiable"
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**request(recipe),"family":family})


def test_core_accepts_larger_boards_but_file_and_web_limits_remain():
    rooms=((0,)*5,)*5
    counts=((1,None,None,None,None),)+((None,)*5,)*4
    recipe=ShadingRecipe(5,5,(OneFalseAdjacentCountPerRoom(rooms,counts),))
    assert recipe.create_empty().solve() is not None
    assert codec.read_recipe(codec.recipe_record(recipe)) == recipe
    assert api.read_request(request(recipe)).recipe == recipe
    with pytest.raises(ValueError,match="at most 9"): oracle.analyze(recipe)
    too_large=ShadingRecipe(6,5,(OneFalseAdjacentCountPerRoom(((0,)*5,)*6,counts+((None,)*5,)),))
    assert codec.read_recipe(codec.recipe_record(too_large)) == too_large
