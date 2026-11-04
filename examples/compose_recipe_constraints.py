"""Add the same count component to explicit cell/corner-edge/center-edge scopes."""

from collections.abc import Callable, Iterable
import json

from generator import ConstraintBuilder, generate, with_constraints
from puzzle import Constraint, Puzzle, Var, sum_expr, unique
from puzzle_defs import NonTouchingBlack, ShadingPuzzle, ShadingRecipe, SlitherlinkPuzzle, SlitherlinkRecipe, YajilinPuzzle, YajilinRecipe


def selected_count[P: Puzzle](select: Callable[[P], Iterable[Var]], count: int) -> ConstraintBuilder[P]:
    """Example component: select binary variables explicitly for each recipe."""
    def build(puzzle: P) -> Iterable[Constraint]:
        return [sum_expr(select(puzzle)) == count]
    return build


def black_cells(puzzle: ShadingPuzzle) -> Iterable[Var]:
    return (puzzle.black[c] for c in puzzle.board.cells)


def corner_edges(puzzle: SlitherlinkPuzzle) -> Iterable[Var]:
    return (puzzle.edge_on[e] for e in puzzle.board.edges)


def center_edges(puzzle: YajilinPuzzle) -> Iterable[Var]:
    return (puzzle.edge_on[e] for e in puzzle.loop_board.edges)


def main() -> None:
    shading = with_constraints(ShadingRecipe(2, 2, (NonTouchingBlack(),)), selected_count(black_cells, 2))
    loop = with_constraints(SlitherlinkRecipe(1, 2), selected_count(corner_edges, 6))
    coupled_base = YajilinRecipe(3, 4)
    coupled = with_constraints(coupled_base, selected_count(center_edges, 12))

    results = []
    # These Python builders have no portable JSON rule encoding. Output a report,
    # not a shading/slitherlink/yajilin artifact that would omit the added rule.
    for label, recipe, answer in [
        ("shading: exactly 2 black cells", shading, lambda s, p: p.result(s)),
        ("slitherlink: exactly 6 used edges", loop, lambda s, p: sorted(map(list, p.result(s)))),
        ("yajilin: exactly 12 used edges", coupled, lambda s, p: {
            "black_cells": sorted(map(list, coupled_base.answer(s, p).black_cells)),
            "loop_edges": sorted(map(list, coupled_base.answer(s, p).loop_edges)),
        }),
    ]:
        clues = generate(recipe, seed=0)
        puzzle = recipe.build_from_clues(clues)
        puzzle.add(unique())
        solution = puzzle.solve()
        if solution is None:
            raise RuntimeError("Composed recipe did not determine a unique answer")
        for i in range(len(clues)):
            trial = recipe.build_from_clues(clues[:i] + clues[i+1:])
            trial.add(unique())
            if trial.solve() is not None:
                raise RuntimeError("Clue reduction was not irreducible")
        results.append({"case": label, "clue_count": len(clues), "unique": True, "irreducible": True,
                        "answer": answer(solution, puzzle)})
    print(json.dumps({"format": "puzzle-box/constraint-composition-demo-v1", "results": results}, indent=2))


if __name__ == "__main__":
    main()
