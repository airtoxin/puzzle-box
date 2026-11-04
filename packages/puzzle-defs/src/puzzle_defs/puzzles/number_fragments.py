"""Fixed-number constraints on a binary shading answer."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Puzzle, SquareGrid, VarMap
from puzzle_defs.number_layout import DEFAULT_NUMBERS, NumberGrid, equal_number_pairs, number_grid
from puzzle_defs.ui import RuleUi, UiChannel, UiParameter, UiRequirements


@dataclass(frozen=True)
class DistinctWhiteNumbers:
    """No row or column contains equal fixed numbers on two white cells."""

    ui: ClassVar[RuleUi] = RuleUi("distinct-white-numbers", "白マスの数字を重複させない",
        "同じ行・列で同じ数字が白マスに2個残らないようにします。数字は固定した入力です。",
        (UiParameter("numbers", "固定数字（行ごとに入力）", "number-grid", DEFAULT_NUMBERS, maximum=99),),
        UiRequirements(channels=(UiChannel("answer","binary-cells"), UiChannel("numbers","cell-numbers"))))
    numbers: NumberGrid

    def __post_init__(self) -> None:
        object.__setattr__(self,"numbers",number_grid(self.numbers))

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        number_grid(self.numbers,rows=len(board.rows()),cols=len(board.cols()))
        for a,b in equal_number_pairs(board,self.numbers):
            puzzle.add(black[a] | black[b])
