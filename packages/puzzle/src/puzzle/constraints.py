from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Iterable, Sequence

if TYPE_CHECKING:
    from puzzle.expr import BoolExpr, Expr, LinearConstraint, Var, VarMap
    from puzzle.grid import Cell, SquareGrid


@dataclass
class AllDifferentConstraint:
    vars: list[Var]


@dataclass
class UniqueConstraint:
    pass


@dataclass
class OneOfConstraint:
    constraints: list[LinearConstraint | BoolExpr]


@dataclass
class SingleCycleConstraint:
    edge_vars: VarMap
    grid: SquareGrid


@dataclass
class ConnectedConstraint:
    cells: list[Cell]
    indicators: dict[Cell, BoolExpr] = field(repr=False)


def all_different(vars: Iterable[Var]) -> AllDifferentConstraint:
    return AllDifferentConstraint(list(vars))


def unique() -> UniqueConstraint:
    return UniqueConstraint()


def one_of(*constraints: LinearConstraint | BoolExpr) -> OneOfConstraint:
    return OneOfConstraint(list(constraints))


def single_cycle(edge_vars: VarMap, grid: SquareGrid) -> SingleCycleConstraint:
    return SingleCycleConstraint(edge_vars, grid)


def connected(
    cells: Sequence[Cell], predicate: Callable[[Cell], BoolExpr]
) -> ConnectedConstraint:
    cell_list = list(cells)
    indicators = {c: predicate(c) for c in cell_list}
    return ConnectedConstraint(cell_list, indicators)


def count_eq(exprs: Iterable[BoolExpr], n: int) -> LinearConstraint:
    from puzzle.expr import sum_expr

    result = sum_expr(exprs)
    return result == n  # type: ignore[return-value]


def exactly_one(exprs: Iterable[Expr]) -> LinearConstraint:
    from puzzle.expr import sum_expr

    result = sum_expr(exprs)
    return result == 1  # type: ignore[return-value]
