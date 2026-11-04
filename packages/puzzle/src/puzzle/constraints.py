from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Iterable, Sequence

from typing import Hashable
from puzzle._symbolic import Symbolic

if TYPE_CHECKING:
    from puzzle.expr import BoolExpr, Expr, LinearConstraint, Var, VarMap
    from puzzle.grid import Cell, SquareGrid


@dataclass
class AllDifferentConstraint(Symbolic):
    vars: list[Var]


@dataclass
class UniqueConstraint(Symbolic):
    pass


@dataclass
class OneOfConstraint(Symbolic):
    constraints: list[LinearConstraint | BoolExpr]


@dataclass
class SingleCycleConstraint(Symbolic):
    edge_vars: VarMap
    grid: SquareGrid


@dataclass
class ConnectedConstraint(Symbolic):
    cells: list[Cell]
    indicators: dict[Cell, BoolExpr | Var] = field(repr=False)
    diagonal: bool = False

    def __post_init__(self) -> None:
        if type(self.diagonal) is not bool:
            raise ValueError("diagonal must be a boolean")


def all_different(vars: Iterable[Var]) -> AllDifferentConstraint:
    return AllDifferentConstraint(list(vars))


def unique() -> UniqueConstraint:
    """Require one assignment of the Puzzle's selected solution variables."""
    return UniqueConstraint()


def one_of(*constraints: LinearConstraint | BoolExpr) -> OneOfConstraint:
    """Require exactly one condition to hold (including overlapping conditions)."""
    return OneOfConstraint(list(constraints))


def single_cycle(edge_vars: VarMap, grid: SquareGrid) -> SingleCycleConstraint:
    return SingleCycleConstraint(edge_vars, grid)


def connected(
    cells: Sequence[Cell], predicate: Callable[[Cell], BoolExpr | Var], *, diagonal: bool = False
) -> ConnectedConstraint:
    """Connect selected cells by edges, or edges and corners if diagonal=True.

    Only supplied cells are available; an empty selection remains allowed.
    """
    cell_list = list(cells)
    indicators = {c: predicate(c) for c in cell_list}
    return ConnectedConstraint(cell_list, indicators, diagonal)


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
class ShapeAcrossConstraint(Symbolic):
    """Constraint on piece shapes across a boundary edge."""

    forbidden_pairs: Sequence[tuple[Hashable, Hashable]]
    use_vars: VarMap


@dataclass(frozen=True)
class NoBoundaryCrossConstraint(Symbolic):
    """At each interior vertex, boundaries must not form a cross (+)."""

    vertex_bridges: Sequence[Sequence[Hashable]]
    use_vars: VarMap


@dataclass
class CompoundConstraint(Symbolic):
    """Multiple constraints to be added together."""

    constraints: list[LinearConstraint]


def non_touching(
    var_map: VarMap,
    adjacency: Sequence[tuple[Hashable, Hashable]],
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
