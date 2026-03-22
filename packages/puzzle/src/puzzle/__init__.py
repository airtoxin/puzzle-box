from puzzle.constraints import (
    AllDifferentConstraint,
    ConnectedConstraint,
    OneOfConstraint,
    SingleCycleConstraint,
    UniqueConstraint,
    CompoundConstraint,
    all_different,
    at_least_one,
    at_most_one,
    connected,
    count_eq,
    exactly_one,
    non_touching,
    one_of,
    single_cycle,
    unique,
)
from puzzle.expr import BoolExpr, BoolVarMap, Expr, LinearConstraint, Var, VarGrid, VarMap, sum_expr
from puzzle.features import MissingFeatureError
from puzzle.grid import Cell, Edge, SquareGrid, Vertex, square_grid
from puzzle.polyomino import (
    Placement,
    Polyomino,
    ShapeAcrossConstraint,
    NoBoundaryCrossConstraint,
    all_adjacent_different_shape,
    different_shape_across,
    enumerate_placements,
    no_boundary_cross,
    polyomino,
    same_shape_across,
)
from puzzle.match import MatchVarMap
from puzzle.puzzle import Puzzle, Solution
from puzzle.regions import (
    Region,
    enumerate_connected_regions,
    enumerate_rectangles,
    filter_number_equals_area,
    filter_one_number_per_region,
    filter_same_number_combination,
)
from puzzle.shikaku import ShikakuRect, enumerate_shikaku_rectangles

Constraint = (
    AllDifferentConstraint
    | BoolExpr
    | LinearConstraint
    | UniqueConstraint
    | OneOfConstraint
    | SingleCycleConstraint
    | ConnectedConstraint
    | ShapeAcrossConstraint
    | NoBoundaryCrossConstraint
)

__all__ = [
    "AllDifferentConstraint",
    "BoolExpr",
    "BoolVarMap",
    "Cell",
    "ConnectedConstraint",
    "CompoundConstraint",
    "Constraint",
    "Edge",
    "Expr",
    "LinearConstraint",
    "MatchVarMap",
    "MissingFeatureError",
    "OneOfConstraint",
    "Placement",
    "Polyomino",
    "Puzzle",
    "Region",
    "SingleCycleConstraint",
    "Solution",
    "SquareGrid",
    "UniqueConstraint",
    "Var",
    "VarGrid",
    "VarMap",
    "Vertex",
    "NoBoundaryCrossConstraint",
    "ShapeAcrossConstraint",
    "ShikakuRect",
    "all_adjacent_different_shape",
    "all_different",
    "at_least_one",
    "at_most_one",
    "different_shape_across",
    "connected",
    "count_eq",
    "enumerate_connected_regions",
    "enumerate_placements",
    "enumerate_rectangles",
    "no_boundary_cross",
    "enumerate_shikaku_rectangles",
    "exactly_one",
    "non_touching",
    "filter_number_equals_area",
    "filter_one_number_per_region",
    "filter_same_number_combination",
    "one_of",
    "polyomino",
    "same_shape_across",
    "single_cycle",
    "square_grid",
    "sum_expr",
    "unique",
]
