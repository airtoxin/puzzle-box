"""Fixed-room and line fragments on the shared binary cell answer."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Cell, Puzzle, SquareGrid, VarMap, at_least_one, connected, sum_expr
from puzzle_defs.room_layout import DEFAULT_ROOMS, RoomMap, room_map
from puzzle_defs.ui import RuleUi, UiChannel, UiParameter, UiRequirements

ROOM_UI = UiRequirements(channels=(UiChannel("answer", "binary-cells"), UiChannel("rooms", "cell-regions")))
ROOM_PARAMETER = UiParameter("rooms", "部屋配置（同じ数字が同じ部屋）", "region-map", DEFAULT_ROOMS)


def _rooms(board: SquareGrid, layout: RoomMap) -> list[list[Cell]]:
    room_map(layout, rows=len(board.rows()), cols=len(board.cols()))
    return [[c for c in board.cells if layout[c.row][c.col] == label]
            for label in sorted({n for row in layout for n in row})]


def _count(count: int) -> None:
    if type(count) is not int or count < 0:
        raise ValueError("Count must be a nonnegative integer")


@dataclass(frozen=True)
class RoomBlackCount:
    """Each fixed room has exactly count black cells; count=0 is allowed."""

    ui: ClassVar[RuleUi] = RuleUi("room-black-count", "各部屋の黒数を固定",
        "共有する部屋配置の各部屋に同数の黒を置きます。黒同士のつながりは別ルールです。",
        (ROOM_PARAMETER, UiParameter("count", "各部屋の黒マス数", "integer", 2)), ROOM_UI)
    rooms: RoomMap
    count: int = 2

    def __post_init__(self) -> None:
        _count(self.count)
        object.__setattr__(self, "rooms", room_map(self.rooms))

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        if self.count > len(board.cells):
            raise ValueError("Black count cannot exceed the board area")
        for cells in _rooms(board, self.rooms):
            puzzle.add(sum_expr(black[c] for c in cells) == self.count)


@dataclass(frozen=True)
class RoomConnectedBlack:
    """Black cells connect inside each fixed room, without leaving the room."""

    ui: ClassVar[RuleUi] = RuleUi("room-connected-black", "各部屋内で黒をつなぐ",
        "各部屋の黒が、その部屋の内側だけを通ってつながります。部屋をまたぐ接触は許します。",
        (ROOM_PARAMETER, UiParameter("nonempty", "各部屋に黒を1つ以上置く", "boolean", True)), ROOM_UI)
    rooms: RoomMap
    nonempty: bool = True

    def __post_init__(self) -> None:
        if type(self.nonempty) is not bool:
            raise ValueError("nonempty must be a boolean")
        object.__setattr__(self, "rooms", room_map(self.rooms))

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        for cells in _rooms(board, self.rooms):
            puzzle.add(connected(cells, lambda c: black[c]))
            if self.nonempty:
                puzzle.add(at_least_one(black[c] for c in cells))


@dataclass(frozen=True)
class LineBlackCount:
    """Each row and each column has count black cells, independently of hints."""

    ui: ClassVar[RuleUi] = RuleUi("line-black-count", "各行・列の黒数を固定",
        "各行と各列に同じ個数の黒を置きます。個数が正なら正方形以外は矛盾します。",
        (UiParameter("count", "各行・列の黒マス数", "integer", 1),))
    count: int = 1

    def __post_init__(self) -> None:
        _count(self.count)

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        if self.count > len(board.cells):
            raise ValueError("Black count cannot exceed the board area")
        for cells in board.rows() + board.cols():
            puzzle.add(sum_expr(black[c] for c in cells) == self.count)
