"""Reuse a fixed recipe and one existing DSL component: connect black cells."""

import json

from generator import generate, with_constraints
from puzzle import Constraint, connected, unique
from puzzle_defs import BlackCount, ConnectedWhite, ShadingPuzzle, ShadingRecipe


def connected_black(puzzle: ShadingPuzzle) -> Constraint:
    return connected(puzzle.board.cells, lambda cell: puzzle.black[cell])


def make_recipe():
    # The count makes both colors nonempty; connected() alone permits emptiness.
    base = ShadingRecipe(2, 3, (BlackCount(2), ConnectedWhite()))
    return with_constraints(base, connected_black)


def main() -> None:
    recipe = make_recipe()
    clues = generate(recipe, seed=0)
    puzzle = recipe.build_from_clues(clues)
    puzzle.add(unique())
    answer = puzzle.solve()
    if answer is None:
        raise RuntimeError("The generated clues did not determine a unique answer")
    # A demonstration report with the actual clues, not a standard saved puzzle:
    # existing JSON recipe formats cannot encode the extra Python component.
    print(json.dumps({"format": "puzzle-box/connected-shading-demo-v1", "rows": 2, "cols": 3,
                      "rules": ["exactly 2 black cells", "white connected", "black connected"],
                      "clues": clues, "answer": puzzle.result(answer), "unique": True}, indent=2))


if __name__ == "__main__":
    main()
