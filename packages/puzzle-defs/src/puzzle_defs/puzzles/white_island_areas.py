"""Numbered white components using bounded, existing connected-region candidates."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Puzzle, SquareGrid, VarMap, sum_expr
from puzzle_defs.number_layout import NumberGrid, number_grid
from puzzle_defs.regions import enumerate_connected_regions, filter_number_equals_area
from puzzle_defs.ui import RuleUi, UiChannel, UiParameter, UiRequirements

MAX_ISLAND_CELLS = 9
DEFAULT_ISLAND_AREAS: NumberGrid = ((1, 0, 0), (0, 0, 2))


@dataclass(frozen=True)
class WhiteIslandAreas:
    """Every white component contains exactly one positive area number.

    Numbered cells are white; zero means no number. Black connectivity and
    black 2x2 exclusion are separate rules. No numbers forces all cells black.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "white-island-areas", "白い島の面積を数字に合わせる",
        "各白連結成分は正の数字を1つ含み、面積をその数字に合わせます。数字マスは白、0は数字なし。9セル以下です。",
        (UiParameter("areas", "白い島の面積（0は数字なし）", "number-grid", DEFAULT_ISLAND_AREAS, maximum=99),),
        UiRequirements(channels=(UiChannel("answer", "binary-cells"), UiChannel("island-areas", "cell-island-areas"))),
    )
    areas: NumberGrid

    def __post_init__(self) -> None:
        grid = number_grid(self.areas)
        if len(grid) * len(grid[0]) > MAX_ISLAND_CELLS:
            raise ValueError(f"White island areas support at most {MAX_ISLAND_CELLS} board cells")
        object.__setattr__(self, "areas", grid)

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        number_grid(self.areas, rows=len(board.rows()), cols=len(board.cols()))
        numbers = {c: self.areas[c.row][c.col] for c in board.cells if self.areas[c.row][c.col] > 0}
        candidates = [region for size in sorted(set(numbers.values()))
                      for region in enumerate_connected_regions(board, size)]
        regions = sorted(filter_number_equals_area(candidates, numbers), key=lambda r: tuple(sorted(r.cells)))
        uses = puzzle.bool_var_map("white_island", regions)
        for cell in numbers:
            puzzle.add(black[cell] == 0)
        # Exact cover of white cells only. Every white cell needs a numbered
        # candidate, and every numbered cell must use one such candidate.
        for cell in board.cells:
            puzzle.add(sum_expr(uses[r] for r in regions if cell in r.cells) == ~black[cell])
        for region in regions:
            boundary = {n for c in region.cells for n in board.neighbors(c)} - region.cells
            for cell in sorted(boundary):
                # A selected candidate is a complete white component; two
                # selected islands cannot touch along an edge.
                puzzle.add(sum_expr([uses[region], ~black[cell]]) <= 1)
