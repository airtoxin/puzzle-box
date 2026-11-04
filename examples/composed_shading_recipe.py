"""Closed, versioned data encoding for two fixed shading constraint builders."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from generator import ConstrainedRecipe, with_constraints
from puzzle import Constraint, at_least_one, connected, sum_expr
from puzzle_defs import ShadingPuzzle, ShadingRecipe
from puzzle_defs.puzzles.shading import Clue
from shading_recipe import load_json, read_recipe as read_base, recipe_record as base_record

FORMAT = "puzzle-box/composed-shading-recipe-v1"
MAX_CELLS = 9
MAX_COMPONENTS = 8
type Recipe = ConstrainedRecipe[ShadingPuzzle, Clue]


def _color(color: str) -> None:
    if type(color) is not str or color not in ("black", "white"):
        raise ValueError("Component color must be black or white")


@dataclass(frozen=True)
class CellCount:
    """The existing selected-count constraint, scoped to a named cell color."""

    color: str
    count: int

    def __post_init__(self) -> None:
        _color(self.color)
        if type(self.count) is not int or self.count < 0:
            raise ValueError("Component count must be a nonnegative integer")

    def __call__(self, puzzle: ShadingPuzzle) -> list[Constraint]:
        return [sum_expr(puzzle.black[c] if self.color == "black" else ~puzzle.black[c]
                         for c in puzzle.board.cells) == self.count]


@dataclass(frozen=True)
class ConnectedCells:
    """The existing orthogonal connected constraint with explicit emptiness."""

    color: str
    nonempty: bool = True

    def __post_init__(self) -> None:
        _color(self.color)
        if type(self.nonempty) is not bool:
            raise ValueError("Component nonempty must be a boolean")

    def __call__(self, puzzle: ShadingPuzzle) -> list[Constraint]:
        cells = puzzle.board.cells
        selected = {c: puzzle.black[c] if self.color == "black" else ~puzzle.black[c] for c in cells}
        result: list[Constraint] = [connected(cells, lambda c: selected[c])]
        if self.nonempty:
            result.append(at_least_one(selected.values()))
        return result


def _read_component(data: Any) -> CellCount | ConnectedCells:
    if not isinstance(data, dict):
        raise ValueError("A component must be an object")
    if data.get("id") == "cell-count/v1" and set(data) == {"id", "color", "count"}:
        return CellCount(data["color"], data["count"])
    if data.get("id") == "connected-cells/v1" and set(data) == {"id", "color", "nonempty"}:
        return ConnectedCells(data["color"], data["nonempty"])
    raise ValueError("Unknown component ID/version or invalid component fields")


def read_recipe(data: Any) -> Recipe:
    if not isinstance(data, dict) or set(data) != {"format", "base", "components"}:
        raise ValueError("Composed recipe must contain exactly format, base and components")
    if data["format"] != FORMAT:
        raise ValueError("Unsupported composed recipe format/version")
    base = read_base(data["base"])
    if base.rows * base.cols > MAX_CELLS:
        raise ValueError("Composed shading files support at most 9 cells")
    raw = data["components"]
    if not isinstance(raw, list) or len(raw) > MAX_COMPONENTS:
        raise ValueError("Components must be an array of at most 8 occurrences")
    components = tuple(_read_component(item) for item in raw)
    if any(type(c) is CellCount and c.count > base.rows * base.cols for c in components):
        raise ValueError("Component count cannot exceed the board area")
    return with_constraints(base, *components)


def recipe_record(recipe: Recipe) -> dict[str, Any]:
    # Do not call unknown builders or inspect their names/closures. Subclasses can
    # change behavior, so exact types are part of the serialization contract.
    if type(recipe) is not ConstrainedRecipe or type(recipe.base) is not ShadingRecipe:
        raise ValueError("Only an exact ConstrainedRecipe with a ShadingRecipe base can be saved")
    components = []
    for builder in recipe.builders:
        if type(builder) is CellCount:
            count = cast(CellCount, builder)
            components.append({"id": "cell-count/v1", "color": count.color, "count": count.count})
        elif type(builder) is ConnectedCells:
            group = cast(ConnectedCells, builder)
            components.append({"id": "connected-cells/v1", "color": group.color, "nonempty": group.nonempty})
        else:
            raise ValueError("Cannot save arbitrary Python builders or component subclasses")
    record = {"format": FORMAT, "base": base_record(recipe.base), "components": components}
    read_recipe(record)  # Apply identical schema/bounds on export, without solving.
    return record


def load_recipe(path: Path) -> Recipe:
    return read_recipe(load_json(path, label="Composed recipe"))
