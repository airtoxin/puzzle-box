"""Ranked orientations versus independent leaf pruning and component sizes."""

from dataclasses import replace
import importlib
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from puzzle import Cell, at_least_one, unique
from puzzle_defs import (AcyclicColor, ConnectedBlack, ConnectedWhite, NoBlack2x2,
                         RoomBlackCount, ShadingRecipe, UniformRooms)

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


def all_answers(recipe):
    puzzle = recipe.create_empty()
    answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(puzzle.black[c] != solution.value(puzzle.black[c]) for c in puzzle.board.cells))
    return answers


def leaf_reference(bits,rows,cols,black):
    # Repeatedly remove degree-zero/one vertices. Exactly forests disappear;
    # this uses neither the encoder's orientation/ranks nor component counts.
    cells = {(r,c) for r in range(rows) for c in range(cols) if bool(bits[r*cols+c]) == black}
    while cells:
        leaves = {(r,c) for r,c in cells if sum((s,t) in cells for s,t in ((r-1,c),(r+1,c),(r,c-1),(r,c+1))) <= 1}
        if not leaves: return False
        cells -= leaves
    return True


@pytest.mark.parametrize("rows,cols,black", [(1,1,True),(1,4,False),(2,3,True),(2,3,False)])
def test_color_forests_match_leaf_pruning_and_component_checker(rows,cols,black):
    rule = AcyclicColor(black)
    masks = list(product((0,1),repeat=rows*cols))
    expected = {bits for bits in masks if leaf_reference(bits,rows,cols,black)}
    assert {bits for bits in masks if oracle.accepts(rule,bits,rows,cols)} == expected
    assert all_answers(ShadingRecipe(rows,cols,(rule,))) == expected


def test_three_by_three_reference_checkers_agree_on_all_512_boards():
    # Keep repeated projected DSL enumeration bounded at 2x3. Larger induced
    # cycles, branches and witnesses have dedicated solver counterexamples;
    # compare the two inexpensive reference algorithms exhaustively at 3x3.
    rule = AcyclicColor(False)
    for bits in product((0,1),repeat=9):
        assert oracle.accepts(rule,bits,3,3) == leaf_reference(bits,3,3,False)


@pytest.mark.parametrize("rooms", [((0,),),((0,0,1),),((0,0,1),(0,1,1)),((0,1),(2,3))])
def test_uniform_rooms_match_explicit_color_assignment_to_each_room(rooms):
    rule = UniformRooms(rooms)
    rows,cols = len(rooms),len(rooms[0])
    labels = sorted({n for row in rule.rooms for n in row})
    expected = {tuple(colors[rule.rooms[r][c]] for r in range(rows) for c in range(cols))
                for colors in product((0,1),repeat=len(labels))}
    assert all_answers(ShadingRecipe(rows,cols,(rule,))) == expected
    assert {bits for bits in product((0,1),repeat=rows*cols) if oracle.accepts(rule,bits,rows,cols)} == expected


def fixed(rows,cols,rules,black):
    return ShadingRecipe(rows,cols,rules).build_from_clues(
        [(Cell(r,c),int((r,c) in black)) for r in range(rows) for c in range(cols)])


def test_induced_cycles_cannot_hide_an_edge_or_be_confused_with_two_by_two():
    ring = {(r,c) for r in range(3) for c in range(3)} - {(1,1)}
    assert fixed(3,3,(NoBlack2x2(),),ring).solve() is not None
    assert fixed(3,3,(AcyclicColor(True),),ring).solve() is None
    square = {(0,0),(0,1),(1,0),(1,1)}
    assert fixed(2,2,(AcyclicColor(True),),square).solve() is None
    # Only the selected color is checked, not an opposite-color cycle.
    assert fixed(3,3,(AcyclicColor(False),),ring).solve() is not None


def test_branches_isolation_absence_and_multiple_components_remain_allowed():
    tee = {(0,0),(0,1),(0,2),(1,1)}
    assert fixed(2,3,(AcyclicColor(True),ConnectedBlack()),tee).solve() is not None
    isolated = {(0,0),(0,2)}
    assert fixed(1,3,(AcyclicColor(True),),isolated).solve() is not None
    assert fixed(1,3,(AcyclicColor(True),ConnectedBlack()),isolated).solve() is None
    assert fixed(2,2,(AcyclicColor(True),),set()).solve() is not None


def test_witnesses_do_not_change_visible_uniqueness_even_with_repeated_colors():
    rules = (AcyclicColor(),AcyclicColor(True),AcyclicColor())
    puzzle = fixed(2,3,rules,{(0,0),(0,1),(0,2)})
    assert puzzle.solution_vars is not None and len(puzzle.solution_vars) == 6
    puzzle.add(unique())
    assert puzzle.solve(seed=0) is not None


@pytest.mark.parametrize("bad", [0,1,None,"white"])
def test_color_is_a_strict_boolean(bad):
    with pytest.raises(ValueError): AcyclicColor(bad)
    with pytest.raises(ValueError): codec.read_rule({"type":"acyclic-color","black":bad})


@pytest.mark.parametrize("bad", [{},[],[[]],[[0],[1,2]],[[True]],[[1.0]],[[0,1],[1,0]]])
def test_room_input_is_strict_and_connected(bad):
    with pytest.raises(ValueError): UniformRooms(bad)
    with pytest.raises(ValueError): codec.read_rule({"type":"uniform-rooms","rooms":bad})


def test_room_copy_normalization_shared_layout_and_exact_codecs():
    raw: Any = [[4,4,1],[4,1,1]]
    rule = UniformRooms(raw)
    raw[0][0] = 0
    assert rule.rooms == ((0,0,1),(0,1,1))
    for r in [rule,AcyclicColor(),AcyclicColor(True)]:
        assert codec.read_rule(codec.rule_record(r)) == r
        with pytest.raises(ValueError): codec.read_rule({**codec.rule_record(r),"extra":0})
        with pytest.raises(ValueError,match="exact built-in"):
            codec.rule_record(type("Changed",(type(r),),{})(*([rule.rooms] if type(r) is UniformRooms else [])))
    with pytest.raises(ValueError,match="dimensions"): ShadingRecipe(3,2,(rule,)).create_empty()
    other = RoomBlackCount(((0,0,0),(1,1,1)),1)
    with pytest.raises(ValueError,match="same partition"): codec.recipe_record(ShadingRecipe(2,3,(rule,other)))


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_room_example_needs_a_retained_hint_and_checks_both_new_rules():
    recipe = codec.load_recipe(EXAMPLES / "shading-room-forest-recipe.json")
    answers = {(1,1,0,1,0,0),(0,0,1,0,1,1)}
    assert all_answers(recipe) == answers
    assert oracle.analyze(recipe)["completion_count"] == 2
    result = worker.generate_request(request(recipe))
    assert result["status"] == "ok" and len(result["clues"]) == 1
    assert saved.verify(result["record"])["unique"]
    text = saved.show(result["record"])
    assert "entirely black or entirely white" in text and "has no cycle" in text and "Fixed rooms" in text
    assert deductions.explain_puzzle(result["record"])["rules_without_deductions"][:2] == [1,2]
    answer = [v for row in result["record"]["solution"] for v in row]
    assert tuple(answer) in answers
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":result["clues"],
                               "answer":answer}) == {"status":"ok","correct":True}
    # Display compatibility does not prove mathematical feasibility.
    conflict = replace(recipe,rules=(*recipe.rules,RoomBlackCount(recipe.rules[0].rooms,1)))
    assert worker.generate_request(request(conflict))["status"] == "unsatisfiable"
    plan = api.read_request(request(recipe)).plan
    assert plan["rooms"] == [[0,0,1],[0,1,1]]
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**request(recipe),"family":family})


def test_square_room_cycle_forces_black_but_connectivity_and_nonempty_are_separate():
    rooms = ((0,0,1),(0,0,1))
    rules = (UniformRooms(rooms),AcyclicColor())
    assert all_answers(ShadingRecipe(2,3,rules)) == {(1,1,0,1,1,0),(1,1,1,1,1,1)}
    assert all_answers(ShadingRecipe(2,3,(*rules,ConnectedWhite()))) == {(1,1,0,1,1,0)}
    assert not all_answers(ShadingRecipe(2,3,(*rules,NoBlack2x2())))
