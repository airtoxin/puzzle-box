"""Fixed-size color components using labels and a descending spanning forest."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Puzzle, SquareGrid, VarMap, sum_expr
from puzzle_defs.ui import RuleUi, UiParameter

MAX_COMPONENT_CELLS = 100


@dataclass(frozen=True)
class ColorComponentSize:
    """Every orthogonal component of one color has exactly size cells.

    Empty selected-color sets are allowed. Component labels and parent edges
    are internal witnesses; the answer remains the black/white cells only.
    """

    ui: ClassVar[RuleUi] = RuleUi("color-component-size", "同色の連結成分のサイズを固定",
        "対象色の各連結成分を指定マス数にします。上下左右の接触だけを数え、対象色0個も許します。最大100セルです。",
        (UiParameter("size", "各連結成分のマス数", "integer", 3, minimum=1),
         UiParameter("black", "黒を対象にする（オフなら白）", "boolean", True)))
    size: int
    black: bool = True

    def __post_init__(self) -> None:
        if type(self.size) is not int or self.size < 1:
            raise ValueError("Component size must be a positive integer")
        if type(self.black) is not bool:
            raise ValueError("black must be a boolean")

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        if len(board.cells) > MAX_COMPONENT_CELLS:
            raise ValueError(f"Fixed component sizes support at most {MAX_COMPONENT_CELLS} board cells")
        if self.size > len(board.cells):
            raise ValueError("Component size cannot exceed the board area")
        cells = list(board.cells)
        labels = puzzle.int_var_map("component_label", cells, 0, len(cells))
        depth = puzzle.int_var_map("component_depth", cells, 0, len(cells)-1)
        parents = puzzle.bool_var_map("component_parent", [(c,n) for c in cells for n in board.neighbors(c)])
        selected = {c:black[c] if self.black else ~black[c] for c in board.cells}
        opposite = {c:~black[c] if self.black else black[c] for c in board.cells}
        for index, cell in enumerate(cells, 1):
            root = labels[cell] == index
            puzzle.add(sum_expr([selected[cell], labels[cell] == 0]) == 1)
            # Canonical root: the first cell of this component. This removes
            # label symmetry without excluding any visible assignment.
            puzzle.add(labels[cell] <= index)
            puzzle.add(sum_expr([opposite[cell], root]
                               + [parents[cell,n] for n in board.neighbors(cell)]) == 1)
            for neighbor in board.neighbors(cell):
                parent = parents[cell,neighbor]
                puzzle.add(sum_expr([~parent, selected[neighbor]]) >= 1)
                puzzle.add(sum_expr([depth[cell]] + [~parent]*len(cells)) > depth[neighbor])
                # Adjacent selected cells cannot split into different labels.
                puzzle.add(sum_expr([opposite[cell], opposite[neighbor],
                                     labels[cell] == labels[neighbor]]) >= 1)
            # Descending parent paths must terminate at their label's root,
            # so disconnected regions cannot share a label. Count that region.
            puzzle.add(sum_expr(labels[c] == index for c in cells) == sum_expr([root]*self.size))
