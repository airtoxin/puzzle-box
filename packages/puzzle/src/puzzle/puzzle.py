from ortools.sat.python import cp_model

from puzzle.constraints import AllDifferentConstraint, UniqueConstraint
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


class _SolutionCounter(cp_model.CpSolverSolutionCallback):
    def __init__(self, limit: int) -> None:
        super().__init__()
        self.count = 0
        self._limit = limit

    def on_solution_callback(self) -> None:
        self.count += 1
        if self.count >= self._limit:
            self.stop_search()


class Puzzle:
    def __init__(self, name: str) -> None:
        self.name = name
        self._model = cp_model.CpModel()
        self._vars: list[Var] = []
        self._require_unique = False

    def int_var_grid(
        self, name: str, cells: list[Cell], lo: int, hi: int
    ) -> VarGrid:
        vars = {
            cell: Var(self._model.new_int_var(lo, hi, f"{name}_{cell.row}_{cell.col}"))
            for cell in cells
        }
        self._vars.extend(vars.values())
        return VarGrid(vars)

    def add(
        self, constraint: AllDifferentConstraint | LinearConstraint | UniqueConstraint
    ) -> None:
        if isinstance(constraint, AllDifferentConstraint):
            self._model.add_all_different([v._internal for v in constraint.vars])
        elif isinstance(constraint, LinearConstraint):
            self._model.add(constraint._internal)
        elif isinstance(constraint, UniqueConstraint):
            self._require_unique = True

    def solve(self) -> Solution | None:
        solver = cp_model.CpSolver()

        if self._require_unique:
            solver.parameters.enumerate_all_solutions = True
            counter = _SolutionCounter(limit=2)
            status = solver.solve(self._model, counter)
            if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                return None
            if counter.count != 1:
                return None
            return Solution(solver)

        status = solver.solve(self._model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None
        return Solution(solver)
