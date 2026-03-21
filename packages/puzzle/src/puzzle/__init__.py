from puzzle.constraints import AllDifferentConstraint, all_different
from puzzle.expr import LinearConstraint, Var, VarGrid
from puzzle.grid import Cell, SquareGrid, square_grid
from puzzle.puzzle import Puzzle, Solution

Constraint = AllDifferentConstraint | LinearConstraint

__all__ = [
    "AllDifferentConstraint",
    "Cell",
    "Constraint",
    "LinearConstraint",
    "Puzzle",
    "Solution",
    "SquareGrid",
    "Var",
    "VarGrid",
    "all_different",
    "square_grid",
]
