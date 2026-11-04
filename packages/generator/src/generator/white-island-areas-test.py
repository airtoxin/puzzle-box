"""Numbered-island exact cover versus anchor floods and the existing solver."""

from dataclasses import replace
import importlib
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from generator import with_constraints
from puzzle import Cell, at_least_one
from puzzle_defs import (ConnectedBlack, DistinctWhiteNumbers, NoBlack2x2, NurikabePuzzle,
                         RoomConnectedBlack, ShadingRecipe, WhiteIslandAreas, WhiteVisibilityCounts)
from puzzle_defs.puzzles.white_island_areas import DEFAULT_ISLAND_AREAS

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


def accepts_areas(areas, bits):
    rows, cols = len(areas), len(areas[0])
    white = {(r,c) for r in range(rows) for c in range(cols) if bits[r*cols+c] == 0}
    accounted = set()
    for r in range(rows):
        for c in range(cols):
            if areas[r][c] == 0:
                continue
            if (r,c) not in white or (r,c) in accounted:
                return False
            region = set()
            todo = [(r,c)]
            while todo:
                p = todo.pop()
                if p in region or p not in white:
                    continue
                region.add(p)
                s,t = p
                todo.extend([(s+1,t),(s-1,t),(s,t+1),(s,t-1)])
            if len(region) != areas[r][c]:
                return False
            accounted.update(region)
    return accounted == white


def all_answers(recipe):
    puzzle = recipe.create_empty()
    answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(puzzle.black[c] != solution.value(puzzle.black[c]) for c in puzzle.board.cells))
    return answers


@pytest.mark.parametrize("areas", [((0,),), ((1,),), ((2,),), ((2,0,0),), ((1,0),(0,1)),
    DEFAULT_ISLAND_AREAS, ((3,0,0),(0,0,0),(0,0,0)), ((9,0,0),(0,0,0),(0,0,0)),
    ((1,1),(1,1)), ((99,0),(0,0))])
def test_all_visible_answers_match_independent_anchor_flood_and_component_checker(areas):
    rows, cols = len(areas), len(areas[0])
    rule = WhiteIslandAreas(areas)
    masks = list(product((0,1),repeat=rows*cols))
    expected = {bits for bits in masks if accepts_areas(areas,bits)}
    assert {b for b in masks if oracle.accepts(rule,b,rows,cols)} == expected
    assert all_answers(ShadingRecipe(rows,cols,(rule,))) == expected


@pytest.mark.parametrize("areas", [((0,),), ((1,),), DEFAULT_ISLAND_AREAS,
    ((1,0),(0,1)), ((2,0,0),(0,0,2)), ((3,0,0),(0,0,0),(0,0,0))])
def test_complete_composition_preserves_existing_nurikabe_answers(areas):
    rows, cols = len(areas), len(areas[0])
    recipe = ShadingRecipe(rows,cols,(WhiteIslandAreas(areas),ConnectedBlack(False),NoBlack2x2()))
    legacy = NurikabePuzzle([[n if n else None for n in row] for row in areas])
    answers = set()
    while (solution := legacy.solve(seed=0)) is not None:
        bits = tuple(int(n == 0) for row in legacy.result(solution) for n in row)
        assert bits not in answers
        answers.add(bits)
        legacy.add(at_least_one(legacy.owner[c] != solution.value(legacy.owner[c]) for c in legacy.board.cells))
    assert all_answers(recipe) == answers


def test_numbers_are_white_and_unanchored_white_components_are_forbidden():
    recipe = ShadingRecipe(2,3,(WhiteIslandAreas(((1,0,0),(0,0,0))),))
    assert all_answers(recipe) == {(0,1,1,1,1,1)}
    assert recipe.build_from_clues([(Cell(0,0),1)]).solve() is None
    assert recipe.build_from_clues([(Cell(1,2),0)]).solve() is None
    assert not all_answers(ShadingRecipe(1,2,(WhiteIslandAreas(((2,2),)),)))


@pytest.mark.parametrize("bad", [{}, [], [[]], [[1],[2,3]], [[True]], [[1.0]], [[-1]], [[100]], [["1"]]])
def test_areas_are_strict_bounded_arrays(bad):
    with pytest.raises(ValueError): WhiteIslandAreas(bad)
    with pytest.raises(ValueError): codec.read_rule({"type":"white-island-areas","areas":bad})


def test_data_is_immutable_exact_and_rejected_before_large_enumeration(monkeypatch):
    raw: Any = [[1,0,0],[0,0,2]]
    rule = WhiteIslandAreas(raw)
    raw[0][0] = 9
    assert rule.areas == DEFAULT_ISLAND_AREAS
    assert codec.read_rule(codec.rule_record(rule)) == rule
    with pytest.raises(ValueError): codec.read_rule({**codec.rule_record(rule),"extra":0})
    with pytest.raises(ValueError,match="exact built-in"):
        codec.rule_record(type("Changed",(WhiteIslandAreas,),{})(DEFAULT_ISLAND_AREAS))
    with pytest.raises(ValueError,match="dimensions"): ShadingRecipe(3,2,(rule,)).create_empty()
    recipe = ShadingRecipe(2,3,(rule,WhiteIslandAreas(((0,0,0),(0,0,0)))))
    with pytest.raises(ValueError,match="same areas"): codec.recipe_record(recipe)
    with pytest.raises(ValueError,match="same areas"): saved.puzzle_record(recipe,[],seed=0)
    module = importlib.import_module("puzzle_defs.puzzles.white_island_areas")
    monkeypatch.setattr(module,"enumerate_connected_regions",lambda *a,**k: pytest.fail("Must reject first"))
    with pytest.raises(ValueError,match="9 board cells"): WhiteIslandAreas(((0,)*4,)*3)


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_nurikabe_example_generates_and_checks_with_no_extra_hints_and_supports_components():
    recipe = replace(codec.load_recipe(EXAMPLES / "shading-nurikabe-recipe.json"),clue_kinds=())
    result = worker.generate_request(request(recipe))
    assert result["status"] == "ok" and result["clues"] == []
    assert saved.verify(result["record"])["unique"] and result == worker.generate_request(request(recipe))
    assert result["record"]["solution"] == [[0,1,0],[1,1,0]]
    assert "1 . .\n. . 2" in saved.show(result["record"])
    assert "Answer template: .??/??." in saved.show(result["record"])
    assert 1 in deductions.explain_puzzle(result["record"])["rules_without_deductions"]
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":[],
                               "answer":[0,1,0,1,1,0]}) == {"status":"ok","correct":True}
    puzzle = recipe.create_empty()
    assert puzzle.solution_vars is not None and len(puzzle.solution_vars) == 6
    configured = with_constraints(recipe,composed.CellCount("black",3))
    record = composed_saved.generate_record(composed.recipe_record(configured),seed=0)
    assert "1 . .\n. . 2" in composed_saved.show(record)


def test_area_visibility_label_and_room_grids_keep_distinct_plan_data():
    recipe = codec.load_recipe(EXAMPLES / "shading-nurikabe-recipe.json")
    hybrid = replace(recipe,rules=(*recipe.rules,
        DistinctWhiteNumbers(((1,2,3),(4,5,6))),
        WhiteVisibilityCounts(((0,0,0),(0,0,2))),
        RoomConnectedBlack(((0,0,0),(1,1,1)))))
    plan = api.read_request(request(hybrid)).plan
    assert plan["island_areas"] == [[1,0,0],[0,0,2]]
    assert plan["sight_counts"] == [[0,0,0],[0,0,2]]
    assert plan["numbers"] == [[1,2,3],[4,5,6]] and plan["rooms"] == [[0,0,0],[1,1,1]]
    assert all_answers(hybrid) == {(0,1,0,1,1,0)}
    bad_rooms = replace(hybrid,rules=(*hybrid.rules[:-1],RoomConnectedBlack(((0,0,1),(0,1,1)))))
    assert bad_rooms.create_empty().solve() is None
    for invalid in [{}, [[0]], [[False]*3]*2, [[100]*3]*2]:
        broken = request(recipe)
        broken["rules"][0]["parameters"]["areas"] = invalid
        with pytest.raises(ValueError): api.read_request(broken)
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**request(recipe),"family":family})
