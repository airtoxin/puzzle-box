from typing import Hashable

from ortools.sat.python import cp_model

from puzzle.constraints import (
    AllDifferentConstraint,
    OneOfConstraint,
    SingleCycleConstraint,
    UniqueConstraint,
)
from puzzle.expr import BoolVarMap, LinearConstraint, Var, VarGrid
from puzzle.grid import Cell, SquareGrid


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


ConstraintType = (
    AllDifferentConstraint
    | LinearConstraint
    | UniqueConstraint
    | OneOfConstraint
    | SingleCycleConstraint
)


class Puzzle:
    def __init__(self, name: str) -> None:
        self.name = name
        self._model = cp_model.CpModel()
        self._vars: list[Var] = []
        self._require_unique = False
        self._indicator_count = 0

    def int_var_grid(
        self, name: str, cells: list[Cell], lo: int, hi: int
    ) -> VarGrid:
        vars = {
            cell: Var(self._model.new_int_var(lo, hi, f"{name}_{cell.row}_{cell.col}"))
            for cell in cells
        }
        self._vars.extend(vars.values())
        return VarGrid(vars)

    def bool_var_map(
        self, name: str, keys: list[Hashable]
    ) -> BoolVarMap:
        vars = {
            key: Var(self._model.new_bool_var(f"{name}_{key}"))
            for key in keys
        }
        self._vars.extend(vars.values())
        return BoolVarMap(vars)

    def add(self, constraint: ConstraintType) -> None:
        if isinstance(constraint, AllDifferentConstraint):
            self._model.add_all_different([v._internal for v in constraint.vars])
        elif isinstance(constraint, LinearConstraint):
            self._model.add(constraint._internal)
        elif isinstance(constraint, UniqueConstraint):
            self._require_unique = True
        elif isinstance(constraint, OneOfConstraint):
            self._add_one_of(constraint)
        elif isinstance(constraint, SingleCycleConstraint):
            self._add_single_cycle(constraint.edge_vars, constraint.grid)

    def _add_one_of(self, constraint: OneOfConstraint) -> None:
        indicators = []
        for c in constraint.constraints:
            b = self._model.new_bool_var(f"_one_of_{self._indicator_count}")
            self._indicator_count += 1
            self._model.add(c._internal).only_enforce_if(b)
            indicators.append(b)
        self._model.add_exactly_one(indicators)

    def _add_single_cycle(
        self, edge_vars: BoolVarMap, grid: SquareGrid
    ) -> None:
        vertices = grid.vertices
        vertex_id = {v: i for i, v in enumerate(vertices)}

        arcs: list[tuple[int, int, cp_model.IntVar]] = []

        for edge in grid.edges:
            v1, v2 = edge.v1, edge.v2
            id1, id2 = vertex_id[v1], vertex_id[v2]
            edge_var = edge_vars[edge]

            arc_fwd = self._model.new_bool_var(f"_arc_{id1}_{id2}")
            arc_bwd = self._model.new_bool_var(f"_arc_{id2}_{id1}")

            # edge_on ↔ exactly one direction
            self._model.add(arc_fwd + arc_bwd == edge_var._internal)

            arcs.append((id1, id2, arc_fwd))
            arcs.append((id2, id1, arc_bwd))

        # Self-loops for vertices not in the cycle
        for v in vertices:
            vid = vertex_id[v]
            self_loop = self._model.new_bool_var(f"_self_loop_{vid}")
            arcs.append((vid, vid, self_loop))

        self._model.add_circuit(arcs)

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
