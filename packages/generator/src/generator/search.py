"""Bounded solver generation; exhaustive enumeration remains a separate diagnostic."""

from dataclasses import dataclass
import math
import random
import time
from typing import Literal

from generator import GeneratablePuzzle
from puzzle import Puzzle, Solution


DEFAULT_MAX_CANDIDATES = 64


@dataclass(frozen=True)
class GenerationResult[P: Puzzle, C]:
    status: Literal["ok", "unsatisfiable", "insufficient_hints", "search_exhausted", "unconfirmed"]
    clues: tuple[C, ...] = ()
    candidates: int = 0
    unique: bool | None = None
    irreducible: bool | None = None
    puzzle: P | None = None
    solution: Solution | None = None


def generate_bounded[P: Puzzle, C](recipe: GeneratablePuzzle[P, C], *, seed: int = 42,
                                    budget: float = 10, max_candidates: int = DEFAULT_MAX_CANDIDATES) -> GenerationResult[P, C]:
    """Retry distinct visible answers and reduce only with solver proofs.

    UNSAT before any candidate proves no completion. Exhausting all rejected
    candidates proves insufficient hints; a time/attempt limit proves neither.
    A reduction trial must find a second answer to prove a retained clue needed.
    No artifact is returned when uniqueness or irreducibility is unconfirmed.
    """
    if not math.isfinite(budget) or budget < 0:
        raise ValueError("budget must be finite and nonnegative")
    if type(max_candidates) is not int or max_candidates < 1:
        raise ValueError("max_candidates must be a positive integer")
    deadline = time.monotonic() + budget
    def remaining():
        return max(0.0, deadline - time.monotonic())

    empty = recipe.create_empty()
    for attempt in range(max_candidates):
        candidate = empty.solve_result(seed=seed, time_limit=remaining())
        if candidate.status == "unsat":
            return GenerationResult("insufficient_hints" if attempt else "unsatisfiable", candidates=attempt)
        if candidate.solution is None:
            return GenerationResult("unconfirmed", candidates=attempt)
        clues = recipe.extract_clues(candidate.solution, empty)
        initial = recipe.build_from_clues(clues).solve_result(
            seed=seed, time_limit=remaining(), check_unique=True)
        if initial.status == "unsat":
            raise ValueError("Extracted clues contradict their source solution")
        if initial.uniqueness == "multiple":
            empty.exclude_solution(candidate.solution)
            continue
        if initial.uniqueness != "unique":
            return GenerationResult("unconfirmed", candidates=attempt + 1)

        order = list(range(len(clues)))
        random.Random(seed).shuffle(order)
        retained = list(range(len(clues)))
        for index in order:
            trial_indices = [i for i in retained if i != index]
            result = recipe.build_from_clues([clues[i] for i in trial_indices]).solve_result(
                seed=seed, time_limit=remaining(), check_unique=True)
            if result.status == "unsat":
                raise ValueError("Removing a clue made a satisfiable recipe infeasible")
            if result.uniqueness == "unique":
                retained = trial_indices
            elif result.uniqueness != "multiple":
                return GenerationResult("unconfirmed", candidates=attempt + 1, unique=True)
        # Under the recipe's monotonicity contract a clue that was necessary
        # earlier is still necessary after other clues have been removed.
        return GenerationResult("ok", tuple(clues[i] for i in retained), attempt + 1, True, True,
                                empty, candidate.solution)
    return GenerationResult("search_exhausted", candidates=max_candidates)
