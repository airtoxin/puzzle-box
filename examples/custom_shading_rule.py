"""Generate a small puzzle by combining one custom rule with a built-in rule."""
import json

from generator import generate
from puzzle import Puzzle, SquareGrid, VarMap, sum_expr, unique
from puzzle_defs import NonTouchingBlack, ShadingRecipe


class OneOrTwoBlack:
    """Fixed base rule: the board contains one or two black cells."""

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        total = sum_expr(black[c] for c in board.cells)
        puzzle.add(total >= 1)
        puzzle.add(total <= 2)


def make_recipe() -> ShadingRecipe:
    return ShadingRecipe(2, 2, (NonTouchingBlack(), OneOrTwoBlack()))


def main() -> None:
    recipe = make_recipe()
    clues = generate(recipe, seed=0)
    puzzle = recipe.build_from_clues(clues)
    puzzle.add(unique())
    answer = puzzle.solve()
    if answer is None:
        raise RuntimeError("Generated clues did not determine a unique answer")
    # This report includes the answer. Built-in saved-puzzle formats cannot
    # encode arbitrary Python rule classes; rebuild using this same recipe.
    print(json.dumps({"format": "puzzle-box/custom-shading-demo-v1", "seed": 0,
                      "rules": ["one or two black cells", "black cells do not share an edge"],
                      "clues": clues, "answer": puzzle.result(answer), "unique": True}, indent=2))


if __name__ == "__main__":
    main()
