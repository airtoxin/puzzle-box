"""Clue-independent runs on the two straight diagonal directions."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Cell, Puzzle, SquareGrid, VarMap, sum_expr
from puzzle_defs.ui import RuleUi, UiParameter


@dataclass(frozen=True)
class DiagonalRunLimit:
    """Limit both colors' 45-degree runs; rows and columns remain free.

    Every cell participates. There are no holes, turns or wraparound, and
    neither color has to occur. Add row/column and room rules independently.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "diagonal-run-limit", "斜めの同色連続長を制限",
        "両方向の斜めで、黒・白それぞれの連続長を制限します。縦横・曲がる経路は数えず、空きマスのない黒白盤面が対象です。",
        (UiParameter("max_length", "斜めの最大連続長", "integer", 2, minimum=1, maximum=25),),
    )
    max_length: int = 2

    def __post_init__(self) -> None:
        if type(self.max_length) is not int or self.max_length < 1:
            raise ValueError("max_length must be a positive integer")

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        rows, cols = len(board.rows()), len(board.cols())
        if self.max_length >= min(rows, cols):
            return  # Huge redundant limits never reach CP-SAT integer bounds.
        for r in range(rows-self.max_length):
            for c in range(cols):
                for step in (-1, 1):
                    if 0 <= c+step*self.max_length < cols:
                        count = sum_expr(black[Cell(r+i,c+step*i)] for i in range(self.max_length+1))
                        puzzle.add(count >= 1)
                        puzzle.add(count <= self.max_length)
