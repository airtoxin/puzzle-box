"""Color components with rectangular or nonrectangular shape, without area clues."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Puzzle, SquareGrid, VarMap, at_least_one, sum_expr
from puzzle_defs.regions import enumerate_rectangles
from puzzle_defs.ui import RuleUi, UiParameter

COLOR = UiParameter("black", "黒を対象にする（オフなら白）", "boolean", True)


def _check_color(black: bool) -> None:
    if type(black) is not bool:
        raise ValueError("black must be a boolean")


@dataclass(frozen=True)
class RectangularComponents:
    """Every orthogonal component of the chosen color is a filled rectangle."""

    ui: ClassVar[RuleUi] = RuleUi("rectangular-components", "連結成分を長方形にする",
        "対象色の各連結成分を、正方形・1マス・細い帯も含む長方形にします。対象色0個も許します。", (COLOR,))
    black: bool = True

    def __post_init__(self) -> None:
        _check_color(self.black)

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        # A connected polyomino is rectangular iff it has no concave corner:
        # a 2x2 window with exactly three cells of that component's color.
        for window in board.windows(2, 2):
            puzzle.add(sum_expr(black[c] if self.black else ~black[c] for c in window) != 3)


@dataclass(frozen=True)
class NonRectangularComponents:
    """Every chosen-color component is nonrectangular; absence is allowed."""

    ui: ClassVar[RuleUi] = RuleUi("nonrectangular-components", "連結成分の長方形を禁止",
        "対象色の各連結成分は長方形以外にします。1マス・細い帯も禁止します。対象色0個は許します。",
        (UiParameter("black", COLOR.label, "boolean", False),))
    black: bool = False

    def __post_init__(self) -> None:
        _check_color(self.black)

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        chosen = {c: black[c] if self.black else ~black[c] for c in board.cells}
        opposite = {c: ~black[c] if self.black else black[c] for c in board.cells}
        # Forbid each filled rectangle from being an entire component. An
        # attached cell of the same color makes it a proper subset, so is allowed.
        for rectangle in enumerate_rectangles(board):
            interior = rectangle.cells
            boundary = {n for cell in interior for n in board.neighbors(cell)} - interior
            puzzle.add(at_least_one([opposite[c] for c in sorted(interior)]
                                    + [chosen[c] for c in sorted(boundary)]))
