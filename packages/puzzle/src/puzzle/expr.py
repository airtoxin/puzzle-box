from __future__ import annotations

from typing import Any, Hashable, Iterable, cast

from ortools.sat.python import cp_model

from puzzle.grid import Cell


class LinearConstraint:
    """Public wrapper around a bounded linear expression."""

    def __init__(self, _internal: cp_model.BoundedLinearExpression | Any) -> None:
        self._internal: cp_model.BoundedLinearExpression = _internal


class Expr:
    """Wrapper around a CP-SAT linear expression."""

    def __init__(self, _internal: cp_model.LinearExprT) -> None:
        self._internal = _internal

    def __eq__(self, other: object) -> LinearConstraint:  # type: ignore[override]
        if isinstance(other, int):
            return LinearConstraint(self._internal == other)
        if isinstance(other, Expr):
            return LinearConstraint(self._internal == other._internal)
        return NotImplemented

    def __ne__(self, other: object) -> LinearConstraint:  # type: ignore[override]
        if isinstance(other, int):
            return LinearConstraint(self._internal != other)
        if isinstance(other, Expr):
            return LinearConstraint(self._internal != other._internal)
        return NotImplemented

    def __le__(self, other: int | Expr) -> LinearConstraint:
        if isinstance(other, int):
            return LinearConstraint(self._internal <= other)
        if isinstance(other, Expr):
            return LinearConstraint(self._internal <= other._internal)
        return NotImplemented

    def __ge__(self, other: int | Expr) -> LinearConstraint:
        if isinstance(other, int):
            return LinearConstraint(self._internal >= other)
        if isinstance(other, Expr):
            return LinearConstraint(self._internal >= other._internal)
        return NotImplemented

    def __lt__(self, other: int | Expr) -> LinearConstraint:
        if isinstance(other, int):
            return LinearConstraint(self._internal < other)
        if isinstance(other, Expr):
            return LinearConstraint(self._internal < other._internal)
        return NotImplemented

    def __gt__(self, other: int | Expr) -> LinearConstraint:
        if isinstance(other, int):
            return LinearConstraint(self._internal > other)
        if isinstance(other, Expr):
            return LinearConstraint(self._internal > other._internal)
        return NotImplemented

    def __or__(self, other: Expr) -> LinearConstraint:  # type: ignore[override]
        """At least one is true: self + other >= 1."""
        if isinstance(other, Expr):
            s = cp_model.LinearExpr.sum([self._internal, other._internal])
            return LinearConstraint(s >= 1)
        return NotImplemented

    def __hash__(self) -> int:
        return id(self._internal)


class BoolExpr(Expr):
    """A reified boolean expression usable as both a 0/1 Expr and a constraint.

    Wraps an indicator bool var that is fully reified:
    indicator == 1 ↔ original constraint holds.
    """

    def __init__(
        self,
        indicator: cp_model.IntVar,
        constraint: cp_model.BoundedLinearExpression | Any,
    ) -> None:
        super().__init__(indicator)
        self._constraint: cp_model.BoundedLinearExpression = constraint


class Var(Expr):
    """A single integer decision variable."""

    def __init__(self, _internal: cp_model.IntVar, _model: cp_model.CpModel) -> None:
        super().__init__(_internal)
        self._model = _model
        self._indicator_count = 0

    def _reify(
        self, constraint: cp_model.BoundedLinearExpression | Any, negation: cp_model.BoundedLinearExpression | Any
    ) -> BoolExpr:
        b = self._model.new_bool_var(
            f"_ind_{self._internal.name}_{self._indicator_count}"  # type: ignore[union-attr]
        )
        self._indicator_count += 1
        self._model.add(constraint).only_enforce_if(b)
        self._model.add(negation).only_enforce_if(b.Not())
        return BoolExpr(b, constraint)

    def __eq__(self, other: object) -> BoolExpr:  # type: ignore[override]
        if isinstance(other, int):
            return self._reify(self._internal == other, self._internal != other)
        if isinstance(other, Var):
            return self._reify(
                self._internal == other._internal,
                self._internal != other._internal,
            )
        return NotImplemented  # type: ignore[return-value]

    def __ne__(self, other: object) -> BoolExpr:  # type: ignore[override]
        if isinstance(other, int):
            return self._reify(self._internal != other, self._internal == other)
        if isinstance(other, Var):
            return self._reify(
                self._internal != other._internal,
                self._internal == other._internal,
            )
        return NotImplemented  # type: ignore[return-value]

    def __invert__(self) -> BoolExpr:
        """Negate a boolean variable: ~black[c] is true when black[c] is false."""
        internal = cast(cp_model.IntVar, self._internal)
        return BoolExpr(
            cast(cp_model.IntVar, internal.Not()),
            self._internal == 0,
        )

    def __hash__(self) -> int:
        return id(self._internal)


class VarGrid:
    def __init__(self, vars: dict[Cell, Var]) -> None:
        self._vars = vars

    def __getitem__(self, cell: Cell) -> Var:
        return self._vars[cell]


class VarMap:
    def __init__(self, vars: dict[Hashable, Var]) -> None:
        self._vars = vars

    def __getitem__(self, key: Hashable) -> Var:
        return self._vars[key]

    def __contains__(self, key: Hashable) -> bool:
        return key in self._vars


BoolVarMap = VarMap


def sum_expr(exprs: Iterable[Expr]) -> Expr:
    internals = [v._internal for v in exprs]
    return Expr(cp_model.LinearExpr.sum(internals))
