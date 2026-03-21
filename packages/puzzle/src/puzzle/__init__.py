from puzzle.constraints import (
    AllDifferentConstraint,
    ConnectedConstraint,
    OneOfConstraint,
    SingleCycleConstraint,
    UniqueConstraint,
    all_different,
    connected,
    count_eq,
    one_of,
    single_cycle,
    unique,
)
from puzzle.expr import BoolExpr, BoolVarMap, Expr, LinearConstraint, Var, VarGrid, VarMap, sum_expr
from puzzle.grid import Cell, Edge, SquareGrid, Vertex, square_grid
from puzzle.puzzle import Puzzle, Solution

Constraint = (
    AllDifferentConstraint
    | BoolExpr
    | LinearConstraint
    | UniqueConstraint
    | OneOfConstraint
    | SingleCycleConstraint
    | ConnectedConstraint
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
    "OneOfConstraint",
    "Puzzle",
    "SingleCycleConstraint",
    "Solution",
    "SquareGrid",
    "UniqueConstraint",
    "Var",
    "VarGrid",
    "VarMap",
    "Vertex",
    "all_different",
    "connected",
    "count_eq",
    "one_of",
    "single_cycle",
    "square_grid",
    "sum_expr",
    "unique",
]
