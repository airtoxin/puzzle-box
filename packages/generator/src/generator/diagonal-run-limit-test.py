"""Diagonal windows versus complete-line grouping and projected CSP answers."""

import importlib
from itertools import product
from pathlib import Path

import pytest

from puzzle import at_least_one
from puzzle_defs import (DiagonalRunLimit, NoThreeConsecutive, RunLengthLimit,
                         RoomBlackCount, ShadingRecipe)

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
    puzzle = recipe.create_empty(); answers = set()
    assert puzzle.solution_vars is not None and len(puzzle.solution_vars) == recipe.rows*recipe.cols
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(puzzle.black[c] != solution.value(puzzle.black[c]) for c in puzzle.board.cells))
    return answers


def reference(bits, rows, cols, maximum):
    # Walk each maximal diagonal once, and measure runs without CSP windows.
    for step in (-1, 1):
        starts = [(0,c) for c in range(cols)] + [(r,0 if step == 1 else cols-1) for r in range(1,rows)]
        for r,c in starts:
            previous, length = None, 0
            while r < rows and 0 <= c < cols:
                value = bits[r*cols+c]
                length = length+1 if value == previous else 1
                if length > maximum:
                    return False
                previous = value; r += 1; c += step
    return True


@pytest.mark.parametrize("rows,cols,maximum", [
    (1,1,1),(1,4,1),(4,1,1),(2,2,1),(2,3,1),(2,3,2),(3,3,1),(3,3,2),
])
def test_projected_answers_match_two_independent_diagonal_scans(rows,cols,maximum):
    rule = DiagonalRunLimit(maximum)
    boards = list(product((0,1),repeat=rows*cols))
    expected = {b for b in boards if reference(b,rows,cols,maximum)}
    assert {b for b in boards if oracle.accepts(rule,b,rows,cols)} == expected
    assert all_answers(ShadingRecipe(rows,cols,(rule,))) == expected
    assert {tuple(1-v for v in b) for b in expected} == expected


def test_diagonals_do_not_mean_rows_columns_turns_or_wraparound():
    horizontal = (1,1,1, 0,0,0, 1,1,1)
    assert oracle.accepts(DiagonalRunLimit(),horizontal,3,3)
    assert not oracle.accepts(NoThreeConsecutive(),horizontal,3,3)
    for diagonal in [(1,0,0, 0,1,0, 0,0,1),(0,0,1, 0,1,0, 1,0,0)]:
        assert oracle.accepts(NoThreeConsecutive(),diagonal,3,3)
        assert not oracle.accepts(DiagonalRunLimit(),diagonal,3,3)
    assert all_answers(ShadingRecipe(1,4,(DiagonalRunLimit(1),))) == set(product((0,1),repeat=4))
    assert not all_answers(ShadingRecipe(2,2,(DiagonalRunLimit(1),RunLengthLimit(1))))


@pytest.mark.parametrize("value", [0,-1,True,False,1.5,"2",None])
def test_strict_positive_limits(value):
    with pytest.raises(ValueError): DiagonalRunLimit(value)
    with pytest.raises(ValueError): codec.read_rule({"type":"diagonal-run-limit","max_length":value})


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],
                      "parameters":{k:v for k,v in r.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_exact_codec_legacy_separation_and_redundant_huge_limit():
    rule = DiagonalRunLimit(2**100)
    assert codec.read_rule(codec.rule_record(rule)) == rule
    assert all_answers(ShadingRecipe(2,2,(rule,))) == set(product((0,1),repeat=4))
    for broken in [{"type":rule.ui.identifier},{**codec.rule_record(rule),"extra":0}]:
        with pytest.raises(ValueError): codec.read_rule(broken)
    with pytest.raises(ValueError,match="exact built-in"):
        codec.rule_record(type("Changed",(DiagonalRunLimit,),{})(2))
    assert codec.read_rule({"type":"run-length-limit","max_length":2}) == RunLengthLimit(2)
    assert codec.read_rule({"type":"no-three-consecutive"}) == NoThreeConsecutive()
    assert codec.rule_record(NoThreeConsecutive()) == {"type":"no-three-consecutive"}


def test_full_board_nondango_fragment_retains_needed_hints_and_checks_answers():
    recipe = codec.load_recipe(EXAMPLES/"shading-diagonal-runs-recipe.json")
    assert isinstance(recipe.rules[0],RoomBlackCount)
    without_diagonal = ShadingRecipe(3,3,recipe.rules[:-1])
    assert len(all_answers(without_diagonal)) == 13
    expected = {tuple(map(int,b)) for b in
                ['010001101','010010101','010110001','011100001','100001110','101100010']}
    assert all_answers(recipe) == set(finite.identifiable_completions(recipe)) == expected
    result = worker.generate_request(request(recipe))
    assert result["status"] == "ok" and result["clues"]
    assert result == worker.generate_request(request(recipe))
    assert saved.verify(result["record"])["unique"]
    assert "straight diagonal run" in saved.show(result["record"])
    assert "Every cell participates" in saved.show(result["record"])
    assert 3 in deductions.explain_puzzle(result["record"])["rules_without_deductions"]
    answer = sum(result["record"]["solution"],[])
    data = {"format":checks.FORMAT,"request":result["request"],"clues":result["clues"],"answer":answer}
    assert checks.check_answer(data) == {"status":"ok","correct":True}
    assert checks.check_answer({**data,"answer":[1-v for v in answer]}) == {"status":"ok","correct":False}
    data_without_cells = {**request(recipe),"clue_kinds":[]}
    assert worker.generate_request(data_without_cells)["status"] == "insufficient_hints"
    # One black per entire row gives only permutation matrices before the new
    # rule, and no valid boards after it: a short diagonal can also be all white.
    stripes = RoomBlackCount(((0,0,0),(1,1,1),(2,2,2)),1)
    assert len(all_answers(ShadingRecipe(3,3,(stripes,NoThreeConsecutive())))) == 6
    assert not all_answers(ShadingRecipe(3,3,(stripes,NoThreeConsecutive(),DiagonalRunLimit())))


def test_web_metadata_and_resource_limits_reject_other_profiles():
    data = request(ShadingRecipe(2,3,(DiagonalRunLimit(25),)))
    parsed = api.read_request(data)
    assert parsed.recipe.rules == (DiagonalRunLimit(25),)
    assert {c["kind"] for c in parsed.plan["requirements"]["channels"]} == {"binary-cells","cell-givens"}
    assert api.CATALOG["diagonal-run-limit"].ui.parameters[0].maximum == 25
    for value in [0,26,True,2.0]:
        broken = request(ShadingRecipe(2,3,(DiagonalRunLimit(),)))
        broken["rules"][0]["parameters"]["max_length"] = value
        with pytest.raises(ValueError): api.read_request(broken)
    for family in ["slitherlink","coupled"]:
        with pytest.raises(ValueError): api.read_request({**data,"family":family})
    assert api.read_request(request(ShadingRecipe(4,3,(DiagonalRunLimit(),)))).recipe.rows == 4
