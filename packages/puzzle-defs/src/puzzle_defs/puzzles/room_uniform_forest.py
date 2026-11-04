"""Room equality and color forests, independent pieces of Nurimeizu rules."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Puzzle, SquareGrid, VarMap, sum_expr
from puzzle_defs.puzzles.component_shapes import _check_color
from puzzle_defs.puzzles.room_fragments import ROOM_PARAMETER, ROOM_UI, _rooms
from puzzle_defs.room_layout import RoomMap, room_map
from puzzle_defs.ui import RuleUi, UiParameter


@dataclass(frozen=True)
class UniformRooms:
    """Every fixed room is all black or all white; either color is allowed."""

    ui: ClassVar[RuleUi] = RuleUi(
        "uniform-rooms", "部屋内を同じ色にする",
        "各部屋をすべて黒かすべて白にします。部屋同士の色や連結は別条件です。",
        (ROOM_PARAMETER,), ROOM_UI,
    )
    rooms: RoomMap

    def __post_init__(self) -> None:
        object.__setattr__(self, "rooms", room_map(self.rooms))

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        for members in _rooms(board, self.rooms):
            for cell in members[1:]:
                puzzle.add(black[cell] == black[members[0]])


@dataclass(frozen=True)
class AcyclicColor:
    """The induced orthogonal graph of one color is a forest, possibly empty.

    Every touching pair is an edge: this does not select a spanning tree while
    ignoring other adjacencies. Branches and disconnected trees are allowed.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "acyclic-color", "同色マスの輪を禁止",
        "対象色の上下左右の接触で輪ができないようにします。枝分かれ・複数成分・対象色0個は許します。連結は別条件です。",
        (UiParameter("black", "輪を禁止する色は黒（オフなら白）", "boolean", False),),
    )
    black: bool = False

    def __post_init__(self) -> None:
        _check_color(self.black)

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        cells = board.cells
        edges = [(a, b) for a in cells for b in board.neighbors(a) if a < b]
        arcs = [(source, target) for a, b in edges for source, target in ((a, b), (b, a))]
        directions = puzzle.bool_var_map("forest_direction", arcs)
        rank = puzzle.int_var_map("forest_rank", cells, 0, len(cells)-1)
        selected = {c: black[c] if self.black else ~black[c] for c in cells}
        opposite = {c: ~black[c] if self.black else black[c] for c in cells}
        for a, b in edges:
            oriented = sum_expr([directions[a, b], directions[b, a]])
            puzzle.add(oriented <= selected[a])
            puzzle.add(oriented <= selected[b])
            # Exactly one direction iff both endpoints have the selected color.
            puzzle.add(sum_expr([directions[a, b], directions[b, a], opposite[a], opposite[b]]) >= 1)
        for cell in cells:
            puzzle.add(sum_expr(directions[n, cell] for n in board.neighbors(cell)) <= 1)
        for a, b in arcs:
            # Active arcs strictly increase rank; inactive arcs impose no bound.
            puzzle.add(sum_expr([rank[b]] + [~directions[a, b]] * len(cells)) > rank[a])
        # A forest can be oriented away from arbitrary roots. Conversely, an
        # undirected cycle with indegree <= 1 forces a directed cycle, which
        # strict ranks forbid. Witnesses never replace the visible cell answer.
