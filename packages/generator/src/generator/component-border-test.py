"""Virtual outside connectivity versus independent in-board boundary floods."""

from dataclasses import replace
import importlib
from itertools import product
from pathlib import Path

import pytest

from generator import generate
from puzzle import Cell, at_least_one, unique
from puzzle_defs import ComponentsTouchBorder, ConnectedBlack, NonTouchingBlack, ShadingRecipe

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    oracle = importlib.import_module("analyze_shading")
    codec = importlib.import_module("shading_recipe")
    saved = importlib.import_module("generate_shading")
    deductions = importlib.import_module("explain_shading")
    api = importlib.import_module("web_catalog")
    worker = importlib.import_module("web_worker")
    checks = importlib.import_module("web_answers")


def reaches_boundary(bits, rows, cols, black):
    chosen = {(r,c) for r in range(rows) for c in range(cols) if bits[r*cols+c] == int(black)}
    reached = {p for p in chosen if p[0] in (0,rows-1) or p[1] in (0,cols-1)}
    stack = list(reached)
    while stack:
        r,c = stack.pop()
        for next_cell in [(r+1,c),(r-1,c),(r,c+1),(r,c-1)]:
            if next_cell in chosen and next_cell not in reached:
                reached.add(next_cell)
                stack.append(next_cell)
    return reached == chosen


def all_answers(recipe):
    puzzle = recipe.create_empty()
    answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(puzzle.black[c] != solution.value(puzzle.black[c]) for c in puzzle.board.cells))
    return answers


@pytest.mark.parametrize("black", [True,False])
def test_all_three_by_three_visible_answers_match_in_board_boundary_flood(black):
    rule = ComponentsTouchBorder(black)
    expected = {bits for bits in product((0,1),repeat=9) if reaches_boundary(bits,3,3,black)}
    assert len(expected) == 496
    assert {b for b in product((0,1),repeat=9) if oracle.accepts(rule,b,3,3)} == expected
    assert all_answers(ShadingRecipe(3,3,(rule,))) == expected


@pytest.mark.parametrize("rows,cols", [(1,1),(1,4),(4,1),(2,3)])
@pytest.mark.parametrize("black", [True,False])
def test_all_cells_of_thin_boards_are_already_on_the_boundary(rows,cols,black):
    assert all_answers(ShadingRecipe(rows,cols,(ComponentsTouchBorder(black),))) == set(product((0,1),repeat=rows*cols))


def fixed(black_cells, extra=()):
    recipe = ShadingRecipe(3,3,(ComponentsTouchBorder(),*extra))
    return recipe.build_from_clues([(Cell(r,c),int((r,c) in black_cells)) for r in range(3) for c in range(3)])


def test_separate_border_components_are_allowed_but_diagonals_do_not_reach_the_edge():
    corners = {(0,0),(2,2)}
    assert fixed(corners).solve() is not None
    assert fixed(corners,(ComponentsTouchBorder(False),)).solve() is not None
    assert fixed(corners,(ConnectedBlack(),)).solve() is None
    assert fixed({(0,0),(1,1)}).solve() is None
    assert fixed({(0,0),(1,1),(0,1)}).solve() is not None
    assert fixed(set()).solve() is not None and fixed({(r,c) for r in range(3) for c in range(3)}).solve() is not None
    black_ring = {(r,c) for r in range(3) for c in range(3)} - {(1,1)}
    assert fixed(black_ring).solve() is not None
    assert fixed(black_ring,(ComponentsTouchBorder(False),)).solve() is None


def test_outside_frame_and_connectivity_witnesses_do_not_become_answer_variables():
    puzzle = fixed({(0,0),(2,2)})
    assert puzzle.solution_vars is not None and len(puzzle.solution_vars) == 9
    puzzle.add(unique())
    assert puzzle.solve() is not None


@pytest.mark.parametrize("bad", [0,1,None,"true",[],{}])
def test_color_and_file_schema_are_strict(bad):
    with pytest.raises(ValueError): ComponentsTouchBorder(bad)
    with pytest.raises(ValueError): codec.read_rule({"type":"components-touch-border","black":bad})


def test_round_trip_and_unknown_fields_or_subclasses():
    for black in (True,False):
        rule = ComponentsTouchBorder(black)
        assert codec.read_rule(codec.rule_record(rule)) == rule
        with pytest.raises(ValueError): codec.read_rule({**codec.rule_record(rule),"extra":0})
    with pytest.raises(ValueError,match="exact built-in"):
        codec.rule_record(type("Changed",(ComponentsTouchBorder,),{})())


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_cave_composition_eliminates_an_enclosed_black_component_without_extra_hints():
    recipe = replace(codec.load_recipe(EXAMPLES / "shading-cave-recipe.json"),clue_kinds=())
    expected = (0,0,0,0,1,0,0,1,0)
    base = replace(recipe,rules=recipe.rules[:-1])
    assert all_answers(base) == {expected,(0,0,0,0,1,0,0,0,0)}
    assert all_answers(recipe) == {expected}
    assert not all_answers(replace(recipe,rules=(*recipe.rules,NonTouchingBlack())))
    result = worker.generate_request(request(recipe))
    assert result["status"] == "ok" and result["clues"] == [] and saved.verify(result["record"])["unique"]
    assert worker.generate_request(request(base))["status"] == "insufficient_hints"
    assert "boundary through black cells" in saved.show(result["record"])
    assert 3 in deductions.explain_puzzle(result["record"])["rules_without_deductions"]
    checked = {"format":checks.FORMAT,"request":result["request"],"clues":[],"answer":list(expected)}
    assert checks.check_answer(checked) == {"status":"ok","correct":True}
    assert checks.check_answer({**checked,"answer":[0,0,0,0,1,0,0,0,0]}) == {"status":"ok","correct":False}


def test_white_boundary_composes_with_black_connectivity_and_two_by_two_exclusion():
    recipe = codec.load_recipe(EXAMPLES / "shading-coral-shape-recipe.json")
    masks = list(product((0,1),repeat=9))
    base = {bits for bits in masks if all(oracle.accepts(rule,bits,3,3) for rule in recipe.rules[:-1])}
    expected = {b for b in base if reaches_boundary(b,3,3,False)}
    assert expected and expected < base
    assert all_answers(recipe) == expected
    record = saved.puzzle_record(recipe,generate(recipe,seed=0),seed=0)
    assert saved.verify(record)["unique"] and "boundary through white cells" in saved.show(record)
