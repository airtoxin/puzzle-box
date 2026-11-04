"""Component shape semantics, independent bounding boxes, and real compositions."""

from dataclasses import fields
import importlib
from itertools import product
from pathlib import Path

import pytest

from generator import generate
from puzzle import Cell, at_least_one
from puzzle_defs import (BlackCount, BlackDominoes, NonRectangularComponents,
                         RectangularComponents, ShadingRecipe)

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


def all_answers(recipe):
    puzzle = recipe.create_empty()
    answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(puzzle.black[c] != solution.value(puzzle.black[c]) for c in puzzle.board.cells))
    return answers


@pytest.mark.parametrize("rows,cols", [(1,1), (1,5), (5,1), (2,3), (3,2), (2,4), (3,3)])
@pytest.mark.parametrize("kind", [RectangularComponents, NonRectangularComponents])
@pytest.mark.parametrize("black", [True, False])
def test_local_corners_and_rectangle_clauses_match_independent_component_boxes(rows, cols, kind, black):
    rule = kind(black)
    expected = {bits for bits in product((0,1), repeat=rows*cols) if oracle.accepts(rule, bits, rows, cols)}
    assert all_answers(ShadingRecipe(rows, cols, (rule,))) == expected


@pytest.mark.parametrize("black", [True, False])
def test_empty_singleton_border_rectangle_and_bent_components(black):
    rectangle, nonrectangle = RectangularComponents(black), NonRectangularComponents(black)
    def accepts(rule, selected):
        bits = tuple(int(((r,c) in selected) == black) for r in range(3) for c in range(3))
        return oracle.accepts(rule, bits, 3, 3)
    assert accepts(rectangle, set()) and accepts(nonrectangle, set())
    for selected in [{(0,0)}, {(r,0) for r in range(3)}, {(r,c) for r in range(3) for c in range(3)}]:
        assert accepts(rectangle, selected) and not accepts(nonrectangle, selected)
    # Includes filled subrectangles. They must not be mistaken for complete components.
    bent = {(0,0),(0,1),(1,0)}
    assert accepts(nonrectangle, bent) and not accepts(rectangle, bent)
    separated = bent | {(2,2)}
    assert not accepts(rectangle, separated) and not accepts(nonrectangle, separated)


def test_nonrectangular_is_per_component_not_negation_of_all_rectangular():
    selected = {(0,0),(0,1),(1,0),(2,2)}  # one L plus a diagonal, isolated singleton
    recipe = ShadingRecipe(3,3, (NonRectangularComponents(True),))
    clues = [(Cell(r,c), int((r,c) in selected)) for r in range(3) for c in range(3)]
    assert recipe.build_from_clues(clues).solve() is None


@pytest.mark.parametrize("kind", [RectangularComponents, NonRectangularComponents])
@pytest.mark.parametrize("black", [True, False])
def test_exact_codec_and_declarative_color_parameter(kind, black):
    rule = kind(black)
    assert codec.read_rule(codec.rule_record(rule)) == rule
    assert {p.name for p in rule.ui.parameters} == {f.name for f in fields(rule)} == {"black"}
    for data in [{"type":rule.ui.identifier}, {**codec.rule_record(rule), "black": 1},
                 {**codec.rule_record(rule), "black": "white"}, {**codec.rule_record(rule), "extra": 0}]:
        with pytest.raises(ValueError): codec.read_rule(data)
    with pytest.raises(ValueError): kind(1)
    with pytest.raises(ValueError, match="exact built-in"): codec.rule_record(type("Changed", (kind,), {})(black))


def request(recipe):
    return {"format": api.PROFILE_FORMAT, "family":"shading", "rows":recipe.rows, "cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds), "seed":0, "budget_seconds":10}


def test_choco_shape_composition_matches_eight_independent_answers_and_round_trips():
    recipe = codec.load_recipe(EXAMPLES / "shading-choco-shapes-recipe.json")
    expected = {bits for bits in product((0,1), repeat=6)
                if all(oracle.accepts(rule,bits,2,3) for rule in recipe.rules)}
    assert len(expected) == 8 and all_answers(recipe) == expected
    assert set(finite.identifiable_completions(recipe)) == expected
    result = worker.generate_request(request(recipe))
    assert result == worker.generate_request(request(recipe)) and result["status"] == "ok"
    assert result["clues"] and saved.verify(result["record"])["unique"]
    assert "Every edge-connected black component is a filled rectangle" in saved.show(result["record"])
    assert "Every edge-connected white component is nonrectangular" in saved.show(result["record"])
    trace = deductions.explain_puzzle(result["record"])
    assert trace["rules_without_deductions"] == [1,2]
    answer = [v for row in result["record"]["solution"] for v in row]
    assert checks.check_answer({"format":checks.FORMAT, "request":result["request"], "clues":result["clues"],
                               "answer":answer}) == {"status":"ok", "correct":True}
    for family in ["slitherlink", "coupled"]:
        with pytest.raises(ValueError): api.read_request({**request(recipe), "family":family})


def test_opposite_component_requirements_and_empty_color_are_distinct():
    for black in [False, True]:
        rules = (RectangularComponents(black), NonRectangularComponents(black))
        assert all_answers(ShadingRecipe(2,3,rules)) == {tuple([int(not black)]*6)}
        with_color = (*rules, BlackCount(1))
        assert not all_answers(ShadingRecipe(2,3,with_color))


def test_black_dominoes_imply_black_rectangles_and_explicit_white_rectangles_generate():
    base = ShadingRecipe(2,3,(BlackDominoes(),))
    assert all_answers(base) == all_answers(ShadingRecipe(2,3,(*base.rules,RectangularComponents())))
    recipe = ShadingRecipe(2,3,(RectangularComponents(False), BlackCount(2)))
    record = saved.puzzle_record(recipe, generate(recipe,seed=0), seed=0)
    assert saved.verify(record)["unique"]
