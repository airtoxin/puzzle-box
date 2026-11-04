"""Whole-component covers versus union-find and independent room-local floods."""

from dataclasses import replace
import importlib
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from puzzle import Cell, at_least_one, unique
from puzzle_defs import (ColorComponentSize, EqualRoomComponentSizes, RoomBlackCount,
                         RoomComponentCount, ShadingRecipe)

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

LAYOUTS = [((0,),),((0,0,0,0),),((0,0),(0,0)),((0,0,1),(0,1,1)),((0,0,0),(1,1,1))]


def component_sizes(bits,rooms,black):
    rows,cols = len(rooms),len(rooms[0])
    selected = [i for i,v in enumerate(bits) if bool(v) == black]
    parent = {i:i for i in selected}
    def root(i):
        while parent[i] != i:
            i = parent[i]
        return i
    for i in selected:
        for j in selected:
            if (rooms[i//cols][i%cols] == rooms[j//cols][j%cols]
                    and abs(i//cols-j//cols)+abs(i%cols-j%cols) == 1):
                parent[root(i)] = root(j)
    sizes = {n:[] for row in rooms for n in row}
    groups = {root(i) for i in selected}
    for r in groups:
        sizes[rooms[r//cols][r%cols]].append(sum(root(i) == r for i in selected))
    return {n:sorted(values) for n,values in sizes.items()}


def reference(rule,bits):
    sizes = component_sizes(bits,rule.rooms,rule.black).values()
    if type(rule) is RoomComponentCount:
        return all(len(s) == rule.count for s in sizes)
    return all(len(set(s)) <= 1 for s in sizes)


def all_answers(recipe):
    p = recipe.create_empty()
    answers = set()
    while (solution := p.solve(seed=0)) is not None:
        bits = tuple(v for row in p.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        p.add(at_least_one(p.black[c] != solution.value(p.black[c]) for c in p.board.cells))
    return answers


@pytest.mark.parametrize("rooms",LAYOUTS)
@pytest.mark.parametrize("black",[True,False])
def test_component_counts_and_equal_sizes_match_complete_union_find_answers(rooms,black):
    rows,cols = len(rooms),len(rooms[0])
    boards = list(product((0,1),repeat=rows*cols))
    rules = [EqualRoomComponentSizes(rooms,black)] + [RoomComponentCount(rooms,count,black)
             for count in range(min(3,rows*cols)+1)]
    for rule in rules:
        expected = {bits for bits in boards if reference(rule,bits)}
        assert {bits for bits in boards if oracle.accepts(rule,bits,rows,cols)} == expected
        assert all_answers(ShadingRecipe(rows,cols,(rule,))) == expected


def test_three_by_three_finite_floods_match_union_find_on_every_board():
    rooms = ((0,0,1),(0,1,1),(1,1,1))
    for black in (True,False):
        for rule in [EqualRoomComponentSizes(rooms,black),RoomComponentCount(rooms,0,black),RoomComponentCount(rooms,2,black)]:
            for bits in product((0,1),repeat=9):
                assert oracle.accepts(rule,bits,3,3) == reference(rule,bits)


def fixed(rooms,bits,*rules):
    rows,cols = len(rooms),len(rooms[0])
    return ShadingRecipe(rows,cols,rules).build_from_clues(
        [(Cell(r,c),bits[r*cols+c]) for r in range(rows) for c in range(cols)])


def test_components_cannot_split_merge_or_count_as_cells_and_equal_sizes_are_separate():
    rooms = ((0,0,0,0),)
    assert fixed(rooms,(1,1,1,1),RoomComponentCount(rooms,2)).solve() is None
    assert fixed(rooms,(1,1,1,1),RoomComponentCount(rooms,1)).solve() is not None
    rooms = ((0,0,0),)
    assert fixed(rooms,(1,0,1),RoomComponentCount(rooms,1)).solve() is None
    assert fixed(rooms,(1,0,1),RoomComponentCount(rooms,2)).solve() is not None
    rooms = ((0,0,0),(0,0,0));bits=(1,1,0,0,0,1)
    assert fixed(rooms,bits,RoomComponentCount(rooms,2)).solve() is not None
    assert fixed(rooms,bits,EqualRoomComponentSizes(rooms)).solve() is None
    # Equal area permits a horizontal and vertical domino, with corner contact.
    rooms = ((0,0,0),(0,0,0),(0,0,0));bits=(1,1,0,0,0,1,0,0,1)
    assert fixed(rooms,bits,RoomComponentCount(rooms,2),EqualRoomComponentSizes(rooms)).solve() is not None


def test_empty_single_and_repeated_covers_do_not_change_visible_uniqueness():
    rooms = ((0,0,0),)
    for bits in [(0,0,0),(1,1,1)]:
        rules = (EqualRoomComponentSizes(rooms),EqualRoomComponentSizes(rooms),RoomComponentCount(rooms,int(any(bits))))
        p = fixed(rooms,bits,*rules)
        assert p.solution_vars is not None and len(p.solution_vars) == 3
        p.add(unique())
        assert p.solve() is not None  # empty equal-size witnesses have >1 value
    rooms = ((0,0,0),(1,1,1));bits=(1,0,1,1,1,1)
    assert fixed(rooms,bits,EqualRoomComponentSizes(rooms)).solve() is not None  # sizes 1 and 3 between rooms


@pytest.mark.parametrize("kind",[RoomComponentCount,EqualRoomComponentSizes])
@pytest.mark.parametrize("bad",[0,1,None,"black"])
def test_color_is_strict_boolean(kind,bad):
    with pytest.raises(ValueError): kind(((0,0),),black=bad)
    data={"type":kind.ui.identifier,"rooms":[[0,0]],"black":bad}
    if kind is RoomComponentCount:data["count"]=1
    with pytest.raises(ValueError):codec.read_rule(data)


@pytest.mark.parametrize("bad",[True,1.0,-1,None,"2",3])
def test_count_is_a_strict_bounded_nonnegative_integer(bad):
    with pytest.raises(ValueError): RoomComponentCount(((0,0),),bad)
    with pytest.raises(ValueError): codec.read_rule({"type":"room-component-count","rooms":[[0,0]],"black":True,"count":bad})


@pytest.mark.parametrize("kind",[RoomComponentCount,EqualRoomComponentSizes])
@pytest.mark.parametrize("bad",[{},[],[[]],[[0],[1,2]],[[True]],[[1.0]],[[0,1],[1,0]],[[0]*5,[0]*5]])
def test_invalid_or_large_rooms_fail_before_candidate_enumeration(kind,bad):
    with pytest.raises(ValueError): kind(bad)
    data={"type":kind.ui.identifier,"rooms":bad,"black":True}
    if kind is RoomComponentCount:data["count"]=0
    with pytest.raises(ValueError):codec.read_rule(data)


def test_copy_codec_and_shared_partition_contracts():
    raw: Any = [[4,4,1],[4,1,1]]
    rules = [RoomComponentCount(raw),EqualRoomComponentSizes(raw)]
    raw[0][0]=0
    for rule in rules:
        assert rule.rooms == ((0,0,1),(0,1,1))
        assert codec.read_rule(codec.rule_record(rule)) == rule
        assert codec.read_rule(codec.rule_record(replace(rule,black=False))) == replace(rule,black=False)
        with pytest.raises(ValueError):codec.read_rule({**codec.rule_record(rule),"extra":0})
        with pytest.raises(ValueError):codec.read_rule({"type":rule.ui.identifier,"rooms":[[0,0]]})
        with pytest.raises(ValueError,match="exact built-in"):codec.rule_record(type("Changed",(type(rule),),{})(rule.rooms))
        with pytest.raises(ValueError,match="dimensions"):ShadingRecipe(3,2,(rule,)).create_empty()
    recipe=ShadingRecipe(2,3,tuple(rules))
    assert codec.read_recipe(codec.recipe_record(recipe)) == recipe
    with pytest.raises(ValueError,match="same partition"):
        codec.recipe_record(replace(recipe,rules=(*rules,RoomBlackCount(((0,0,0),(1,1,1)),1))))


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],"parameters":{k:v for k,v in r.items() if k!="type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def nuritwin_reference(rooms):
    expected=set()
    for bits in product((0,1),repeat=9):
        groups=component_sizes(bits,rooms,True).values()
        if not all(len(s)==2 and s[0]==s[1] for s in groups):continue
        if len(component_sizes(bits,((0,0,0),)*3,True)[0]) != 1:continue
        if any(all(bits[(r+dr)*3+c+dc] for dr,dc in product((0,1),repeat=2)) for r,c in product(range(2),repeat=2)):continue
        expected.add(bits)
    return expected


def test_nuritwin_connects_globally_but_keeps_two_local_components_per_room():
    recipe=codec.load_recipe(EXAMPLES/"shading-nuritwin-recipe.json")
    rooms=recipe.rules[0].rooms
    expected=nuritwin_reference(rooms)
    assert len(expected)==2 and all_answers(recipe)==expected
    assert oracle.analyze(recipe)["completion_count"]==2
    result=worker.generate_request(request(recipe))
    assert result["status"]=="ok" and len(result["clues"])==1
    assert saved.verify(result["record"])["unique"]
    assert "exactly 2 black components" in saved.show(result["record"])
    assert deductions.explain_puzzle(result["record"])["rules_without_deductions"]==[1,2,3,4]
    answer=[v for row in result["record"]["solution"] for v in row]
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":result["clues"],"answer":answer})=={"status":"ok","correct":True}
    # Those four black cells form ONE global component, not room-local size 1.
    assert recipe.build_from_clues([(Cell(r,c),answer[r*3+c]) for r,c in product(range(3),repeat=2)]).solve() is not None
    assert not all_answers(replace(recipe,rules=(*recipe.rules,ColorComponentSize(1))))
    other=((0,0,0),(0,1,1),(1,1,1))
    unique_recipe=replace(recipe,rules=(RoomComponentCount(other),EqualRoomComponentSizes(other),*recipe.rules[2:]))
    assert all_answers(unique_recipe)==nuritwin_reference(other)=={(0,1,0,1,1,0,1,0,0)}
    assert worker.generate_request(request(unique_recipe))["clues"]==[]
    for family in ("slitherlink","coupled"):
        with pytest.raises(ValueError):api.read_request({**request(recipe),"family":family})


def test_saved_display_rejects_over_limit_component_layouts():
    data=saved.puzzle_record(ShadingRecipe(1,2,(RoomComponentCount(((0,0),),0),)),[],seed=0)
    data.update(rows=2,cols=5,solution=[[0]*5,[0]*5],rules=[{"type":"room-component-count","rooms":[[0]*5,[0]*5],"black":True,"count":0}])
    with pytest.raises(ValueError,match="at most 9"):saved.show(data)
