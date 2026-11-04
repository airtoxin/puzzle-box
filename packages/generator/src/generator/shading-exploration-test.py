"""Check every subset and removal against actual DSL answers and hint extraction."""

from functools import lru_cache
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from puzzle import Cell, at_least_one, unique
from puzzle_defs import BlackCount, ConnectedWhite, NonTouchingBlack, NoWhite2x2, ShadingRecipe

SCRIPT = Path(__file__).resolve().parents[4] / "examples" / "explore_shading.py"
POOL = (BlackCount(2), NonTouchingBlack(), ConnectedWhite(), NoWhite2x2())


@pytest.fixture(scope="module")
def explorer():
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location("shading_exploration_example", SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.path.remove(str(SCRIPT.parent))


@lru_cache(maxsize=None)
def _answers(rules, rows=2, cols=2) -> frozenset[tuple[int, ...]]:
    puzzle = ShadingRecipe(rows, cols, rules).create_empty()
    variables = [puzzle.black[c] for c in puzzle.board.cells]
    answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(v != solution.value(v) for v in variables))
        assert len(answers) <= 2**(rows*cols)
    return frozenset(answers)


@lru_cache(maxsize=None)
def _signature(bits, kinds):
    recipe = ShadingRecipe(2, 2, (), kinds)
    puzzle = recipe.build_from_clues([(Cell(i//2, i%2), v) for i, v in enumerate(bits)])
    solution = puzzle.solve(seed=0)
    assert solution is not None
    return tuple(recipe.extract_clues(solution, puzzle))


def _flat(grid):
    return tuple(v for row in grid for v in row)


@pytest.mark.parametrize("kinds", [(), ("cell",), ("row-count",), ("row-count", "column-count")])
def test_all_subsets_and_every_removal_match_dsl_answer_sets(explorer, kinds):
    report = explorer.explore(2, 2, POOL, kinds)
    assert report["enumerated_combinations"] == len(report["combinations"]) == 16
    sets = {mask: _answers(tuple(rule for i, rule in enumerate(POOL) if mask & (1 << i))) for mask in range(16)}
    for combo in report["combinations"]:
        mask = combo["mask"]
        base = sets[mask]
        assert combo["rule_indices"] == [i+1 for i in range(4) if mask & (1 << i)]
        assert combo["completion_count"] == len(base)
        original_unique = {b for b in base if sum(_signature(b, kinds) == _signature(c, kinds) for c in base) == 1}
        assert combo["identifiable_completions"] == len(original_unique)
        if not base:
            assert combo["equivalence_id"] is None
            assert combo["redundant_without_hints"] is combo["redundant_given_full_hints"] is None
        for removal in combo["removals"]:
            relaxed = sets[mask ^ (1 << (removal["rule_index"]-1))]
            added = relaxed - base
            affected = {b for b in base if any(_signature(b, kinds) == _signature(c, kinds) for c in added)}
            lost = original_unique & affected
            assert removal["added_completions"] == len(added)
            assert removal["completions_without_rule"] == len(relaxed)
            assert removal["redundant_without_hints"] == (base == relaxed if base else None)
            assert removal["redundant_given_full_hints"] == (not affected if base else None)
            assert removal["hint_affected_completions"] == (len(affected) if base else None)
            assert removal["uniqueness_tested_completions"] == len(original_unique)
            assert removal["uniqueness_lost_completions"] == (len(lost) if original_unique else None)
            if added:
                assert _flat(removal["added_answer_witness"]) in added
            if affected:
                witness = removal["same_hint_witness"]
                a, b = _flat(witness["original_answer"]), _flat(witness["new_answer_without_rule"])
                assert a in base and b in added and _signature(a, kinds) == _signature(b, kinds)
                assert witness["unique_before"] == (a in original_unique)
            else:
                assert removal["same_hint_witness"] is None
    for a in report["combinations"]:
        for b in report["combinations"]:
            if a["completion_count"] and b["completion_count"]:
                assert (a["equivalence_id"] == b["equivalence_id"]) == (sets[a["mask"]] == sets[b["mask"]])


def test_default_search_counts_and_implied_window_rule(explorer):
    report = explorer.explore(2, 2, POOL)
    assert report["feasible_combinations"] == 14
    assert report["identifiable_combinations"] == 12
    assert report["distinct_feasible_answer_sets"] == 11
    combo = report["combinations"][9]  # Count 2 + NoWhite2x2.
    assert combo["rule_indices"] == [1, 4]
    assert combo["redundant_without_hints"] == [4]
    assert combo["redundant_given_full_hints"] == [1, 4]
    assert combo["equivalence_id"] == report["combinations"][1]["equivalence_id"]


def test_hint_redundancy_is_not_redundancy_after_clue_reduction(explorer):
    report = explorer.explore(2, 2, (BlackCount(1),), ("cell",))
    removal = report["combinations"][1]["removals"][0]
    assert removal["redundant_without_hints"] is False
    assert removal["redundant_given_full_hints"] is True
    clues = [(Cell(0, 0), 0), (Cell(0, 1), 0), (Cell(1, 0), 0)]
    before = ShadingRecipe(2, 2, (BlackCount(1),)).build_from_clues(clues)
    before.add(unique())
    assert before.solve() is not None
    after = ShadingRecipe(2, 2, ()).build_from_clues(clues)
    after.add(unique())
    assert after.solve() is None


def test_full_hint_uniqueness_can_depend_on_non_touching_on_three_by_three(explorer):
    kinds = ("row-count", "column-count")
    recipe = ShadingRecipe(3, 3, (BlackCount(3), NonTouchingBlack()), kinds)
    combo = explorer.explore(3, 3, recipe.rules, kinds)["combinations"][3]
    removal = combo["removals"][1]
    assert removal["redundant_given_full_hints"] is False
    assert removal["uniqueness_lost_completions"] > 0
    witness = removal["same_hint_witness"]
    assert witness["unique_before"] is True
    before_bits, after_bits = _flat(witness["original_answer"]), _flat(witness["new_answer_without_rule"])
    hints = explorer.full_clues(recipe, before_bits)
    assert hints == explorer.full_clues(recipe, after_bits)
    before = recipe.build_from_clues(hints)
    before.add(unique())
    assert before.solve() is not None
    relaxed = ShadingRecipe(3, 3, (BlackCount(3),), kinds)
    after = relaxed.build_from_clues(hints)
    after.add(unique())
    assert after.solve() is None
    for bits in (before_bits, after_bits):
        fixed = relaxed.build_from_clues([(Cell(i//3, i%3), v) for i, v in enumerate(bits)])
        assert fixed.solve() is not None
    # Validate the complete contribution counts with actual uniqueness solves.
    answers = _answers(recipe.rules, 3, 3)
    identified = lost = 0
    for bits in answers:
        hints = explorer.full_clues(recipe, bits)
        puzzle = recipe.build_from_clues(hints)
        puzzle.add(unique())
        if puzzle.solve() is not None:
            identified += 1
            trial = relaxed.build_from_clues(hints)
            trial.add(unique())
            lost += trial.solve() is None
    assert combo["completion_count"] == len(answers) == 22
    assert combo["identifiable_completions"] == identified == 16
    assert removal["uniqueness_lost_completions"] == lost == 12


def test_a_small_board_implication_is_not_generalized_to_other_sizes(explorer):
    pool = (BlackCount(2), NoWhite2x2())
    small = explorer.explore(2, 2, pool)["combinations"][3]
    larger = explorer.explore(3, 3, pool)["combinations"][3]
    assert small["redundant_without_hints"] == [2]
    assert larger["redundant_without_hints"] == []
    witness = larger["removals"][1]["added_answer_witness"]
    clues = [(Cell(r, c), witness[r][c]) for r in range(3) for c in range(3)]
    assert ShadingRecipe(3, 3, (BlackCount(2),)).build_from_clues(clues).solve() is not None
    assert ShadingRecipe(3, 3, pool).build_from_clues(clues).solve() is None


def test_duplicate_redundancies_cannot_be_removed_together(explorer):
    report = explorer.explore(2, 2, (BlackCount(1), BlackCount(1)), ())
    both = report["combinations"][3]
    assert both["redundant_without_hints"] == [1, 2]
    assert both["completion_count"] == 4 and report["combinations"][0]["completion_count"] == 16
    assert both["identifiable_completions"] == 0
    assert all(r["uniqueness_lost_completions"] is None for r in both["removals"])


def test_stronger_diagonal_rule_implies_orthogonal_rule_on_this_board(explorer):
    combo = explorer.explore(2, 2, (NonTouchingBlack(), NonTouchingBlack(True)))["combinations"][3]
    assert combo["redundant_without_hints"] == [1]
    assert combo["removals"][1]["added_completions"] == 2


def test_incompatible_counts_are_compared_as_optional_candidates(explorer):
    report = explorer.explore(2, 2, (BlackCount(1), BlackCount(2)))
    assert report["feasible_combinations"] == 3
    impossible = report["combinations"][3]
    assert impossible["completion_count"] == 0 and impossible["redundant_without_hints"] is None
    assert [r["added_completions"] for r in impossible["removals"]] == [6, 4]
    assert all(r["uniqueness_lost_completions"] is None for r in impossible["removals"])


def test_empty_and_maximum_candidate_pools(explorer):
    empty = explorer.explore(1, 1, (), ())
    assert empty["enumerated_combinations"] == 1 and empty["combinations"][0]["completion_count"] == 2
    maximum = explorer.explore(1, 1, (BlackCount(0),)*8, ())
    assert maximum["enumerated_combinations"] == maximum["feasible_combinations"] == 256
    assert maximum["identifiable_combinations"] == 255
    with pytest.raises(ValueError, match="8 rule"):
        explorer.explore(1, 1, (BlackCount(0),)*9)


@pytest.mark.parametrize("rows,cols,rules,kinds", [(4, 3, (), ()), (0, 2, (), ()),
    (2, 2, (BlackCount(5),), ()), (2, 2, (), ("cell", "cell"))])
def test_invalid_pool_parameters(explorer, rows, cols, rules, kinds):
    with pytest.raises(ValueError):
        explorer.explore(rows, cols, rules, kinds)


def test_custom_rules_are_rejected_before_their_apply_method(explorer):
    class Custom:
        def apply(self, *args):
            pytest.fail("Custom rules must not be interpreted")
    with pytest.raises(ValueError, match="built-in"):
        explorer.explore(2, 2, (Custom(),))


@pytest.mark.parametrize("selection", [[0], [5], [1, 1], [True]])
def test_invalid_subset_explanation_indices(explorer, selection):
    with pytest.raises(ValueError, match="indices"):
        explorer.explain(explorer.explore(2, 2, POOL), selection)


def _cli(*args: str, hash_seed: str = "1") -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], check=False, capture_output=True,
                          text=True, timeout=45, env=dict(os.environ, PYTHONHASHSEED=hash_seed))


def test_cli_repeatability_json_and_subset_explanation(tmp_path):
    path = tmp_path / "exploration.json"
    first, second = _cli("--json", "--output", str(path)), _cli("--json", hash_seed="999")
    assert first.returncode == second.returncode == 0, (first.stderr, second.stderr)
    assert first.stdout == second.stdout == path.read_text(encoding="utf-8")
    assert json.loads(first.stdout)["enumerated_combinations"] == 16
    detail = _cli("--rows", "3", "--cols", "3", "--black-counts", "3", "--explain", "1", "2")
    assert detail.returncode == 0 and "Shared full hints:" in detail.stdout
    assert "1+2 |" in detail.stdout and "1+2+3 |" not in detail.stdout
    empty = _cli("--rows", "1", "--cols", "1", "--candidates", "--hints", "--json")
    assert empty.returncode == 0 and json.loads(empty.stdout)["enumerated_combinations"] == 1


def test_cli_variants_and_errors_do_not_overwrite_output(tmp_path):
    variants = _cli("--black-counts", "1", "2", "--include-diagonal", "--json")
    assert variants.returncode == 0
    assert json.loads(variants.stdout)["enumerated_combinations"] == 64
    path = tmp_path / "keep.json"
    path.write_text("keep", encoding="utf-8")
    for args in [("--explain", "99"), ("--explain", "1", "--json"), ("--rows", "5"),
                 ("--candidates", "count", "--include-diagonal")]:
        result = _cli(*args, "--output", str(path))
        assert result.returncode == 2 and "Traceback" not in result.stderr
        assert path.read_text(encoding="utf-8") == "keep"
