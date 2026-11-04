"""Color-neutral area clues for the component containing the clue cell."""

from dataclasses import dataclass
from typing import ClassVar

from puzzle import Puzzle, SquareGrid, VarMap, one_of, sum_expr
from puzzle_defs.number_layout import NumberGrid, number_grid
from puzzle_defs.regions import enumerate_connected_regions
from puzzle_defs.ui import RuleUi, UiChannel, UiParameter, UiRequirements

MAX_COMPONENT_AREA_CELLS = 9
DEFAULT_COMPONENT_AREAS: NumberGrid = ((1,0,0),(0,0,4))


@dataclass(frozen=True)
class ComponentAreaClues:
    """Positive clues fix their own same-color component's area, not its color.

    Zero is absent. Repeated clues in a component and unnumbered components
    are allowed. Bounded enumeration is limited to nine whole-board cells.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "component-area-clues", "数字セルが属する成分の面積を固定",
        "数字を含む同色の上下左右の成分を、そのマス数にします。数字セルは黒にも白にもできます。0は数字なし。9セル以下の実験的な部品です。",
        (UiParameter("component_areas", "所属する成分の面積（0は数字なし）", "number-grid", DEFAULT_COMPONENT_AREAS),),
        UiRequirements(channels=(UiChannel("answer","binary-cells"),UiChannel("component-areas","cell-component-areas"))),
    )
    component_areas: NumberGrid

    def __post_init__(self) -> None:
        grid = number_grid(self.component_areas)
        if len(grid)*len(grid[0]) > MAX_COMPONENT_AREA_CELLS:
            raise ValueError(f"Component area clues support at most {MAX_COMPONENT_AREA_CELLS} board cells")
        object.__setattr__(self,"component_areas",grid)

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        number_grid(self.component_areas,rows=len(board.rows()),cols=len(board.cols()))
        if len(board.cells) > MAX_COMPONENT_AREA_CELLS:
            raise ValueError(f"Component area clues support at most {MAX_COMPONENT_AREA_CELLS} board cells")
        for origin in board.cells:
            area = self.component_areas[origin.row][origin.col]
            if not area:
                continue
            allowed = []
            regions = sorted((r for r in enumerate_connected_regions(board,area) if origin in r.cells),
                             key=lambda r:tuple(sorted(r.cells)))
            for region in regions:
                boundary = {n for c in region.cells for n in board.neighbors(c)}-region.cells
                for color in (False,True):
                    mismatch = [~black[c] if color else black[c] for c in sorted(region.cells)]
                    mismatch += [black[c] if color else ~black[c] for c in sorted(boundary)]
                    allowed.append(sum_expr(mismatch) == 0)
            # The origin belongs to exactly one maximal same-color component,
            # so these candidate/color predicates are mutually exclusive.
            puzzle.add(one_of(*allowed))
