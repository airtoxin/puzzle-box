"""Bounded room-local component count and size equality, from Nuritwin."""

from collections.abc import Iterator
from dataclasses import dataclass, replace
from typing import ClassVar

from puzzle import Cell, Puzzle, SquareGrid, VarMap, sum_expr
from puzzle_defs.puzzles.component_shapes import _check_color
from puzzle_defs.puzzles.room_fragments import ROOM_PARAMETER, ROOM_UI, _count, _rooms
from puzzle_defs.regions import Region, enumerate_connected_regions
from puzzle_defs.room_layout import RoomMap, room_map
from puzzle_defs.ui import RuleUi, UiParameter

MAX_ROOM_COMPONENT_CELLS = 9


def _bounded_rooms(rooms: RoomMap) -> RoomMap:
    layout = room_map(rooms)
    if len(layout)*len(layout[0]) > MAX_ROOM_COMPONENT_CELLS:
        raise ValueError(f"Room components support at most {MAX_ROOM_COMPONENT_CELLS} board cells")
    return layout


def _component_uses(puzzle: Puzzle, board: SquareGrid, black: VarMap, rooms: RoomMap,
                    color: bool) -> Iterator[tuple[list[Cell], list[Region], VarMap]]:
    if len(board.cells) > MAX_ROOM_COMPONENT_CELLS:
        raise ValueError(f"Room components support at most {MAX_ROOM_COMPONENT_CELLS} board cells")
    selected = {c:black[c] if color else ~black[c] for c in board.cells}
    for members in _rooms(board, rooms):
        target = set(members)
        regions = sorted((region for size in range(1,len(members)+1)
                          for region in enumerate_connected_regions(board,size,target)),
                         key=lambda region:tuple(sorted(region.cells)))
        uses = puzzle.bool_var_map("room_component", regions)
        for cell in members:
            puzzle.add(sum_expr(uses[r] for r in regions if cell in r.cells) == selected[cell])
        for region in regions:
            # Only same-room neighbors are forbidden. The full color can join
            # two local components through another room, as Nuritwin requires.
            boundary = ({n for c in region.cells for n in board.neighbors(c)} & target)-region.cells
            for cell in sorted(boundary):
                puzzle.add(sum_expr([uses[region],selected[cell]]) <= 1)
        # Exact cover + maximality makes active regions precisely the induced
        # components, without splitting, overlapping or merging disconnected sets.
        yield members,regions,uses


@dataclass(frozen=True)
class RoomComponentCount:
    """Each fixed room contains exactly count selected-color components."""

    ui: ClassVar[RuleUi] = RuleUi(
        "room-component-count", "各部屋の対象色の成分数を固定",
        "部屋内だけを通る上下左右の連結成分を数えます。0は対象色なし。部屋外を通ってつながっていても別成分です。9セル以下の実験的な部品です。",
        (ROOM_PARAMETER, UiParameter("count", "各部屋の対象色の成分数", "integer", 2),
         UiParameter("black", "成分を数える色は黒（オフなら白）", "boolean", True)), replace(ROOM_UI, max_cells=9),
    )
    rooms: RoomMap
    count: int = 2
    black: bool = True

    def __post_init__(self) -> None:
        _count(self.count)
        _check_color(self.black)
        object.__setattr__(self, "rooms", _bounded_rooms(self.rooms))
        if self.count > len(self.rooms)*len(self.rooms[0]):
            raise ValueError("Component count cannot exceed the board area")

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        if self.count > len(board.cells):
            raise ValueError("Component count cannot exceed the board area")
        for _,regions,uses in _component_uses(puzzle,board,black,self.rooms,self.black):
            puzzle.add(sum_expr(uses[r] for r in regions) == self.count)


@dataclass(frozen=True)
class EqualRoomComponentSizes:
    """All selected-color components in each room have the same area.

    Empty/single-component rooms pass. Areas can differ between rooms, and
    connectivity outside a room does not merge its local components.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "equal-room-component-sizes", "成分の大きさを部屋ごとにそろえる",
        "各部屋内の対象色の成分を同じマス数にします。0個・1個は許し、部屋ごとに大きさは変えられます。形の一致は不要。9セル以下の実験的な部品です。",
        (ROOM_PARAMETER, UiParameter("black", "サイズをそろえる色は黒（オフなら白）", "boolean", True)), replace(ROOM_UI, max_cells=9),
    )
    rooms: RoomMap
    black: bool = True

    def __post_init__(self) -> None:
        _check_color(self.black)
        object.__setattr__(self, "rooms", _bounded_rooms(self.rooms))

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        for members,regions,uses in _component_uses(puzzle,board,black,self.rooms,self.black):
            n = len(members)
            size = puzzle.int_var_map("room_component_size",[members[0]],1,n)[members[0]]
            for region in regions:
                # Active -> equality. Inactive bounds are vacuous for 1<=size<=n.
                puzzle.add(sum_expr([size]+[~uses[region]]*n) >= len(region.cells))
                puzzle.add(sum_expr([size]+[uses[region]]*n) <= len(region.cells)+n)
