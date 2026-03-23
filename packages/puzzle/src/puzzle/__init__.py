from puzzle.constraints import (
    AllDifferentConstraint,
    CompoundConstraint,
    ConnectedConstraint,
    NoBoundaryCrossConstraint,
    OneOfConstraint,
    ShapeAcrossConstraint,
    SingleCycleConstraint,
    UniqueConstraint,
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
from puzzle.match import MatchVarMap
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
    | NoBoundaryCrossConstraint
    | CompoundConstraint
)

__all__ = [
    "AllDifferentConstraint",
    "BoolExpr",
    "BoolVarMap",
    "Cell",
    "CompoundConstraint",
    "ConnectedConstraint",
    "Constraint",
    "Edge",
    "Expr",
    "LinearConstraint",
    "MatchVarMap",
    "MissingFeatureError",
    "NoBoundaryCrossConstraint",
    "OneOfConstraint",
    "Puzzle",
    "ShapeAcrossConstraint",
    "SingleCycleConstraint",
    "Solution",
    "SquareGrid",
    "UniqueConstraint",
    "Var",
    "VarGrid",
    "VarMap",
    "Vertex",
    "all_different",
    "at_least_one",
    "at_most_one",
    "connected",
    "count_eq",
    "exactly_one",
    "non_touching",
    "one_of",
    "single_cycle",
    "square_grid",
    "sum_expr",
    "unique",
]
