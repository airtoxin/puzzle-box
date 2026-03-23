"""Generic puzzle instance generator.

Works with any Puzzle subclass that implements:
- create_empty() -> Puzzle
- extract_clues(solution, puzzle) -> list[Clue]
- build_from_clues(clues) -> Puzzle
"""

from __future__ import annotations

import random
from typing import Any, Protocol, TypeVar

from puzzle import Puzzle, Solution
from puzzle.constraints import UniqueConstraint


class GeneratablePuzzle(Protocol):
    """Protocol for puzzle classes that support generation."""

    @classmethod
    def create_empty(cls) -> Puzzle: ...

    @classmethod
    def extract_clues(cls, solution: Solution, puzzle: Puzzle) -> list[Any]: ...

    @classmethod
    def build_from_clues(cls, clues: list[Any]) -> Puzzle: ...


def generate(
    puzzle_class: type[GeneratablePuzzle],
    seed: int = 42,
) -> list[Any]:
    """Generate a minimal-clue puzzle instance with a unique solution.

    1. Create an empty puzzle and solve with random seed
    2. Extract all clues from the solution
    3. Reduce clues while maintaining unique solvability
    """
    empty = puzzle_class.create_empty()
    solution = empty.solve(seed=seed)
    if solution is None:
        raise RuntimeError(f"Failed to generate a random solution for {puzzle_class}")
    clues = puzzle_class.extract_clues(solution, empty)
    return reduce_clues(puzzle_class, clues, seed=seed)


def reduce_clues(
    puzzle_class: type[GeneratablePuzzle],
    clues: list[Any],
    seed: int | None = None,
) -> list[Any]:
    """Remove clues one by one while maintaining unique solvability.

    Iterates through clues in random order. For each clue, tries
    removing it. If the puzzle still has a unique solution, the
    clue is permanently removed.
    """
    rng = random.Random(seed)
    indices = list(range(len(clues)))
    rng.shuffle(indices)

    current = list(clues)
    for idx in indices:
        item = clues[idx]
        trial = [c for c in current if c != item]
        instance = puzzle_class.build_from_clues(trial)
        instance.add(UniqueConstraint())
        if instance.solve() is not None:
            current = trial

    return current


__all__ = ["GeneratablePuzzle", "generate", "reduce_clues"]
