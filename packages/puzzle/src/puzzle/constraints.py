from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Iterable, Sequence

from typing import Hashable

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


def at_least_one(exprs: Iterable[Expr]) -> LinearConstraint:
    from puzzle.expr import sum_expr

    result = sum_expr(exprs)
    return result >= 1  # type: ignore[return-value]


def at_most_one(exprs: Iterable[Expr]) -> LinearConstraint:
    from puzzle.expr import sum_expr

    result = sum_expr(exprs)
    return result <= 1  # type: ignore[return-value]


@dataclass(frozen=True)
class ShapeAcrossConstraint:
    """Constraint on piece shapes across a boundary edge."""

    forbidden_pairs: list[tuple[Hashable, Hashable]]
    use_vars: VarMap


@dataclass(frozen=True)
class NoBoundaryCrossConstraint:
    """At each interior vertex, boundaries must not form a cross (+)."""

    vertex_bridges: list[list[Hashable]]
    use_vars: VarMap


@dataclass
class CompoundConstraint:
    """Multiple constraints to be added together."""

    constraints: list[LinearConstraint]


def non_touching(
    var_map: VarMap,
    adjacency: Sequence[tuple[Cell, Cell]],
) -> CompoundConstraint:
    """No two selected variables in adjacent pairs are both true."""
    from puzzle.expr import sum_expr

    constraints: list[LinearConstraint] = []
    for a, b in adjacency:
        if a in var_map and b in var_map:  # type: ignore[operator]
            constraints.append(
                sum_expr([var_map[a], var_map[b]]) <= 1  # type: ignore[return-value]
            )
    return CompoundConstraint(constraints)
