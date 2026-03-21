from puzzle.constraints import AllDifferentConstraint, UniqueConstraint, all_different, unique
from puzzle.expr import LinearConstraint, Var, VarGrid
from puzzle.grid import Cell, SquareGrid, square_grid
from puzzle.puzzle import Puzzle, Solution

Constraint = AllDifferentConstraint | LinearConstraint | UniqueConstraint

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
    "UniqueConstraint",
    "all_different",
    "square_grid",
    "unique",
]
