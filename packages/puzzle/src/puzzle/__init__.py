from puzzle.constraints import (
    AllDifferentConstraint,
    ConnectedConstraint,
    OneOfConstraint,
    SingleCycleConstraint,
    UniqueConstraint,
    all_different,
    connected,
    count_eq,
    exactly_one,
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
    all_adjacent_different_shape,
    different_shape_across,
    enumerate_placements,
    polyomino,
    same_shape_across,
)
from puzzle.puzzle import Puzzle, Solution

Constraint = (
    AllDifferentConstraint
    | BoolExpr
    | LinearConstraint
    | UniqueConstraint
    | OneOfConstraint
    | SingleCycleConstraint
    | ConnectedConstraint
    | ShapeAcrossConstraint
)

__all__ = [
    "AllDifferentConstraint",
    "BoolExpr",
    "BoolVarMap",
    "Cell",
    "ConnectedConstraint",
    "Constraint",
    "Edge",
    "Expr",
    "LinearConstraint",
    "MissingFeatureError",
    "OneOfConstraint",
    "Placement",
    "Polyomino",
    "Puzzle",
    "SingleCycleConstraint",
    "Solution",
    "SquareGrid",
    "UniqueConstraint",
    "Var",
    "VarGrid",
    "VarMap",
    "Vertex",
    "ShapeAcrossConstraint",
    "all_adjacent_different_shape",
    "all_different",
    "different_shape_across",
    "connected",
    "count_eq",
    "enumerate_placements",
    "exactly_one",
    "one_of",
    "polyomino",
    "same_shape_across",
    "single_cycle",
    "square_grid",
    "sum_expr",
    "unique",
]
