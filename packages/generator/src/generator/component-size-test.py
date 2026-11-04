"""Closed candidate regions versus independent color components, with projected answers."""

import importlib
from itertools import combinations, product
from pathlib import Path

import pytest

from puzzle import at_least_one, square_grid
from puzzle_defs import (BlackDominoes, ColorComponentSize, NonTouchingBlack,
                         ShadingRecipe, enumerate_connected_regions)

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    oracle = importlib.import_module("analyze_shading")
    codec = importlib.import_module("shading_recipe")
    saved = importlib.import_module("generate_shading")
    finite = importlib.import_module("finite_shading")
    deductions = importlib.import_module("explain_shading")
    api = importlib.import_module("web_catalog")
    worker = importlib.import_module("web_worker")


def all_answers(recipe):
    puzzle = recipe.create_empty(); answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(puzzle.black[c] != solution.value(puzzle.black[c]) for c in puzzle.board.cells))
    return answers


@pytest.mark.parametrize("size", [1,2,3,4,6])
@pytest.mark.parametrize("black", [False,True])
def test_all_small_answers_match_component_counts(size, black):
    rule = ColorComponentSize(size,black)
    expected = {bits for bits in product((0,1),repeat=6) if oracle.accepts(rule,bits,2,3)}
    assert all_answers(ShadingRecipe(2,3,(rule,))) == expected


@pytest.mark.parametrize("size", [3,9])
def test_square_and_full_board_components_match_independent_checker(size):
    rule = ColorComponentSize(size)
    expected = {bits for bits in product((0,1),repeat=9) if oracle.accepts(rule,bits,3,3)}
    assert all_answers(ShadingRecipe(3,3,(rule,))) == expected


def test_size_one_and_two_preserve_existing_local_rule_semantics():
    for size,reference in [(1,NonTouchingBlack()),(2,BlackDominoes())]:
        assert all_answers(ShadingRecipe(2,3,(ColorComponentSize(size),))) == all_answers(ShadingRecipe(2,3,(reference,)))


def test_two_occurrences_have_separate_witnesses_and_only_cells_are_answers():
    rules = (ColorComponentSize(3),ColorComponentSize(3,False))
    recipe = ShadingRecipe(2,3,rules); puzzle = recipe.create_empty()
    assert puzzle.solution_vars is not None
    assert {id(v) for v in puzzle.solution_vars} == {id(puzzle.black[c]) for c in puzzle.board.cells}
    expected = {bits for bits in product((0,1),repeat=6) if all(oracle.accepts(r,bits,2,3) for r in rules)}
    assert all_answers(recipe) == expected
    assert codec.read_recipe(codec.recipe_record(recipe)) == recipe


@pytest.mark.parametrize("size,black", [(0,True),(-1,True),(True,True),(1.5,True),(3,1)])
def test_strict_parameters(size, black):
    with pytest.raises(ValueError): ColorComponentSize(size,black)


def test_unsupported_area_and_oversized_component_fail_before_enumeration(monkeypatch):
    module = importlib.import_module("puzzle_defs.puzzles.component_size")
    monkeypatch.setattr(module,"enumerate_connected_regions",lambda *a,**k: pytest.fail("Must validate first"))
    for recipe in [ShadingRecipe(2,5,(ColorComponentSize(3),)),ShadingRecipe(2,3,(ColorComponentSize(7),))]:
        with pytest.raises(ValueError): recipe.create_empty()
        with pytest.raises(ValueError): codec.recipe_record(recipe)


def test_strict_codec_does_not_drop_custom_semantics():
    rule = ColorComponentSize(3,False)
    assert codec.read_rule(codec.rule_record(rule)) == rule
    with pytest.raises(ValueError): codec.read_rule({**codec.rule_record(rule),"extra":0})
    with pytest.raises(ValueError): codec.read_rule({"type":"color-component-size","size":3})
    with pytest.raises(ValueError,match="exact built-in"):
        codec.rule_record(type("Changed",(ColorComponentSize,),{})(3))


def test_memoized_region_growth_matches_independent_combinations_on_every_small_target():
    board = square_grid(2,3)
    for mask in product((False,True),repeat=6):
        target = {c for c,yes in zip(board.cells,mask) if yes}
        for size in range(0,8):
            expected = set()
            for choice in combinations(sorted(target),size):
                if not choice: continue
                group = {(c.row,c.col) for c in choice}; todo = [min(group)]; reached = set()
                while todo:
                    point = todo.pop()
                    if point in reached: continue
                    reached.add(point); r,c = point
                    todo.extend(p for p in [(r-1,c),(r+1,c),(r,c-1),(r,c+1)] if p in group and p not in reached)
                if reached == group: expected.add(frozenset(choice))
            assert {r.cells for r in enumerate_connected_regions(board,size,target)} == expected


def test_larger_legacy_targets_keep_the_same_adjacent_pairs_without_memoization():
    board = square_grid(2,5)
    expected = {frozenset((a,b)) for a,b in combinations(board.cells,2)
                if abs(a.row-b.row)+abs(a.col-b.col) == 1}
    assert {r.cells for r in enumerate_connected_regions(board,2)} == expected


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


@pytest.mark.parametrize("name", ["component-size","equal-islands"])
def test_black_and_white_examples_generate_unique_puzzles_with_two_initial_answers(name):
    recipe = codec.load_recipe(EXAMPLES / f"shading-{name}-recipe.json")
    expected = {bits for bits in product((0,1),repeat=9) if all(oracle.accepts(r,bits,3,3) for r in recipe.rules)}
    assert len(expected) == 2 and all_answers(recipe) == set(finite.identifiable_completions(recipe)) == expected
    result = worker.generate_request(request(recipe))
    assert result == worker.generate_request(request(recipe)) and result["status"] == "ok"
    assert result["clues"] and saved.verify(result["record"])["unique"]
    assert "component contains exactly 3 cells" in saved.show(result["record"])
    assert 1 in deductions.explain_puzzle(result["record"])["rules_without_deductions"]
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**request(recipe),"family":family})
