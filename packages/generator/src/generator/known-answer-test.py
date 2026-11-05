"""Integration checks for the optional projected-answer reduction path."""

from itertools import product
from pathlib import Path
import importlib

import pytest

from generator.search import generate_bounded
from puzzle import Puzzle, SolveResult
from puzzle_defs import BlackCount, ConnectedWhite, NonTouchingBlack, ShadingRecipe

with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(Path(__file__).resolve().parents[4] / "examples"))
    oracle = importlib.import_module("analyze_shading")
    worker = importlib.import_module("web_worker")


@pytest.mark.parametrize("size,count", [(2, 2), (3, 2)])
@pytest.mark.parametrize("kinds", [("cell",), ("row-count", "column-count"),
                                   ("cell", "row-count", "column-count")])
@pytest.mark.parametrize("seed", [0, 1])
def test_known_answer_matches_baseline_and_independent_enumeration(size, count, kinds, seed):
    recipe = ShadingRecipe(size, 3, (BlackCount(count), NonTouchingBlack(), ConnectedWhite()), kinds)
    fast = generate_bounded(recipe, seed=seed, budget=30, answer_variables=worker._shading_answer_variables)
    original = generate_bounded(recipe, seed=seed, budget=30)
    assert (fast.status, fast.candidates, fast.unique, fast.irreducible, fast.clues) == (
        original.status, original.candidates, original.unique, original.irreducible, original.clues)
    if fast.status != "ok":
        assert fast.status in ("insufficient_hints", "search_exhausted")
        return
    boards = [bits for bits in product((0, 1), repeat=size * 3)
              if all(oracle.accepts(rule, bits, size, 3) for rule in recipe.rules)]
    def matches(clues):
        return [bits for bits in boards if set(clues) <= set(oracle.full_clues(recipe, bits))]
    assert len(matches(fast.clues)) == 1
    assert fast.puzzle is not None and fast.solution is not None
    assert matches(fast.clues)[0] == tuple(v for row in fast.puzzle.result(fast.solution) for v in row)
    assert all(len(matches(fast.clues[:i] + fast.clues[i+1:])) > 1 for i in range(len(fast.clues)))


def test_custom_rule_auxiliary_variables_do_not_change_visible_uniqueness():
    class AuxiliaryRule:
        def apply(self, puzzle, board, black):
            puzzle.bool_var_map("arbitrary_witness", ["unconstrained"])
            puzzle.add(black[board.cells[0]] == 1)
    recipe = ShadingRecipe(2, 2, (AuxiliaryRule(),), ("cell", "row-count"))
    baseline = generate_bounded(recipe, seed=0)
    fast = generate_bounded(recipe, seed=0, answer_variables=worker._shading_answer_variables)
    assert fast.status == baseline.status == "ok"
    assert fast.clues == baseline.clues and fast.unique and fast.irreducible
    # A free witness has two assignments for every visible grid.
    assert fast.puzzle is not None and fast.puzzle.solution_vars is not None
    assert len(fast.puzzle.solution_vars) == 4


def test_duplicate_clues_remain_distinct_occurrences():
    class DuplicateRecipe(ShadingRecipe):
        def extract_clues(self, solution, puzzle):
            clues = super().extract_clues(solution, puzzle)
            return clues + clues[:1]
    recipe = DuplicateRecipe(2, 2, (BlackCount(1),), ("cell",))
    baseline = generate_bounded(recipe, seed=0)
    fast = generate_bounded(recipe, seed=0, answer_variables=worker._shading_answer_variables)
    assert fast.status == baseline.status == "ok" and fast.clues == baseline.clues
    assert len(set(fast.clues)) == len(fast.clues)


@pytest.mark.parametrize("limit,expected", [(1, "search_exhausted"), (64, "insufficient_hints")])
def test_candidate_limit_and_insufficient_hints_remain_distinct(limit, expected):
    recipe = ShadingRecipe(2, 2, (BlackCount(1),), ("row-count",))
    assert generate_bounded(recipe, max_candidates=limit, answer_variables=worker._shading_answer_variables).status == expected
    impossible = ShadingRecipe(1, 2, (BlackCount(2), NonTouchingBlack()))
    assert generate_bounded(impossible, answer_variables=worker._shading_answer_variables).status == "unsatisfiable"


def test_rejected_ambiguous_candidate_is_retried(monkeypatch):
    from ortools.sat.python import cp_model
    from puzzle import Solution
    original = Puzzle.solve_result
    first = True
    def solve(puzzle, *args, **kwargs):
        nonlocal first
        if first:
            first = False
            model = puzzle._model.clone()
            solver = cp_model.CpSolver()
            for var, bit in zip(puzzle.solution_vars, (1, 0, 0, 1)):
                model.add(var._internal == bit)
            solver.solve(model)
            return SolveResult("sat", Solution(solver, puzzle._model))
        return original(puzzle, *args, **kwargs)
    monkeypatch.setattr(Puzzle, "solve_result", solve)
    recipe = ShadingRecipe(2, 2, (BlackCount(2),), ("row-count",))
    result = generate_bounded(recipe, answer_variables=worker._shading_answer_variables)
    assert result.status == "ok" and result.candidates > 1 and result.unique and result.irreducible


@pytest.mark.parametrize("stage", [1, 2, 3])
def test_unknown_never_publishes_an_unproven_artifact(monkeypatch, stage):
    original = Puzzle.solve_result
    calls = 0
    def solve(puzzle, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == stage:
            if stage == 2:
                actual = original(puzzle, *args, **kwargs)
                return SolveResult("sat", actual.solution, "unknown")
            return SolveResult("unknown")
        return original(puzzle, *args, **kwargs)
    monkeypatch.setattr(Puzzle, "solve_result", solve)
    result = generate_bounded(ShadingRecipe(2, 3, (BlackCount(2),)),
                              answer_variables=worker._shading_answer_variables)
    assert result.status == "unconfirmed" and result.irreducible is None
    assert not result.clues and result.puzzle is None and result.solution is None
    assert result.unique is (True if stage == 3 else None)


@pytest.mark.parametrize("stage", [1, 2, 3, 4])
def test_solver_unknown_at_each_proof_phase(monkeypatch, stage):
    from ortools.sat.python import cp_model
    original = cp_model.CpSolver.solve
    calls = 0
    def solve(solver, model, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == stage:
            return cp_model.UNKNOWN
        return original(solver, model, *args, **kwargs)
    monkeypatch.setattr(cp_model.CpSolver, "solve", solve)
    result = generate_bounded(ShadingRecipe(2, 3, (BlackCount(2),)),
                              answer_variables=worker._shading_answer_variables)
    assert result.status == "unconfirmed" and result.irreducible is None and not result.clues
    assert result.unique is (True if stage == 4 else None)


def test_invalid_alternative_model_raises(monkeypatch):
    original = Puzzle.solve_result
    calls = 0
    def solve(puzzle, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise ValueError("Invalid solver model")
        return original(puzzle, *args, **kwargs)
    monkeypatch.setattr(Puzzle, "solve_result", solve)
    with pytest.raises(ValueError, match="Invalid solver model"):
        generate_bounded(ShadingRecipe(2, 3, (BlackCount(2),)),
                         answer_variables=worker._shading_answer_variables)


def test_incomplete_projection_falls_back_to_two_solve_checks(monkeypatch):
    checks = []
    original = Puzzle.solve_result
    def solve(puzzle, *args, **kwargs):
        checks.append(kwargs.get("check_unique", False))
        return original(puzzle, *args, **kwargs)
    monkeypatch.setattr(Puzzle, "solve_result", solve)
    recipe = ShadingRecipe(2, 2, (BlackCount(1),))
    def incomplete(puzzle):
        cell = puzzle.board.cells[0]
        return {cell: puzzle.black[cell]}
    result = generate_bounded(recipe, answer_variables=incomplete)
    assert result.status == "ok" and len(checks) > 2 and all(checks[1:])


def test_custom_rule_that_changes_projection_uses_normal_check(monkeypatch):
    class RestrictedAnswer:
        def apply(self, puzzle, board, black):
            puzzle.set_solution_vars(black[cell] for cell in board.cells[:2])
    checks = []
    original = Puzzle.solve_result
    def solve(puzzle, *args, **kwargs):
        checks.append(kwargs.get("check_unique", False))
        return original(puzzle, *args, **kwargs)
    monkeypatch.setattr(Puzzle, "solve_result", solve)
    recipe = ShadingRecipe(2, 2, (RestrictedAnswer(),))
    result = generate_bounded(recipe, answer_variables=worker._shading_answer_variables)
    assert result.status == "ok" and len(checks) > 2 and all(checks[1:])


def test_mismatched_initial_values_use_normal_check(monkeypatch):
    checks = []
    original = Puzzle.solve_result
    def solve(puzzle, *args, **kwargs):
        checks.append(kwargs.get("check_unique", False))
        return original(puzzle, *args, **kwargs)
    monkeypatch.setattr(Puzzle, "solve_result", solve)
    calls = 0
    def mismatched(puzzle):
        nonlocal calls
        calls += 1
        cells = puzzle.board.cells
        return {cell: puzzle.black[cells[-i-1] if calls == 2 else cell] for i, cell in enumerate(cells)}
    result = generate_bounded(ShadingRecipe(2, 2, (BlackCount(1),)), answer_variables=mismatched)
    assert result.status == "ok" and len(checks) > 2 and all(checks[1:])


def test_cross_model_assignment_requires_complete_local_projection():
    first = ShadingRecipe(2, 2, ()).create_empty()
    second = ShadingRecipe(2, 2, ()).create_empty()
    local = [second.black[cell] for cell in second.board.cells]
    foreign = [first.black[cell] for cell in first.board.cells]
    with pytest.raises(ValueError):
        second.exclude_projected_assignment(foreign, [0] * 4)
    with pytest.raises(ValueError):
        second.exclude_projected_assignment(local[:-1], [0] * 3)
    assert second.solve_result().status == "sat"
    second.exclude_projected_assignment(local, [0] * 4)
    for var in local:
        second.add(var == 0)
    assert second.solve_result().status == "unsat"
