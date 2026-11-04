"""Fixed Kuromasu-style sight counts, independent of removable cell clues."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Cell, Puzzle, SquareGrid, Var, VarMap, sum_expr
from puzzle_defs.number_layout import NumberGrid, number_grid
from puzzle_defs.ui import RuleUi, UiChannel, UiParameter, UiRequirements

DEFAULT_SIGHT_COUNTS: NumberGrid = ((0, 3, 2), (0, 0, 0))


@dataclass(frozen=True)
class WhiteVisibilityCounts:
    """Positive entries require white cells and exact straight visibility.

    Count the origin once, then white cells in four straight rays, stopping
    before the first black cell or board edge. Zero means no requirement.
    Connectivity and black-cell noncontact remain separate rules.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "white-visibility-counts", "数字から見える白マス数を固定",
        "正の数字のマスは白。自身を1回含み、黒か外枠まで上下左右に見える白の合計を指定します。0は指定なしです。",
        (UiParameter("counts", "見える白マス数（0は指定なし）", "number-grid", DEFAULT_SIGHT_COUNTS, maximum=99),),
        UiRequirements(channels=(UiChannel("answer", "binary-cells"), UiChannel("sight-counts", "cell-sight-counts"))),
    )
    counts: NumberGrid

    def __post_init__(self) -> None:
        object.__setattr__(self, "counts", number_grid(self.counts))

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        if len(board.cells) > 25:
            raise ValueError("White visibility supports at most 25 board cells")
        number_grid(self.counts, rows=len(board.rows()), cols=len(board.cols()))
        cells = set(board.cells)
        for origin in board.cells:
            count = self.counts[origin.row][origin.col]
            if count == 0:
                continue
            puzzle.add(black[origin] == 0)
            seen: list[Var] = []
            for direction, (dr, dc) in enumerate(((1, 0), (-1, 0), (0, 1), (0, -1))):
                ray: list[Cell] = []
                target = Cell(origin.row + dr, origin.col + dc)
                while target in cells:
                    ray.append(target)
                    target = Cell(target.row + dr, target.col + dc)
                visible = puzzle.bool_var_map(f"sight_{origin.row}_{origin.col}_{direction}", ray)
                previous: int | Var = 1
                for target in ray:
                    current = visible[target]
                    # Exact AND of the previous prefix and the next cell's
                    # whiteness. A white cell beyond a black blocker is hidden.
                    puzzle.add(current <= previous)
                    puzzle.add(sum_expr([current, black[target]]) <= 1)
                    puzzle.add(sum_expr([current, black[target]]) >= previous)
                    seen.append(current)
                    previous = current
            puzzle.add(sum_expr(seen) == count - 1)
