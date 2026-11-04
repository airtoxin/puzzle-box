"""Fixed Minesweeper-style numeric givens on the shared binary answer cells."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Puzzle, SquareGrid, VarMap, sum_expr
from puzzle_defs.clue_layout import ClueGrid, clue_grid
from puzzle_defs.ui import RuleUi, UiChannel, UiParameter, UiRequirements

DEFAULT_NEIGHBOR_COUNTS: ClueGrid = ((0, None, 1), (None, 1, None))


@dataclass(frozen=True)
class AdjacentBlackCounts:
    """Numbered cells are white; counts constrain adjacent black cells.

    None means absent, zero is a real clue, and the origin is never counted.
    diagonal=True counts all eight surrounding cells; False counts four sides.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "adjacent-black-counts", "数字の周囲の黒マス数を固定",
        "数字マスは白。周囲の黒数を数字に合わせます。0も数ヒントで、数字なしは . と入力します。自身は数えません。",
        (UiParameter("neighbor_counts", "周囲の黒数（. は数字なし、0も有効）", "clue-grid", DEFAULT_NEIGHBOR_COUNTS, maximum=8),
         UiParameter("diagonal", "斜めの4マスも数える", "boolean", True)),
        UiRequirements(channels=(UiChannel("answer", "binary-cells"), UiChannel("neighbor-counts", "cell-neighbor-counts"))),
    )
    neighbor_counts: ClueGrid
    diagonal: bool = True

    def __post_init__(self) -> None:
        if type(self.diagonal) is not bool:
            raise ValueError("diagonal must be a boolean")
        object.__setattr__(self, "neighbor_counts", clue_grid(self.neighbor_counts, maximum=8))

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        clue_grid(self.neighbor_counts, rows=len(board.rows()), cols=len(board.cols()), maximum=8)
        pairs = board.king_neighbor_pairs() if self.diagonal else board.adjacent_cell_pairs()
        neighbors = {c: [] for c in board.cells}
        for first, second in pairs:
            neighbors[first].append(second)
            neighbors[second].append(first)
        for cell in board.cells:
            count = self.neighbor_counts[cell.row][cell.col]
            if count is not None:
                puzzle.add(black[cell] == 0)
                puzzle.add(sum_expr(black[c] for c in neighbors[cell]) == count)
