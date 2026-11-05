"""No isolated orthogonal components: each must join another at a corner."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Cell, Puzzle, SquareGrid, VarMap, sum_expr
from puzzle_defs.puzzles.component_shapes import _check_color
from puzzle_defs.ui import RuleUi, UiParameter, UiRequirements

MAX_CORNER_LINK_CELLS = 100


@dataclass(frozen=True)
class CornerLinkedComponents:
    """Every chosen-color orthogonal component touches another diagonally.

    Empty color sets and multiple chains are allowed. Diagonal contacts inside
    the same orthogonal component do not count. Board limit: 100 cells;
    finite diagnostics remain limited to nine.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "corner-linked-components", "各成分を別の成分と角でつなぐ",
        "対象色の各上下左右の成分を、別成分と角で接触させます。成分内部の角接触は数えません。複数チェーン・対象色0個は許し、形の一致は検査しません。",
        (UiParameter("black", "角でつなぐ色は黒（オフなら白）", "boolean", True),),
        requirements=UiRequirements(max_cells=100),
    )
    black: bool = True

    def __post_init__(self) -> None:
        _check_color(self.black)

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        if len(board.cells) > MAX_CORNER_LINK_CELLS:
            raise ValueError(f"Corner-linked components support at most {MAX_CORNER_LINK_CELLS} board cells")
        cells = list(board.cells)
        cell_set = set(cells)
        n = len(cells)
        selected = {c:black[c] if self.black else ~black[c] for c in board.cells}
        opposite = {c:~black[c] if self.black else black[c] for c in board.cells}
        labels = puzzle.int_var_map("corner_component_label", cells, 0, n)
        depth = puzzle.int_var_map("corner_component_depth", cells, 0, n-1)
        witness_depth = puzzle.int_var_map("corner_witness_depth", cells, 0, n-1)
        edges = [(c, other) for c in cells for other in board.neighbors(c)]
        parents = puzzle.bool_var_map("corner_component_parent", edges)
        witness_parents = puzzle.bool_var_map("corner_witness_parent", edges)
        diagonal = {c: [d for dr in (-1, 1) for dc in (-1, 1)
                        if (d := Cell(c.row+dr, c.col+dc)) in cell_set] for c in cells}
        contacts = puzzle.bool_var_map("corner_external_contact", [(c,d) for c in cells for d in diagonal[c]])

        for index, cell in enumerate(cells, 1):
            root = labels[cell] == index
            puzzle.add(sum_expr([selected[cell], labels[cell] == 0]) == 1)
            puzzle.add(labels[cell] <= index)
            # Each selected cell either is its component's canonical root or
            # has a selected orthogonal parent with smaller depth. Adjacent
            # selected cells share a label, so labels identify exactly the
            # maximal orthogonal components, even with internal corner contact.
            puzzle.add(sum_expr([opposite[cell], root]
                               + [parents[cell, other] for other in board.neighbors(cell)]) == 1)
            for other in board.neighbors(cell):
                parent = parents[cell, other]
                witness_parent = witness_parents[cell, other]
                puzzle.add(sum_expr([~parent, selected[other]]) >= 1)
                puzzle.add(sum_expr([depth[cell]] + [~parent]*n) > depth[other])
                puzzle.add(sum_expr([opposite[cell], opposite[other], labels[cell] == labels[other]]) >= 1)
                # A second decreasing forest leads every selected cell to a
                # genuine cross-component corner contact in its own component.
                puzzle.add(sum_expr([~witness_parent, selected[cell]]) >= 1)
                puzzle.add(sum_expr([~witness_parent, selected[other]]) >= 1)
                puzzle.add(sum_expr([witness_depth[cell]] + [~witness_parent]*n) > witness_depth[other])
            for other in diagonal[cell]:
                contact = contacts[cell, other]
                puzzle.add(sum_expr([~contact, selected[cell]]) >= 1)
                puzzle.add(sum_expr([~contact, selected[other]]) >= 1)
                puzzle.add(sum_expr([~contact, labels[cell] != labels[other]]) >= 1)
            puzzle.add(sum_expr([opposite[cell]] + [contacts[cell, other] for other in diagonal[cell]]
                               + [witness_parents[cell, other] for other in board.neighbors(cell)]) >= 1)
