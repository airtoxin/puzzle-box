"""Clue-independent binary-cell fragments, not complete named puzzles."""

from dataclasses import dataclass
from itertools import combinations
from typing import ClassVar

from puzzle import Puzzle, SquareGrid, VarMap, at_least_one, connected, sum_expr
from puzzle_defs.ui import RuleUi, UiParameter


def _limit_runs(puzzle: Puzzle, board: SquareGrid, black: VarMap, maximum: int) -> None:
    if maximum >= max(len(board.rows()), len(board.cols())):
        return  # Also keeps arbitrarily large, redundant limits out of CP-SAT bounds.
    for shape in ((1, maximum + 1), (maximum + 1, 1)):
        for window in board.windows(*shape):
            count = sum_expr(black[c] for c in window)
            puzzle.add(count >= 1)
            puzzle.add(count <= maximum)


@dataclass(frozen=True)
class ConnectedBlack:
    """Black cells form one orthogonal component; empty is opt-in."""

    ui: ClassVar[RuleUi] = RuleUi("connected-black", "黒マスをつなぐ",
        "すべての黒マスが上下左右でつながります。", (
            UiParameter("nonempty", "黒マスを1つ以上にする", "boolean", True),))
    nonempty: bool = True

    def __post_init__(self) -> None:
        if type(self.nonempty) is not bool:
            raise ValueError("nonempty must be a boolean")

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        puzzle.add(connected(board.cells, lambda c: black[c]))
        if self.nonempty:
            puzzle.add(at_least_one(black[c] for c in board.cells))


@dataclass(frozen=True)
class NoBlack2x2:
    """Every 2x2 window contains at least one white cell."""

    ui: ClassVar[RuleUi] = RuleUi("no-black-2x2", "黒い2×2を禁止",
        "すべての2×2領域に白マスを含めます。")

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        for window in board.windows(2, 2):
            puzzle.add(at_least_one(~black[c] for c in window))


@dataclass(frozen=True)
class BlackDominoes:
    """Each orthogonal black component has size two. Zero components is allowed."""

    ui: ClassVar[RuleUi] = RuleUi("black-dominoes", "黒マスを2個ずつにする",
        "黒の連結成分は上下左右に接する2マスです。斜めの接触と黒0個は許します。部屋の条件は含みません。")

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        for cell in board.cells:
            neighbors = board.neighbors(cell)
            count = sum_expr(black[c] for c in neighbors)
            # Black vertices have degree exactly one; white vertices are free.
            puzzle.add(count >= black[cell])
            puzzle.add(sum_expr([black[c] for c in neighbors] + [black[cell]] * len(neighbors))
                       <= len(neighbors) + 1)


@dataclass(frozen=True)
class NoThreeConsecutive:
    """No horizontal or vertical triple is all black or all white."""

    ui: ClassVar[RuleUi] = RuleUi("no-three-consecutive", "同色の3連続を禁止",
        "各行・列で黒または白が3マス連続しないようにします。斜めは対象外です。")

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        _limit_runs(puzzle, board, black, 2)


@dataclass(frozen=True)
class RunLengthLimit:
    """Both colors have horizontal/vertical runs of at most max_length cells."""

    ui: ClassVar[RuleUi] = RuleUi("run-length-limit", "同色の連続長に上限を付ける",
        "黒・白それぞれの横・縦の連続長を制限します。斜めや曲がる経路は数えません。",
        (UiParameter("max_length", "同色の最大連続長", "integer", 3, minimum=1, maximum=25),))
    max_length: int = 3

    def __post_init__(self) -> None:
        if type(self.max_length) is not int or self.max_length < 1:
            raise ValueError("max_length must be a positive integer")

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        _limit_runs(puzzle, board, black, self.max_length)


@dataclass(frozen=True)
class BalancedLines:
    """Every row and column has equal color counts; odd dimensions are UNSAT."""

    ui: ClassVar[RuleUi] = RuleUi("balanced-lines", "各行・列の白黒を同数にする",
        "すべての行と列で白黒の個数を同じにします。縦横とも偶数が必要です。")

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        for line in board.rows() + board.cols():
            puzzle.add(sum_expr(black[c] for c in line) == sum_expr(~black[c] for c in line))


@dataclass(frozen=True)
class DistinctLines:
    """Rows are pairwise different, as are columns. A row may equal a column."""

    ui: ClassVar[RuleUi] = RuleUi("distinct-lines", "同じ行・同じ列を禁止",
        "行同士・列同士で同一の白黒配列を禁止します。行と列の一致は許します。")

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        for lines in (board.rows(), board.cols()):
            for first, second in combinations(lines, 2):
                puzzle.add(at_least_one(black[a] != black[b] for a, b in zip(first, second)))
