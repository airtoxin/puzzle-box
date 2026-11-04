"""Strict data-only interchange for the small built-in shading recipes."""

from pathlib import Path
from typing import Any

from puzzle_defs import (BlackCount, ConnectedWhite, NonTouchingBlack, NoWhite2x2, ShadingRecipe,
                         BalancedLines, BlackDominoes, ConnectedBlack, DistinctLines,
                         NoBlack2x2, NoThreeConsecutive)
from puzzle_defs import RoomBlackCount, RoomConnectedBlack, LineBlackCount, NoWhiteAcrossThreeRooms
from puzzle_defs import RectangularComponents, NonRectangularComponents
from puzzle_defs import DistinctWhiteNumbers
from puzzle_defs import RunLengthLimit
from puzzle_defs import RoomRotationalSymmetry
from puzzle_defs import ColorComponentSize
from puzzle_defs.puzzles.component_size import MAX_COMPONENT_CELLS
from puzzle_defs.number_layout import DEFAULT_NUMBERS, NumberGrid, number_grid
from puzzle_defs.room_layout import DEFAULT_ROOMS, RoomMap, room_map
from puzzle_defs.puzzles.shading import CLUE_KINDS, ShadingRule
from json_records import MAX_BYTES as MAX_RECIPE_BYTES, load_json as _load_json

RECIPE_FORMAT = "puzzle-box/shading-recipe-v1"
MAX_RECIPE_RULES = 8
DEFAULT_RULES = ("count", "non-touching", "connected-white", "no-white-2x2")
PARAMETERLESS_RULE_TYPES = (NoWhite2x2, NoBlack2x2, BlackDominoes, NoThreeConsecutive,
                           BalancedLines, DistinctLines)
BUILT_IN_RULE_TYPES = (BlackCount, NonTouchingBlack, ConnectedWhite, NoWhite2x2,
                      ConnectedBlack, NoBlack2x2, BlackDominoes, NoThreeConsecutive,
                      BalancedLines, DistinctLines, RoomBlackCount, RoomConnectedBlack, LineBlackCount,
                      RectangularComponents, NonRectangularComponents, NoWhiteAcrossThreeRooms, DistinctWhiteNumbers,
                      RunLengthLimit, RoomRotationalSymmetry, ColorComponentSize)
RULES = tuple(kind.ui.identifier for kind in BUILT_IN_RULE_TYPES)


def rule_choices(*, count: int = 3, diagonal: bool = False, allow_empty_white: bool = False) -> dict[str, ShadingRule]:
    """CLI defaults, kept separate from the subset enabled by default."""
    return {"count": BlackCount(count), "non-touching": NonTouchingBlack(diagonal),
            "connected-white": ConnectedWhite(not allow_empty_white),
            "connected-black": ConnectedBlack(),
            "rectangular-components": RectangularComponents(),
            "nonrectangular-components": NonRectangularComponents(),
            "room-black-count": RoomBlackCount(DEFAULT_ROOMS),
            "room-connected-black": RoomConnectedBlack(DEFAULT_ROOMS), "line-black-count": LineBlackCount(),
            "no-white-across-three-rooms": NoWhiteAcrossThreeRooms(DEFAULT_ROOMS),
            "distinct-white-numbers": DistinctWhiteNumbers(DEFAULT_NUMBERS),
            "run-length-limit": RunLengthLimit(),
            "room-rotational-symmetry": RoomRotationalSymmetry(DEFAULT_ROOMS),
            "color-component-size": ColorComponentSize(3),
            **{kind.ui.identifier: kind() for kind in PARAMETERLESS_RULE_TYPES}}


def rule_record(rule: ShadingRule) -> dict[str, Any]:
    # A subclass may change apply(); serializing only its parent would lose rules.
    if type(rule) is BlackCount:
        return {"type": "count", "count": rule.count}
    if type(rule) is NonTouchingBlack:
        return {"type": "non-touching", "diagonal": rule.diagonal}
    if type(rule) is ConnectedWhite:
        return {"type": "connected-white", "nonempty": rule.nonempty}
    if type(rule) is ConnectedBlack:
        return {"type": "connected-black", "nonempty": rule.nonempty}
    if type(rule) is RoomBlackCount:
        return {"type": "room-black-count", "rooms": [list(row) for row in rule.rooms], "count": rule.count}
    if type(rule) is RoomConnectedBlack:
        return {"type": "room-connected-black", "rooms": [list(row) for row in rule.rooms], "nonempty": rule.nonempty}
    if type(rule) is LineBlackCount:
        return {"type": "line-black-count", "count": rule.count}
    if type(rule) is NoWhiteAcrossThreeRooms or type(rule) is RoomRotationalSymmetry:
        return {"type": rule.ui.identifier, "rooms": [list(row) for row in rule.rooms]}
    if type(rule) is DistinctWhiteNumbers:
        return {"type": rule.ui.identifier, "numbers": [list(row) for row in rule.numbers]}
    if type(rule) is RunLengthLimit:
        return {"type": rule.ui.identifier, "max_length": rule.max_length}
    if type(rule) is ColorComponentSize:
        return {"type": rule.ui.identifier, "size": rule.size, "black": rule.black}
    if type(rule) is RectangularComponents or type(rule) is NonRectangularComponents:
        return {"type": rule.ui.identifier, "black": rule.black}
    for kind in PARAMETERLESS_RULE_TYPES:
        if type(rule) is kind:
            return {"type": kind.ui.identifier}
    raise ValueError("This file format supports exact built-in shading rules only, not subclasses")


def read_rule(data: Any) -> ShadingRule:
    if not isinstance(data, dict):
        raise ValueError("A rule must be an object")
    kind = data.get("type")
    if kind == "count" and set(data) == {"type", "count"}:
        return BlackCount(data["count"])
    if kind == "non-touching" and set(data) == {"type", "diagonal"}:
        return NonTouchingBlack(data["diagonal"])
    if kind == "connected-white" and set(data) == {"type", "nonempty"}:
        return ConnectedWhite(data["nonempty"])
    if kind == "connected-black" and set(data) == {"type", "nonempty"}:
        return ConnectedBlack(data["nonempty"])
    if kind in ("room-black-count", "room-connected-black"):
        parameter = "count" if kind == "room-black-count" else "nonempty"
        if (set(data) != {"type", "rooms", parameter} or type(data["rooms"]) is not list
                or any(type(row) is not list for row in data["rooms"])):
            raise ValueError("Invalid room rule parameters; rooms must be an array of arrays")
        if kind == "room-black-count":
            return RoomBlackCount(tuple(tuple(row) for row in data["rooms"]), data["count"])
        return RoomConnectedBlack(tuple(tuple(row) for row in data["rooms"]), data["nonempty"])
    if kind == "line-black-count" and set(data) == {"type", "count"}:
        return LineBlackCount(data["count"])
    if kind == "run-length-limit" and set(data) == {"type", "max_length"}:
        return RunLengthLimit(data["max_length"])
    if kind == "color-component-size" and set(data) == {"type","size","black"}:
        return ColorComponentSize(data["size"],data["black"])
    if kind in ("no-white-across-three-rooms","room-rotational-symmetry"):
        if (set(data) != {"type", "rooms"} or type(data["rooms"]) is not list
                or any(type(row) is not list for row in data["rooms"])):
            raise ValueError("Invalid room rule parameters; rooms must be an array of arrays")
        constructor = NoWhiteAcrossThreeRooms if kind == "no-white-across-three-rooms" else RoomRotationalSymmetry
        return constructor(tuple(tuple(row) for row in data["rooms"]))
    if kind == "distinct-white-numbers":
        if (set(data) != {"type","numbers"} or type(data["numbers"]) is not list
                or any(type(row) is not list for row in data["numbers"])):
            raise ValueError("Fixed numbers must be an array of arrays")
        return DistinctWhiteNumbers(tuple(tuple(row) for row in data["numbers"]))
    for shape_rule in (RectangularComponents, NonRectangularComponents):
        if kind == shape_rule.ui.identifier and set(data) == {"type", "black"}:
            return shape_rule(data["black"])
    for rule_type in PARAMETERLESS_RULE_TYPES:
        if kind == rule_type.ui.identifier and set(data) == {"type"}:
            return rule_type()
    raise ValueError("Unknown rule or invalid rule parameters")


def check_demo_size(recipe: ShadingRecipe) -> None:
    if recipe.rows * recipe.cols > 25:
        raise ValueError("This small-board demo supports at most 25 cells")


def shared_rooms(recipe: ShadingRecipe) -> RoomMap | None:
    layouts = [rule.rooms for rule in recipe.rules
               if type(rule) is RoomBlackCount or type(rule) is RoomConnectedBlack
               or type(rule) is NoWhiteAcrossThreeRooms or type(rule) is RoomRotationalSymmetry]
    for layout in layouts:
        room_map(layout, rows=recipe.rows, cols=recipe.cols)
    if layouts and any(layout != layouts[0] for layout in layouts):
        raise ValueError("Room rules must share the same partition for this file/UI format")
    return layouts[0] if layouts else None


def read_recipe(data: Any) -> ShadingRecipe:
    fields = {"format", "rows", "cols", "rules", "clue_kinds"}
    if not isinstance(data, dict) or set(data) != fields:
        raise ValueError("Recipe must contain exactly format, rows, cols, rules and clue_kinds")
    if data["format"] != RECIPE_FORMAT:
        raise ValueError("Unsupported recipe format; puzzle artifacts and exploration reports are not recipes")
    if not isinstance(data["rules"], list) or len(data["rules"]) > MAX_RECIPE_RULES:
        raise ValueError("Recipe rules must be an array of at most 8 rule occurrences")
    kinds = data["clue_kinds"]
    if not isinstance(kinds, list) or any(type(k) is not str or k not in CLUE_KINDS for k in kinds):
        raise ValueError("Recipe clue_kinds must be an array of cell, row-count or column-count values")
    recipe = ShadingRecipe(data["rows"], data["cols"], tuple(read_rule(r) for r in data["rules"]), tuple(kinds))
    check_demo_size(recipe)
    for rule in recipe.rules:
        if type(rule) is ColorComponentSize:
            if recipe.rows*recipe.cols > MAX_COMPONENT_CELLS:
                raise ValueError(f"Fixed component sizes support at most {MAX_COMPONENT_CELLS} board cells")
            if rule.size > recipe.rows*recipe.cols:
                raise ValueError("Component size cannot exceed the board area")
    shared_rooms(recipe)
    shared_numbers(recipe)
    if any((type(r) is BlackCount or type(r) is RoomBlackCount or type(r) is LineBlackCount)
           and r.count > recipe.rows * recipe.cols for r in recipe.rules):
        raise ValueError("Black count cannot exceed the board area")
    return recipe


def shared_numbers(recipe: ShadingRecipe) -> NumberGrid | None:
    grids = [rule.numbers for rule in recipe.rules if type(rule) is DistinctWhiteNumbers]
    for grid in grids:
        number_grid(grid,rows=recipe.rows,cols=recipe.cols)
    if grids and any(grid != grids[0] for grid in grids):
        raise ValueError("Number rules must share the same fixed numbers for this file/UI format")
    return grids[0] if grids else None


def recipe_record(recipe: ShadingRecipe) -> dict[str, Any]:
    if type(recipe) is not ShadingRecipe:
        raise ValueError("This format requires an exact ShadingRecipe; composed recipes and subclasses need their own codec")
    record = {"format": RECIPE_FORMAT, "rows": recipe.rows, "cols": recipe.cols,
              "rules": [rule_record(r) for r in recipe.rules], "clue_kinds": list(recipe.clue_kinds)}
    read_recipe(record)  # Enforce the same bounds for export and import.
    return record


def load_json(path: Path, *, label: str = "Recipe") -> Any:
    """Read bounded JSON without silently accepting duplicate fields or NaN."""
    return _load_json(path, label=label)


def load_recipe(path: Path) -> ShadingRecipe:
    return read_recipe(load_json(path))


def check_distinct_paths(first: Path, second: Path) -> None:
    if first.resolve() == second.resolve() or (first.exists() and second.exists() and first.samefile(second)):
        raise ValueError("Input and output must use different files")
