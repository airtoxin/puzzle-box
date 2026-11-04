"""Connectivity through edges and corners, separate from component shapes."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Puzzle, SquareGrid, VarMap, at_least_one, connected
from puzzle_defs.puzzles.component_shapes import _check_color
from puzzle_defs.ui import RuleUi, UiParameter


@dataclass(frozen=True)
class CornerConnectedColor:
    """Selected color connects through any edge or corner (eight neighbors).

    This changes global connectivity only, not the definition of orthogonal
    components used by other fragments. Nonemptiness is explicit.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "corner-connected-color", "タテヨコ・ナナメで色をつなぐ",
        "対象色を辺または頂点経由でつなぎます。他の成分の形・面積・連結の定義は変えません。",
        (UiParameter("black", "頂点経由でつなぐ色は黒（オフなら白）", "boolean", False),
         UiParameter("nonempty", "頂点経由でつなぐ色を1つ以上にする", "boolean", True)),
    )
    black: bool = False
    nonempty: bool = True

    def __post_init__(self) -> None:
        _check_color(self.black)
        if type(self.nonempty) is not bool:
            raise ValueError("nonempty must be a boolean")

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        selected = {c: black[c] if self.black else ~black[c] for c in board.cells}
        puzzle.add(connected(board.cells, lambda c: selected[c], diagonal=True))
        if self.nonempty:
            puzzle.add(at_least_one(selected[c] for c in board.cells))
