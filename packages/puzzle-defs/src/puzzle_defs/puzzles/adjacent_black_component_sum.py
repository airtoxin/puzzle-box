"""Numeric Kurotto circles; sum each adjacent black component's area once."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Puzzle, SquareGrid, VarMap, sum_expr
from puzzle_defs.clue_layout import ClueGrid, clue_grid
from puzzle_defs.regions import enumerate_connected_regions
from puzzle_defs.ui import RuleUi, UiChannel, UiParameter, UiRequirements

MAX_COMPONENT_SUM_CELLS = 9
DEFAULT_COMPONENT_COUNTS: ClueGrid = ((5, None, None), (None, None, None))


@dataclass(frozen=True)
class AdjacentBlackComponentSum:
    """Numbered cells are white and sum distinct adjacent black component sizes.

    Touch is orthogonal; multiple contacts with one component count it once.
    None is no circle, not an unnumbered white circle. Zero is a real clue.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "adjacent-black-component-sum", "接する黒成分の面積合計を固定",
        "数字マスは白。上下左右で接する黒成分の面積を、同じ成分は1回だけ足します。0も数字、. は丸なし。9セル以下です。",
        (UiParameter("component_counts", "接する黒成分の面積合計（. は丸なし）", "clue-grid", DEFAULT_COMPONENT_COUNTS, maximum=99),),
        UiRequirements(max_cells=9, channels=(UiChannel("answer", "binary-cells"), UiChannel("component-counts", "cell-component-counts"))),
    )
    component_counts: ClueGrid

    def __post_init__(self) -> None:
        grid = clue_grid(self.component_counts)
        if len(grid) * len(grid[0]) > MAX_COMPONENT_SUM_CELLS:
            raise ValueError(f"Black component sums support at most {MAX_COMPONENT_SUM_CELLS} board cells")
        object.__setattr__(self, "component_counts", grid)

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        clue_grid(self.component_counts, rows=len(board.rows()), cols=len(board.cols()))
        numbers = {c: self.component_counts[c.row][c.col] for c in board.cells
                   if self.component_counts[c.row][c.col] is not None}
        if not numbers:
            return  # No circles means no condition, without enumerating regions.
        available = set(board.cells) - numbers.keys()
        regions = [r for size in range(1, len(available)+1)
                   for r in enumerate_connected_regions(board, size, available)]
        regions.sort(key=lambda r: tuple(sorted(r.cells)))
        uses = puzzle.bool_var_map("adjacent_black_component", regions)
        for cell in numbers:
            puzzle.add(black[cell] == 0)
        for cell in board.cells:
            puzzle.add(sum_expr(uses[r] for r in regions if cell in r.cells) == black[cell])
        for region in regions:
            boundary = {n for c in region.cells for n in board.neighbors(c)} - region.cells
            for cell in sorted(boundary):
                # Active candidates must be whole components, never pieces of
                # one component that could be counted independently.
                puzzle.add(sum_expr([uses[region], black[cell]]) <= 1)
        for cell, count in numbers.items():
            adjacent = set(board.neighbors(cell))
            # Each region appears once even when several of its cells touch
            # the circle; repetition weights its area, not its contact count.
            terms = [uses[r] for r in regions if r.cells & adjacent for _ in r.cells]
            puzzle.add(sum_expr(terms) == count)
