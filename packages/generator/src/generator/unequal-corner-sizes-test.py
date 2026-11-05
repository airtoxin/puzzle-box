"""Component witness pairs versus flood fill and an independent union-find."""

from dataclasses import replace
import importlib
from itertools import product
from pathlib import Path

import pytest

from puzzle import Cell, at_least_one, unique
from puzzle_defs import (BlackCount, BlackDominoes, CornerLinkedComponents,
                         RoomComponentCount, ShadingRecipe, UnequalCornerComponentSizes)

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
    checks = importlib.import_module("web_answers")


def reference(bits,rows,cols,color):
    selected = [i for i,v in enumerate(bits) if bool(v) == color]
    parents = {i:i for i in selected}
    def root(i):
        while parents[i] != i:
            i = parents[i]
        return i
    for i in selected:
        for j in selected:
            if abs(i//cols-j//cols)+abs(i%cols-j%cols) == 1:
                parents[root(i)] = root(j)
    sizes = {}
    for i in selected:
        sizes[root(i)] = sizes.get(root(i),0)+1
    return all(root(i) == root(j) or sizes[root(i)] != sizes[root(j)]
               for i in selected for j in selected
               if abs(i//cols-j//cols) == abs(i%cols-j%cols) == 1)


def all_answers(recipe):
    puzzle = recipe.create_empty(); answers = set()
    assert puzzle.solution_vars is not None
    assert {id(v) for v in puzzle.solution_vars} == {id(puzzle.black[c]) for c in puzzle.board.cells}
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(puzzle.black[c] != solution.value(puzzle.black[c]) for c in puzzle.board.cells))
    return answers


@pytest.mark.parametrize("rows,cols",[(1,1),(1,4),(2,2),(2,3),(3,2)])
@pytest.mark.parametrize("color",[True,False])
def test_all_small_projected_answers_match_two_component_checks(rows,cols,color):
    rule = UnequalCornerComponentSizes(color)
    boards = list(product((0,1),repeat=rows*cols))
    expected = {b for b in boards if reference(b,rows,cols,color)}
    assert {b for b in boards if oracle.accepts(rule,b,rows,cols)} == expected
    assert all_answers(ShadingRecipe(rows,cols,(rule,))) == expected


def fixed(rows,cols,bits,*rules):
    return ShadingRecipe(rows,cols,rules).build_from_clues(
        [(Cell(r,c),bits[r*cols+c]) for r in range(rows) for c in range(cols)])


def test_nine_cell_flood_and_union_checks_agree_on_all_boards():
    for color in [True,False]:
        rule = UnequalCornerComponentSizes(color)
        for bits in product((0,1),repeat=9):
            assert oracle.accepts(rule,bits,3,3) == reference(bits,3,3,color)


@pytest.mark.parametrize("rows,cols,bits,expected",[
    (2,2,(1,0,0,1),False),  # Two equal singletons meet at a corner.
    (3,3,(1,1,0,0,0,1,0,0,1),False),  # Equal dominoes, in different orientations.
    (3,3,(1,0,0,0,1,0,0,1,0),True),  # A singleton meets a domino.
    (1,5,(1,1,0,1,1),True),  # Equal components are separated.
    (2,2,(1,1,1,0),True),  # Internal corner, not two components.
    (3,3,(1,1,1,1,0,1,1,1,1),True),  # One component with a hole.
    (2,3,(0,)*6,True),
    (2,3,(1,)*6,True),
])
def test_contact_area_and_identity_boundaries(rows,cols,bits,expected):
    for color in [True,False]:
        colored = bits if color else tuple(1-v for v in bits)
        p = fixed(rows,cols,colored,UnequalCornerComponentSizes(color))
        p.add(unique())  # Witnesses must not create additional visible answers.
        assert (p.solve(seed=0) is not None) == expected


def test_repeated_global_witnesses_do_not_follow_user_room_boundaries():
    rules = (UnequalCornerComponentSizes(),UnequalCornerComponentSizes(False))
    expected = {b for b in product((0,1),repeat=6)
                if reference(b,2,3,True) and reference(b,2,3,False)}
    assert all_answers(ShadingRecipe(2,3,rules)) == expected
    # The two room-local dominoes are one global component. Comparing their
    # local areas at this border would incorrectly reject this assignment.
    room_rule = RoomComponentCount(((0,0,0),(1,1,1)),1)
    p = fixed(2,3,(1,1,0,0,1,1),room_rule,UnequalCornerComponentSizes())
    p.add(unique()); assert p.solve(seed=0) is not None


def test_identical_rule_occurrences_preserve_answers_and_saved_occurrences():
    rule = UnequalCornerComponentSizes()
    recipe = ShadingRecipe(2,3,(rule,rule))  # Reapply the same immutable instance.
    expected = {b for b in product((0,1),repeat=6) if reference(b,2,3,True)}
    assert all_answers(recipe) == expected
    record = codec.recipe_record(recipe)
    assert record["rules"] == [codec.rule_record(rule),codec.rule_record(rule)]
    assert codec.read_recipe(record) == recipe
    p = fixed(2,3,(1,1,0,0,1,1),rule,rule)
    p.add(unique()); assert p.solve(seed=0) is not None
    # Saved/Python rule occurrences and closed Web IDs have different contracts.
    with pytest.raises(ValueError,match="duplicate"):
        api.read_request(request(recipe))


@pytest.mark.parametrize("bad",[0,1,None,"black",1.0])
def test_strict_color_input(bad):
    with pytest.raises(ValueError): UnequalCornerComponentSizes(bad)
    with pytest.raises(ValueError): codec.read_rule({"type":"unequal-corner-component-sizes","black":bad})


def test_exact_codecs_and_large_boards_reject_before_candidate_enumeration(monkeypatch):
    rule = UnequalCornerComponentSizes()
    assert codec.read_rule(codec.rule_record(rule)) == rule
    for broken in [{"type":rule.ui.identifier},{**codec.rule_record(rule),"extra":0}]:
        with pytest.raises(ValueError): codec.read_rule(broken)
    with pytest.raises(ValueError,match="exact built-in"):
        codec.rule_record(type("Changed",(UnequalCornerComponentSizes,),{})())
    module = importlib.import_module("puzzle_defs.puzzles.unequal_corner_sizes")
    monkeypatch.setattr(module,"_component_uses",lambda *a,**k:pytest.fail("Must reject before enumeration"))
    recipe = ShadingRecipe(2,5,(rule,))
    for action in [recipe.create_empty,lambda:codec.recipe_record(recipe),
                   lambda:saved.puzzle_record(recipe,[],seed=0)]:
        with pytest.raises(ValueError,match="at most 9"): action()


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_nuribou_example_removes_an_equal_corner_pair_and_retains_necessary_hints():
    recipe = codec.load_recipe(EXAMPLES/"shading-nuribou-recipe.json")
    assert len(all_answers(replace(recipe,rules=recipe.rules[:-1]))) == 3
    expected = {tuple(map(int,b)) for b in ["010001001","110001000"]}
    assert all_answers(recipe) == set(finite.identifiable_completions(recipe)) == expected
    # Comparing WHITE components instead leaves the third black assignment.
    white = replace(recipe,rules=(*recipe.rules[:-1],UnequalCornerComponentSizes(False)))
    assert len(all_answers(white)) == 3
    result = worker.generate_request(request(recipe))
    assert result["status"] == "ok" and result["clues"]
    assert saved.verify(result["record"])["unique"]
    assert "different areas" in saved.show(result["record"])
    assert "Answer template:" in saved.show(result["record"])
    assert 4 in deductions.explain_puzzle(result["record"])["rules_without_deductions"]
    answer = sum(result["record"]["solution"],[])
    data = {"format":checks.FORMAT,"request":result["request"],"clues":result["clues"],"answer":answer}
    assert checks.check_answer(data) == {"status":"ok","correct":True}
    assert checks.check_answer({**data,"answer":[1-v for v in answer]}) == {"status":"ok","correct":False}
    assert worker.generate_request({**request(recipe),"clue_kinds":[]})["status"] == "insufficient_hints"


def test_incompatible_equal_size_contact_chain_and_other_profiles():
    recipe = ShadingRecipe(3,3,(BlackDominoes(),CornerLinkedComponents(),BlackCount(4),UnequalCornerComponentSizes()))
    assert all_answers(replace(recipe,rules=recipe.rules[:-1]))
    assert worker.generate_request(request(recipe))["status"] == "unsatisfiable"
    data = request(ShadingRecipe(2,3,(UnequalCornerComponentSizes(),)))
    parsed = api.read_request(data)
    assert {c["kind"] for c in parsed.plan["requirements"]["channels"]} == {"binary-cells","cell-givens"}
    assert "rooms" not in parsed.plan  # Internal one-room witnesses are not UI inputs.
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**data,"family":family})
