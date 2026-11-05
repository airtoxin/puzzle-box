"""Conditional shape-contact rules, separate from room piece-size constraints."""

from dataclasses import dataclass, replace
from typing import ClassVar

from puzzle import Cell, Puzzle, SquareGrid, VarMap, non_touching, sum_expr
from puzzle_defs.polyomino import Placement, different_shape_across, polyomino
from puzzle_defs.regions import enumerate_connected_regions
from puzzle_defs.room_layout import RoomMap, room_map
from puzzle_defs.puzzles.room_fragments import ROOM_PARAMETER, ROOM_UI, _rooms
from puzzle_defs.ui import RuleUi


@dataclass(frozen=True)
class NoTouchingEqualTetrominoes:
    """Equal room-local tetrominoes cannot share edges, including reflection.

    Only a room whose complete black set is connected and has four cells is
    a tetromino. Other masks are unrestricted by this fragment, not rejected.
    RoomBlackCount(4) and RoomConnectedBlack provide those separate conditions.
    """

    ui: ClassVar[RuleUi] = RuleUi("no-touching-equal-tetrominoes", "同形テトロミノの部屋間接触を禁止",
        "各部屋の黒が連結4マスのとき、回転・反転して同じ形同士の辺接触を禁止します。黒数・部屋内連結は別ルールです。",
        (ROOM_PARAMETER,), replace(ROOM_UI, max_cells=25))
    rooms: RoomMap

    def __post_init__(self) -> None:
        object.__setattr__(self, "rooms", room_map(self.rooms))

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        if len(board.cells) > 25:
            raise ValueError("Tetromino contacts support at most 25 board cells")
        groups = _rooms(board, self.rooms)
        placements: list[Placement] = []
        members_by_placement: dict[Placement, list[Cell]] = {}
        for members in groups:
            regions = enumerate_connected_regions(board, 4, set(members))
            for region in sorted(regions, key=lambda r: tuple(sorted(r.cells))):
                variants = polyomino(
                    "shape", [(c.row, c.col) for c in region.cells], allow_reflect=True,
                ).variants
                placement = Placement(str(min(variants)), region.cells)
                placements.append(placement)
                members_by_placement[placement] = members
        active = puzzle.bool_var_map("room_tetromino", placements)
        for placement in placements:
            members = members_by_placement[placement]
            mismatch = sum_expr(
                [~black[c] for c in sorted(placement.cells)]
                + [black[c] for c in members if c not in placement.cells]
            )
            # Exact equivalence, not just candidate -> matching black cells.
            # Inactive requires a mismatch; active requires the complete mask.
            puzzle.add(sum_expr([mismatch, active[placement]]) >= 1)
            puzzle.add(sum_expr([mismatch] + [active[placement]] * len(members)) <= len(members))
        cells = set(board.cells)
        for edge in board.edges:
            a, b = board.cells_sharing_edge(edge)
            if a in cells and b in cells and self.rooms[a.row][a.col] != self.rooms[b.row][b.col]:
                pairs = different_shape_across(edge, active, placements, board).forbidden_pairs
                # These are conditional black pieces, not a full-board tiling.
                # Reuse geometric pair detection with the generic key constraint;
                # do not advertise region_partition/shape_class capabilities.
                puzzle.add(non_touching(active, pairs))
