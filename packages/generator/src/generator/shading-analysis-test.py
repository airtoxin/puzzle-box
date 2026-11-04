"""Compare the finite diagnostic checker to the actual DSL and hint extraction."""

import importlib.util
from itertools import combinations, product
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from puzzle import Cell, at_least_one
from puzzle_defs import BlackCount, ConnectedWhite, NonTouchingBlack, NoWhite2x2, ShadingRecipe
from puzzle_defs.puzzles.shading import CLUE_KINDS

SCRIPT = Path(__file__).resolve().parents[4] / "examples" / "analyze_shading.py"


@pytest.fixture(scope="module")
def analysis():
    # Import the standalone example with its sibling JSON-format helper.
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location("shading_analysis_example", SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.path.remove(str(SCRIPT.parent))


def _solver_answers(recipe: ShadingRecipe) -> set[tuple[int, ...]]:
    puzzle = recipe.create_empty()
    variables = [puzzle.black[c] for c in puzzle.board.cells]
    answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(v != solution.value(v) for v in variables))
        assert len(answers) <= 2**(recipe.rows * recipe.cols)
    return answers


RULE_SETS = [(), (BlackCount(0),), (BlackCount(4),), (NonTouchingBlack(),),
             (NonTouchingBlack(True),), (ConnectedWhite(),), (ConnectedWhite(False),), (NoWhite2x2(),)]
RULE_SETS += [(BlackCount(n), NonTouchingBlack(diagonal), ConnectedWhite(nonempty), NoWhite2x2())
              for n, diagonal, nonempty in product(range(5), [False, True], [False, True])]


@pytest.mark.parametrize("rules", RULE_SETS)
def test_finite_acceptance_matches_every_two_by_two_dsl_answer(analysis, rules):
    recipe = ShadingRecipe(2, 2, rules)
    exact = {bits for bits in product([0, 1], repeat=4)
             if all(analysis.accepts(rule, bits, 2, 2) for rule in rules)}
    assert exact == _solver_answers(recipe)
    report = analysis.analyze(recipe)
    assert report["completion_count"] == len(exact)
    assert report["identifiable_completions"] == len(exact)  # Full cell clues.


def test_row_column_clues_cannot_distinguish_the_two_diagonals(analysis):
    recipe = ShadingRecipe(2, 2, (BlackCount(2), NonTouchingBlack()), ("row-count", "column-count"))
    report = analysis.analyze(recipe, seed_count=8)
    assert report["completion_count"] == 2
    assert report["hint_policy"] == "none_identifiable"
    assert report["full_clue_groups"] == 1 and report["identifiable_completions"] == 0
    assert report["ambiguous_example"]["answer_count"] == 2
    assert len(report["ambiguous_example"]["witnesses"]) == 2
    assert all(a["answers_with_same_full_clues"] == 2 for a in report["seed_probe"]["attempts"])
    # Adding cell hints fixes the policy; changing seeds alone cannot.
    with_cells = analysis.analyze(ShadingRecipe(2, 2, recipe.rules, CLUE_KINDS))
    assert with_cells["hint_policy"] == "all_identifiable"
    assert with_cells["completion_count"] == with_cells["identifiable_completions"] == 2
    assert "No seed can" in analysis.explain(report)


def test_relaxing_a_rule_can_make_some_completions_identifiable(analysis):
    report = analysis.analyze(ShadingRecipe(2, 2, (BlackCount(2),), ("row-count", "column-count")))
    assert report["completion_count"] == 6
    assert report["identifiable_completions"] == 4
    assert report["ambiguous_completions"] == 2 and report["hint_policy"] == "some_identifiable"
    assert report["full_clue_groups"] == 5


def test_three_rule_conflict_and_every_proper_subset_are_checked(analysis):
    rules = (BlackCount(5), NonTouchingBlack(), ConnectedWhite(), NoWhite2x2())
    recipe = ShadingRecipe(3, 3, rules)
    report = analysis.analyze(recipe, seed_count=4)
    assert report["completion_count"] == 0 and report["enumerated_boards"] == 512
    assert report["minimal_conflicts"] == [[1, 2, 3]]
    assert report["hint_policy"] == "no_completion" and report["ambiguous_example"] is None
    assert report["seed_probe"]["attempts"] == []
    assert recipe.create_empty().solve() is None
    for removed in range(3):
        subset = tuple(r for i, r in enumerate(rules[:3]) if i != removed)
        assert ShadingRecipe(3, 3, subset).create_empty().solve() is not None
    assert "Changing seeds or clues cannot" in analysis.explain(report)


def test_conflicts_keep_duplicate_rule_occurrences_separate(analysis):
    report = analysis.analyze(ShadingRecipe(2, 2, (BlackCount(0), BlackCount(0), NoWhite2x2())))
    assert report["minimal_conflicts"] == [[1, 3], [2, 3]]


@pytest.mark.parametrize("rows,cols,rules", [
    (3, 3, (BlackCount(3), NonTouchingBlack(), ConnectedWhite(), NoWhite2x2())),
    (3, 3, (BlackCount(2), NonTouchingBlack(True), ConnectedWhite())),
    (2, 3, (BlackCount(2), ConnectedWhite(), NoWhite2x2())),
])
def test_connected_and_overlapping_window_cases_match_all_dsl_answers(analysis, rows, cols, rules):
    recipe = ShadingRecipe(rows, cols, rules)
    exact = {bits for bits in product([0, 1], repeat=rows*cols)
             if all(analysis.accepts(rule, bits, rows, cols) for rule in rules)}
    assert exact == _solver_answers(recipe)


def test_all_reported_conflicts_are_inclusion_minimal(analysis):
    rules = (BlackCount(0), BlackCount(2), NonTouchingBlack(True), NoWhite2x2())
    report = analysis.analyze(ShadingRecipe(2, 2, rules))
    assert report["minimal_conflicts"] == [[1, 2], [1, 4], [2, 3]]
    for core in report["minimal_conflicts"]:
        for size in range(len(core)):
            for indices in combinations(core, size):
                assert ShadingRecipe(2, 2, tuple(rules[i-1] for i in indices)).create_empty().solve() is not None


@pytest.mark.parametrize("kinds", [(), ("cell",), ("row-count",), ("column-count",),
                                  ("row-count", "column-count"), CLUE_KINDS])
def test_full_hint_signatures_match_dsl_extraction_for_every_board(analysis, kinds):
    recipe = ShadingRecipe(2, 2, (), kinds)
    for bits in product([0, 1], repeat=4):
        puzzle = recipe.build_from_clues([(Cell(i//2, i%2), b) for i, b in enumerate(bits)])
        solution = puzzle.solve(seed=0)
        assert solution is not None
        assert tuple(recipe.extract_clues(solution, puzzle)) == analysis.full_clues(recipe, bits)


def test_no_hints_can_identify_a_completion_when_rules_alone_are_unique(analysis):
    report = analysis.analyze(ShadingRecipe(1, 1, (BlackCount(1),), ()), seed_count=4)
    assert report["completion_count"] == report["identifiable_completions"] == 1
    assert report["hint_policy"] == "all_identifiable"
    assert report["seed_probe"]["distinct_completions"] == 1
    assert report["seed_probe"]["identifiable_attempts"] == 4
    assert [a["answer_id"] for a in report["seed_probe"]["attempts"]] == [1, 1, 1, 1]


@pytest.mark.parametrize("rules", [(ConnectedWhite(False),), (NoWhite2x2(),), (NonTouchingBlack(True),)])
def test_one_row_boundary_rules_match_dsl(analysis, rules):
    recipe = ShadingRecipe(1, 3, rules)
    assert analysis.analyze(recipe)["completion_count"] == len(_solver_answers(recipe))


def test_unsupported_rule_semantics_are_rejected_before_apply(analysis):
    class Custom:
        def apply(self, *args):
            pytest.fail("Custom rule must not be applied")

    class Subclass(BlackCount):
        pass

    for rule in [Custom(), Subclass(1)]:
        with pytest.raises(ValueError, match="built-in"):
            analysis.analyze(ShadingRecipe(2, 2, (rule,)))


@pytest.mark.parametrize("seed_start,seed_count", [(-1, 1), (0, -1), (0, 33), (True, 1),
                                                (0, True), (2**31-1, 2)])
def test_invalid_seed_probe_limits(analysis, seed_start, seed_count):
    with pytest.raises(ValueError):
        analysis.analyze(ShadingRecipe(1, 1, ()), seed_start=seed_start, seed_count=seed_count)


def test_size_rule_and_count_limits(analysis):
    for recipe in [ShadingRecipe(2, 5, ()), ShadingRecipe(1, 1, (BlackCount(0),)*9),
                   ShadingRecipe(1, 1, (BlackCount(2),))]:
        with pytest.raises(ValueError):
            analysis.analyze(recipe)
    assert len(analysis.analyze(ShadingRecipe(1, 1, ()), seed_start=2**31-1, seed_count=1)
               ["seed_probe"]["attempts"]) == 1


@pytest.mark.parametrize("damage", ["no-solution", "wrong-answer", "wrong-clues"])
def test_solver_and_extraction_disagreement_is_not_reported_as_a_recipe_result(analysis, monkeypatch, damage):
    from puzzle_defs import ShadingPuzzle

    recipe = ShadingRecipe(1, 1, (BlackCount(1),))
    if damage == "no-solution":
        monkeypatch.setattr(ShadingPuzzle, "solve", lambda *a, **k: None)
    elif damage == "wrong-answer":
        monkeypatch.setattr(ShadingPuzzle, "result", lambda *a, **k: [[0]])
    else:
        monkeypatch.setattr(ShadingRecipe, "extract_clues", lambda *a, **k: [])
    with pytest.raises(RuntimeError, match="finite"):
        analysis.analyze(recipe, seed_count=1)


def _cli(*args: str, hash_seed: str = "1") -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], check=False, capture_output=True,
                          text=True, timeout=45, env=dict(os.environ, PYTHONHASHSEED=hash_seed))


def test_cli_reports_are_repeatable_and_match_the_saved_json(tmp_path):
    path = tmp_path / "analysis.json"
    args = ("--seed-count", "8", "--json", "--output", str(path))
    first, second = _cli(*args), _cli(*args, hash_seed="999")
    assert first.returncode == second.returncode == 0, (first.stderr, second.stderr)
    assert first.stdout == second.stdout == path.read_text(encoding="utf-8")
    data = json.loads(first.stdout)
    assert data["completion_count"] == 2 and data["identifiable_completions"] == 0
    assert 1 <= data["seed_probe"]["distinct_completions"] <= 2
    assert data["seed_probe"]["identifiable_attempts"] == 0
    text = _cli()
    assert text.returncode == 0 and "No seed can" in text.stdout
    assert "#./.#" in text.stdout and ".#/#." in text.stdout


def test_cli_contradictions_are_results_but_invalid_input_is_an_error(tmp_path):
    result = _cli("--diagonal", "--json")
    assert result.returncode == 0
    assert json.loads(result.stdout)["minimal_conflicts"] == [[1, 2]]
    path = tmp_path / "keep.json"
    path.write_text("keep", encoding="utf-8")
    for args in [("--rows", "5"), ("--black-count", "5"), ("--seed-count", "33")]:
        invalid = _cli(*args, "--output", str(path))
        assert invalid.returncode == 2 and "Traceback" not in invalid.stderr
        assert path.read_text(encoding="utf-8") == "keep"
