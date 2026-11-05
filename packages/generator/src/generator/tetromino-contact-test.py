"""Exact room masks, independent congruence, and a small full LITS composition."""

import importlib
from itertools import combinations, product
from pathlib import Path

import pytest

from generator import generate
from puzzle import Cell, at_least_one
from puzzle.constraints import ShapeAcrossConstraint
from puzzle.features import MissingFeatureError
from puzzle_defs import NoTouchingEqualTetrominoes, RoomConnectedBlack, ShadingRecipe

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

ROOMS = ((0,0,0,0),(0,0,0,0),(1,1,1,1),(1,1,1,1))


def all_answers(recipe):
    puzzle = recipe.create_empty(); answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(puzzle.black[c] != solution.value(puzzle.black[c]) for c in puzzle.board.cells))
    return answers


def connected(points):
    if not points: return False
    todo=[min(points)]; seen=set()
    while todo:
        r,c=todo.pop()
        if (r,c) in seen: continue
        seen.add((r,c)); todo.extend(p for p in [(r-1,c),(r+1,c),(r,c-1),(r,c+1)] if p in points and p not in seen)
    return seen == points


def congruent(first,second):
    # Align each candidate origin to a fixed anchor, using eight independently
    # written rigid transforms rather than the production polyomino variants.
    anchor=min(second)
    transforms=[lambda r,c:(r,c),lambda r,c:(r,-c),lambda r,c:(-r,c),lambda r,c:(-r,-c),
                lambda r,c:(c,r),lambda r,c:(c,-r),lambda r,c:(-c,r),lambda r,c:(-c,-r)]
    for transform in transforms:
        rotated={transform(r,c) for r,c in first}
        for origin in rotated:
            if {(r-origin[0]+anchor[0],c-origin[1]+anchor[1]) for r,c in rotated} == second: return True
    return False


def fixed_solution(first,second,extra=()):
    recipe=ShadingRecipe(4,4,(NoTouchingEqualTetrominoes(ROOMS),*extra))
    black=first|second
    return recipe.build_from_clues([(Cell(r,c),int((r,c) in black)) for r in range(4) for c in range(4)]).solve()


@pytest.mark.parametrize("second", [{(2,0),(3,0),(3,1),(3,2)}, {(2,2),(3,0),(3,1),(3,2)},
                                   {(2,0),(2,1),(2,2),(3,2)}])
def test_translated_reflected_and_rotated_equal_pieces_cannot_fake_inactive_witnesses(second):
    first={(0,0),(1,0),(1,1),(1,2)}
    assert congruent(first,second)
    assert fixed_solution(first,second) is None


def test_different_shapes_and_diagonal_only_equal_shapes_are_allowed():
    first={(0,0),(1,0),(1,1),(1,2)}
    different={(2,1),(3,0),(3,1),(3,2)}
    assert not congruent(first,different) and fixed_solution(first,different) is not None
    diagonal={(2,3),(3,1),(3,2),(3,3)}
    assert congruent(first,diagonal) and fixed_solution(first,diagonal) is not None


def test_other_masks_remain_outside_the_fragment_until_size_and_connectivity_are_added():
    rooms=((0,0,0),(1,1,1))
    assert all_answers(ShadingRecipe(2,3,(NoTouchingEqualTetrominoes(rooms),))) == set(product((0,1),repeat=6))
    first={(0,0),(1,0),(0,2),(1,2)}; second={(2,0),(3,0),(2,2),(3,2)}
    assert fixed_solution(first,second) is not None
    assert fixed_solution(first,second,(RoomConnectedBlack(ROOMS),)) is None
    # A larger black set is not a tetromino even when it contains a matching
    # connected four-cell subset touching another room's piece.
    first={(0,0),(1,0),(1,1),(1,2)}
    second={(2,0),(3,0),(3,1),(3,2),(2,3)}
    assert fixed_solution(first,second) is not None


def test_conditional_pieces_do_not_claim_full_tiling_capabilities():
    puzzle=ShadingRecipe(4,4,(NoTouchingEqualTetrominoes(ROOMS),)).create_empty()
    with pytest.raises(MissingFeatureError):
        puzzle.add(ShapeAcrossConstraint([],puzzle.bool_var_map("unrelated",[])))


def test_small_room_masks_match_independent_conditional_checker():
    rooms=((0,0,0,0),(1,1,1,1)); rule=NoTouchingEqualTetrominoes(rooms)
    expected={b for b in product((0,1),repeat=8) if oracle.accepts(rule,b,2,4)}
    assert len(expected) == 255 and all_answers(ShadingRecipe(2,4,(rule,))) == expected


def test_full_lits_matches_independent_two_room_piece_enumeration_and_generates():
    recipe=codec.load_recipe(EXAMPLES / "shading-lits-recipe.json")
    choices=[]
    for rows in [range(2),range(2,4)]:
        cells={(r,c) for r in rows for c in range(4)}
        choices.append([set(p) for p in combinations(sorted(cells),4) if connected(set(p))])
    base_expected=set(); expected=set()
    for first,second in product(*choices):
        black=first|second
        if not connected(black): continue
        if any({(r,c),(r+1,c),(r,c+1),(r+1,c+1)} <= black for r in range(3) for c in range(3)): continue
        bits=tuple(int((r,c) in black) for r in range(4) for c in range(4)); base_expected.add(bits)
        if not congruent(first,second): expected.add(bits)
    assert expected and expected < base_expected
    assert all_answers(ShadingRecipe(4,4,recipe.rules[:-1])) == base_expected
    assert all_answers(recipe) == expected
    puzzle=recipe.create_empty()
    assert puzzle.solution_vars is not None and len(puzzle.solution_vars) == 16
    clues=generate(recipe,seed=0); record=saved.puzzle_record(recipe,clues,seed=0)
    assert clues and saved.verify(record)["unique"] and "rotations/reflections" in saved.show(record)
    with pytest.raises(ValueError,match="9 cells"): deductions.explain_puzzle(record)


def test_codec_geometry_and_input_size_are_validated_before_candidate_enumeration(monkeypatch):
    rule=NoTouchingEqualTetrominoes(ROOMS)
    assert codec.read_rule(codec.rule_record(rule)) == rule
    with pytest.raises(ValueError): codec.read_rule({**codec.rule_record(rule),"extra":0})
    with pytest.raises(ValueError): codec.read_rule({"type":rule.ui.identifier,"rooms":{}})
    with pytest.raises(ValueError,match="exact built-in"):
        codec.rule_record(type("Changed",(NoTouchingEqualTetrominoes,),{})(ROOMS))
    wrong=ShadingRecipe(4,4,(rule,RoomConnectedBlack(((0,)*4,)*4)))
    with pytest.raises(ValueError,match="same partition"): codec.recipe_record(wrong)
    module=importlib.import_module("puzzle_defs.puzzles.room_shapes")
    monkeypatch.setattr(module,"enumerate_connected_regions",lambda *a,**k: pytest.fail("Must reject first"))
    with pytest.raises(ValueError,match="100 board cells"):
        ShadingRecipe(1,101,(NoTouchingEqualTetrominoes(((0,)*101,)),)).create_empty()


def test_web_sized_o_and_l_example_is_valid_until_black_two_by_two_is_forbidden():
    recipe=codec.load_recipe(EXAMPLES / "shading-tetromino-contact-recipe.json")
    assert len(all_answers(recipe)) == 2
    from puzzle_defs import NoBlack2x2
    assert not all_answers(ShadingRecipe(3,3,(*recipe.rules,NoBlack2x2())))


def test_six_by_six_fixed_boards_match_independent_shape_and_contact_checker():
    rooms = tuple((r//3,)*6 for r in range(6))
    rule = NoTouchingEqualTetrominoes(rooms)
    first = {(1,0),(2,0),(2,1),(2,2)}
    examples = [
        {(3,0),(4,0),(4,1),(4,2)},  # translated L touching the first
        {(3,1),(4,0),(4,1),(4,2)},  # T touching L
        {(3,3),(4,3),(4,4),(4,5)},  # equal L without edge contact
        {(3,0),(4,0),(4,1),(4,2),(3,5)},  # five cells is not a piece
        {(3,0),(3,2),(4,0),(4,2)},  # disconnected four-cell mask
        set(),
    ]
    for second in examples:
        points = first | second
        touch = any(abs(r-s)+abs(c-t) == 1 for r,c in first for s,t in second)
        expected = not (len(second) == 4 and connected(second) and touch and congruent(first, second))
        bits = tuple(int((r,c) in points) for r in range(6) for c in range(6))
        assert oracle.accepts(rule, bits, 6, 6) == expected
        p = ShadingRecipe(6,6,(rule,)).build_from_clues(
            [(Cell(r,c),int((r,c) in points)) for r in range(6) for c in range(6)])
        assert (p.solve(seed=0) is not None) == expected


def test_six_by_six_lits_generation_is_unique_and_checks_real_answers():
    rooms = [[r//3]*6 for r in range(6)]
    request = {"format": api.FORMAT, "rows": 6, "cols": 6,
        "rules": [{"id":"room-black-count","parameters":{"rooms":rooms,"count":4}},
                  {"id":"room-connected-black","parameters":{"rooms":rooms,"nonempty":True}},
                  {"id":"connected-black","parameters":{"nonempty":True}},
                  {"id":"no-black-2x2","parameters":{}},
                  {"id":"no-touching-equal-tetrominoes","parameters":{"rooms":rooms}}],
        "clue_kinds":["cell","row-count","column-count"],"seed":0,"budget_seconds":30}
    result = worker.generate_request(request)
    assert result["status"] == "ok" and result["evidence"]["unique"] and result["evidence"]["irreducible"]
    assert result["plan"]["requirements"]["max_cells"] == 100
    assert saved.verify(result["record"])["unique"]
    answer = [v for row in result["record"]["solution"] for v in row]
    assert oracle.accepts(NoTouchingEqualTetrominoes(tuple(map(tuple,rooms))), answer, 6, 6)
    submission = {"format":checks.FORMAT,"request":request,"clues":result["clues"],"answer":answer}
    assert checks.check_answer(submission) == {"status":"ok","correct":True}
    answer[0] = 1-answer[0]
    assert checks.check_answer(submission) == {"status":"ok","correct":False}


def test_full_100_cell_board_preserves_rotated_shape_contacts():
    rooms = tuple((r//5,)*10 for r in range(10))
    rule = NoTouchingEqualTetrominoes(rooms)
    first = {(3,0),(4,0),(4,1),(4,2)}
    same_touching = {(5,0),(6,0),(6,1),(6,2)}
    rotated_touching = {(5,1),(6,1),(7,0),(7,1)}
    different_touching = {(5,1),(6,0),(6,1),(6,2)}
    for second, expected in [(same_touching, False), (rotated_touching, False), (different_touching, True)]:
        bits = tuple(int((r,c) in first|second) for r in range(10) for c in range(10))
        assert oracle.accepts(rule,bits,10,10) == expected
        puzzle = ShadingRecipe(10,10,(rule,)).build_from_clues(
            [(Cell(r,c),int((r,c) in first|second)) for r in range(10) for c in range(10)])
        assert (puzzle.solve(seed=0) is not None) == expected
