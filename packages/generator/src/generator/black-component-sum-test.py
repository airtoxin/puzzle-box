"""Region witnesses versus per-circle union floods and whole black components."""

from dataclasses import replace
import importlib
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from generator import with_constraints
from puzzle import Cell, at_least_one
from puzzle_defs import (AdjacentBlackComponentSum, AdjacentBlackCounts, DistinctWhiteNumbers,
                         NoBlack2x2, RoomConnectedBlack, ShadingRecipe, WhiteIslandAreas, WhiteVisibilityCounts)
from puzzle_defs.puzzles.adjacent_black_component_sum import DEFAULT_COMPONENT_COUNTS

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    oracle = importlib.import_module("analyze_shading")
    codec = importlib.import_module("shading_recipe")
    saved = importlib.import_module("generate_shading")
    composed = importlib.import_module("composed_shading_recipe")
    composed_saved = importlib.import_module("generate_composed_shading")
    deductions = importlib.import_module("explain_shading")
    api = importlib.import_module("web_catalog")
    worker = importlib.import_module("web_worker")
    checks = importlib.import_module("web_answers")


def union_reference(counts,bits):
    rows,cols = len(counts),len(counts[0])
    black = {(r,c) for r in range(rows) for c in range(cols) if bits[r*cols+c]}
    for r in range(rows):
        for c in range(cols):
            n = counts[r][c]
            if n is None:
                continue
            if (r,c) in black:
                return False
            reached = set()
            todo = [(r-1,c),(r+1,c),(r,c-1),(r,c+1)]
            while todo:
                p = todo.pop()
                if p not in black or p in reached:
                    continue
                reached.add(p)
                s,t = p
                todo.extend([(s-1,t),(s+1,t),(s,t-1),(s,t+1)])
            if len(reached) != n:
                return False
    return True


def all_answers(recipe):
    puzzle = recipe.create_empty()
    answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(puzzle.black[c] != solution.value(puzzle.black[c]) for c in puzzle.board.cells))
    return answers


@pytest.mark.parametrize("counts", [((None,),), ((0,),), ((1,),), DEFAULT_COMPONENT_COUNTS,
    ((None,None,None),(None,8,None),(None,None,None)),
    ((None,None,None),(None,2,None),(None,None,None)),
    ((None,None,None),(None,0,None),(None,None,None)),
    ((None,2,None),(None,None,None),(None,2,None)), ((0,0),(0,0)), ((99,None),(None,None))])
def test_all_answers_match_distinct_component_checker_and_union_flood(counts):
    rows,cols = len(counts),len(counts[0])
    rule = AdjacentBlackComponentSum(counts)
    masks = list(product((0,1),repeat=rows*cols))
    expected = {b for b in masks if union_reference(counts,b)}
    assert {b for b in masks if oracle.accepts(rule,b,rows,cols)} == expected
    assert all_answers(ShadingRecipe(rows,cols,(rule,))) == expected


def fixed(counts,black):
    rows,cols = len(counts),len(counts[0])
    return ShadingRecipe(rows,cols,(AdjacentBlackComponentSum(counts),)).build_from_clues(
        [(Cell(r,c),int((r,c) in black)) for r in range(rows) for c in range(cols)]).solve()


def test_multiple_contacts_count_once_and_components_extend_beyond_neighboring_cells():
    ring = {(r,c) for r in range(3) for c in range(3)} - {(1,1)}
    assert fixed(((None,None,None),(None,8,None),(None,None,None)),ring) is not None
    assert fixed(((None,None,None),(None,32,None),(None,None,None)),ring) is None
    assert fixed(((None,None,None),(None,4,None),(None,None,None)),ring) is None
    assert fixed(DEFAULT_COMPONENT_COUNTS,{(r,c) for r in range(2) for c in range(3)}-{(0,0)}) is not None


def test_separate_components_sum_and_one_component_can_serve_different_circles():
    separate = {(0,1),(2,1)}
    assert fixed(((None,None,None),(None,2,None),(None,None,None)),separate) is not None
    assert fixed(((None,None,None),(None,1,None),(None,None,None)),separate) is None
    assert fixed(((3,None,None),(None,None,None),(None,None,3)),{(0,1),(1,1),(2,1)}) is not None
    corners = {(0,0),(0,2),(2,0),(2,2)}
    assert fixed(((None,None,None),(None,0,None),(None,None,None)),corners) is not None


@pytest.mark.parametrize("bad", [{}, [], [[]], [[0],[1,2]], [[False]], [[1.0]], [[-1]], [[100]], [["."]]])
def test_input_schema_is_strict(bad):
    with pytest.raises(ValueError): AdjacentBlackComponentSum(bad)
    with pytest.raises(ValueError): codec.read_rule({"type":"adjacent-black-component-sum","component_counts":bad})


def test_round_trip_immutability_bounds_and_absent_circles(monkeypatch):
    raw: Any = [[5,None,None],[None,None,None]]
    rule = AdjacentBlackComponentSum(raw)
    raw[0][0] = None
    assert rule.component_counts == DEFAULT_COMPONENT_COUNTS
    assert codec.read_rule(codec.rule_record(rule)) == rule
    with pytest.raises(ValueError): codec.read_rule({**codec.rule_record(rule),"extra":0})
    with pytest.raises(ValueError,match="exact built-in"):
        codec.rule_record(type("Changed",(AdjacentBlackComponentSum,),{})(DEFAULT_COMPONENT_COUNTS))
    with pytest.raises(ValueError,match="dimensions"): ShadingRecipe(3,2,(rule,)).create_empty()
    conflicting = ShadingRecipe(2,3,(rule,AdjacentBlackComponentSum(((None,)*3,)*2)))
    with pytest.raises(ValueError,match="same counts"): codec.recipe_record(conflicting)
    with pytest.raises(ValueError,match="same counts"): saved.puzzle_record(conflicting,[],seed=0)
    module = importlib.import_module("puzzle_defs.puzzles.adjacent_black_component_sum")
    monkeypatch.setattr(module,"enumerate_connected_regions",lambda *a,**k: pytest.fail("Must not enumerate"))
    with pytest.raises(ValueError,match="9 board cells"): AdjacentBlackComponentSum(((None,)*4,)*3)
    assert all_answers(ShadingRecipe(1,1,(AdjacentBlackComponentSum(((None,),)),))) == {(0,),(1,)}


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_example_generates_unique_and_does_not_inherit_a_black_two_by_two_ban():
    recipe = replace(codec.load_recipe(EXAMPLES / "shading-kurotto-recipe.json"),clue_kinds=())
    result = worker.generate_request(request(recipe))
    assert result["status"] == "ok" and result["clues"] == [] and saved.verify(result["record"])["unique"]
    assert result["record"]["solution"] == [[0,1,1],[1,1,1]]
    assert not all_answers(replace(recipe,rules=(*recipe.rules,NoBlack2x2())))
    assert "5 . .\n. . ." in saved.show(result["record"]) and "component once" in saved.show(result["record"])
    assert 1 in deductions.explain_puzzle(result["record"])["rules_without_deductions"]
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":[],
                               "answer":[0,1,1,1,1,1]}) == {"status":"ok","correct":True}
    puzzle = recipe.create_empty()
    assert puzzle.solution_vars is not None and len(puzzle.solution_vars) == 6
    configured = with_constraints(recipe,composed.CellCount("black",5))
    record = composed_saved.generate_record(composed.recipe_record(configured),seed=0)
    assert "5 . .\n. . ." in composed_saved.show(record)


def test_component_sum_data_is_separate_from_other_numeric_meanings():
    recipe = ShadingRecipe(2,3,(
        AdjacentBlackComponentSum(((0,None,None),(None,1,None))),
        AdjacentBlackCounts(((0,None,1),(None,1,None))),
        DistinctWhiteNumbers(((1,2,3),(4,5,6))),WhiteVisibilityCounts(((4,0,0),(0,0,0))),
        WhiteIslandAreas(((5,0,0),(0,0,0))),RoomConnectedBlack(((0,0,0),(1,1,1)),False)))
    plan = api.read_request(request(recipe)).plan
    assert plan["component_counts"] == [[0,None,None],[None,1,None]]
    assert plan["neighbor_counts"] == [[0,None,1],[None,1,None]]
    assert all_answers(recipe) == {(0,0,0,0,0,1)}
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**request(recipe),"family":family})
