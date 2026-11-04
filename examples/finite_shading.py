"""Select an identifiable small-board completion before reducing its clues."""

import random

from generator import InitialCluesNotUniqueError, reduce_clues
from puzzle import unique
from puzzle_defs import ShadingRecipe
from puzzle_defs.puzzles.shading import Clue
from analyze_shading import Bits, finite_space, full_clues

SELECTION = "finite-identifiable-v1"


def identifiable_completions(recipe: ShadingRecipe) -> list[Bits]:
    """Enumerate exact built-in rules (<=9 cells, <=8 occurrences), in bit order."""
    _, boards, masks = finite_space(recipe)
    valid = set(range(len(boards)))
    for mask in masks:
        valid.intersection_update(mask)
    if not valid:
        raise ValueError("No completion satisfies these rules; change the recipe")
    groups: dict[tuple[Clue, ...], list[Bits]] = {}
    for index in sorted(valid):
        bits = boards[index]
        groups.setdefault(full_clues(recipe, bits), []).append(bits)
    eligible = sorted(group[0] for group in groups.values() if len(group) == 1)
    if not eligible:
        raise InitialCluesNotUniqueError(
            "No completion is identifiable by the selected full candidate hints; "
            "changing the seed cannot help this recipe"
        )
    return eligible


def generate_finite(recipe: ShadingRecipe, *, seed: int = 42) -> list[Clue]:
    """Choose a finite candidate, check it with the DSL, then reduce real clues.

    The oracle only chooses the starting answer. The unmodified recipe and
    normal generator verify uniqueness and irreducibility; no extra hint kind
    or selection constraint is added to the puzzle being generated.
    """
    if type(seed) is not int or not 0 <= seed <= 2**31 - 1:
        raise ValueError("Seed must be an integer between 0 and 2147483647")
    bits = random.Random(seed).choice(identifiable_completions(recipe))
    clues = list(full_clues(recipe, bits))
    puzzle = recipe.build_from_clues(clues)
    puzzle.add(unique())
    solution = puzzle.solve(seed=seed)
    if solution is None or tuple(v for row in puzzle.result(solution) for v in row) != bits:
        raise RuntimeError("Selected finite completion disagrees with the DSL uniqueness check")
    actual_clues = recipe.extract_clues(solution, puzzle)
    if actual_clues != clues:
        raise RuntimeError("Selected finite hints disagree with the recipe's extracted clues")
    return reduce_clues(recipe, actual_clues, seed=seed)
