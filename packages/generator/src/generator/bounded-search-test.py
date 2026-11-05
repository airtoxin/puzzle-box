"""Bounded generation compared with independent finite answer sets."""

import importlib
from itertools import product
from pathlib import Path

import pytest

from generator.search import generate_bounded
from puzzle import Puzzle, SolveResult
from puzzle_defs import BlackCount, ColorComponentSize, NonTouchingBlack, ShadingRecipe

with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(Path(__file__).resolve().parents[4] / "examples"))
    oracle = importlib.import_module("analyze_shading")
    worker = importlib.import_module("web_worker")
    answers = importlib.import_module("web_answers")
    saved = importlib.import_module("generate_shading")
    catalog = importlib.import_module("web_catalog")


@pytest.mark.parametrize("seed", [0, 1, 42])
def test_small_generated_puzzle_is_independently_unique_and_irreducible(seed):
    recipe = ShadingRecipe(2, 3, (BlackCount(2), NonTouchingBlack()), ("cell", "row-count", "column-count"))
    result = generate_bounded(recipe, seed=seed)
    assert result.status == "ok" and result.unique and result.irreducible
    boards = [bits for bits in product((0, 1), repeat=6)
              if all(oracle.accepts(rule, bits, 2, 3) for rule in recipe.rules)]
    def matches(clues):
        return [bits for bits in boards if set(clues) <= set(oracle.full_clues(recipe, bits))]
    assert len(matches(result.clues)) == 1
    assert all(len(matches(result.clues[:i]+result.clues[i+1:])) > 1 for i in range(len(result.clues)))


def test_proven_impossibility_is_separate_from_attempt_limit_and_timeout():
    assert generate_bounded(ShadingRecipe(1, 2, (BlackCount(2), NonTouchingBlack()))).status == "unsatisfiable"
    ambiguous = ShadingRecipe(2, 2, (BlackCount(1),), ("row-count",))
    assert generate_bounded(ambiguous).status == "insufficient_hints"
    assert generate_bounded(ambiguous, max_candidates=1).status == "search_exhausted"
    assert generate_bounded(ambiguous, budget=0).status == "unconfirmed"
    assert generate_bounded(ShadingRecipe(2, 2, (), ())).status == "insufficient_hints"


def test_retries_a_candidate_whose_hints_are_ambiguous(monkeypatch):
    recipe = ShadingRecipe(2, 2, (BlackCount(2),), ("row-count",))
    original = Puzzle.solve_result
    initial = True
    def solve(puzzle, *args, **kwargs):
        nonlocal initial
        if initial:
            initial = False
            # Get a real witness for 10/01 without constraining the search model.
            model = puzzle._model.clone()
            from ortools.sat.python import cp_model
            solver = cp_model.CpSolver()
            for var, bit in zip(puzzle.solution_vars, (1, 0, 0, 1)):
                model.add(var._internal == bit)
            solver.solve(model)
            from puzzle import Solution
            return SolveResult("sat", Solution(solver, puzzle._model))
        return original(puzzle, *args, **kwargs)
    monkeypatch.setattr(Puzzle, "solve_result", solve)
    result = generate_bounded(recipe)
    assert result.status == "ok" and result.candidates > 1


def test_unknown_reduction_never_claims_irreducibility(monkeypatch):
    original = Puzzle.solve_result
    calls = 0
    def solve(puzzle, *args, **kwargs):
        nonlocal calls
        calls += 1
        return SolveResult("unknown") if calls == 3 else original(puzzle, *args, **kwargs)
    monkeypatch.setattr(Puzzle, "solve_result", solve)
    result = generate_bounded(ShadingRecipe(2, 3, (BlackCount(2),)))
    assert result.status == "unconfirmed" and result.unique and result.irreducible is None and not result.clues


def test_large_web_generation_checking_and_saved_compatibility_without_enumeration(monkeypatch):
    monkeypatch.setattr(oracle, "finite_space", lambda *a: pytest.fail("No production enumeration"))
    data = {"format": catalog.FORMAT, "rows": 8, "cols": 8,
            "rules": [{"id": "count", "parameters": {"count": 16}}],
            "clue_kinds": ["cell", "row-count", "column-count"], "seed": 0, "budget_seconds": 10}
    result = worker.generate_request(data)
    assert result["status"] == "ok" and result["evidence"]["method"] == "cp-sat"
    assert saved.verify(result["record"])["valid"]
    answer = [v for row in result["record"]["solution"] for v in row]
    submission = {"format": answers.FORMAT, "request": data, "clues": result["clues"], "answer": answer}
    assert answers.check_answer(submission) == {"status": "ok", "correct": True}
    answer[0] = 1-answer[0]
    assert answers.check_answer(submission) == {"status": "ok", "correct": False}
    monkeypatch.setattr(Puzzle, "solve_result", lambda *a, **k: SolveResult("unknown"))
    assert answers.check_answer(submission) == {"status": "unconfirmed"}


@pytest.mark.parametrize("black", [True, False])
def test_large_fixed_components_match_independent_flood_fill(black):
    rule = ColorComponentSize(3, black)
    recipe = ShadingRecipe(5, 5, (rule,))
    puzzle = recipe.create_empty()
    result = puzzle.solve_result(seed=0, time_limit=5)
    assert result.solution is not None
    bits = tuple(v for row in puzzle.result(result.solution) for v in row)
    assert oracle.accepts(rule, bits, 5, 5)
    # A nonempty three-cell component is allowed, a touching fourth is not.
    for length, expected in [(3, "sat"), (4, "unsat")]:
        fixed = recipe.create_empty()
        for index, cell in enumerate(fixed.board.cells):
            fixed.add(fixed.black[cell] == int((index < length) == black))
        assert fixed.solve_result(seed=0, time_limit=5).status == expected


def test_catalog_reports_each_remaining_rule_limit():
    limits = {r["identifier"]: r["requirements"]["max_cells"] for r in catalog.catalog()["rules"]}
    assert limits["count"] == limits["color-component-size"] == 100
    assert limits["white-island-areas"] == limits["unequal-corner-component-sizes"] == 9
    assert limits["corner-linked-components"] == 100
    assert limits["white-visibility-counts"] == 100
    assert limits["no-touching-equal-tetrominoes"] == 100
