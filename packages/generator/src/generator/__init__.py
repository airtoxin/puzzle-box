"""Generic puzzle instance generator.

Works with puzzle classes or configured recipe objects that implement:
- create_empty() -> Puzzle
- extract_clues(solution, puzzle) -> list[Clue]
- build_from_clues(clues) -> Puzzle
"""

from __future__ import annotations

import random
from typing import Protocol

from puzzle import Puzzle, Solution
from puzzle.constraints import UniqueConstraint


class InitialCluesNotUniqueError(ValueError):
    """Initial clues failed the uniqueness check (not a solver status).

    This includes inconsistent clues or a failure to prove uniqueness. Other
    input and recipe errors remain their original exceptions.
    """


class GeneratablePuzzle[P: Puzzle, C](Protocol):
    """A typed puzzle class or recipe with fixed dimensions and base rules.

    Removing clues must only remove constraints, never change the base rules,
    board, or meaning of a solution. Class methods and instance methods both fit.
    """

    def create_empty(self) -> P: ...

    def extract_clues(self, solution: Solution, puzzle: P) -> list[C]: ...

    def build_from_clues(self, clues: list[C]) -> P: ...


def generate[P: Puzzle, C](
    puzzle_class: GeneratablePuzzle[P, C],
    seed: int = 42,
) -> list[C]:
    """Generate an irreducible clue set with a unique solution.

    1. Create an empty puzzle and solve with random seed
    2. Extract all clues from the solution
    3. Validate uniqueness, then reduce clues while maintaining it

    Raises InitialCluesNotUniqueError (a ValueError) if the extracted clues
    do not pass the uniqueness check.
    This does not guarantee the globally smallest clue set or human difficulty.
    """
    empty = puzzle_class.create_empty()
    solution = empty.solve(seed=seed)
    if solution is None:
        raise RuntimeError(f"Failed to generate a random solution for {puzzle_class}")
    clues = puzzle_class.extract_clues(solution, empty)
    return reduce_clues(puzzle_class, clues, seed=seed)


def reduce_clues[P: Puzzle, C](
    puzzle_class: GeneratablePuzzle[P, C],
    clues: list[C],
    seed: int | None = None,
) -> list[C]:
    """Remove clues one by one while maintaining unique solvability.

    Iterates through clues in random order. For each clue, tries
    removing it. If the puzzle still has a unique solution, the
    clue is permanently removed. Equal clues are separate occurrences. The input
    list is not modified. Under the recipe's monotonicity contract, the result is
    irreducible: no single remaining clue can be removed while keeping uniqueness.

    Raises InitialCluesNotUniqueError (a ValueError) if the initial clues fail
    the uniqueness check, including multiple solutions or no solution.
    """
    initial = puzzle_class.build_from_clues(list(clues))
    initial.add(UniqueConstraint())
    if initial.solve() is None:
        raise InitialCluesNotUniqueError("Initial clues must define a uniquely solvable puzzle")

    rng = random.Random(seed)
    indices = list(range(len(clues)))
    rng.shuffle(indices)

    remaining = list(range(len(clues)))
    for idx in indices:
        trial_indices = [i for i in remaining if i != idx]
        trial = [clues[i] for i in trial_indices]
        instance = puzzle_class.build_from_clues(trial)
        instance.add(UniqueConstraint())
        if instance.solve() is not None:
            remaining = trial_indices

    return [clues[i] for i in remaining]


__all__ = ["GeneratablePuzzle", "InitialCluesNotUniqueError", "generate", "reduce_clues"]
