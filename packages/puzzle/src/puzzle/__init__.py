from puzzle.constraints import (
    AllDifferentConstraint,
    OneOfConstraint,
    SingleCycleConstraint,
    UniqueConstraint,
    all_different,
    one_of,
    single_cycle,
    unique,
)
from puzzle.expr import BoolVarMap, Expr, LinearConstraint, Var, VarGrid, sum_expr
from puzzle.grid import Cell, Edge, SquareGrid, Vertex, square_grid
from puzzle.puzzle import Puzzle, Solution

Constraint = (
    AllDifferentConstraint
    | LinearConstraint
    | UniqueConstraint
    | OneOfConstraint
    | SingleCycleConstraint
)

__all__ = [
    "AllDifferentConstraint",
    "BoolVarMap",
    "Cell",
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
    "Vertex",
    "all_different",
    "one_of",
    "single_cycle",
    "square_grid",
    "sum_expr",
    "unique",
]
