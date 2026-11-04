"""Trusted application code explicitly registering a developer's own component."""

from dataclasses import dataclass

from puzzle import Cell, Constraint, sum_expr
from puzzle_defs import ShadingPuzzle
from component_registry import IntParam
from composed_shading_recipe import BUILTIN_COMPONENTS
from generate_composed_shading import main


@dataclass(frozen=True)
class RowBlackBand:
    minimum: int
    maximum: int

    def __post_init__(self) -> None:
        if (type(self.minimum) is not int or type(self.maximum) is not int
                or not 0 <= self.minimum <= self.maximum <= 9):
            raise ValueError("RowBlackBand requires 0 <= minimum <= maximum <= 9")

    def __call__(self, puzzle: ShadingPuzzle) -> list[Constraint]:
        result: list[Constraint] = []
        for row in range(puzzle.rows):
            total = sum_expr(puzzle.black[Cell(row, col)] for col in range(puzzle.cols))
            result.extend([total >= self.minimum, total <= self.maximum])
        return result


# This code is selected by the application author. No file controls imports or
# registrations, and extending this value does not mutate BUILTIN_COMPONENTS.
COMPONENTS = BUILTIN_COMPONENTS.with_component(
    "example/row-black-band/v1", RowBlackBand,
    minimum=IntParam(0, 9), maximum=IntParam(0, 9),
)


if __name__ == "__main__":
    raise SystemExit(main(registry=COMPONENTS))
