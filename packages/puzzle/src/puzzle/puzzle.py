from dataclasses import dataclass
import math
import time
from typing import Hashable, Iterable, Literal, Sequence, cast

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
    """A snapshot of one feasible answer, bound to its source model."""

    def __init__(self, solver: cp_model.CpSolver, model: cp_model.CpModel) -> None:
        response = solver.response_proto
        if response.status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise ValueError("Solution requires a feasible solver response")
        self._model = model
        self._values = tuple(response.solution)

    def value(self, var: Var) -> int:
        if var._model is not self._model:
            raise ValueError("Solution variables must belong to the same Puzzle")
        index = cast(cp_model.IntVar, var._internal).index
        if not 0 <= index < len(self._values):
            raise ValueError("Cannot read a variable created after this solution")
        return self._values[index]

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


@dataclass(frozen=True)
class SolveResult:
    """Feasibility and visible-answer uniqueness are separate proof results."""

    status: Literal["sat", "unsat", "unknown"]
    solution: Solution | None = None
    uniqueness: Literal["unique", "multiple", "unknown", "not_checked"] = "not_checked"


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

    @property
    def solution_vars(self) -> tuple[Var, ...] | None:
        """Snapshot of explicit answer variables, or None for factory defaults.

        None keeps including future factory variables. An explicit empty tuple
        selects no answer variables; it is distinct from the default mode.
        """
        return None if self._solution_vars is None else tuple(self._solution_vars)

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
        """Create match variables for a simple bipartite graph.

        Each side and the allowed pairs must be duplicate-free. Pair endpoints
        must belong to their declared side. Validate before mutating the model.
        """
        left_keys, right_keys = list(left), list(right)
        pairs = list(allowed_pairs)
        left_set, right_set = set(left_keys), set(right_keys)
        if len(left_set) != len(left_keys):
            raise ValueError("Duplicate keys in left matching vertices")
        if len(right_set) != len(right_keys):
            raise ValueError("Duplicate keys in right matching vertices")
        if len(set(pairs)) != len(pairs):
            raise ValueError("Matching allowed_pairs must not contain duplicate pairs")
        for a, b in pairs:
            if a not in left_set or b not in right_set:
                raise ValueError("Matching pairs must use declared left and right endpoints")

        vars: dict[tuple[Hashable, Hashable], Var] = {}
        pairs_by_left: dict[Hashable, list[tuple[Hashable, Hashable]]] = {}
        pairs_by_right: dict[Hashable, list[tuple[Hashable, Hashable]]] = {}

        for a, b in pairs:
            pair = (a, b)
            v = Var(
                self._model.new_bool_var(f"{name}_{a}_{b}"),
                self._model,
            )
            vars[pair] = v
            self._vars.append(v)
            pairs_by_left.setdefault(a, []).append(pair)
            pairs_by_right.setdefault(b, []).append(pair)

        return MatchVarMap(vars, left_keys, right_keys, pairs_by_left, pairs_by_right)

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
                _check_same_model(_expression_vars(indicator._internal), self._model)
        elif isinstance(constraint, SingleCycleConstraint):
            self._check_var_map_model(constraint.edge_vars)
        elif isinstance(constraint, (ShapeAcrossConstraint, NoBoundaryCrossConstraint)):
            self._check_var_map_model(constraint.use_vars)
        elif isinstance(constraint, UniqueConstraint):
            pass
        else:
            raise TypeError("Puzzle.add() expects a DSL constraint, not a Python value or collection")

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
        offsets = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        if constraint.diagonal:
            offsets += [(-1, -1), (-1, 1), (1, -1), (1, 1)]

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
                for dr, dc in offsets
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
        A supplied seed uses one search worker for repeatable search with a fixed
        model and solver version. Unseeded solving keeps the solver's defaults.
        """
        result = self.solve_result(seed=seed)
        if self._require_unique and result.uniqueness != "unique":
            return None
        return result.solution

    def exclude_solution(self, solution: Solution) -> None:
        """Exclude one visible answer and all of its auxiliary witnesses."""
        variables = self._vars if self._solution_vars is None else self._solution_vars
        if solution._model is not self._model:
            raise ValueError("Solution must belong to the same Puzzle")
        if not variables:
            self._model.add_bool_or([])
            return
        self._model.add_forbidden_assignments(
            [var._internal for var in variables], [[solution.value(var) for var in variables]],
        )

    def solve_result(self, seed: int | None = None, *, time_limit: float | None = None,
                     check_unique: bool = False) -> SolveResult:
        """Solve within one shared time budget, preserving unknown outcomes.

        SAT includes a witness even if uniqueness is multiple or unknown. Only
        an INFEASIBLE second solve proves uniqueness. Model errors raise instead
        of becoming mathematical verdicts. The original model is unchanged.
        """
        if time_limit is not None and (not math.isfinite(time_limit) or time_limit < 0):
            raise ValueError("time_limit must be finite and nonnegative")
        deadline = None if time_limit is None else time.monotonic() + time_limit

        def run(model: cp_model.CpModel):
            solver = cp_model.CpSolver()
            if seed is not None:
                solver.parameters.random_seed = seed
                solver.parameters.num_search_workers = 1
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return solver, cp_model.UNKNOWN
                solver.parameters.max_time_in_seconds = remaining
            status = solver.solve(model)
            if status == cp_model.MODEL_INVALID:
                raise ValueError("Invalid solver model")
            return solver, status

        solver, status = run(self._model)
        if status == cp_model.INFEASIBLE:
            return SolveResult("unsat")
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return SolveResult("unknown")
        solution = Solution(solver, self._model)
        if not (check_unique or self._require_unique):
            return SolveResult("sat", solution)
        variables = self._vars if self._solution_vars is None else self._solution_vars
        if not variables:
            return SolveResult("sat", solution, "unique")
        alternative = self._model.clone()
        alternative.add_forbidden_assignments(
            [var._internal for var in variables], [[solution.value(var) for var in variables]],
        )
        _, status = run(alternative)
        uniqueness = ("unique" if status == cp_model.INFEASIBLE else "multiple"
                      if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else "unknown")
        return SolveResult("sat", solution, uniqueness)
