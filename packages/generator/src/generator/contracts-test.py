from dataclasses import dataclass
from itertools import product

import pytest

from generator import InitialCluesNotUniqueError, generate, reduce_clues
from puzzle import Puzzle, Solution, non_touching, square_grid, sum_expr

Clue = tuple[int, int]


class StripPuzzle(Puzzle):
    def __init__(self, width: int, clues: list[Clue], separated: bool = True):
        super().__init__("strip")
        self.board = square_grid(1, width)
        self.black = self.bool_var_map("black", self.board.cells)
        self.add(sum_expr(self.black[c] for c in self.board.cells) == 2)
        if separated:
            self.add(non_touching(self.black, self.board.adjacent_cell_pairs()))
        for col, value in clues:
            self.add(self.black[self.board.cell(0, col)] == value)


@dataclass(frozen=True)
class StripRecipe:
    width: int
    separated: bool = True

    def create_empty(self) -> StripPuzzle:
        return self.build_from_clues([])

    def extract_clues(self, solution: Solution, puzzle: StripPuzzle) -> list[Clue]:
        return [(c.col, solution.value(puzzle.black[c])) for c in puzzle.board.cells]

    def build_from_clues(self, clues: list[Clue]) -> StripPuzzle:
        return StripPuzzle(self.width, clues, self.separated)


def _answers(recipe: StripRecipe, clues: list[Clue]) -> list[tuple[int, ...]]:
    """Independent exhaustive oracle, with no CP-SAT or DSL constraints."""
    return [
        bits for bits in product([0, 1], repeat=recipe.width)
        if sum(bits) == 2
        and (not recipe.separated or not any(a and b for a, b in zip(bits, bits[1:])))
        and all(bits[col] == value for col, value in clues)
    ]


@pytest.mark.parametrize("width", [4, 5, 6])
@pytest.mark.parametrize("separated", [False, True])
def test_configured_recipes_generate_unique_irreducible_clues(width: int, separated: bool):
    recipe = StripRecipe(width, separated)
    clues: list[Clue] = generate(recipe, seed=17)
    assert len(_answers(recipe, clues)) == 1
    for idx in range(len(clues)):
        assert len(_answers(recipe, clues[:idx] + clues[idx + 1:])) > 1


@pytest.mark.parametrize("clues", [[], [(0, 0)], [(0, 0), (0, 1)]])
def test_reduction_rejects_ambiguous_or_inconsistent_initial_clues(clues: list[Clue]):
    with pytest.raises(InitialCluesNotUniqueError, match="uniquely solvable") as error:
        reduce_clues(StripRecipe(5), clues)
    assert isinstance(error.value, ValueError)


def test_duplicate_clues_are_removed_one_occurrence_at_a_time():
    # These duplicated clues fix the only answer 1001. Removing both occurrences
    # of either clue at once loses uniqueness, but one of each can be removed.
    clues = [(1, 0), (1, 0), (2, 0), (2, 0)]
    original = clues.copy()
    recipe = StripRecipe(4, separated=False)
    reduced = reduce_clues(recipe, clues, seed=4)
    assert reduced == [(1, 0), (2, 0)]
    assert clues == original
    assert reduce_clues(recipe, clues, seed=4) == reduced
    assert len(_answers(recipe, reduced)) == 1


def test_empty_clues_can_already_determine_one_answer():
    assert reduce_clues(StripRecipe(3), []) == []


def test_generation_rejects_an_infeasible_base_model():
    with pytest.raises(RuntimeError, match="Failed to generate"):
        generate(StripRecipe(1))


def test_generation_rejects_incomplete_clue_extraction():
    class IncompleteRecipe(StripRecipe):
        def extract_clues(self, solution: Solution, puzzle: StripPuzzle) -> list[Clue]:
            return []

    with pytest.raises(ValueError, match="uniquely solvable"):
        generate(IncompleteRecipe(5))


@pytest.mark.parametrize("allow_touch", [False, True])
def test_composition_example_runs_end_to_end(allow_touch: bool):
    import json
    from pathlib import Path
    import subprocess
    import sys

    script = Path(__file__).resolve().parents[4] / "examples" / "compose_binary.py"
    args = [sys.executable, str(script), "--width", "6", "--count", "2", "--seed", "17"]
    if allow_touch:
        args.append("--allow-touch")
    result = subprocess.run(args, check=True, capture_output=True, text=True, timeout=30)
    data = json.loads(result.stdout)
    recipe = StripRecipe(6, separated=not allow_touch)
    answers = _answers(recipe, data["clues"])
    assert answers == [tuple(data["solution"])]
    for idx in range(len(data["clues"])):
        trial = data["clues"][:idx] + data["clues"][idx + 1:]
        assert len(_answers(recipe, trial)) > 1
