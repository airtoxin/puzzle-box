"""Bipartite matching variable map."""

from __future__ import annotations

from typing import TYPE_CHECKING, Hashable, Sequence

if TYPE_CHECKING:
    from puzzle.constraints import CompoundConstraint
    from puzzle.expr import Var, VarMap


class MatchVarMap:
    """Boolean variables for bipartite matching between left and right sets.

    For each allowed pair (a, b) in left × right, a boolean variable
    match[a, b] indicates whether the pair is matched.
    """

    def __init__(
        self,
        vars: dict[tuple[Hashable, Hashable], Var],
        left: list[Hashable],
        right: list[Hashable],
        pairs_by_left: dict[Hashable, list[tuple[Hashable, Hashable]]],
        pairs_by_right: dict[Hashable, list[tuple[Hashable, Hashable]]],
    ) -> None:
        self._vars = vars
        self._left = left
        self._right = right
        self._pairs_by_left = pairs_by_left
        self._pairs_by_right = pairs_by_right

    def __getitem__(self, key: tuple[Hashable, Hashable]) -> Var:
        return self._vars[key]

    def left_degree_eq(self, n: int) -> CompoundConstraint:
        """Each left element is matched to exactly n right elements."""
        from puzzle.constraints import CompoundConstraint
        from puzzle.expr import sum_expr

        constraints = []
        for l in self._left:
            pairs = self._pairs_by_left.get(l, [])
            if pairs:
                constraints.append(
                    sum_expr(self._vars[p] for p in pairs) == n  # type: ignore[return-value]
                )
            elif n > 0:
                # No pairs available but n > 0 required — add infeasible constraint
                from puzzle.expr import LinearConstraint
                from ortools.sat.python import cp_model
                constraints.append(LinearConstraint(cp_model.LinearExpr.sum([]) >= n))
        return CompoundConstraint(constraints)

    def left_degree_le(self, n: int) -> CompoundConstraint:
        """Each left element is matched to at most n right elements."""
        from puzzle.constraints import CompoundConstraint
        from puzzle.expr import sum_expr

        constraints = []
        for l in self._left:
            pairs = self._pairs_by_left.get(l, [])
            if pairs:
                constraints.append(
                    sum_expr(self._vars[p] for p in pairs) <= n  # type: ignore[return-value]
                )
        return CompoundConstraint(constraints)

    def right_degree_eq(self, n: int) -> CompoundConstraint:
        """Each right element is matched to exactly n left elements."""
        from puzzle.constraints import CompoundConstraint
        from puzzle.expr import sum_expr

        constraints = []
        for r in self._right:
            pairs = self._pairs_by_right.get(r, [])
            if pairs:
                constraints.append(
                    sum_expr(self._vars[p] for p in pairs) == n  # type: ignore[return-value]
                )
            elif n > 0:
                from puzzle.expr import LinearConstraint
                from ortools.sat.python import cp_model
                constraints.append(LinearConstraint(cp_model.LinearExpr.sum([]) >= n))
        return CompoundConstraint(constraints)

    def right_degree_le(self, n: int) -> CompoundConstraint:
        """Each right element is matched to at most n right elements."""
        from puzzle.constraints import CompoundConstraint
        from puzzle.expr import sum_expr

        constraints = []
        for r in self._right:
            pairs = self._pairs_by_right.get(r, [])
            if pairs:
                constraints.append(
                    sum_expr(self._vars[p] for p in pairs) <= n  # type: ignore[return-value]
                )
        return CompoundConstraint(constraints)

    def right_selected_iff(self, var_map: VarMap) -> CompoundConstraint:
        """Right element's var == 1 iff it is matched to some left element.

        For each right element r: var_map[r] == sum(match[l, r] for l).
        """
        from puzzle.constraints import CompoundConstraint
        from puzzle.expr import LinearConstraint, sum_expr

        constraints = []
        for r in self._right:
            if r not in var_map:  # type: ignore[operator]
                continue
            pairs = self._pairs_by_right.get(r, [])
            if pairs:
                match_sum = sum_expr(self._vars[p] for p in pairs)
                constraints.append(
                    LinearConstraint(match_sum._internal == var_map[r]._internal)
                )
            else:
                # No matches possible → var must be 0
                constraints.append(
                    LinearConstraint(var_map[r]._internal == 0)
                )
        return CompoundConstraint(constraints)
