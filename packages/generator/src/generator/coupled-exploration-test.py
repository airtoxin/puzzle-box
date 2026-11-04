from dataclasses import replace
from functools import lru_cache
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from puzzle import Cell, Edge, Vertex, at_least_one, unique
from puzzle_defs import ArrowSite, YajilinAnswer, YajilinRecipe

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
sys.path.insert(0, str(EXAMPLES))
experiment = importlib.import_module("explore_coupled")
oracle = importlib.import_module("coupled_oracle")


@lru_cache(maxsize=None)
def _report(rows=2, cols=4, sites=()):
    return experiment.analyze(rows, cols, sites, verify_models=True)


def _hint(row, kinds):
    return next(h for h in row["hints"] if h["kinds"] == list(kinds))


def _answer(data):
    return YajilinAnswer(frozenset(Cell(*c) for c in data["black_cells"]),
                        frozenset(Edge(Vertex(a, b), Vertex(c, d)) for a, b, c, d in data["loop_edges"]))


@pytest.mark.parametrize("rows,cols,sites", [
    (2, 2, ()), (2, 3, ()), (3, 2, ()), (2, 4, ()), (4, 2, ()),
    (2, 4, (ArrowSite(Cell(0, 1), "down"),)),
    (2, 2, (ArrowSite(Cell(0, 0), "right"),)),
])
def test_all_eight_models_match_the_independent_finite_oracle(rows, cols, sites):
    report = _report(rows, cols, sites)
    assert report["models_verified"]
    assert report["answer_projection"] == ["black_cells", "loop_edges"]
    assert len(report["combinations"]) == 8
    for row in report["combinations"]:
        assert row["model_verification"]["distinct_joint_answers"] == row["answer_count"]
        assert row["model_verification"]["raw_assignments"] >= row["answer_count"]
        assert len(row["hints"]) == 8
        assert _hint(row, ("arrow", "black", "edge"))["unique_joint_groups"] == row["answer_count"]
        for hint in row["hints"]:
            assert hint["false_unique_black_groups"] == hint["unique_black_groups"] - hint["unique_joint_groups"]
            for stronger in row["hints"]:
                if set(hint["kinds"]) <= set(stronger["kinds"]):
                    assert hint["unique_joint_groups"] <= stronger["unique_joint_groups"]


def test_default_counts_and_projection_counterexample_are_concrete():
    report = _report()
    assert report["base_answer_count"] == 1792  # 7 edge sets x 256 cell assignments
    assert [r["answer_count"] for r in report["combinations"]] == [1792, 7, 287, 2, 1536, 6, 246, 1]
    row = report["combinations"][3]
    hint = _hint(row, ("black",))
    assert hint["unique_joint_groups"] == 0
    assert hint["false_unique_black_groups"] == 1
    first, second = map(_answer, hint["projection_counterexample"]["answers"])
    assert first.black_cells == second.black_cells == frozenset()
    assert first.loop_edges != second.loop_edges
    assert sorted([oracle.components(first.loop_edges), oracle.components(second.loop_edges)]) == [1, 2]
    assert oracle.full_clues(YajilinRecipe(2, 4), first, ("black",)) == oracle.full_clues(YajilinRecipe(2, 4), second, ("black",))
    assert _hint(row, ("edge",))["unique_joint_groups"] == 2
    # Circuit orientations are auxiliary assignments, never two visible answers.
    final = report["combinations"][7]["model_verification"]
    assert final == {"equal": True, "raw_assignments": 2, "distinct_joint_answers": 1}


def test_unique_constraint_checks_both_cells_and_edges():
    puzzle = experiment.CoupledModel(YajilinRecipe(2, 4), 3)
    puzzle.add(unique())
    assert puzzle.solve() is None
    # Deliberately wrong projection demonstrates the false positive.
    puzzle.set_solution_vars(puzzle.black[c] for c in puzzle.cells)
    assert puzzle.solve() is not None


def test_rule_contribution_depends_on_hint_policy():
    row = _report()["combinations"][7]
    assert _hint(row, ())["unique_groups_lost_if_removed"] == dict.fromkeys(oracle.RULES, 1)
    assert _hint(row, ("black", "edge"))["unique_groups_lost_if_removed"] == dict.fromkeys(oracle.RULES, 0)
    assert not any(r["redundant_on_this_layout"] for r in row["removals"])
    # Same rules can be redundant on a smaller, different finite layout.
    tiny = _report(2, 2)["combinations"][7]
    assert all(r["redundant_on_this_layout"] for r in tiny["removals"] if r["rule"] != "coupling")


def test_infeasible_coupling_and_non_touching_has_a_minimal_conflict():
    report = _report(2, 4, (ArrowSite(Cell(0, 1), "down"),))
    assert not report["fixed_base_infeasible"]
    conflict = report["combinations"][3]
    assert conflict["answer_count"] == 0 and conflict["minimal_conflict"]
    assert all(removal["added_answers"] > 0 and removal["witness"] for removal in conflict["removals"])
    assert not report["combinations"][7]["minimal_conflict"]
    blocked = _report(2, 2, (ArrowSite(Cell(0, 0), "right"),))
    assert blocked["fixed_base_infeasible"]
    assert all(r["answer_count"] == 0 and not r["minimal_conflict"] for r in blocked["combinations"])


@pytest.mark.parametrize("direction", ["up", "down", "left", "right"])
def test_all_rules_match_existing_yajilin_and_reuse_clue_meanings(direction):
    recipe = YajilinRecipe(2, 4, (ArrowSite(Cell(0, 0), direction),))
    puzzle = recipe.create_empty()
    answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        answer = recipe.answer(solution, puzzle)
        assert answer not in answers
        answers.add(answer)
        for mask in range(8):
            kinds = tuple(k for i, k in enumerate(oracle.HINTS) if mask & (1 << i))
            with_hints = replace(recipe, clue_kinds=kinds)
            assert tuple(with_hints.extract_clues(solution, puzzle)) == oracle.full_clues(recipe, answer, kinds)
        variables = ([puzzle.is_black[c] for c in puzzle.board.cells if c not in puzzle.clue_cells]
                     + [puzzle.edge_on[e] for e in puzzle.loop_board.edges])
        puzzle.add(at_least_one(v != solution.value(v) for v in variables))
        assert len(answers) <= 7
    expected = {a for a in oracle.universe(recipe) if oracle.accepts(recipe, 7, a)}
    assert answers == expected and answers
    actual, _ = experiment.model_answers(experiment.CoupledModel(recipe, 7))
    assert actual == expected


def test_partial_model_enumeration_cannot_claim_complete_verification():
    with pytest.raises(RuntimeError, match="did not finish"):
        experiment.model_answers(experiment.CoupledModel(YajilinRecipe(2, 4), 0), time_limit=0)


@pytest.mark.parametrize("mask", [-1, 8, True])
def test_invalid_rule_masks_are_rejected(mask):
    with pytest.raises(ValueError, match="mask"):
        experiment.CoupledModel(YajilinRecipe(2, 2), mask)


def _cli(*args, hash_seed="1"):
    return subprocess.run([sys.executable, str(EXAMPLES / "explore_coupled.py"), *args],
                          text=True, capture_output=True, timeout=60,
                          env=dict(os.environ, PYTHONHASHSEED=hash_seed))


def test_cli_is_repeatable_and_renders_actual_projection_witnesses():
    first, second = _cli("--json"), _cli("--json", hash_seed="999")
    assert first.returncode == second.returncode == 0, (first.stderr, second.stderr)
    assert first.stdout == second.stdout
    data = json.loads(first.stdout)
    assert data["models_verified"] is False
    shown = _cli("--verify-models", "--explain", "3", "--hints", "black")
    assert shown.returncode == 0, shown.stderr
    assert "Model/oracle comparison: verified" in shown.stdout
    assert "Answer 1:" in shown.stdout and "Answer 2:" in shown.stdout
    assert ".---.   .---." in shown.stdout


@pytest.mark.parametrize("args", [
    ("--rows", "3", "--cols", "3"), ("--rows", "1000000"), ("--rows", "1"),
    ("--arrow", "0", "4", "left"), ("--arrow", "0", "0", "north"),
    ("--arrow", "0", "0", "up", "--arrow", "0", "0", "down"),
    ("--hints", "black", "black"),
])
def test_cli_rejects_invalid_or_unbounded_experiments(args):
    result = _cli(*args)
    assert result.returncode == 2
    assert not result.stdout and "error:" in result.stderr and "Traceback" not in result.stderr
