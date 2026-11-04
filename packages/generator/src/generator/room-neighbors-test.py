"""Room graph constraints versus independent bit-mask contact and counts."""

from dataclasses import replace
import importlib
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from puzzle import Cell, at_least_one, unique
from puzzle_defs import (AdjacentRoomCountsDiffer, NoColorAcrossRooms, NonTouchingBlack,
                         RoomBlackCount, ShadingRecipe)

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

KINDS = (NoColorAcrossRooms, AdjacentRoomCountsDiffer)


def all_answers(recipe):
    p = recipe.create_empty()
    answers = set()
    while (solution := p.solve(seed=0)) is not None:
        bits = tuple(v for row in p.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        p.add(at_least_one(p.black[c] != solution.value(p.black[c]) for c in p.board.cells))
    return answers


def reference(kind, rooms, black, bits):
    # Grow whole bitsets by a one-cell orthogonal shift. This uses neither
    # SquareGrid pairs nor the finite checker's pairwise distance predicate.
    rows, cols = len(rooms),len(rooms[0])
    area = rows*cols
    full = (1 << area)-1
    left = sum(1 << (r*cols) for r in range(rows))
    right = left << (cols-1)
    def expand(mask):
        return (((mask & ~right) << 1) | ((mask & ~left) >> 1) | (mask << cols) | (mask >> cols)) & full
    masks = [sum(1 << (r*cols+c) for r in range(rows) for c in range(cols) if rooms[r][c] == label)
             for label in sorted({n for row in rooms for n in row})]
    selected = sum(1 << i for i,v in enumerate(bits) if bool(v) == black)
    for i,a in enumerate(masks):
        for b in masks[i+1:]:
            if kind is NoColorAcrossRooms:
                if expand(a & selected) & b & selected: return False
            elif expand(a) & b and (a & selected).bit_count() == (b & selected).bit_count():
                return False
    return True


@pytest.mark.parametrize("rooms", [((0,),),((0,0),(0,0)),((0,1,2),),
    ((0,0,1),),((0,1),(2,3)),((0,0,1),(0,1,1)),((0,0,0),(1,1,1))])
@pytest.mark.parametrize("black", [True,False])
@pytest.mark.parametrize("kind", KINDS)
def test_projected_answer_sets_match_bitset_reference_and_distance_checker(rooms, black, kind):
    rows,cols = len(rooms),len(rooms[0])
    rule = kind(rooms,black)
    boards = list(product((0,1),repeat=rows*cols))
    expected = {b for b in boards if reference(kind,rule.rooms,black,b)}
    assert {b for b in boards if oracle.accepts(rule,b,rows,cols)} == expected
    assert all_answers(ShadingRecipe(rows,cols,(rule,))) == expected


def test_independent_checkers_agree_on_concave_three_by_three_rooms():
    rooms = ((0,1,0),(0,1,0),(0,0,0))
    for kind,black in product(KINDS,(True,False)):
        rule = kind(rooms,black)
        for bits in product((0,1),repeat=9):
            assert oracle.accepts(rule,bits,3,3) == reference(kind,rooms,black,bits)


def fixed(rooms, bits, *rules):
    rows,cols = len(rooms),len(rooms[0])
    return ShadingRecipe(rows,cols,rules).build_from_clues(
        [(Cell(r,c),bits[r*cols+c]) for r in range(rows) for c in range(cols)])


def test_boundary_contact_is_distinct_from_global_noncontact_and_room_counts():
    rooms = ((0,0,1),)
    assert fixed(rooms,(1,1,0),NoColorAcrossRooms(rooms)).solve() is not None
    assert fixed(rooms,(1,1,0),NonTouchingBlack()).solve() is None
    assert fixed(rooms,(0,1,1),NoColorAcrossRooms(rooms)).solve() is None
    # Count the whole room, even though both bordering cells here are black.
    rooms = ((0,0,0,1),)
    assert fixed(rooms,(1,0,1,1),AdjacentRoomCountsDiffer(rooms)).solve() is not None
    assert fixed(rooms,(1,0,1,1),NoColorAcrossRooms(rooms)).solve() is None
    # Equal counts in corner-only / non-neighbor rooms are permitted.
    for rooms,bits in [(((0,1),(2,3)),(1,0,0,1)),(((0,1,2),),(1,0,1))]:
        p = fixed(rooms,bits,*(kind(rooms) for kind in KINDS))
        p.add(unique())
        assert p.solution_vars is not None and len(p.solution_vars) == len(bits)
        assert p.solve() is not None


def test_zero_counts_and_selected_color_do_not_add_hidden_nonempty_conditions():
    rooms = ((0,1),)
    assert fixed(rooms,(0,0),NoColorAcrossRooms(rooms)).solve() is not None
    assert fixed(rooms,(0,0),AdjacentRoomCountsDiffer(rooms)).solve() is None
    assert fixed(rooms,(0,1),AdjacentRoomCountsDiffer(rooms)).solve() is not None
    assert fixed(((0,0),),(0,0),AdjacentRoomCountsDiffer(((0,0),))).solve() is not None
    rooms = ((0,0,1),)
    assert fixed(rooms,(1,0,1),AdjacentRoomCountsDiffer(rooms)).solve() is None
    assert fixed(rooms,(1,0,1),AdjacentRoomCountsDiffer(rooms,False)).solve() is not None


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("bad", [0,1,None,"black"])
def test_color_is_strict_boolean(kind,bad):
    with pytest.raises(ValueError): kind(((0,),),bad)
    with pytest.raises(ValueError): codec.read_rule({"type":kind.ui.identifier,"rooms":[[0]],"black":bad})


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("bad", [{},[],[[]],[[0],[1,2]],[[True]],[[1.0]],[[0,1],[1,0]]])
def test_room_maps_are_strict_connected_partitions(kind,bad):
    with pytest.raises(ValueError): kind(bad)
    with pytest.raises(ValueError): codec.read_rule({"type":kind.ui.identifier,"rooms":bad,"black":True})


def test_canonical_copies_exact_codecs_and_shared_layouts():
    raw: Any = [[4,4,1],[4,1,1]]
    rules = [kind(raw) for kind in KINDS]
    raw[0][0] = 0
    for rule in rules:
        assert rule.rooms == ((0,0,1),(0,1,1))
        for r in (rule,replace(rule,black=False)):
            assert codec.read_rule(codec.rule_record(r)) == r
        with pytest.raises(ValueError): codec.read_rule({**codec.rule_record(rule),"extra":0})
        with pytest.raises(ValueError): codec.read_rule({"type":rule.ui.identifier,"rooms":[[0]]})
        with pytest.raises(ValueError,match="exact built-in"):
            codec.rule_record(type("Changed",(type(rule),),{})(rule.rooms))
        with pytest.raises(ValueError,match="dimensions"): ShadingRecipe(3,2,(rule,)).create_empty()
    same = ShadingRecipe(2,3,tuple(rules))
    assert codec.read_recipe(codec.recipe_record(same)) == same
    with pytest.raises(ValueError,match="same partition"):
        codec.recipe_record(replace(same,rules=(*rules,RoomBlackCount(((0,0,0),(1,1,1)),1))))


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_shimaguni_composes_with_room_connectivity_and_keeps_needed_cell_clues():
    recipe = codec.load_recipe(EXAMPLES/"shading-shimaguni-recipe.json")
    answers = {(0,0,1,1,1,0),(0,1,1,1,0,0),(1,0,0,0,1,1),(1,1,0,0,0,1)}
    assert all_answers(recipe) == answers
    assert oracle.analyze(recipe)["completion_count"] == 4
    result = worker.generate_request(request(recipe))
    assert result["status"] == "ok" and len(result["clues"]) == 2
    assert saved.verify(result["record"])["unique"]
    text = saved.show(result["record"])
    assert "across a fixed room border" in text and "different total black counts" in text and "Fixed rooms" in text
    assert deductions.explain_puzzle(result["record"])["rules_without_deductions"] == [1,2,3]
    answer = [v for row in result["record"]["solution"] for v in row]
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":result["clues"],
                               "answer":answer}) == {"status":"ok","correct":True}
    # Every completion shares its full count signature with a reflected answer.
    assert worker.generate_request(request(replace(recipe,clue_kinds=("row-count","column-count"))))["status"] == "insufficient_hints"
    conflict = replace(recipe,rules=(*recipe.rules,RoomBlackCount(recipe.rules[1].rooms,1)))
    assert worker.generate_request(request(conflict))["status"] == "unsatisfiable"
    assert api.read_request(request(recipe)).plan["rooms"] == [[0,0,0],[1,1,1]]
    for family in ("slitherlink","coupled"):
        with pytest.raises(ValueError): api.read_request({**request(recipe),"family":family})
