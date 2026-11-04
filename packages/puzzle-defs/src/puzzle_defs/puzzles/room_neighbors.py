"""Independent room-contact and room-count conditions from Shimaguni."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Puzzle, SquareGrid, VarMap, sum_expr
from puzzle_defs.puzzles.component_shapes import _check_color
from puzzle_defs.puzzles.room_fragments import ROOM_PARAMETER, ROOM_UI, _rooms
from puzzle_defs.room_layout import RoomMap, room_map
from puzzle_defs.ui import RuleUi, UiParameter


@dataclass(frozen=True)
class NoColorAcrossRooms:
    """Selected-color cells cannot share an edge across a fixed room border.

    Same-room adjacency and corner contact are allowed; emptiness is allowed.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "no-color-across-rooms", "異なる部屋の対象色を辺で接触させない",
        "部屋境界を挟む2マスを両方対象色にしません。部屋内の接触・角だけの接触・対象色0個は許します。",
        (ROOM_PARAMETER, UiParameter("black", "境界越しの接触を禁止する色は黒（オフなら白）", "boolean", True)), ROOM_UI,
    )
    rooms: RoomMap
    black: bool = True

    def __post_init__(self) -> None:
        _check_color(self.black)
        object.__setattr__(self, "rooms", room_map(self.rooms))

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        room_map(self.rooms, rows=len(board.rows()), cols=len(board.cols()))
        for a,b in board.adjacent_cell_pairs():
            if self.rooms[a.row][a.col] != self.rooms[b.row][b.col]:
                selected = [black[c] if self.black else ~black[c] for c in (a,b)]
                puzzle.add(sum_expr(selected) <= 1)


@dataclass(frozen=True)
class AdjacentRoomCountsDiffer:
    """Edge-neighbor rooms have different total selected-color cell counts.

    Counts include zero and all cells of each room, not only its boundary.
    Non-neighbor rooms may have equal counts; no connectivity is implied.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "adjacent-room-counts-differ", "辺で隣り合う部屋の対象色の個数を変える",
        "辺を共有する部屋ごとに、部屋全体の対象色の個数を異ならせます。0も数え、角だけの隣接は比較しません。連結は別条件です。",
        (ROOM_PARAMETER, UiParameter("black", "部屋ごとの個数を比べる色は黒（オフなら白）", "boolean", True)), ROOM_UI,
    )
    rooms: RoomMap
    black: bool = True

    def __post_init__(self) -> None:
        _check_color(self.black)
        object.__setattr__(self, "rooms", room_map(self.rooms))

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        counts = {self.rooms[cells[0].row][cells[0].col]:
                  sum_expr(black[c] if self.black else ~black[c] for c in cells)
                  for cells in _rooms(board, self.rooms)}
        neighbors = set()
        for a,b in board.adjacent_cell_pairs():
            x,y = self.rooms[a.row][a.col],self.rooms[b.row][b.col]
            if x != y:
                neighbors.add((min(x,y),max(x,y)))
        for a,b in neighbors:
            puzzle.add(counts[a] != counts[b])
