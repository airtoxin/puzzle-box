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
from puzzle_defs import NoTouchingEqualTetrominoes
from puzzle_defs import WhiteVisibilityCounts
from puzzle_defs import ComponentsTouchBorder
from puzzle_defs import WhiteIslandAreas, WhiteAreaClues
from puzzle_defs import AdjacentBlackCounts
from puzzle_defs import ColorDegreeRange, ColorEndpointCount
from puzzle_defs import AdjacentBlackComponentSum
from puzzle_defs import UniformRooms, AcyclicColor, RoomFillLevels
from puzzle_defs import NoColorAcrossRooms, AdjacentRoomCountsDiffer
from puzzle_defs import CornerConnectedColor, WhiteEndpointMarkers, AdjacentBlackRuns
from puzzle_defs.marker_layout import DEFAULT_ENDPOINT_MARKERS, MarkerGrid, marker_grid
from puzzle_defs.run_clue_layout import DEFAULT_BLACK_RUN_CLUES, RunClueGrid, run_clue_grid
from puzzle_defs.puzzles.adjacent_black_component_sum import DEFAULT_COMPONENT_COUNTS
from puzzle_defs.clue_layout import ClueGrid, clue_grid
from puzzle_defs.puzzles.adjacent_black_counts import DEFAULT_NEIGHBOR_COUNTS
from puzzle_defs.puzzles.white_island_areas import DEFAULT_ISLAND_AREAS
from puzzle_defs.puzzles.white_visibility import DEFAULT_SIGHT_COUNTS
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
                      RunLengthLimit, RoomRotationalSymmetry, ColorComponentSize, NoTouchingEqualTetrominoes, WhiteVisibilityCounts,
                      ComponentsTouchBorder, WhiteIslandAreas, AdjacentBlackCounts, ColorDegreeRange, ColorEndpointCount,
                      AdjacentBlackComponentSum, UniformRooms, AcyclicColor, CornerConnectedColor, WhiteAreaClues, WhiteEndpointMarkers, AdjacentBlackRuns, RoomFillLevels,
                      NoColorAcrossRooms, AdjacentRoomCountsDiffer)
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
            "no-touching-equal-tetrominoes": NoTouchingEqualTetrominoes(DEFAULT_ROOMS),
            "white-visibility-counts": WhiteVisibilityCounts(DEFAULT_SIGHT_COUNTS),
            "components-touch-border": ComponentsTouchBorder(),
            "white-area-clues": WhiteAreaClues(DEFAULT_ISLAND_AREAS),
            "white-island-areas": WhiteIslandAreas(DEFAULT_ISLAND_AREAS),
            "adjacent-black-counts": AdjacentBlackCounts(DEFAULT_NEIGHBOR_COUNTS),
            "color-degree-range": ColorDegreeRange(), "color-endpoint-count": ColorEndpointCount(),
            "adjacent-black-runs": AdjacentBlackRuns(DEFAULT_BLACK_RUN_CLUES),
            "white-endpoint-markers": WhiteEndpointMarkers(DEFAULT_ENDPOINT_MARKERS),
            "corner-connected-color": CornerConnectedColor(),
            "uniform-rooms": UniformRooms(DEFAULT_ROOMS), "acyclic-color": AcyclicColor(),
            "room-fill-levels": RoomFillLevels(DEFAULT_ROOMS),
            "no-color-across-rooms": NoColorAcrossRooms(DEFAULT_ROOMS),
            "adjacent-room-counts-differ": AdjacentRoomCountsDiffer(DEFAULT_ROOMS),
            "adjacent-black-component-sum": AdjacentBlackComponentSum(DEFAULT_COMPONENT_COUNTS),
            **{kind.ui.identifier: kind() for kind in PARAMETERLESS_RULE_TYPES}}


def rule_record(rule: ShadingRule) -> dict[str, Any]:
    # A subclass may change apply(); serializing only its parent would lose rules.
    if type(rule) is RoomFillLevels or type(rule) is NoColorAcrossRooms or type(rule) is AdjacentRoomCountsDiffer:
        return {"type": rule.ui.identifier, "rooms": [list(row) for row in rule.rooms], "black": rule.black}
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
    if type(rule) is NoWhiteAcrossThreeRooms or type(rule) is RoomRotationalSymmetry or type(rule) is NoTouchingEqualTetrominoes or type(rule) is UniformRooms:
        return {"type": rule.ui.identifier, "rooms": [list(row) for row in rule.rooms]}
    if type(rule) is DistinctWhiteNumbers:
        return {"type": rule.ui.identifier, "numbers": [list(row) for row in rule.numbers]}
    if type(rule) is WhiteVisibilityCounts:
        return {"type": rule.ui.identifier, "counts": [list(row) for row in rule.counts]}
    if type(rule) is WhiteIslandAreas or type(rule) is WhiteAreaClues:
        return {"type": rule.ui.identifier, "areas": [list(row) for row in rule.areas]}
    if type(rule) is AdjacentBlackCounts:
        return {"type": rule.ui.identifier, "neighbor_counts": [list(row) for row in rule.neighbor_counts], "diagonal": rule.diagonal}
    if type(rule) is ColorDegreeRange:
        return {"type": rule.ui.identifier, "minimum": rule.minimum, "maximum": rule.maximum, "black": rule.black}
    if type(rule) is AdjacentBlackRuns:
        return {"type": rule.ui.identifier, "run_clues": [[list(c) if c is not None else None for c in row] for row in rule.run_clues]}
    if type(rule) is WhiteEndpointMarkers:
        return {"type": rule.ui.identifier, "markers": [list(row) for row in rule.markers]}
    if type(rule) is CornerConnectedColor:
        return {"type": rule.ui.identifier, "black": rule.black, "nonempty": rule.nonempty}
    if type(rule) is AcyclicColor:
        return {"type": rule.ui.identifier, "black": rule.black}
    if type(rule) is ColorEndpointCount:
        return {"type": rule.ui.identifier, "count": rule.count, "black": rule.black}
    if type(rule) is AdjacentBlackComponentSum:
        return {"type": rule.ui.identifier, "component_counts": [list(row) for row in rule.component_counts]}
    if type(rule) is RunLengthLimit:
        return {"type": rule.ui.identifier, "max_length": rule.max_length}
    if type(rule) is ColorComponentSize:
        return {"type": rule.ui.identifier, "size": rule.size, "black": rule.black}
    if type(rule) is ComponentsTouchBorder:
        return {"type": rule.ui.identifier, "black": rule.black}
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
    if kind == "color-degree-range" and set(data) == {"type", "minimum", "maximum", "black"}:
        return ColorDegreeRange(data["minimum"], data["maximum"], data["black"])
    if kind == "color-endpoint-count" and set(data) == {"type", "count", "black"}:
        return ColorEndpointCount(data["count"], data["black"])
    if kind == "corner-connected-color" and set(data) == {"type", "black", "nonempty"}:
        return CornerConnectedColor(data["black"], data["nonempty"])
    if kind == "acyclic-color" and set(data) == {"type", "black"}:
        return AcyclicColor(data["black"])
    if kind == "components-touch-border" and set(data) == {"type", "black"}:
        return ComponentsTouchBorder(data["black"])
    if kind in ("room-fill-levels","no-color-across-rooms","adjacent-room-counts-differ"):
        if (set(data) != {"type", "rooms", "black"} or type(data["rooms"]) is not list
                or any(type(row) is not list for row in data["rooms"])):
            raise ValueError("This room rule requires rooms and a color")
        constructor = {"room-fill-levels":RoomFillLevels,"no-color-across-rooms":NoColorAcrossRooms,
                       "adjacent-room-counts-differ":AdjacentRoomCountsDiffer}[kind]
        return constructor(room_map(data["rooms"]), data["black"])
    if kind in ("no-white-across-three-rooms","room-rotational-symmetry","no-touching-equal-tetrominoes","uniform-rooms"):
        if (set(data) != {"type", "rooms"} or type(data["rooms"]) is not list
                or any(type(row) is not list for row in data["rooms"])):
            raise ValueError("Invalid room rule parameters; rooms must be an array of arrays")
        constructor = {"no-white-across-three-rooms":NoWhiteAcrossThreeRooms,
                       "room-rotational-symmetry":RoomRotationalSymmetry,
                       "no-touching-equal-tetrominoes":NoTouchingEqualTetrominoes,
                       "uniform-rooms":UniformRooms}[kind]
        return constructor(tuple(tuple(row) for row in data["rooms"]))
    if kind == "distinct-white-numbers":
        if (set(data) != {"type","numbers"} or type(data["numbers"]) is not list
                or any(type(row) is not list for row in data["numbers"])):
            raise ValueError("Fixed numbers must be an array of arrays")
        return DistinctWhiteNumbers(tuple(tuple(row) for row in data["numbers"]))
    if kind == "white-visibility-counts":
        if (set(data) != {"type", "counts"} or type(data["counts"]) is not list
                or any(type(row) is not list for row in data["counts"])):
            raise ValueError("Sight counts must be an array of arrays")
        return WhiteVisibilityCounts(tuple(tuple(row) for row in data["counts"]))
    if kind == "adjacent-black-runs":
        if (set(data) != {"type", "run_clues"} or type(data["run_clues"]) is not list
                or any(type(row) is not list for row in data["run_clues"])
                or any(c is not None and type(c) is not list for row in data["run_clues"] for c in row)):
            raise ValueError("Run clues must be an array of rows of arrays or null")
        return AdjacentBlackRuns(run_clue_grid(data["run_clues"]))
    if kind == "white-endpoint-markers":
        if (set(data) != {"type", "markers"} or type(data["markers"]) is not list
                or any(type(row) is not list for row in data["markers"])):
            raise ValueError("Endpoint markers must be an array of arrays")
        return WhiteEndpointMarkers(tuple(tuple(row) for row in data["markers"]))
    if kind in ("white-island-areas", "white-area-clues"):
        if (set(data) != {"type", "areas"} or type(data["areas"]) is not list
                or any(type(row) is not list for row in data["areas"])):
            raise ValueError("Island areas must be an array of arrays")
        constructor = WhiteIslandAreas if kind == "white-island-areas" else WhiteAreaClues
        return constructor(tuple(tuple(row) for row in data["areas"]))
    if kind == "adjacent-black-counts":
        if (set(data) != {"type", "neighbor_counts", "diagonal"} or type(data["neighbor_counts"]) is not list
                or any(type(row) is not list for row in data["neighbor_counts"])):
            raise ValueError("Neighbor counts must be an array of arrays")
        return AdjacentBlackCounts(tuple(tuple(row) for row in data["neighbor_counts"]), data["diagonal"])
    if kind == "adjacent-black-component-sum":
        if (set(data) != {"type", "component_counts"} or type(data["component_counts"]) is not list
                or any(type(row) is not list for row in data["component_counts"])):
            raise ValueError("Black component sums must be an array of arrays")
        return AdjacentBlackComponentSum(tuple(tuple(row) for row in data["component_counts"]))
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
               or type(rule) is NoWhiteAcrossThreeRooms or type(rule) is RoomRotationalSymmetry
               or type(rule) is NoTouchingEqualTetrominoes or type(rule) is UniformRooms or type(rule) is RoomFillLevels
               or type(rule) is NoColorAcrossRooms or type(rule) is AdjacentRoomCountsDiffer]
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
    shared_sight_counts(recipe)
    shared_island_areas(recipe)
    shared_endpoint_markers(recipe)
    shared_black_runs(recipe)
    shared_neighbor_counts(recipe)
    shared_component_counts(recipe)
    if any((type(r) is BlackCount or type(r) is RoomBlackCount or type(r) is LineBlackCount)
           and r.count > recipe.rows * recipe.cols for r in recipe.rules):
        raise ValueError("Black count cannot exceed the board area")
    if any(type(r) is ColorEndpointCount and r.count > recipe.rows * recipe.cols for r in recipe.rules):
        raise ValueError("Endpoint count cannot exceed the board area")
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


def shared_sight_counts(recipe: ShadingRecipe) -> NumberGrid | None:
    grids = [rule.counts for rule in recipe.rules if type(rule) is WhiteVisibilityCounts]
    for grid in grids:
        number_grid(grid, rows=recipe.rows, cols=recipe.cols)
    if grids and any(grid != grids[0] for grid in grids):
        raise ValueError("Visibility rules must share the same sight counts for this file/UI format")
    return grids[0] if grids else None


def shared_island_areas(recipe: ShadingRecipe) -> NumberGrid | None:
    grids = [rule.areas for rule in recipe.rules if type(rule) is WhiteIslandAreas or type(rule) is WhiteAreaClues]
    for grid in grids:
        number_grid(grid, rows=recipe.rows, cols=recipe.cols)
    if grids and any(grid != grids[0] for grid in grids):
        raise ValueError("Island rules must share the same areas for this file/UI format")
    return grids[0] if grids else None


def shared_neighbor_counts(recipe: ShadingRecipe) -> ClueGrid | None:
    grids = [rule.neighbor_counts for rule in recipe.rules if type(rule) is AdjacentBlackCounts]
    for grid in grids:
        clue_grid(grid, rows=recipe.rows, cols=recipe.cols, maximum=8)
    if grids and any(grid != grids[0] for grid in grids):
        raise ValueError("Adjacent-count rules must share the same neighbor counts for this file/UI format")
    return grids[0] if grids else None


def shared_component_counts(recipe: ShadingRecipe) -> ClueGrid | None:
    grids = [rule.component_counts for rule in recipe.rules if type(rule) is AdjacentBlackComponentSum]
    for grid in grids:
        clue_grid(grid, rows=recipe.rows, cols=recipe.cols)
    if grids and any(grid != grids[0] for grid in grids):
        raise ValueError("Component-sum rules must share the same counts for this file/UI format")
    return grids[0] if grids else None


def load_json(path: Path, *, label: str = "Recipe") -> Any:
    """Read bounded JSON without silently accepting duplicate fields or NaN."""
    return _load_json(path, label=label)


def load_recipe(path: Path) -> ShadingRecipe:
    return read_recipe(load_json(path))


def check_distinct_paths(first: Path, second: Path) -> None:
    if first.resolve() == second.resolve() or (first.exists() and second.exists() and first.samefile(second)):
        raise ValueError("Input and output must use different files")


def shared_endpoint_markers(recipe: ShadingRecipe) -> MarkerGrid | None:
    grids = [rule.markers for rule in recipe.rules if type(rule) is WhiteEndpointMarkers]
    for grid in grids:
        marker_grid(grid, rows=recipe.rows, cols=recipe.cols)
    if grids and any(grid != grids[0] for grid in grids):
        raise ValueError("Endpoint rules must share the same markers for this file/UI format")
    return grids[0] if grids else None


def shared_black_runs(recipe: ShadingRecipe) -> RunClueGrid | None:
    grids = [rule.run_clues for rule in recipe.rules if type(rule) is AdjacentBlackRuns]
    for grid in grids:
        run_clue_grid(grid, rows=recipe.rows, cols=recipe.cols)
    if grids and any(grid != grids[0] for grid in grids):
        raise ValueError("Black-run rules must share the same clues for this file/UI format")
    return grids[0] if grids else None
