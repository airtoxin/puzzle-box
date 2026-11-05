"""No isolated orthogonal components: each must join another at a corner."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import ClassVar

from puzzle import Cell, Puzzle, SquareGrid, VarMap, sum_expr
from puzzle_defs.puzzles.component_shapes import _check_color
from puzzle_defs.ui import RuleUi, UiParameter, UiRequirements

MAX_CORNER_LINK_CELLS = 10


def _connected_subsets(board: SquareGrid) -> Iterator[frozenset[Cell]]:
    # At most 1023 masks; visit each subset once, irrespective of growth order.
    cells = tuple(board.cells)
    for mask in range(1,1 << len(cells)):
        subset = {c for i,c in enumerate(cells) if mask & (1 << i)}
        reached = {min(subset)}
        while (more := reached | {n for c in reached for n in board.neighbors(c) if n in subset}) != reached:
            reached = more
        if reached == subset:
            yield frozenset(subset)


@dataclass(frozen=True)
class CornerLinkedComponents:
    """Every chosen-color orthogonal component touches another diagonally.

    Empty color sets and multiple chains are allowed. Diagonal contacts inside
    the same orthogonal component do not count. Core/file limit: ten cells;
    the Web shares that limit; finite diagnostics remain limited to nine.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "corner-linked-components", "各成分を別の成分と角でつなぐ",
        "対象色の各上下左右の成分を、別成分と角で接触させます。成分内部の角接触は数えません。複数チェーン・対象色0個は許し、形の一致は検査しません。",
        (UiParameter("black", "角でつなぐ色は黒（オフなら白）", "boolean", True),),
        requirements=UiRequirements(max_cells=10),
    )
    black: bool = True

    def __post_init__(self) -> None:
        _check_color(self.black)

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        if len(board.cells) > MAX_CORNER_LINK_CELLS:
            raise ValueError(f"Corner-linked components support at most {MAX_CORNER_LINK_CELLS} board cells")
        cells = set(board.cells)
        selected = {c:black[c] if self.black else ~black[c] for c in board.cells}
        opposite = {c:~black[c] if self.black else black[c] for c in board.cells}
        for region in _connected_subsets(board):
            outside = ({Cell(c.row+dr,c.col+dc) for c in region
                        for dr in (-1,0,1) for dc in (-1,0,1)} & cells)-region
            # A proper subset of a component has an external orthogonal
            # selected neighbor. For the actual whole component, only an
            # external diagonal neighbor can satisfy this clause.
            puzzle.add(sum_expr([opposite[c] for c in sorted(region)]
                                +[selected[c] for c in sorted(outside)]) >= 1)
