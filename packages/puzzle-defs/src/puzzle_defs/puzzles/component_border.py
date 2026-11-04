"""Connect each selected-color component to the boundary, via a virtual frame."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Cell, Puzzle, SquareGrid, VarMap, connected
from puzzle_defs.puzzles.component_shapes import _check_color
from puzzle_defs.ui import RuleUi, UiParameter


@dataclass(frozen=True)
class ComponentsTouchBorder:
    """Every orthogonal component of a color reaches a board-edge cell.

    Separate border components are allowed. The selected color may be absent;
    nonemptiness and connectivity inside the board are separate conditions.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "components-touch-border", "全ての連結成分を外枠につなぐ",
        "対象色の各成分から、同じ色の上下左右のマスだけを通って外枠へ到達させます。複数成分や対象色0個も許します。",
        (UiParameter("black", "外枠へつなぐ色は黒（オフなら白）", "boolean", True),),
    )
    black: bool = True

    def __post_init__(self) -> None:
        _check_color(self.black)

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        rows, cols = len(board.rows()), len(board.cols())
        # Include the corners so all four sides form one connected frame even
        # on thin boards. It is an auxiliary graph, never an answer or a clue.
        frame = sorted(
            [Cell(r, c) for r in (-1, rows) for c in range(-1, cols + 1)]
            + [Cell(r, c) for r in range(rows) for c in (-1, cols)]
        )
        outside = puzzle.bool_var_map("outside_frame", frame)
        for cell in frame:
            puzzle.add(outside[cell] == 1)
        selected = {c: black[c] if self.black else ~black[c] for c in board.cells}
        puzzle.add(connected(board.cells + frame, lambda c: outside[c] if c in outside else selected[c]))
