"""Four-neighbor black counts without fixing the numbered cell's color."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Puzzle, SquareGrid, VarMap, sum_expr
from puzzle_defs.clue_layout import ClueGrid, clue_grid
from puzzle_defs.ui import RuleUi, UiChannel, UiParameter, UiRequirements

DEFAULT_ORTHOGONAL_COUNTS: ClueGrid = ((2, None, None), (None, None, None))


@dataclass(frozen=True)
class OrthogonalBlackCounts:
    """Count black cells on four sides; numbered cells can be black or white.

    None is absent, zero is a real clue. The origin, diagonals and cells
    outside the board are never counted. Tile constraints are independent.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "orthogonal-black-counts", "色を固定せず上下左右の黒数を指定",
        "数字マス自身の色は固定せず、上下左右の黒数を数字に合わせます。自身・斜めは数えません。0も数字で、. は数字なしです。",
        (UiParameter("orthogonal_counts", "上下左右の黒数（. は数字なし、0も有効）", "clue-grid", DEFAULT_ORTHOGONAL_COUNTS, maximum=4),),
        UiRequirements(channels=(UiChannel("answer", "binary-cells"), UiChannel("orthogonal-counts", "cell-orthogonal-counts"))),
    )
    orthogonal_counts: ClueGrid

    def __post_init__(self) -> None:
        object.__setattr__(self, "orthogonal_counts", clue_grid(self.orthogonal_counts, maximum=4))

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        clue_grid(self.orthogonal_counts, rows=len(board.rows()), cols=len(board.cols()), maximum=4)
        for cell in board.cells:
            count = self.orthogonal_counts[cell.row][cell.col]
            if count is not None:
                puzzle.add(sum_expr(black[n] for n in board.neighbors(cell)) == count)
