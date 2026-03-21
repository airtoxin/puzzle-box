from __future__ import annotations

from ortools.sat.python import cp_model

from puzzle.grid import Cell


class Var:
    """Public wrapper around an integer decision variable. Hides ortools internals."""

    def __init__(self, _internal: cp_model.IntVar) -> None:
        self._internal = _internal

    def __eq__(self, other: object) -> LinearConstraint:  # type: ignore[override]
        if isinstance(other, int):
            return LinearConstraint(self._internal == other)
        if isinstance(other, Var):
            return LinearConstraint(self._internal == other._internal)
        return NotImplemented

    def __ne__(self, other: object) -> LinearConstraint:  # type: ignore[override]
        if isinstance(other, int):
            return LinearConstraint(self._internal != other)
        if isinstance(other, Var):
            return LinearConstraint(self._internal != other._internal)
        return NotImplemented

    def __le__(self, other: int | Var) -> LinearConstraint:
        if isinstance(other, int):
            return LinearConstraint(self._internal <= other)
        if isinstance(other, Var):
            return LinearConstraint(self._internal <= other._internal)
        return NotImplemented

    def __ge__(self, other: int | Var) -> LinearConstraint:
        if isinstance(other, int):
            return LinearConstraint(self._internal >= other)
        if isinstance(other, Var):
            return LinearConstraint(self._internal >= other._internal)
        return NotImplemented

    def __lt__(self, other: int | Var) -> LinearConstraint:
        if isinstance(other, int):
            return LinearConstraint(self._internal < other)
        if isinstance(other, Var):
            return LinearConstraint(self._internal < other._internal)
        return NotImplemented

    def __gt__(self, other: int | Var) -> LinearConstraint:
        if isinstance(other, int):
            return LinearConstraint(self._internal > other)
        if isinstance(other, Var):
            return LinearConstraint(self._internal > other._internal)
        return NotImplemented

    def __hash__(self) -> int:
        return id(self._internal)


class LinearConstraint:
    """Public wrapper around a bounded linear expression."""

    def __init__(self, _internal: cp_model.BoundedLinearExpression) -> None:
        self._internal = _internal


class VarGrid:
    def __init__(self, vars: dict[Cell, Var]) -> None:
        self._vars = vars

    def __getitem__(self, cell: Cell) -> Var:
        return self._vars[cell]
