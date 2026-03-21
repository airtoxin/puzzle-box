from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from puzzle.expr import BoolVarMap, LinearConstraint, Var
    from puzzle.grid import SquareGrid


@dataclass
class AllDifferentConstraint:
    vars: list[Var]


@dataclass
class UniqueConstraint:
    pass


@dataclass
class OneOfConstraint:
    constraints: list[LinearConstraint]


@dataclass
class SingleCycleConstraint:
    edge_vars: BoolVarMap
    grid: SquareGrid


def all_different(vars: Iterable[Var]) -> AllDifferentConstraint:
    return AllDifferentConstraint(list(vars))


def unique() -> UniqueConstraint:
    return UniqueConstraint()


def one_of(*constraints: LinearConstraint) -> OneOfConstraint:
    return OneOfConstraint(list(constraints))


def single_cycle(edge_vars: BoolVarMap, grid: SquareGrid) -> SingleCycleConstraint:
    return SingleCycleConstraint(edge_vars, grid)
