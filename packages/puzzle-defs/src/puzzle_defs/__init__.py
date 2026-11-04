from puzzle_defs.polyomino import (
    Placement,
    Polyomino,
    all_adjacent_different_shape,
    different_shape_across,
    enumerate_placements,
    no_boundary_cross,
    polyomino,
    same_shape_across,
)
from puzzle_defs.puzzles import (
    HitoriPuzzle,
    NurikabePuzzle,
    ShikakuPuzzle,
    SlitherlinkPuzzle,
    SudokuPuzzle,
    TentsPuzzle,
    TilingPuzzle,
    YajilinPuzzle,
)
from puzzle_defs.puzzles.slitherlink_recipe import CellEdgeCountClue, EdgeStateClue, SlitherlinkRecipe
from puzzle_defs.puzzles.yajilin_recipe import ArrowCountClue, ArrowSite, BlackCellClue, YajilinAnswer, YajilinRecipe
from puzzle_defs.regions import (
    Region,
    enumerate_connected_regions,
    enumerate_rectangles,
    filter_number_equals_area,
    filter_one_number_per_region,
    filter_same_number_combination,
)
from puzzle_defs.shikaku import ShikakuRect, enumerate_shikaku_rectangles
from puzzle_defs.puzzles.shading import (
    BlackCount, ConnectedWhite, NonTouchingBlack, NoWhite2x2,
    ColumnCountClue, RowCountClue, ShadingPuzzle, ShadingRecipe, ShadingRule,
)
from puzzle_defs.puzzles.shading_fragments import (
    BalancedLines, BlackDominoes, ConnectedBlack, DistinctLines, NoBlack2x2, NoThreeConsecutive, RunLengthLimit,
)
from puzzle_defs.puzzles.room_fragments import RoomBlackCount, RoomConnectedBlack, LineBlackCount, NoWhiteAcrossThreeRooms, RoomRotationalSymmetry
from puzzle_defs.puzzles.component_shapes import RectangularComponents, NonRectangularComponents
from puzzle_defs.puzzles.number_fragments import DistinctWhiteNumbers
from puzzle_defs.puzzles.component_size import ColorComponentSize
from puzzle_defs.puzzles.room_shapes import NoTouchingEqualTetrominoes
from puzzle_defs.puzzles.white_visibility import WhiteVisibilityCounts
from puzzle_defs.puzzles.component_border import ComponentsTouchBorder
from puzzle_defs.puzzles.white_island_areas import WhiteIslandAreas, WhiteAreaClues
from puzzle_defs.puzzles.adjacent_black_counts import AdjacentBlackCounts
from puzzle_defs.puzzles.cell_path_fragments import ColorDegreeRange, ColorEndpointCount
from puzzle_defs.puzzles.adjacent_black_component_sum import AdjacentBlackComponentSum
from puzzle_defs.puzzles.room_uniform_forest import UniformRooms, AcyclicColor
from puzzle_defs.puzzles.corner_connected_color import CornerConnectedColor
from puzzle_defs.puzzles.white_endpoint_markers import WhiteEndpointMarkers

__all__ = [
    "WhiteEndpointMarkers",
    "WhiteAreaClues",
    "CornerConnectedColor",
    "UniformRooms",
    "AcyclicColor",
    "AdjacentBlackComponentSum",
    "ColorDegreeRange",
    "ColorEndpointCount",
    "AdjacentBlackCounts",
    "WhiteIslandAreas",
    "ComponentsTouchBorder",
    "WhiteVisibilityCounts",
    "NoTouchingEqualTetrominoes",
    "ColorComponentSize",
    "RoomRotationalSymmetry",
    "RunLengthLimit",
    "DistinctWhiteNumbers",
    "NoWhiteAcrossThreeRooms",
    "RectangularComponents",
    "NonRectangularComponents",
    "RoomBlackCount",
    "RoomConnectedBlack",
    "LineBlackCount",
    "BalancedLines",
    "BlackDominoes",
    "ConnectedBlack",
    "DistinctLines",
    "NoBlack2x2",
    "NoThreeConsecutive",
    "BlackCount",
    "ConnectedWhite",
    "NonTouchingBlack",
    "NoWhite2x2",
    "ColumnCountClue",
    "RowCountClue",
    "ShadingPuzzle",
    "ShadingRecipe",
    "ShadingRule",
    "HitoriPuzzle",
    "NurikabePuzzle",
    "Placement",
    "Polyomino",
    "Region",
    "ShikakuPuzzle",
    "ShikakuRect",
    "SlitherlinkPuzzle",
    "SlitherlinkRecipe",
    "CellEdgeCountClue",
    "EdgeStateClue",
    "SudokuPuzzle",
    "TentsPuzzle",
    "TilingPuzzle",
    "YajilinPuzzle",
    "YajilinRecipe",
    "YajilinAnswer",
    "ArrowSite",
    "ArrowCountClue",
    "BlackCellClue",
    "all_adjacent_different_shape",
    "different_shape_across",
    "enumerate_connected_regions",
    "enumerate_placements",
    "enumerate_rectangles",
    "enumerate_shikaku_rectangles",
    "filter_number_equals_area",
    "filter_one_number_per_region",
    "filter_same_number_combination",
    "no_boundary_cross",
    "polyomino",
    "same_shape_across",
]
