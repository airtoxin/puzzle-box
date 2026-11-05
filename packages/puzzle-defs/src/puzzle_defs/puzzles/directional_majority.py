"""Independent directional runs and room majority counts, inspired by Juosan."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Puzzle, SquareGrid, VarMap, at_least_one, one_of, sum_expr
from puzzle_defs.puzzles.room_fragments import ROOM_PARAMETER, ROOM_UI, _count, _rooms
from puzzle_defs.room_layout import RoomMap, room_map
from puzzle_defs.ui import RuleUi, UiParameter


@dataclass(frozen=True)
class DirectionalRunLimit:
    """Limit each color's straight run perpendicular to its assigned direction.

    When horizontal_black is true, black has a vertical run limit and white
    has a horizontal one. Runs parallel to the assigned direction are free.
    The answer remains binary cells, not line edges or a path.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "directional-run-limit", "色ごとに横・縦の連続を制限",
        "横向きの色は縦に、縦向きの色は横に連続できる長さを制限します。向きに沿う連続長は自由です。回答は黒白のままで、線や経路ではありません。",
        (UiParameter("max_length", "向きと直交する最大連続長", "integer", 2, minimum=1, maximum=25),
         UiParameter("horizontal_black", "横向きを黒で表す（オフなら白）", "boolean", True)),
    )
    max_length: int = 2
    horizontal_black: bool = True

    def __post_init__(self) -> None:
        if type(self.max_length) is not int or self.max_length < 1:
            raise ValueError("max_length must be a positive integer")
        if type(self.horizontal_black) is not bool:
            raise ValueError("horizontal_black must be a boolean")

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        if self.max_length >= max(len(board.rows()), len(board.cols())):
            return
        for window in board.windows(1, self.max_length+1):
            puzzle.add(at_least_one(black[c] if self.horizontal_black else ~black[c] for c in window))
        for window in board.windows(self.max_length+1, 1):
            puzzle.add(at_least_one(~black[c] if self.horizontal_black else black[c] for c in window))


@dataclass(frozen=True)
class RoomMajorityCount:
    """The larger of black/white counts in every fixed room equals count.

    Ties are allowed: in a room of size 2*count, both colors occur count times.
    A single count is shared across rooms, not a per-room number grid.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "room-majority-count", "各部屋の多数色の個数を固定",
        "各部屋で黒・白の多い方の個数を指定値にします。同数も許し、多数色が黒か白かは部屋ごとに自由です。全ての部屋で同じ指定値を使います。",
        (ROOM_PARAMETER, UiParameter("count", "各部屋の多数色の個数", "integer", 2)), ROOM_UI,
    )
    rooms: RoomMap
    count: int = 2

    def __post_init__(self) -> None:
        _count(self.count)
        layout = room_map(self.rooms)
        if self.count > len(layout)*len(layout[0]):
            raise ValueError("Majority count cannot exceed the board area")
        object.__setattr__(self, "rooms", layout)

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        if self.count > len(board.cells):
            raise ValueError("Majority count cannot exceed the board area")
        for members in _rooms(board, self.rooms):
            area = len(members)
            if self.count > area or 2*self.count < area:
                puzzle.add(sum_expr([]) == 1)  # No color can have this maximum count.
                continue
            blacks = sum_expr(black[c] for c in members)
            if 2*self.count == area:
                puzzle.add(blacks == self.count)  # Do not XOR two identical true cases.
            else:
                puzzle.add(one_of(blacks == self.count, blacks == area-self.count))
