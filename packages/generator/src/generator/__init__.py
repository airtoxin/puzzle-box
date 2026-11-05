"""Generic puzzle instance generator.

Works with puzzle classes or configured recipe objects that implement:
- create_empty() -> Puzzle
- extract_clues(solution, puzzle) -> list[Clue]
- build_from_clues(clues) -> Puzzle
"""

from __future__ import annotations

import random
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

from puzzle import Constraint, Puzzle, Solution
from puzzle.constraints import CompoundConstraint, OneOfConstraint, UniqueConstraint


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


type ConstraintBuilder[P: Puzzle] = Callable[[P], Constraint | Iterable[Constraint]]


def _contains_uniqueness_query(constraint: Constraint) -> bool:
    if isinstance(constraint, UniqueConstraint):
        return True
    if isinstance(constraint, (CompoundConstraint, OneOfConstraint)):
        return any(_contains_uniqueness_query(member) for member in constraint.constraints)
    return False


def _answer_projection(puzzle: Puzzle) -> frozenset[int] | None:
    variables = puzzle.solution_vars
    # Variable equality builds DSL constraints; use identity, ignoring harmless
    # ordering/duplicates. Keep default mode distinct from an empty projection.
    return None if variables is None else frozenset(map(id, variables))


@dataclass(frozen=True)
class ConstrainedRecipe[P: Puzzle, C]:
    """Add fixed base constraints to every model built by an existing recipe.

    Builders receive the fresh, concrete puzzle, never cached variables. They
    must depend only on fixed topology/configuration, not hints, solver state or
    invocation count. They may not change the base's answer meaning or clue
    extraction. The base's answer projection is preserved. This wrapper has no
    portable encoding: serializing only its base would omit the added rules.
    Builders return one DSL constraint or an iterable of them. unique() is a
    solve query, not a rule; None from a side-effect-only function is invalid.
    """

    base: GeneratablePuzzle[P, C]
    builders: tuple[ConstraintBuilder[P], ...]

    def __post_init__(self) -> None:
        builders = tuple(self.builders)
        if any(not callable(builder) for builder in builders):
            raise ValueError("Constraint builders must be callable")
        object.__setattr__(self, "builders", builders)

    def _apply(self, puzzle: P) -> P:
        answer_projection = _answer_projection(puzzle)
        for builder in self.builders:
            result = builder(puzzle)
            if isinstance(result, Constraint):
                constraints = iter((result,))
            else:
                message = "Builders must return a DSL constraint or an iterable of DSL constraints"
                if isinstance(result, (str, bytes, bytearray)):
                    raise TypeError(message)
                try:
                    constraints = iter(result)
                except TypeError as exc:
                    raise TypeError(message) from exc
            for constraint in constraints:
                if not isinstance(constraint, Constraint):
                    raise TypeError("Builders must yield DSL constraint objects")
                if _contains_uniqueness_query(constraint):
                    raise ValueError("unique() is a solve query, not an additional base rule")
                puzzle.add(constraint)
            if _answer_projection(puzzle) != answer_projection:
                raise ValueError("Constraint builders must preserve the base recipe's answer projection")
        return puzzle

    def create_empty(self) -> P:
        return self._apply(self.base.create_empty())

    def build_from_clues(self, clues: Sequence[C]) -> P:
        return self._apply(self.base.build_from_clues(list(clues)))

    def extract_clues(self, solution: Solution, puzzle: P) -> list[C]:
        return self.base.extract_clues(solution, puzzle)


def with_constraints[P: Puzzle, C](
    recipe: GeneratablePuzzle[P, C], *builders: ConstraintBuilder[P],
) -> ConstrainedRecipe[P, C]:
    """Compose additional DSL constraints without replacing the recipe's rules.

    The same builders run, in order, for the initial answer and all clue-reduction
    trials. Builders must return constraints using the supplied model's variables.
    They cannot remove base constraints or automatically connect different grids.
    """
    return ConstrainedRecipe(recipe, builders)


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
    initial_result = initial.solve_result(check_unique=True)
    if initial_result.uniqueness != "unique":
        raise InitialCluesNotUniqueError("Initial clues must define a uniquely solvable puzzle")

    rng = random.Random(seed)
    indices = list(range(len(clues)))
    rng.shuffle(indices)

    remaining = list(range(len(clues)))
    for idx in indices:
        trial_indices = [i for i in remaining if i != idx]
        trial = [clues[i] for i in trial_indices]
        instance = puzzle_class.build_from_clues(trial)
        result = instance.solve_result(check_unique=True)
        if result.uniqueness == "unique":
            remaining = trial_indices
        elif result.uniqueness != "multiple":
            raise RuntimeError("Clue necessity was not proven; reduction is unconfirmed")

    return [clues[i] for i in remaining]


__all__ = ["ConstrainedRecipe", "ConstraintBuilder", "GeneratablePuzzle", "InitialCluesNotUniqueError",
           "generate", "reduce_clues", "with_constraints"]
