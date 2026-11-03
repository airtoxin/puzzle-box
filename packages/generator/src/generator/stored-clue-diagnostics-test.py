"""Cross-check fixed-hint rule removal against actual DSL answers."""

from copy import deepcopy
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from generator import generate
from puzzle import Cell, at_least_one
from puzzle_defs import BlackCount, ConnectedWhite, NonTouchingBlack, NoWhite2x2, ShadingRecipe

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"


@pytest.fixture(scope="module")
def diagnostic():
    sys.path.insert(0, str(EXAMPLES))
    try:
        yield importlib.import_module("diagnose_shading_rules")
    finally:
        sys.path.remove(str(EXAMPLES))


def _example():
    return {"format": "puzzle-box/shading-v1", "rows": 2, "cols": 2,
            "rules": [{"type": "count", "count": 1}],
            "clues": [[0, 0, 0], [0, 1, 0], [1, 0, 0]], "solution": [[0, 0], [0, 1]]}


def _flat(board):
    return tuple(v for row in board for v in row)


def _answers(recipe, clues):
    puzzle = recipe.build_from_clues(clues)
    variables = [puzzle.black[c] for c in puzzle.board.cells]
    answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = _flat(puzzle.result(solution))
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(v != solution.value(v) for v in variables))
        assert len(answers) <= 2**(recipe.rows*recipe.cols)
    return answers


def test_full_cell_redundancy_does_not_survive_clue_reduction(diagnostic):
    data = _example()
    before = deepcopy(data)
    report = diagnostic.diagnose(data)
    assert data == before  # This is a report, not a rule/clue rewrite.
    assert report["stored_clues_irreducible"] is True
    removal, = report["removals"]
    assert removal["answers_with_full_candidate_clues"] == 1
    assert removal["necessary_with_full_candidate_clues"] is False
    assert removal["answers_with_stored_clues"] == 2
    assert removal["necessary_with_stored_clues"] is True
    assert removal["needed_with_stored_but_not_full_clues"] is True
    assert removal["stored_clue_alternative"] == [[0, 0], [0, 0]]
    recipe, clues, _ = diagnostic._read_puzzle(data)
    assert _answers(recipe, clues) == {_flat(data["solution"])}
    assert _answers(ShadingRecipe(2, 2, ()), clues) == {_flat(data["solution"]), (0, 0, 0, 0)}


@pytest.mark.parametrize("rules", [
    (BlackCount(1),), (BlackCount(1), NonTouchingBlack()),
    (BlackCount(1), ConnectedWhite(False), NoWhite2x2()),
    (NonTouchingBlack(True), ConnectedWhite(), BlackCount(1)),
])
@pytest.mark.parametrize("kinds", [("cell",), ("row-count", "column-count"),
                                    ("cell", "row-count", "column-count")])
def test_generated_puzzles_every_rule_removal_and_witness_match_dsl(diagnostic, rules, kinds):
    recipe = ShadingRecipe(2, 2, rules, kinds)
    clues = generate(recipe, seed=6)
    puzzle = recipe.build_from_clues(clues)
    solution = puzzle.solve(seed=0)
    assert solution is not None
    answer = puzzle.result(solution)
    full = recipe.extract_clues(solution, puzzle)
    data = {"format": "puzzle-box/shading-v2", "rows": 2, "cols": 2,
            "rules": [diagnostic.rule_record(r) for r in rules], "clue_kinds": list(kinds),
            "clues": [diagnostic.clue_record(c) for c in clues], "solution": answer}
    report = diagnostic.diagnose(data)
    assert report["original_answer_count"] == 1 and report["stored_clues_irreducible"] is True
    assert report["full_candidate_clues"] == [diagnostic.clue_record(c) for c in full]
    original = _flat(answer)
    for i, removal in enumerate(report["removals"]):
        relaxed = ShadingRecipe(2, 2, rules[:i]+rules[i+1:], kinds)
        stored_answers, full_answers = _answers(relaxed, clues), _answers(relaxed, full)
        assert full_answers <= stored_answers and original in full_answers
        assert removal["answers_with_stored_clues"] == len(stored_answers)
        assert removal["answers_with_full_candidate_clues"] == len(full_answers)
        assert removal["necessary_with_stored_clues"] == (len(stored_answers) > 1)
        assert removal["necessary_with_full_candidate_clues"] == (len(full_answers) > 1)
        for field, answers in [("stored_clue_alternative", stored_answers), ("full_clue_alternative", full_answers)]:
            if len(answers) > 1:
                alternative = _flat(removal[field])
                assert alternative in answers and alternative != original
                fixed = [(Cell(j//2, j%2), v) for j, v in enumerate(alternative)]
                assert recipe.build_from_clues(fixed).solve(seed=0) is None
            else:
                assert removal[field] is None


def test_real_three_by_three_generated_artifact_has_two_and_nine_answers(diagnostic):
    data = {"format": "puzzle-box/shading-v2", "rows": 3, "cols": 3,
        "rules": [{"type": "count", "count": 3}, {"type": "non-touching", "diagonal": False}],
        "clue_kinds": ["cell", "row-count", "column-count"],
        "clues": [{"type": "row-count", "row": 0, "count": 1}, {"type": "row-count", "row": 1, "count": 2}],
        "solution": [[0, 1, 0], [1, 0, 1], [0, 0, 0]]}
    report = diagnostic.diagnose(data)
    assert [r["answers_with_stored_clues"] for r in report["removals"]] == [2, 9]
    assert [r["answers_with_full_candidate_clues"] for r in report["removals"]] == [1, 1]
    recipe, clues, _ = diagnostic._read_puzzle(data)
    for i, removal in enumerate(report["removals"]):
        relaxed = ShadingRecipe(3, 3, recipe.rules[:i]+recipe.rules[i+1:], recipe.clue_kinds)
        answers = _answers(relaxed, clues)
        assert len(answers) == removal["answers_with_stored_clues"]
        assert _flat(removal["stored_clue_alternative"]) in answers


def test_nonirreducible_and_duplicate_clues_are_reported_by_occurrence(diagnostic):
    data = _example()
    data["clues"].append([0, 0, 0])
    report = diagnostic.diagnose(data)
    assert report["stored_clues_irreducible"] is False
    assert report["removable_clue_indices"] == [1, 4]
    data["clues"] = [[r, c, data["solution"][r][c]] for r in range(2) for c in range(2)]
    report = diagnostic.diagnose(data)
    assert report["removable_clue_indices"] == [1, 2, 3, 4]
    assert report["removals"][0]["necessary_with_stored_clues"] is False


def test_count_hints_can_need_a_rule_even_before_reduction(diagnostic):
    recipe = ShadingRecipe(3, 3, (BlackCount(3), NonTouchingBlack()), ("row-count", "column-count"))
    answer = [[0, 0, 0], [0, 1, 0], [1, 0, 1]]
    fixed = [(Cell(r, c), answer[r][c]) for r in range(3) for c in range(3)]
    puzzle = recipe.build_from_clues(fixed)
    solution = puzzle.solve(seed=0)
    assert solution is not None
    clues = recipe.extract_clues(solution, puzzle)
    data = {"format": "puzzle-box/shading-v2", "rows": 3, "cols": 3,
            "rules": [diagnostic.rule_record(r) for r in recipe.rules], "clue_kinds": list(recipe.clue_kinds),
            "clues": [diagnostic.clue_record(c) for c in clues], "solution": answer}
    report = diagnostic.diagnose(data)
    removal = report["removals"][1]
    answers = _answers(ShadingRecipe(3, 3, (BlackCount(3),), recipe.clue_kinds), clues)
    assert removal["answers_with_full_candidate_clues"] == removal["answers_with_stored_clues"] == len(answers) == 3
    assert removal["necessary_with_full_candidate_clues"] is True
    assert removal["needed_with_stored_but_not_full_clues"] is False
    assert _flat(removal["full_clue_alternative"]) in answers


def test_individually_redundant_rules_cannot_be_deleted_together(diagnostic):
    data = _example()
    data["rules"] *= 2
    report = diagnostic.diagnose(data)
    assert all(r["answers_with_stored_clues"] == 1 for r in report["removals"])
    data["rules"] = []
    with pytest.raises(ValueError, match="not uniquely solvable.*2 answers"):
        diagnostic.diagnose(data)


def test_no_rules_and_zero_candidate_hints_are_supported(diagnostic):
    data = {"format": "puzzle-box/shading-v2", "rows": 1, "cols": 1, "rules": [],
            "clue_kinds": ["cell"], "clues": [{"type": "cell", "row": 0, "col": 0, "value": 0}],
            "solution": [[0]]}
    report = diagnostic.diagnose(data)
    assert report["removals"] == [] and report["stored_clues_irreducible"] is True
    data.update(rules=[{"type": "count", "count": 0}], clue_kinds=[], clues=[])
    report = diagnostic.diagnose(data)
    assert report["full_candidate_clues"] == []
    assert report["removals"][0]["answers_with_full_candidate_clues"] == 2
    assert report["removals"][0]["necessary_with_full_candidate_clues"] is True


@pytest.mark.parametrize("field,value,pattern", [
    ("clues", [], "not uniquely solvable"),
    ("clues", [[0, 0, 1], [0, 1, 1]], "infeasible"),
    ("solution", [[1, 0], [0, 0]], "does not match"),
    ("solution", [[0, 0], [0, True]], "Invalid stored solution"),
    ("solution", [[0, 1]], "Invalid stored solution"),
    ("clues", {}, "array"), ("clues", [[0, 0, 0]] * 33, "32"),
    ("clues", ["000"], "v1 cell clue"), ("clues", [[0, 0]], "v1 cell clue"),
    ("clues", [[2, 0, 0]], "outside"), ("clues", [[0, 0, True]], "Clue values"),
    ("clues", [[False, 0, 0]], "coordinates"),
    ("rows", True, "positive integers"), ("rows", 5, "at most 9"),
    ("rules", [{"type": "count", "count": 1}] * 9, "at most 8"),
    ("format", "puzzle-box/shading-recipe-v1", "not a recipe"),
])
def test_invalid_or_nonunique_artifacts_are_rejected(diagnostic, field, value, pattern):
    data = _example()
    data[field] = value
    with pytest.raises(ValueError, match=pattern):
        diagnostic.diagnose(data)


def test_mixed_clue_policy_and_count_bounds_are_checked(diagnostic):
    data = _example()
    data.update(format="puzzle-box/shading-v2", clue_kinds=["cell"],
                clues=[{"type": "row-count", "row": 0, "count": 0}])
    with pytest.raises(ValueError, match="not enabled"):
        diagnostic.diagnose(data)
    data["clue_kinds"] = ["row-count"]
    data["clues"][0]["count"] = 3
    with pytest.raises(ValueError, match="exceeds"):
        diagnostic.diagnose(data)
    data["unexpected"] = 0
    with pytest.raises(ValueError, match="unknown puzzle fields"):
        diagnostic.diagnose(data)


def _cli(*args, hash_seed="0"):
    return subprocess.run([sys.executable, str(EXAMPLES / "diagnose_shading_rules.py"), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8", timeout=60,
                          env={**os.environ, "PYTHONHASHSEED": hash_seed})


def test_cli_explains_witnesses_and_reproduces_json_without_mutation(tmp_path):
    path = tmp_path / "puzzle.json"
    raw = json.dumps(_example())
    path.write_text(raw)
    output = tmp_path / "report.json"
    result = _cli(path, "--output", output)
    assert result.returncode == 0, result.stderr
    assert "1 / redundant | 2 / necessary" in result.stdout
    assert "SAME stored clues: ../.." in result.stdout
    first, again = _cli(path, "--json"), _cli(path, "--json", hash_seed="42")
    assert first.returncode == again.returncode == 0
    assert first.stdout == again.stdout == output.read_text()
    assert path.read_text() == raw
    result = _cli(path, "--output", path)
    assert result.returncode == 2 and path.read_text() == raw


@pytest.mark.parametrize("raw", ['{"format":1,"format":2}', '{"rows":NaN}', 'x' * 65537, 'null', '{'],
                         ids=["duplicate", "nan", "large", "null", "syntax"])
def test_cli_invalid_input_preserves_existing_report(tmp_path, raw):
    path, output = tmp_path / "bad.json", tmp_path / "report.json"
    path.write_text(raw)
    output.write_text("keep")
    result = _cli(path, "--output", output)
    assert result.returncode == 2 and "Traceback" not in result.stderr
    assert output.read_text() == "keep"
