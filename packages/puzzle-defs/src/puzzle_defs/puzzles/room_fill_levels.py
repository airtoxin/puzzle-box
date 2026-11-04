"""Aquarium's bottom-up, horizontally level fill inside each fixed room."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Cell, Puzzle, SquareGrid, VarMap
from puzzle_defs.puzzles.component_shapes import _check_color
from puzzle_defs.puzzles.room_fragments import ROOM_PARAMETER, ROOM_UI, _rooms
from puzzle_defs.room_layout import RoomMap, room_map
from puzzle_defs.ui import RuleUi, UiParameter


@dataclass(frozen=True)
class RoomFillLevels:
    """Each room selects a bottom suffix of whole rows, possibly empty/full.

    Separate horizontal segments of one room at the same height share a level.
    There is no flow, connectivity or nonempty requirement between rooms.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "room-fill-levels", "部屋の対象色を下から水平に満たす",
        "対象色を水として部屋内の各行をそろえ、その下の部屋内の全マスも対象色にします。空・満杯可。行列ヒントは常に黒数です。",
        (ROOM_PARAMETER, UiParameter("black", "水に対応する色は黒（オフなら白）", "boolean", True)), ROOM_UI,
    )
    rooms: RoomMap
    black: bool = True

    def __post_init__(self) -> None:
        _check_color(self.black)
        object.__setattr__(self, "rooms", room_map(self.rooms))

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        for members in _rooms(board, self.rooms):
            by_row: dict[int, list[Cell]] = {}
            for cell in members:
                by_row.setdefault(cell.row, []).append(cell)
            levels = [by_row[r] for r in sorted(by_row)]
            for cells in levels:
                for cell in cells[1:]:
                    puzzle.add(black[cell] == black[cells[0]])
            for upper, lower in zip(levels, levels[1:]):
                if self.black:
                    puzzle.add(black[upper[0]] <= black[lower[0]])
                else:
                    puzzle.add(black[upper[0]] >= black[lower[0]])
