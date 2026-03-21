from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from puzzle.expr import Var


@dataclass
class AllDifferentConstraint:
    vars: list[Var]


def all_different(vars: Iterable[Var]) -> AllDifferentConstraint:
    return AllDifferentConstraint(list(vars))
