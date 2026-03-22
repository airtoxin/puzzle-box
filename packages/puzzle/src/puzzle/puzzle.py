from typing import Hashable, Sequence, cast

from ortools.sat.python import cp_model

from puzzle.constraints import (
    AllDifferentConstraint,
    ConnectedConstraint,
    OneOfConstraint,
    SingleCycleConstraint,
    UniqueConstraint,
)
from puzzle.expr import BoolExpr, LinearConstraint, Var, VarGrid, VarMap
from puzzle.features import CONSTRAINT_REQUIRES, MissingFeatureError
from puzzle.grid import Cell, SquareGrid
from puzzle.polyomino import ShapeAcrossConstraint


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
    | BoolExpr
    | LinearConstraint
    | UniqueConstraint
    | OneOfConstraint
    | SingleCycleConstraint
    | ConnectedConstraint
    | ShapeAcrossConstraint
)


class Puzzle:
    def __init__(self, name: str) -> None:
        self.name = name
        self._model = cp_model.CpModel()
        self._vars: list[Var] = []
        self._features: set[str] = set()
        self._require_unique = False
        self._indicator_count = 0

    @property
    def features(self) -> frozenset[str]:
        return frozenset(self._features)

    def add_feature(self, feature: str) -> None:
        self._features.add(feature)

    def _check_requires(self, constraint: ConstraintType) -> None:
        cls_name = type(constraint).__name__
        requires = CONSTRAINT_REQUIRES.get(cls_name, frozenset())
        missing = requires - self._features
        if missing:
            raise MissingFeatureError(cls_name, missing)

    def int_var_grid(
        self, name: str, cells: list[Cell], lo: int, hi: int
    ) -> VarGrid:
        self._features.add("cell_vars")
        vars = {
            cell: Var(
                self._model.new_int_var(lo, hi, f"{name}_{cell.row}_{cell.col}"),
                self._model,
            )
            for cell in cells
        }
        self._vars.extend(vars.values())
        return VarGrid(vars)

    def int_var_map(
        self, name: str, keys: Sequence[Hashable], lo: int, hi: int
    ) -> VarMap:
        self._features.add("cell_vars")
        vars = {
            key: Var(
                self._model.new_int_var(lo, hi, f"{name}_{key}"),
                self._model,
            )
            for key in keys
        }
        self._vars.extend(vars.values())
        return VarMap(vars)

    def bool_var_map(
        self, name: str, keys: Sequence[Hashable]
    ) -> VarMap:
        self._features.add("edge_vars")
        vars = {
            key: Var(
                self._model.new_bool_var(f"{name}_{key}"),
                self._model,
            )
            for key in keys
        }
        self._vars.extend(vars.values())
        return VarMap(vars)

    def add(self, constraint: ConstraintType) -> None:
        self._check_requires(constraint)

        if isinstance(constraint, AllDifferentConstraint):
            self._model.add_all_different([v._internal for v in constraint.vars])
        elif isinstance(constraint, BoolExpr):
            self._model.add(constraint._constraint)
        elif isinstance(constraint, LinearConstraint):
            self._model.add(constraint._internal)
        elif isinstance(constraint, UniqueConstraint):
            self._require_unique = True
        elif isinstance(constraint, OneOfConstraint):
            self._add_one_of(constraint)
        elif isinstance(constraint, SingleCycleConstraint):
            self._add_single_cycle(constraint.edge_vars, constraint.grid)
        elif isinstance(constraint, ConnectedConstraint):
            self._add_connected(constraint)
        elif isinstance(constraint, ShapeAcrossConstraint):
            self._add_shape_across(constraint)

    def _add_one_of(self, constraint: OneOfConstraint) -> None:
        indicators: list[cp_model.IntVar] = []
        for c in constraint.constraints:
            if isinstance(c, BoolExpr):
                indicators.append(cast(cp_model.IntVar, c._internal))
            else:
                b = self._model.new_bool_var(f"_one_of_{self._indicator_count}")
                self._indicator_count += 1
                self._model.add(c._internal).only_enforce_if(b)
                indicators.append(b)
        self._model.add_exactly_one(indicators)

    def _add_single_cycle(self, edge_vars: VarMap, grid: SquareGrid) -> None:
        vertices = grid.vertices
        vertex_id = {v: i for i, v in enumerate(vertices)}

        arcs: list[tuple[int, int, cp_model.IntVar]] = []

        for edge in grid.edges:
            v1, v2 = edge.v1, edge.v2
            id1, id2 = vertex_id[v1], vertex_id[v2]
            edge_var = edge_vars[edge]

            arc_fwd = self._model.new_bool_var(f"_arc_{id1}_{id2}")
            arc_bwd = self._model.new_bool_var(f"_arc_{id2}_{id1}")

            self._model.add(arc_fwd + arc_bwd == edge_var._internal)

            arcs.append((id1, id2, arc_fwd))
            arcs.append((id2, id1, arc_bwd))

        for v in vertices:
            vid = vertex_id[v]
            self_loop = self._model.new_bool_var(f"_self_loop_{vid}")
            arcs.append((vid, vid, self_loop))

        self._model.add_circuit(arcs)

    def _add_connected(self, constraint: ConnectedConstraint) -> None:
        cells = constraint.cells
        indicators = constraint.indicators
        n = len(cells)
        cell_set = set(cells)

        active: dict[Cell, cp_model.IntVar] = {
            c: cast(cp_model.IntVar, indicators[c]._internal) for c in cells
        }

        order_vars = {
            c: self._model.new_int_var(0, n - 1, f"_conn_ord_{c}")
            for c in cells
        }
        is_root = {
            c: self._model.new_bool_var(f"_conn_root_{c}")
            for c in cells
        }

        for c in cells:
            nbrs = [
                Cell(c.row + dr, c.col + dc)
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]
                if Cell(c.row + dr, c.col + dc) in cell_set
            ]

            parent_vars: list[cp_model.IntVar] = []
            for nbr in nbrs:
                p_var = self._model.new_bool_var(f"_conn_par_{c}_{nbr}")
                parent_vars.append(p_var)
                self._model.add(active[nbr] == 1).only_enforce_if(p_var)
                self._model.add(
                    order_vars[c] == order_vars[nbr] + 1
                ).only_enforce_if(p_var)

            self._model.add(is_root[c] == 0).only_enforce_if(active[c].Not())
            if parent_vars:
                self._model.add(
                    cp_model.LinearExpr.sum(parent_vars) == 0
                ).only_enforce_if(active[c].Not())

            self._model.add(order_vars[c] == 0).only_enforce_if(is_root[c])
            if parent_vars:
                self._model.add(
                    cp_model.LinearExpr.sum(parent_vars) == 0
                ).only_enforce_if(is_root[c])

            if parent_vars:
                self._model.add(
                    cp_model.LinearExpr.sum(parent_vars) == 1
                ).only_enforce_if(active[c]).only_enforce_if(is_root[c].Not())
            else:
                self._model.add(is_root[c] == 1).only_enforce_if(active[c])

        root_list = [is_root[c] for c in cells]
        self._model.add(cp_model.LinearExpr.sum(root_list) <= 1)

        active_list = [active[c] for c in cells]
        any_active = self._model.new_bool_var(
            f"_conn_any_{self._indicator_count}"
        )
        self._indicator_count += 1
        self._model.add(
            cp_model.LinearExpr.sum(active_list) >= 1
        ).only_enforce_if(any_active)
        self._model.add(
            cp_model.LinearExpr.sum(active_list) == 0
        ).only_enforce_if(any_active.Not())
        self._model.add(
            cp_model.LinearExpr.sum(root_list) == 1
        ).only_enforce_if(any_active)

    def _add_shape_across(self, constraint: ShapeAcrossConstraint) -> None:
        for pa, pb in constraint.forbidden_pairs:
            va = cast(cp_model.IntVar, constraint.use_vars[pa]._internal)
            vb = cast(cp_model.IntVar, constraint.use_vars[pb]._internal)
            self._model.add(va + vb <= 1)

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
