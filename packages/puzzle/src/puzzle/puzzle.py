from typing import Hashable, Iterable, Sequence, cast

from ortools.sat.python import cp_model

from puzzle.constraints import (
    AllDifferentConstraint,
    CompoundConstraint,
    ConnectedConstraint,
    NoBoundaryCrossConstraint,
    OneOfConstraint,
    ShapeAcrossConstraint,
    SingleCycleConstraint,
    UniqueConstraint,
)
from puzzle.expr import (
    BoolExpr, LinearConstraint, Var, VarGrid, VarMap, _check_same_model, _expression_vars,
)
from puzzle.match import MatchVarMap
from puzzle.features import CONSTRAINT_REQUIRES, MissingFeatureError
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


ConstraintType = (
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


class Puzzle:
    def __init__(self, name: str) -> None:
        self.name = name
        self._model = cp_model.CpModel()
        self._vars: list[Var] = []
        self._solution_vars: list[Var] | None = None
        self._features: set[str] = set()
        self._require_unique = False
        self._indicator_count = 0

    @property
    def features(self) -> frozenset[str]:
        return frozenset(self._features)

    def add_feature(self, feature: str) -> None:
        self._features.add(feature)

    def set_solution_vars(self, variables: Iterable[Var]) -> None:
        """Select the variables whose values distinguish puzzle solutions.

        By default, all variables created through this Puzzle's variable factories
        count. Internal encoding witnesses (loop directions, connectivity trees,
        etc.) never count. Explicit selection also excludes factory-created
        witnesses, such as a tree-to-tent matching. An empty selection has one
        solution exactly when the model is feasible. Later calls replace it.
        """
        selected = list(variables)
        if any(var._model is not self._model for var in selected):
            raise ValueError("Solution variables must belong to this Puzzle")
        self._solution_vars = selected

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

    def match_var_map(
        self,
        name: str,
        left: Sequence[Hashable],
        right: Sequence[Hashable],
        allowed_pairs: Sequence[tuple[Hashable, Hashable]],
    ) -> MatchVarMap:
        """Create boolean match variables for a bipartite matching."""
        vars: dict[tuple[Hashable, Hashable], Var] = {}
        pairs_by_left: dict[Hashable, list[tuple[Hashable, Hashable]]] = {}
        pairs_by_right: dict[Hashable, list[tuple[Hashable, Hashable]]] = {}

        for a, b in allowed_pairs:
            pair = (a, b)
            v = Var(
                self._model.new_bool_var(f"{name}_{a}_{b}"),
                self._model,
            )
            vars[pair] = v
            self._vars.append(v)
            pairs_by_left.setdefault(a, []).append(pair)
            pairs_by_right.setdefault(b, []).append(pair)

        return MatchVarMap(vars, list(left), list(right), pairs_by_left, pairs_by_right)

    def add(self, constraint: ConstraintType) -> None:
        self._check_requires(constraint)
        self._check_constraint_model(constraint)

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
        elif isinstance(constraint, CompoundConstraint):
            for c in constraint.constraints:
                self.add(c)
        elif isinstance(constraint, NoBoundaryCrossConstraint):
            self._add_no_boundary_cross(constraint)

    def _check_constraint_model(self, constraint: ConstraintType) -> None:
        """Preflight every member before compiling a compound constraint."""
        if isinstance(constraint, BoolExpr):
            _check_same_model(_expression_vars(constraint._internal), self._model)
        elif isinstance(constraint, LinearConstraint):
            if not isinstance(constraint._internal, bool):
                _check_same_model(constraint._internal.vars, self._model)
        elif isinstance(constraint, AllDifferentConstraint):
            _check_same_model(
                (cast(cp_model.IntVar, var._internal) for var in constraint.vars), self._model
            )
        elif isinstance(constraint, (OneOfConstraint, CompoundConstraint)):
            for member in constraint.constraints:
                self._check_constraint_model(member)
        elif isinstance(constraint, ConnectedConstraint):
            for indicator in constraint.indicators.values():
                self._check_constraint_model(indicator)
        elif isinstance(constraint, SingleCycleConstraint):
            self._check_var_map_model(constraint.edge_vars)
        elif isinstance(constraint, (ShapeAcrossConstraint, NoBoundaryCrossConstraint)):
            self._check_var_map_model(constraint.use_vars)

    def _check_var_map_model(self, var_map: VarMap) -> None:
        _check_same_model(
            (cast(cp_model.IntVar, var._internal) for var in var_map._vars.values()), self._model
        )

    def _add_one_of(self, constraint: OneOfConstraint) -> None:
        indicators: list[cp_model.IntVar] = []
        for c in constraint.constraints:
            if isinstance(c, BoolExpr):
                indicators.append(cast(cp_model.IntVar, c._internal))
            else:
                b = self._model.new_bool_var(f"_one_of_{self._indicator_count}")
                self._indicator_count += 1
                self._model.add(c._internal).only_enforce_if(b)
                # The indicator must be equivalent to the condition, not just
                # imply it. Complementing the domain also handles != and ranges.
                if isinstance(c._internal, bool):
                    self._model.add(b == int(c._internal))
                else:
                    expr = cp_model.LinearExpr.weighted_sum(
                        c._internal.vars, c._internal.coeffs
                    ) + c._internal.offset
                    self._model.add_linear_expression_in_domain(
                        expr, c._internal.bounds.complement()
                    ).only_enforce_if(b.Not())
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

    def _add_no_boundary_cross(self, constraint: NoBoundaryCrossConstraint) -> None:
        for bridges in constraint.vertex_bridges:
            if not bridges:
                # No placement bridges this vertex — infeasible
                self._model.add(0 >= 1)  # force UNSAT
                return
            internals = [
                cast(cp_model.IntVar, constraint.use_vars[pl]._internal)
                for pl in bridges
            ]
            self._model.add(cp_model.LinearExpr.sum(internals) >= 1)

    def _add_shape_across(self, constraint: ShapeAcrossConstraint) -> None:
        for pa, pb in constraint.forbidden_pairs:
            va = cast(cp_model.IntVar, constraint.use_vars[pa]._internal)
            vb = cast(cp_model.IntVar, constraint.use_vars[pb]._internal)
            self._model.add(va + vb <= 1)

    def solve(self, seed: int | None = None) -> Solution | None:
        """Solve, checking uniqueness over solution variables when requested.

        A unique result is returned only after proving that no different projected
        assignment exists. The original model is never changed by the check.
        """
        solver = cp_model.CpSolver()
        if seed is not None:
            solver.parameters.random_seed = seed

        status = solver.solve(self._model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None

        if self._require_unique:
            variables = self._vars if self._solution_vars is None else self._solution_vars
            if variables:
                alternative = self._model.clone()
                # The clone retains variable indices. Exclude the whole visible
                # assignment, thereby excluding all its internal witnesses at once.
                alternative.add_forbidden_assignments(
                    [var._internal for var in variables],
                    [[solver.value(var._internal) for var in variables]],
                )
                checker = cp_model.CpSolver()
                if seed is not None:
                    checker.parameters.random_seed = seed
                if checker.solve(alternative) != cp_model.INFEASIBLE:
                    return None
        return Solution(solver)
