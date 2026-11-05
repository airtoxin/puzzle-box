"""Feasibility, projected uniqueness, and inconclusive solver responses."""

import pytest
from ortools.sat.python import cp_model

from puzzle import Puzzle, unique


def binary():
    puzzle = Puzzle("two visible answers")
    bit = puzzle.bool_var_map("bit", [0])[0]
    return puzzle, bit


def test_statuses_and_visible_exclusion_do_not_count_witnesses():
    puzzle, bit = binary()
    puzzle.bool_var_map("unseen", range(4))
    puzzle.set_solution_vars([bit])
    multiple = puzzle.solve_result(seed=0, check_unique=True)
    assert multiple.status == "sat" and multiple.uniqueness == "multiple"
    assert multiple.solution is not None
    puzzle.exclude_solution(multiple.solution)
    only = puzzle.solve_result(seed=0, check_unique=True)
    assert only.uniqueness == "unique" and only.solution is not None
    assert only.solution.value(bit) != multiple.solution.value(bit)
    puzzle.exclude_solution(only.solution)
    assert puzzle.solve_result().status == "unsat"


def test_unknown_does_not_mean_unsat_or_unique(monkeypatch):
    puzzle, _ = binary()
    assert puzzle.solve_result(time_limit=0).status == "unknown"
    original = cp_model.CpSolver.solve
    calls = []
    def solve(self, model, *args, **kwargs):
        calls.append(self.parameters.max_time_in_seconds)
        if len(calls) == 2:
            return cp_model.UNKNOWN
        return original(self, model, *args, **kwargs)
    monkeypatch.setattr(cp_model.CpSolver, "solve", solve)
    result = puzzle.solve_result(seed=0, time_limit=1, check_unique=True)
    assert result.status == "sat" and result.solution is not None and result.uniqueness == "unknown"
    assert 0 < calls[1] <= calls[0] <= 1
    calls.clear()
    puzzle.add(unique())
    assert puzzle.solve(seed=0) is None


def test_empty_projection_and_foreign_solution():
    puzzle, _ = binary()
    puzzle.set_solution_vars([])
    result = puzzle.solve_result(check_unique=True)
    assert result.uniqueness == "unique" and result.solution is not None
    foreign, _ = binary()
    with pytest.raises(ValueError, match="same Puzzle"):
        foreign.exclude_solution(result.solution)
    puzzle.exclude_solution(result.solution)
    assert puzzle.solve_result().status == "unsat"


@pytest.mark.parametrize("budget", [-1, float("nan"), float("inf")])
def test_invalid_budgets(budget):
    with pytest.raises(ValueError):
        binary()[0].solve_result(time_limit=budget)


def test_model_error_is_not_a_mathematical_verdict(monkeypatch):
    monkeypatch.setattr(cp_model.CpSolver, "solve", lambda *a, **k: cp_model.MODEL_INVALID)
    with pytest.raises(ValueError, match="Invalid solver model"):
        binary()[0].solve_result()
