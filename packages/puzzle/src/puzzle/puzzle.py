from ortools.sat.python import cp_model

from puzzle.constraints import AllDifferentConstraint
from puzzle.expr import LinearConstraint, Var, VarGrid
from puzzle.grid import Cell


class Solution:
    def __init__(self, solver: cp_model.CpSolver) -> None:
        self._solver = solver

    def value(self, var: Var) -> int:
        return self._solver.value(var._internal)

    def grid_values(self, var_grid: VarGrid, rows: int, cols: int) -> list[list[int]]:
        return [
            [self.value(var_grid[Cell(r, c)]) for c in range(cols)]
            for r in range(rows)
        ]


class Puzzle:
    def __init__(self, name: str) -> None:
        self.name = name
        self._model = cp_model.CpModel()

    def int_var_grid(
        self, name: str, cells: list[Cell], lo: int, hi: int
    ) -> VarGrid:
        vars = {
            cell: Var(self._model.new_int_var(lo, hi, f"{name}_{cell.row}_{cell.col}"))
            for cell in cells
        }
        return VarGrid(vars)

    def add(self, constraint: AllDifferentConstraint | LinearConstraint) -> None:
        if isinstance(constraint, AllDifferentConstraint):
            self._model.add_all_different([v._internal for v in constraint.vars])
        elif isinstance(constraint, LinearConstraint):
            self._model.add(constraint._internal)

    def solve(self) -> Solution | None:
        solver = cp_model.CpSolver()
        status = solver.solve(self._model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None
        return Solution(solver)
