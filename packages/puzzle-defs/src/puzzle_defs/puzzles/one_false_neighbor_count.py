"""Exactly one false orthogonal black-count clue per fixed room, from Usowan."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Puzzle, SquareGrid, VarMap, one_of, sum_expr
from puzzle_defs.clue_layout import ClueGrid, clue_grid
from puzzle_defs.puzzles.adjacent_black_counts import AdjacentBlackCounts
from puzzle_defs.puzzles.room_fragments import ROOM_PARAMETER, _rooms
from puzzle_defs.room_layout import RoomMap, room_map
from puzzle_defs.ui import RuleUi, UiChannel, UiRequirements


@dataclass(frozen=True)
class OneFalseAdjacentCountPerRoom:
    """Numbered cells are white; exactly one count per room must be false.

    Counts use four orthogonal neighbors, including those outside the room.
    None is absent, zero is a clue. A room without a clue is unsatisfiable.
    Connectivity and non-touching black cells are separate fragments.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "one-false-adjacent-count-per-room", "各部屋の隣接黒数にウソを1つだけ置く",
        "数字マスは白。上下左右の黒数が数字と違うマスを各部屋にちょうど1つ置き、他の数字は正しくします。部屋外の隣も数えます。数字なしの部屋は成立しません。",
        (ROOM_PARAMETER, AdjacentBlackCounts.ui.parameters[0]),
        UiRequirements(channels=(UiChannel("answer", "binary-cells"), UiChannel("rooms", "cell-regions"),
                                 UiChannel("neighbor-counts", "cell-neighbor-counts"))),
    )
    rooms: RoomMap
    neighbor_counts: ClueGrid

    def __post_init__(self) -> None:
        layout = room_map(self.rooms)
        object.__setattr__(self, "rooms", layout)
        object.__setattr__(self, "neighbor_counts", clue_grid(
            self.neighbor_counts, rows=len(layout), cols=len(layout[0]), maximum=8))

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        groups = _rooms(board, self.rooms)
        numbered = [c for c in board.cells if self.neighbor_counts[c.row][c.col] is not None]
        wrong = puzzle.bool_var_map("false_adjacent_count", numbered)
        for cell in numbered:
            count = self.neighbor_counts[cell.row][cell.col]
            assert count is not None
            puzzle.add(black[cell] == 0)
            # XOR fully reifies wrong <-> actual count != given count. A free
            # selector would incorrectly allow two false clues in one room.
            puzzle.add(one_of(wrong[cell] == 1, sum_expr(black[n] for n in board.neighbors(cell)) == count))
        for members in groups:
            puzzle.add(sum_expr(wrong[c] for c in members if c in wrong) == 1)
