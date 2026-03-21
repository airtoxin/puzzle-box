from __future__ import annotations

from typing import Any, Hashable, Iterable

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

    def __hash__(self) -> int:
        return id(self._internal)


class Var(Expr):
    """A single integer decision variable."""
    pass


class VarGrid:
    def __init__(self, vars: dict[Cell, Var]) -> None:
        self._vars = vars

    def __getitem__(self, cell: Cell) -> Var:
        return self._vars[cell]


class BoolVarMap:
    def __init__(self, vars: dict[Hashable, Var]) -> None:
        self._vars = vars

    def __getitem__(self, key: Hashable) -> Var:
        return self._vars[key]


def sum_expr(vars: Iterable[Expr]) -> Expr:
    internals = [v._internal for v in vars]
    return Expr(cp_model.LinearExpr.sum(internals))
