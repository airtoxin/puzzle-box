"""Compose a count rule and optional non-touching rule, then generate clues.

Run: uv run --all-packages python examples/compose_binary.py --width 6 --count 2
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json

from generator import generate
from puzzle import Puzzle, Solution, non_touching, square_grid, sum_expr, unique

Clue = tuple[int, int]


class BinaryStrip(Puzzle):
    def __init__(self, width: int, count: int, separated: bool, clues: list[Clue]):
        super().__init__("binary strip")
        self.board = square_grid(1, width)
        self.black = self.bool_var_map("black", self.board.cells)
        self.add(sum_expr(self.black[c] for c in self.board.cells) == count)
        if separated:
            self.add(non_touching(self.black, self.board.adjacent_cell_pairs()))
        for col, value in clues:
            self.add(self.black[self.board.cell(0, col)] == value)

    def result(self, solution: Solution) -> list[int]:
        return [solution.value(self.black[c]) for c in self.board.cells]


@dataclass(frozen=True)
class StripRecipe:
    width: int
    count: int
    separated: bool

    def create_empty(self) -> BinaryStrip:
        return self.build_from_clues([])

    def extract_clues(self, solution: Solution, puzzle: BinaryStrip) -> list[Clue]:
        return list(enumerate(puzzle.result(solution)))

    def build_from_clues(self, clues: list[Clue]) -> BinaryStrip:
        return BinaryStrip(self.width, self.count, self.separated, clues)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=6)
    parser.add_argument("--count", type=int, default=2)
    parser.add_argument("--allow-touch", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.width < 1 or not 0 <= args.count <= args.width:
        parser.error("width must be positive and count must be between 0 and width")
    if not args.allow_touch and args.count > (args.width + 1) // 2:
        parser.error("too many selected cells for the non-touching rule")

    recipe = StripRecipe(args.width, args.count, not args.allow_touch)
    clues = generate(recipe, seed=args.seed)
    puzzle = recipe.build_from_clues(clues)
    puzzle.add(unique())
    solution = puzzle.solve()
    assert solution is not None
    print(json.dumps({
        "width": recipe.width,
        "count": recipe.count,
        "non_touching": recipe.separated,
        "seed": args.seed,
        "clues": clues,
        "solution": puzzle.result(solution),
    }))


if __name__ == "__main__":
    main()
