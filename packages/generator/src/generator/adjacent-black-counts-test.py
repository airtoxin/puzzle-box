"""Minesweeper neighborhoods, real zero clues, and nullable-grid compatibility."""

from dataclasses import replace
import importlib
from itertools import product
import json
from pathlib import Path
from typing import Any

import pytest

from generator import with_constraints
from puzzle import at_least_one
from puzzle_defs import (AdjacentBlackCounts, DistinctWhiteNumbers, RoomConnectedBlack,
                         ShadingRecipe, WhiteIslandAreas, WhiteVisibilityCounts)
from puzzle_defs.clue_layout import clue_grid
from puzzle_defs.number_layout import number_grid
from puzzle_defs.puzzles.adjacent_black_counts import DEFAULT_NEIGHBOR_COUNTS
from puzzle_defs.ui import UiParameter

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


def bit_reference(counts, diagonal, bits):
    rows, cols = len(counts), len(counts[0])
    # Explicit direction bit masks, independent of grid neighbor pairs and the
    # finite checker's distance expression.
    offsets = [(-1,0),(1,0),(0,-1),(0,1)]
    if diagonal:
        offsets += [(-1,-1),(-1,1),(1,-1),(1,1)]
    mines = sum(b << i for i,b in enumerate(bits))
    for r in range(rows):
        for c in range(cols):
            n = counts[r][c]
            if n is None:
                continue
            mask = sum(1 << ((r+dr)*cols+c+dc) for dr,dc in offsets if 0 <= r+dr < rows and 0 <= c+dc < cols)
            if bits[r*cols+c] or (mines & mask).bit_count() != n:
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


@pytest.mark.parametrize("counts", [((None,),), ((0,),), ((1,),), ((None,None,None),),
    DEFAULT_NEIGHBOR_COUNTS, ((0,None,None),(None,None,None),(None,None,None)),
    ((None,None,None),(None,4,None),(None,None,None)),
    ((None,None,None),(None,8,None),(None,None,None)), ((0,0),(0,0))])
@pytest.mark.parametrize("diagonal", [True,False])
def test_all_projected_answers_match_direction_bit_masks_and_independent_distance_checker(counts,diagonal):
    rows, cols = len(counts), len(counts[0])
    rule = AdjacentBlackCounts(counts,diagonal)
    masks = list(product((0,1),repeat=rows*cols))
    expected = {b for b in masks if bit_reference(counts,diagonal,b)}
    assert {b for b in masks if oracle.accepts(rule,b,rows,cols)} == expected
    assert all_answers(ShadingRecipe(rows,cols,(rule,))) == expected


@pytest.mark.parametrize("bad", [{}, [], [[]], [[0],[1,2]], [[True]], [[1.0]], [[-1]], [[9]], [["."]]])
def test_neighbor_counts_are_strict_arrays_with_real_nulls(bad):
    with pytest.raises(ValueError): AdjacentBlackCounts(bad)
    with pytest.raises(ValueError): codec.read_rule({"type":"adjacent-black-counts","neighbor_counts":bad,"diagonal":True})


@pytest.mark.parametrize("bad", [0,1,None,"true"])
def test_diagonal_is_a_strict_boolean(bad):
    with pytest.raises(ValueError): AdjacentBlackCounts(((None,),),bad)


def test_nullable_data_does_not_weaken_existing_number_grids_or_conflate_zero():
    assert clue_grid([[None,0,8]],maximum=8) == ((None,0,8),)
    assert all_answers(ShadingRecipe(1,1,(AdjacentBlackCounts(((None,),)),))) == {(0,),(1,)}
    assert all_answers(ShadingRecipe(1,1,(AdjacentBlackCounts(((0,),)),))) == {(0,)}
    for constructor in [number_grid,WhiteIslandAreas,WhiteVisibilityCounts,DistinctWhiteNumbers]:
        with pytest.raises(ValueError): constructor([[None]])
    parameter = UiParameter("neighbor_counts","Neighbors","clue-grid",((None,0),),maximum=8)
    parameter.validate([[None,0]],area=2,rows=1,cols=2)
    for bad in [[{}],[[None,9]],[[None,False]],[[None]],{}]:
        with pytest.raises(ValueError): parameter.validate(bad,area=2,rows=1,cols=2)
    with pytest.raises(ValueError): clue_grid([[0]],maximum=True)


def test_round_trip_mutability_dimensions_and_distinct_meanings():
    raw: Any = [[0,None,1],[None,1,None]]
    rule = AdjacentBlackCounts(raw)
    raw[0][0] = None
    assert rule.neighbor_counts == DEFAULT_NEIGHBOR_COUNTS
    record = codec.rule_record(rule)
    assert codec.read_rule(json.loads(json.dumps(record))) == rule
    assert record["neighbor_counts"][0][:2] == [0,None]
    with pytest.raises(ValueError): codec.read_rule({**record,"extra":0})
    with pytest.raises(ValueError,match="exact built-in"):
        codec.rule_record(type("Changed",(AdjacentBlackCounts,),{})(DEFAULT_NEIGHBOR_COUNTS))
    with pytest.raises(ValueError,match="dimensions"): ShadingRecipe(3,2,(rule,)).create_empty()
    recipe = ShadingRecipe(2,3,(rule,AdjacentBlackCounts(((None,)*3,)*2)))
    with pytest.raises(ValueError,match="same neighbor counts"): codec.recipe_record(recipe)
    with pytest.raises(ValueError,match="same neighbor counts"): saved.puzzle_record(recipe,[],seed=0)


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_minesweeper_example_generates_without_extra_hints_or_a_total_mine_count():
    recipe = replace(codec.load_recipe(EXAMPLES / "shading-minesweeper-recipe.json"),clue_kinds=())
    result = worker.generate_request(request(recipe))
    assert result["status"] == "ok" and result["clues"] == []
    assert saved.verify(result["record"])["unique"] and result == worker.generate_request(request(recipe))
    assert result["record"]["solution"] == [[0,0,0],[0,0,1]]
    assert "0 . 1\n. 1 ." in saved.show(result["record"])
    assert "Answer template: .?./?.?" in saved.show(result["record"])
    assert 1 in deductions.explain_puzzle(result["record"])["rules_without_deductions"]
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":[],
                               "answer":[0,0,0,0,0,1]}) == {"status":"ok","correct":True}
    puzzle = recipe.create_empty()
    assert puzzle.solution_vars is not None and len(puzzle.solution_vars) == 6
    configured = with_constraints(recipe,composed.CellCount("black",1))
    record = composed_saved.generate_record(composed.recipe_record(configured),seed=0)
    assert "0 . 1\n. 1 ." in composed_saved.show(record)


def test_nullable_neighbor_counts_compose_with_other_numeric_meanings_and_rooms():
    recipe = codec.load_recipe(EXAMPLES / "shading-minesweeper-recipe.json")
    hybrid = replace(recipe,rules=(*recipe.rules,DistinctWhiteNumbers(((1,2,3),(4,5,6))),
        WhiteVisibilityCounts(((4,0,0),(0,0,0))),WhiteIslandAreas(((5,0,0),(0,0,0))),
        RoomConnectedBlack(((0,0,0),(1,1,1)),False)))
    data = request(hybrid)
    plan = api.read_request(data).plan
    assert plan["neighbor_counts"] == [[0,None,1],[None,1,None]]
    assert plan["sight_counts"] == [[4,0,0],[0,0,0]] and plan["island_areas"] == [[5,0,0],[0,0,0]]
    assert plan["numbers"] == [[1,2,3],[4,5,6]] and plan["rooms"] == [[0,0,0],[1,1,1]]
    assert all_answers(hybrid) == {(0,0,0,0,0,1)}
    for invalid in [{}, [[None]], [[True]*3]*2, [[9]*3]*2]:
        broken = request(recipe)
        broken["rules"][0]["parameters"]["neighbor_counts"] = invalid
        with pytest.raises(ValueError): api.read_request(broken)
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**data,"family":family})
