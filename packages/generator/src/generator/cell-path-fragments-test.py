"""Degree and exact endpoint indicators versus masks and induced-path walks."""

import importlib
from itertools import product
from pathlib import Path

import pytest

from puzzle import Cell, Puzzle, at_least_one, unique
from puzzle_defs import (ColorDegreeRange, ColorEndpointCount, ConnectedBlack,
                         ConnectedWhite, ShadingRecipe)

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


def selected_degrees(bits, rows, cols, black):
    selected = {i for i,b in enumerate(bits) if b == int(black)}
    mask = sum(1 << i for i in selected)
    result = []
    for i in selected:
        r,c = divmod(i,cols)
        neighbors = sum(1 << (s*cols+t) for s,t in [(r-1,c),(r+1,c),(r,c-1),(r,c+1)]
                        if 0 <= s < rows and 0 <= t < cols)
        result.append((mask & neighbors).bit_count())
    return result


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
@pytest.mark.parametrize("minimum,maximum", [(0,0),(0,1),(1,2),(2,2),(3,4),(0,4)])
def test_degree_ranges_match_all_two_by_three_masks(minimum,maximum,black):
    rule = ColorDegreeRange(minimum,maximum,black)
    masks = list(product((0,1),repeat=6))
    expected = {b for b in masks if all(minimum <= n <= maximum for n in selected_degrees(b,2,3,black))}
    assert {b for b in masks if oracle.accepts(rule,b,2,3)} == expected
    assert all_answers(ShadingRecipe(2,3,(rule,))) == expected


@pytest.mark.parametrize("black", [True,False])
@pytest.mark.parametrize("count", [0,1,2,3,6])
def test_endpoint_counts_match_all_masks_without_assuming_even_counts(count,black):
    rule = ColorEndpointCount(count,black)
    masks = list(product((0,1),repeat=6))
    expected = {b for b in masks if selected_degrees(b,2,3,black).count(1) == count}
    assert {b for b in masks if oracle.accepts(rule,b,2,3)} == expected
    assert all_answers(ShadingRecipe(2,3,(rule,))) == expected


def path_walks(rows,cols):
    cells = {(r,c) for r in range(rows) for c in range(cols)}
    paths = set()
    def visit(path):
        if len(path) >= 2:
            paths.add(frozenset(path))
        r,c = path[-1]
        for q in [(r-1,c),(r+1,c),(r,c-1),(r,c+1)]:
            if q not in cells or q in path:
                continue
            # A new cell may touch the previous end only; this directly walks
            # induced paths instead of testing degrees or counting endpoints.
            if sum(abs(q[0]-s)+abs(q[1]-t) == 1 for s,t in path) == 1:
                visit(path+[q])
    for cell in sorted(cells):
        visit([cell])
    return paths


def fixed(rows,cols,rules,selected):
    recipe = ShadingRecipe(rows,cols,rules)
    return recipe.build_from_clues([(Cell(r,c),int((r,c) in selected)) for r in range(rows) for c in range(cols)])


@pytest.mark.parametrize("black", [True,False])
def test_full_path_composition_matches_independent_walks_and_keeps_diagonal_contact(black):
    connected = ConnectedBlack() if black else ConnectedWhite()
    recipe = ShadingRecipe(3,3,(connected,ColorDegreeRange(1,2,black),ColorEndpointCount(2,black)))
    paths = path_walks(3,3)
    expected = {tuple(int(((r,c) in p) == black) for r in range(3) for c in range(3)) for p in paths}
    assert expected and all_answers(recipe) == expected
    # Open perimeter with diagonally adjacent endpoints across a missing corner.
    diagonal = {(0,1),(0,2),(1,2),(2,2),(2,1),(2,0),(1,0)}
    assert frozenset(diagonal) in paths


def test_each_path_condition_has_a_concrete_counterexample_when_omitted():
    rules = (ConnectedBlack(),ColorDegreeRange(),ColorEndpointCount())
    branch_cycle = {(0,0),(0,1),(1,0),(1,1),(0,2),(2,0)}
    assert fixed(3,3,(rules[0],rules[2]),branch_cycle).solve() is not None
    assert fixed(3,3,rules,branch_cycle).solve() is None
    square = {(0,0),(0,1),(1,0),(1,1)}
    assert fixed(3,3,rules[:2],square).solve() is not None
    assert fixed(3,3,rules,square).solve() is None
    separate = square | {(0,3),(1,3)}
    assert fixed(3,4,rules[1:],separate).solve() is not None
    assert fixed(3,4,rules,separate).solve() is None


def test_isolated_selected_cells_and_opposite_cells_with_one_neighbor_are_not_endpoints():
    assert all_answers(ShadingRecipe(1,2,(ColorEndpointCount(0),))) == {(0,0),(1,0),(0,1)}
    assert all_answers(ShadingRecipe(1,1,(ColorEndpointCount(1),))) == set()
    assert not all_answers(ShadingRecipe(1,1,(ColorDegreeRange(1,2),ColorEndpointCount(0),ConnectedBlack())))
    tee = {(0,0),(0,1),(0,2),(1,1)}
    assert fixed(2,3,(ColorEndpointCount(3),),tee).solve() is not None
    assert fixed(2,3,(ColorEndpointCount(2),),tee).solve() is None  # Cannot hide an endpoint witness.


def test_both_colors_and_auxiliary_variables_preserve_visible_uniqueness():
    rules = (ColorDegreeRange(),ColorDegreeRange(1,2,False),
             ColorEndpointCount(),ColorEndpointCount(2,False),ConnectedBlack(),ConnectedWhite())
    puzzle = fixed(2,3,rules,{(0,0),(0,1),(0,2)})
    assert puzzle.solution_vars is not None and len(puzzle.solution_vars) == 6
    puzzle.add(unique())
    assert puzzle.solve() is not None


@pytest.mark.parametrize("minimum,maximum", [(-1,2),(0,5),(3,2),(True,2),(0,1.0)])
def test_degree_range_validation(minimum,maximum):
    with pytest.raises(ValueError): ColorDegreeRange(minimum,maximum)


@pytest.mark.parametrize("bad", [-1,True,1.0,"2"])
def test_endpoint_count_validation(bad):
    with pytest.raises(ValueError): ColorEndpointCount(bad)


@pytest.mark.parametrize("bad", [0,1,None,"black"])
def test_color_is_a_strict_boolean(bad):
    with pytest.raises(ValueError): ColorEndpointCount(2,bad)
    with pytest.raises(ValueError): ColorDegreeRange(1,2,bad)


def test_exact_codecs_and_endpoint_bound_are_checked_before_auxiliary_maps(monkeypatch):
    for rule in [ColorDegreeRange(),ColorDegreeRange(0,4,False),ColorEndpointCount(0,False),ColorEndpointCount()]:
        assert codec.read_rule(codec.rule_record(rule)) == rule
        with pytest.raises(ValueError): codec.read_rule({**codec.rule_record(rule),"extra":0})
    with pytest.raises(ValueError,match="exact built-in"):
        codec.rule_record(type("Changed",(ColorDegreeRange,),{})())
    with pytest.raises(ValueError,match="Endpoint count"):
        codec.recipe_record(ShadingRecipe(1,1,(ColorEndpointCount(),)))
    monkeypatch.setattr(Puzzle,"int_var_map",lambda *a,**k: pytest.fail("Must reject first"))
    with pytest.raises(ValueError,match="Endpoint count"):
        ShadingRecipe(1,1,(ColorEndpointCount(),)).create_empty()


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


@pytest.mark.parametrize("name,color", [("cell-path","black"),("white-path","white")])
def test_examples_generate_check_and_report_unsupported_deductions(name,color):
    recipe = codec.load_recipe(EXAMPLES / f"shading-{name}-recipe.json")
    result = worker.generate_request(request(recipe))
    assert result["status"] == "ok" and saved.verify(result["record"])["unique"]
    assert "orthogonally adjacent" in saved.show(result["record"]) and color in saved.show(result["record"])
    assert deductions.explain_puzzle(result["record"])["rules_without_deductions"][-2:] == [2,3]
    answer = [v for row in result["record"]["solution"] for v in row]
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":result["clues"],
                               "answer":answer}) == {"status":"ok","correct":True}
    data = request(recipe)
    data["rules"][1]["parameters"]["minimum"] = 3
    with pytest.raises(ValueError): api.read_request(data)
