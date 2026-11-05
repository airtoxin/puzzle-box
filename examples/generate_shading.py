"""Generate, display, check and verify small composed shading puzzles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import sys
import time
from typing import Any

import ortools

from generator import InitialCluesNotUniqueError, generate
from puzzle import Cell, unique
from puzzle_defs import (
    BlackCount, ConnectedWhite, NonTouchingBlack, NoWhite2x2,
    ColumnCountClue, RowCountClue, ShadingRecipe,
    BalancedLines, BlackDominoes, ConnectedBlack, DistinctLines, NoBlack2x2, NoThreeConsecutive,
    RoomBlackCount, RoomConnectedBlack, LineBlackCount, NoWhiteAcrossThreeRooms,
    RectangularComponents, NonRectangularComponents,
    DistinctWhiteNumbers,
    RunLengthLimit,
    DiagonalRunLimit,
    UnequalCornerComponentSizes,
    RoomRotationalSymmetry,
    ColorComponentSize,
    NoTouchingEqualTetrominoes,
    WhiteVisibilityCounts,
    ComponentsTouchBorder,
    WhiteIslandAreas, WhiteAreaClues, WhiteEndpointMarkers, AdjacentBlackRuns,
    AdjacentBlackCounts, OrthogonalBlackCounts,
    ColorDegreeRange, ColorEndpointCount,
    AdjacentBlackComponentSum, UniformRooms, AcyclicColor, CornerConnectedColor, RoomFillLevels,
    NoColorAcrossRooms, AdjacentRoomCountsDiffer,
    RoomComponentCount, EqualRoomComponentSizes,
    ComponentAreaClues,
    CornerLinkedComponents, OneFalseAdjacentCountPerRoom, DirectionalRunLimit, RoomMajorityCount,
)
from puzzle_defs.puzzles.shading import CLUE_KINDS, Clue, ShadingRule
from puzzle_defs.room_layout import RoomMap
from puzzle_defs.number_layout import NumberGrid
from puzzle_defs.clue_layout import ClueGrid
from puzzle_defs.run_clue_layout import RunClueGrid
from shading_recipe import (RULES, DEFAULT_RULES, rule_choices, check_demo_size, check_distinct_paths,
                            load_recipe, read_rule, rule_record, shared_rooms, shared_numbers,
                            shared_sight_counts, shared_island_areas, shared_neighbor_counts, shared_component_counts, shared_endpoint_markers, shared_black_runs, shared_component_areas, shared_orthogonal_counts)
from json_records import encode_json, load_json, read_array

FORMAT = "puzzle-box/shading-v1"
MIXED_FORMAT = "puzzle-box/shading-v2"


def _check_clue_kinds(recipe: ShadingRecipe, clues: list[Clue]) -> None:
    for clue in clues:
        kind = "row-count" if isinstance(clue, RowCountClue) else (
            "column-count" if isinstance(clue, ColumnCountClue) else "cell")
        if kind not in recipe.clue_kinds:
            raise ValueError("Stored clue type is not enabled by clue_kinds")


def _check_irreducible(recipe: ShadingRecipe, clues: list[Clue], *, deadline: float | None = None) -> None:
    for idx in range(len(clues)):
        trial = recipe.build_from_clues(clues[:idx] + clues[idx + 1:])
        result = trial.solve_result(check_unique=True,
            time_limit=None if deadline is None else max(0.0, deadline-time.monotonic()))
        if result.uniqueness == "unique":
            raise ValueError("Stored clues are not irreducible: a clue can still be removed")
        if result.uniqueness != "multiple":
            raise TimeoutError("Clue necessity was not proven")


def puzzle_record(recipe: ShadingRecipe, clues: list[Clue], *, seed: int,
                  selection: str = "solver", time_limit: float | None = None) -> dict[str, Any]:
    """Serialize a unique, irreducible puzzle accepted by the built-in reader."""
    deadline = None if time_limit is None else time.monotonic() + time_limit
    if type(recipe) is not ShadingRecipe:
        raise ValueError("This format requires an exact ShadingRecipe; composed recipes and subclasses need their own codec")
    check_demo_size(recipe)
    if selection not in ("solver", "finite"):
        raise ValueError("Unknown completion selection")
    rules = [rule_record(rule) for rule in recipe.rules]
    shared_rooms(recipe)
    shared_numbers(recipe)
    shared_sight_counts(recipe)
    shared_island_areas(recipe)
    shared_endpoint_markers(recipe)
    shared_black_runs(recipe)
    shared_component_areas(recipe)
    shared_orthogonal_counts(recipe)
    shared_neighbor_counts(recipe)
    shared_component_counts(recipe)
    _check_clue_kinds(recipe, clues)
    legacy = recipe.clue_kinds == ("cell",)
    encoded_clues = [clue_record(clue, legacy=legacy) for clue in clues]
    # Validate the exact saved representation before solving. Python considers
    # bool/float coordinates equal to ints, but the file format rejects them.
    clues = [read_clue(clue, legacy=legacy) for clue in encoded_clues]
    puzzle = recipe.build_from_clues(clues)
    result = puzzle.solve_result(seed=seed, check_unique=True,
        time_limit=None if deadline is None else max(0.0, deadline-time.monotonic()))
    if result.status == "unknown" or result.uniqueness == "unknown":
        raise TimeoutError("Uniqueness was not proven")
    solution = result.solution
    if result.uniqueness != "unique" or solution is None:
        raise ValueError("Generated clues did not determine a unique answer")
    _check_irreducible(recipe, clues, deadline=deadline)
    return encode_record(recipe, clues, puzzle.result(solution), seed=seed, selection=selection)


def encode_record(recipe: ShadingRecipe, clues: list[Clue], answer: list[list[int]], *, seed: int,
                  selection: str = "solver") -> dict[str, Any]:
    """Encode an already verified result, without repeating solver queries.

    This is serialization only. Call puzzle_record to verify arbitrary clues;
    bounded generation supplies its own uniqueness and irreducibility proofs.
    """
    legacy = recipe.clue_kinds == ("cell",)
    record = {
        "format": FORMAT if legacy else MIXED_FORMAT,
        "rows": recipe.rows, "cols": recipe.cols,
        "rules": [rule_record(rule) for rule in recipe.rules], "seed": seed,
        "clues": [clue_record(clue, legacy=legacy) for clue in clues],
        "solution": answer,
        "environment": {"python": platform.python_version(), "ortools": ortools.__version__,
                        "seeded_search_workers": 1},
    }
    if not legacy:
        record["clue_kinds"] = list(recipe.clue_kinds)
    if selection == "finite":
        from finite_shading import SELECTION
        record["environment"]["completion_selection"] = SELECTION
    return record


def clue_record(clue: Clue, *, legacy: bool = False) -> dict[str, Any] | list[int]:
    if isinstance(clue, tuple):
        cell, value = clue
        if legacy:
            return [cell.row, cell.col, value]
        return {"type": "cell", "row": cell.row, "col": cell.col, "value": value}
    if legacy:
        raise ValueError("The v1 format supports cell clues only")
    if isinstance(clue, RowCountClue):
        return {"type": "row-count", "row": clue.row, "count": clue.count}
    return {"type": "column-count", "col": clue.col, "count": clue.count}


def read_clue(data: Any, *, legacy: bool = False) -> Clue:
    if legacy:
        if not isinstance(data, list) or len(data) != 3:
            raise ValueError("A v1 cell clue must be an array of row, column and value")
        row, col, value = data
    elif isinstance(data, dict):
        if data.get("type") == "row-count" and set(data) == {"type", "row", "count"}:
            return RowCountClue(data["row"], data["count"])
        if data.get("type") == "column-count" and set(data) == {"type", "col", "count"}:
            return ColumnCountClue(data["col"], data["count"])
        if data.get("type") != "cell" or set(data) != {"type", "row", "col", "value"}:
            raise ValueError("Unknown clue type or invalid clue fields")
        row, col, value = data["row"], data["col"], data["value"]
    else:
        raise ValueError("A v2 clue must be an object")
    if type(row) is not int or type(col) is not int:
        raise ValueError("Clue coordinates must be integers")
    return (Cell(row, col), value)


def _read_record(data: dict[str, Any]) -> tuple[ShadingRecipe, list[Clue], list[list[int]]]:
    if not isinstance(data, dict) or data.get("format") not in (FORMAT, MIXED_FORMAT):
        raise ValueError(f"Unsupported puzzle format; expected an object with format {FORMAT} or {MIXED_FORMAT}")
    legacy = data["format"] == FORMAT
    required = {"format", "rows", "cols", "rules", "clues", "solution"}
    if not legacy:
        required.add("clue_kinds")
    if not required <= set(data) or set(data) - required - {"seed", "environment"}:
        raise ValueError("Missing or unknown puzzle fields; additional rules need a supported composed format")
    recipe = ShadingRecipe(data["rows"], data["cols"],
                           tuple(read_rule(r) for r in read_array(data["rules"], "rules")),
                           ("cell",) if legacy else tuple(read_array(data["clue_kinds"], "clue_kinds")))
    check_demo_size(recipe)
    shared_rooms(recipe)
    shared_numbers(recipe)
    shared_sight_counts(recipe)
    shared_island_areas(recipe)
    shared_endpoint_markers(recipe)
    shared_black_runs(recipe)
    shared_component_areas(recipe)
    shared_orthogonal_counts(recipe)
    shared_neighbor_counts(recipe)
    shared_component_counts(recipe)
    clues = [read_clue(clue, legacy=legacy) for clue in read_array(data["clues"], "clues")]
    _check_clue_kinds(recipe, clues)
    answer = data["solution"]
    if (not isinstance(answer, list) or len(answer) != recipe.rows
            or any(not isinstance(row, list) or len(row) != recipe.cols
                   or any(type(v) is not int or v not in (0, 1) for v in row) for row in answer)):
        raise ValueError("Invalid solution grid")
    return recipe, clues, answer


def verify(data: dict[str, Any]) -> dict[str, Any]:
    recipe, clues, answer = _read_record(data)
    puzzle = recipe.build_from_clues(clues)
    puzzle.add(unique())
    solution = puzzle.solve()
    if solution is None:
        raise ValueError("Stored clues are not uniquely solvable")
    if puzzle.result(solution) != answer:
        raise ValueError("Stored solution does not match the uniquely determined answer")
    _check_irreducible(recipe, clues)
    return {"valid": True, "unique": True, "irreducible": True, "clue_count": len(clues)}


def _rule_text(rule: ShadingRule) -> str:
    if type(rule) is UnequalCornerComponentSizes:
        color = "black" if rule.black else "white"
        return f"Distinct orthogonal {color} components touching at a corner have different areas; internal corners and separated equal components are allowed. Shape is unrestricted by this rule."
    if isinstance(rule, BlackCount):
        subject = "cell is" if rule.count == 1 else "cells are"
        return f"Exactly {rule.count} {subject} black."
    if isinstance(rule, NonTouchingBlack):
        contact = "an edge or a corner" if rule.diagonal else "an edge"
        return f"Black cells must not share {contact}."
    if isinstance(rule, ConnectedWhite):
        empty = "at least one must be white" if rule.nonempty else "zero white cells are allowed"
        return f"All white cells connect through edges; {empty}."
    if isinstance(rule, NoWhite2x2):
        return "Every 2x2 block contains at least one black cell."
    if type(rule) is ConnectedBlack:
        empty = "at least one must be black" if rule.nonempty else "zero black cells are allowed"
        return f"All black cells connect through edges; {empty}."
    if type(rule) is NoBlack2x2:
        return "Every 2x2 block contains at least one white cell."
    if type(rule) is BlackDominoes:
        return "Every edge-connected black component has exactly two cells; zero components and diagonal contact are allowed."
    if type(rule) is NoThreeConsecutive:
        return "No row or column contains three consecutive cells of the same color."
    if type(rule) is BalancedLines:
        return "Every row and column contains equal numbers of black and white cells."
    if type(rule) is DistinctLines:
        return "Rows differ from other rows, and columns from other columns; a row may equal a column."
    if type(rule) is RoomBlackCount:
        return f"Every room contains exactly {rule.count} black cells."
    if type(rule) is RoomConnectedBlack:
        empty = "at least one per room" if rule.nonempty else "empty rooms allowed"
        return f"Black cells connect inside each room without leaving it; {empty}."
    if type(rule) is LineBlackCount:
        return f"Every row and every column contains exactly {rule.count} black cells."
    if type(rule) is NoWhiteAcrossThreeRooms:
        return "A straight white run cannot cross two room boundaries; re-entering a room counts again."
    if type(rule) is DistinctWhiteNumbers:
        return "No row or column contains equal fixed numbers on two white cells."
    if type(rule) is WhiteVisibilityCounts:
        return "Positive sight counts require white cells and count visible white cells in four straight directions, including themselves once, stopping before black cells or the border; zero is no requirement."
    if type(rule) is AdjacentBlackRuns:
        return "Clue cells are white. The cyclic eight-neighbor black-run lengths match each unordered clue multiset; outside cells break runs, zero means no adjacent black, and absent cells have no clue."
    if type(rule) is WhiteEndpointMarkers:
        return "Circles are white with exactly one orthogonal white neighbor; no other white cell may have degree one. Isolated white cells are not endpoints. Compose a separate visibility rule for numbered straight-run lengths."
    if type(rule) is WhiteAreaClues:
        return "Numbered cells are white. Each white component has zero or one number; if present it equals the area. Unnumbered components are allowed; zero means no number."
    if type(rule) is WhiteIslandAreas:
        return "Every white island contains exactly one positive area number and that many cells; numbered cells are white, and zero means no number."
    if type(rule) is OrthogonalBlackCounts:
        return "Every orthogonal count equals the black cells on its four sides, excluding itself and diagonals. Numbered cells may be black or white; zero is a real clue and null means absent."
    if type(rule) is DirectionalRunLimit:
        horizontal = "black" if rule.horizontal_black else "white"
        vertical = "white" if rule.horizontal_black else "black"
        return f"Treat {horizontal} as horizontal and {vertical} as vertical. Their straight runs perpendicular to that direction have length at most {rule.max_length}; parallel runs are unrestricted. Answers remain black/white cells, not edges."
    if type(rule) is RoomMajorityCount:
        return f"In every room the larger of its black and white counts is {rule.count}. Ties are allowed, and the majority color may differ between rooms."
    if type(rule) is OneFalseAdjacentCountPerRoom:
        return "Numbered cells are white. In every room exactly one given count differs from its four orthogonally adjacent black cells; all other counts are correct. Neighbors across room borders count; zero is a clue, and a room without clues is unsatisfiable."
    if type(rule) is AdjacentBlackCounts:
        neighbors = "eight surrounding" if rule.diagonal else "four orthogonally adjacent"
        return f"Numbered cells are white and count black cells in the {neighbors} cells, excluding themselves; zero is a real clue, and absent entries impose no condition."
    if type(rule) is ColorDegreeRange:
        color = "black" if rule.black else "white"
        return f"Every {color} cell has {rule.minimum}..{rule.maximum} orthogonally adjacent {color} cells; no connectivity or nonemptiness is implied."
    if type(rule) is ColorEndpointCount:
        color = "black" if rule.black else "white"
        return f"Exactly {rule.count} {color} cells have one orthogonal {color} neighbor; isolated cells are not endpoints, and branches or cycles are not excluded."
    if type(rule) is CornerConnectedColor:
        color = "black" if rule.black else "white"
        empty = "at least one is required" if rule.nonempty else "absence is allowed"
        return f"All {color} cells connect through edges or corners (eight neighbors); {empty}. Other rules still use their own adjacency definitions."
    if type(rule) is CornerLinkedComponents:
        color = "black" if rule.black else "white"
        return f"Every orthogonal {color} component touches a different component at a corner; empty color sets and multiple chains are allowed, and shapes are not compared."
    if type(rule) is ComponentAreaClues:
        return "Each positive clue fixes the area of its own same-color component; clue cells may be black or white, zero is absent, and repeated/unnumbered components are allowed."
    if type(rule) is RoomComponentCount:
        color = "black" if rule.black else "white"
        return f"Each room contains exactly {rule.count} {color} components using only edges inside that room."
    if type(rule) is EqualRoomComponentSizes:
        color = "black" if rule.black else "white"
        return f"All {color} components inside each room have equal areas; zero or one component is allowed and sizes may differ between rooms."
    if type(rule) is NoColorAcrossRooms:
        color = "black" if rule.black else "white"
        return f"No two {color} cells share an edge across a fixed room border; within-room and corner contacts are allowed."
    if type(rule) is AdjacentRoomCountsDiffer:
        color = "black" if rule.black else "white"
        return f"Rooms sharing an edge have different total {color} counts, including zero; corner-only neighbors are not compared."
    if type(rule) is RoomFillLevels:
        color = "black" if rule.black else "white"
        return f"Each fixed room fills bottom-up in whole horizontal levels of {color}; empty/full rooms are allowed. Row/column clues still count black cells."
    if type(rule) is UniformRooms:
        return "Every fixed room is entirely black or entirely white; either color is allowed."
    if type(rule) is AcyclicColor:
        color = "black" if rule.black else "white"
        return f"The induced orthogonal graph of {color} cells has no cycle; branches, disconnected trees, and absence of that color are allowed."
    if type(rule) is AdjacentBlackComponentSum:
        return "Numbered circles are white and sum the areas of distinct edge-adjacent black components; multiple contacts count a component once. Zero is a clue, and absent entries mean no circle."
    if type(rule) is ComponentsTouchBorder:
        color = "black" if rule.black else "white"
        return f"Every edge-connected {color} component reaches the board boundary through {color} cells; separate border components and absence of {color} cells are allowed."
    if type(rule) is RunLengthLimit:
        return f"Each horizontal or vertical run of black or white cells has length at most {rule.max_length}."
    if type(rule) is DiagonalRunLimit:
        return f"Each straight diagonal run of black or white cells has length at most {rule.max_length}; rows and columns are unrestricted by this rule. Every cell participates."
    if type(rule) is RoomRotationalSymmetry:
        return "Black cells in each room have 180-degree symmetry about its bounding-box center; rotation outside the room is forbidden."
    if type(rule) is ColorComponentSize:
        color = "black" if rule.black else "white"
        return f"Every edge-connected {color} component contains exactly {rule.size} cells; absence of {color} cells is allowed."
    if type(rule) is NoTouchingEqualTetrominoes:
        return "If a room's entire black set is a connected tetromino, it cannot touch a congruent room tetromino along an edge; rotations/reflections count as equal."
    if type(rule) is RectangularComponents or type(rule) is NonRectangularComponents:
        color = "black" if rule.black else "white"
        shape = "a filled rectangle" if type(rule) is RectangularComponents else "nonrectangular"
        return f"Every edge-connected {color} component is {shape}; no {color} cells is allowed."
    raise ValueError("Cannot display an unknown rule")


def show(data: dict[str, Any], *, reveal: bool = False) -> str:
    # Verify before displaying a puzzle or revealing a stored answer. Metadata
    # alone is not evidence that the saved problem is uniquely solvable.
    verify(data)
    recipe, clues, answer = _read_record(data)
    return _render_puzzle(recipe.rows, recipe.cols, clues, answer,
                          [_rule_text(rule) for rule in recipe.rules], reveal=reveal,
                          rooms=shared_rooms(recipe), numbers=shared_numbers(recipe), sight_counts=shared_sight_counts(recipe),
                          island_areas=shared_island_areas(recipe), neighbor_counts=shared_neighbor_counts(recipe),
                          component_counts=shared_component_counts(recipe), endpoint_markers=shared_endpoint_markers(recipe), black_run_clues=shared_black_runs(recipe),
                          component_areas=shared_component_areas(recipe), orthogonal_counts=shared_orthogonal_counts(recipe))


def _render_puzzle(rows: int, cols: int, clues: list[Clue], answer: list[list[int]],
                   rules: list[str], *, reveal: bool = False, rooms: RoomMap | None = None,
                   numbers: NumberGrid | None = None, sight_counts: NumberGrid | None = None,
                   island_areas: NumberGrid | None = None, neighbor_counts: ClueGrid | None = None,
                   component_counts: ClueGrid | None = None, endpoint_markers: NumberGrid | None = None, black_run_clues: RunClueGrid | None = None,
                   component_areas: NumberGrid | None = None, orthogonal_counts: ClueGrid | None = None) -> str:
    """Presentation only: each format's caller must verify its full recipe first."""
    cells = [["?" for _ in range(cols)] for _ in range(rows)]
    for grid in (sight_counts, island_areas, endpoint_markers):
        if grid is not None:
            for r in range(rows):
                for c in range(cols):
                    if grid[r][c] > 0:
                        cells[r][c] = "."
    for grid in (neighbor_counts, component_counts):
        if grid is not None:
            for r in range(rows):
                for c in range(cols):
                    if grid[r][c] is not None:
                        cells[r][c] = "."
    if black_run_clues is not None:
        for r in range(rows):
            for c in range(cols):
                if black_run_clues[r][c] is not None:
                    cells[r][c] = "."
    row_counts: dict[int, int] = {}
    col_counts: dict[int, int] = {}
    for clue in clues:
        if isinstance(clue, RowCountClue):
            row_counts[clue.row] = clue.count
        elif isinstance(clue, ColumnCountClue):
            col_counts[clue.col] = clue.count
        else:
            cell, value = clue
            cells[cell.row][cell.col] = "#" if value else "."
    if reveal:
        cells = [["#" if value else "." for value in row] for row in answer]
    title = "Solution" if reveal else "Shading puzzle"
    lines = [f"{title}: {rows} rows x {cols} columns", "", "Rules:"]
    lines.extend(f"- {text}" for text in rules)
    if not rules:
        lines.append("- No additional rules.")
    lines.extend([
        "", f"{'column':>11} " + " ".join(f"{c+1:>2}" for c in range(cols)),
        f"{'count':>11} " + " ".join(f"{col_counts.get(c, '-'):>2}" for c in range(cols)),
        f"{'row':>3} {'count':>5} |",
    ])
    lines.extend(f"{r+1:>3} {row_counts.get(r, '-'):>5} | " + " ".join(f"{v:>2}" for v in row)
                 for r, row in enumerate(cells))
    lines.extend(["", "# = black, . = white, ? = unknown; - = no count clue.",
                  "Displayed row and column numbers start at 1."])
    if not reveal:
        lines.extend(["Answer template: " + "/".join("".join(row) for row in cells),
                      'Replace every ? with . or #, then use check FILE --answer "ROWS".'])
    if rooms is not None:
        lines.extend(["", "Fixed rooms (same label = same room; not answer values):"])
        lines.extend(" ".join(str(n) for n in row) for row in rooms)
    if numbers is not None:
        lines.extend(["", "Fixed numbers (labels, not answer values):"])
        lines.extend(" ".join(str(n) for n in row) for row in numbers)
    if sight_counts is not None:
        lines.extend(["", "Fixed white sight counts (. = no requirement; origin is counted once):"])
        lines.extend(" ".join(str(n) if n else "." for n in row) for row in sight_counts)
    if island_areas is not None:
        lines.extend(["", "Fixed white island areas (. = no number):"])
        lines.extend(" ".join(str(n) if n else "." for n in row) for row in island_areas)
    if black_run_clues is not None:
        lines.extend(["", "Fixed cyclic black-run clues (. = absent; 0 = no adjacent black):"])
        lines.extend(" ".join("." if clue is None else ",".join(map(str,clue)) for clue in row) for row in black_run_clues)
    if endpoint_markers is not None:
        lines.extend(["", "Fixed white endpoint circles (o = circle; . = absent):"])
        lines.extend(" ".join("o" if n else "." for n in row) for row in endpoint_markers)
    if neighbor_counts is not None:
        lines.extend(["", "Fixed adjacent black counts (. = no clue; 0 is a clue):"])
        lines.extend(" ".join("." if n is None else str(n) for n in row) for row in neighbor_counts)
    if component_counts is not None:
        lines.extend(["", "Fixed adjacent black-component area sums (. = no circle; 0 is a clue):"])
        lines.extend(" ".join("." if n is None else str(n) for n in row) for row in component_counts)
    if orthogonal_counts is not None:
        lines.extend(["", "Fixed orthogonal black counts (clue colors remain free; . = absent; 0 is a clue):"])
        lines.extend(" ".join("." if n is None else str(n) for n in row) for row in orthogonal_counts)
    if component_areas is not None:
        lines.extend(["", "Fixed containing-component areas (0 = absent; clue colors remain free):"])
        lines.extend(" ".join(str(n) for n in row) for row in component_areas)
    return "\n".join(lines)


def _parse_answer(text: str, rows: int, cols: int) -> list[list[int]]:
    parts = ["".join(row.split()) for row in text.strip().split("/")]
    if len(parts) != rows or any(len(row) != cols for row in parts):
        raise ValueError(f"Answer must have {rows} rows of {cols} cells, separated by '/'")
    if any(value not in ".#" for row in parts for value in row):
        raise ValueError("Fill every cell with '.' (white) or '#' (black); '?' is not a complete answer")
    return [[int(value == "#") for value in row] for row in parts]


def check_answer(data: dict[str, Any], text: str) -> bool:
    recipe, _, answer = _read_record(data)
    candidate = _parse_answer(text, recipe.rows, recipe.cols)
    # Only compare after proving that the saved answer is the unique solution.
    verify(data)
    return candidate == answer


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("generate")
    make.add_argument("--recipe", type=Path, help="Load a shading recipe; do not combine with rule or board options")
    make.add_argument("--rows", type=int)
    make.add_argument("--cols", type=int)
    make.add_argument("--rules", nargs="+", choices=RULES)
    make.add_argument("--hints", nargs="+", choices=CLUE_KINDS,
                      help="Candidate clue kinds; include cell to disambiguate count clues")
    make.add_argument("--black-count", type=int)
    make.add_argument("--diagonal", action="store_true", default=None)
    make.add_argument("--allow-empty-white", action="store_true", default=None)
    make.add_argument("--seed", type=int, default=42)
    make.add_argument("--selection", choices=("solver", "finite"), default="solver",
                      help="Starting answer: solver (default), or identifiable finite pool (at most 9 cells)")
    make.add_argument("--output", type=Path)
    make.add_argument("--quiet", action="store_true", help="Save with --output without printing the answer JSON")
    audit = commands.add_parser("verify", help="Verify a generated puzzle artifact")
    audit.add_argument("file", type=Path)
    display = commands.add_parser("show", help="Display a puzzle without revealing its answer")
    display.add_argument("file", type=Path)
    display.add_argument("--solution", action="store_true", help="Reveal the verified solution")
    check = commands.add_parser("check", help="Check a complete answer without revealing the solution")
    check.add_argument("file", type=Path)
    check.add_argument("--answer", required=True, help="Rows separated by '/', using . for white and # for black")
    args = parser.parse_args()
    try:
        if args.command == "verify":
            result = verify(load_json(args.file))
            print(json.dumps(result, sort_keys=True))
            return 0
        if args.command == "show":
            print(show(load_json(args.file), reveal=args.solution))
            return 0
        if args.command == "check":
            correct = check_answer(load_json(args.file), args.answer)
            print("Correct. All rules and clues are satisfied." if correct else
                  "Not correct. Check the rules and given clues.")
            return 0 if correct else 1
        if args.quiet and args.output is None:
            raise ValueError("Use --output with --quiet to save the generated puzzle")
        if not 0 <= args.seed <= 2**31 - 1:
            raise ValueError("Seed must be between 0 and 2147483647")
        if args.recipe is not None:
            options = ("rows", "cols", "rules", "hints", "black_count", "diagonal", "allow_empty_white")
            if any(getattr(args, name) is not None for name in options):
                raise ValueError("Do not combine --recipe with board, rule or hint options")
            if args.output is not None:
                check_distinct_paths(args.recipe, args.output)
            recipe = load_recipe(args.recipe)
        else:
            choices = rule_choices(count=3 if args.black_count is None else args.black_count,
                                   diagonal=bool(args.diagonal), allow_empty_white=bool(args.allow_empty_white))
            recipe = ShadingRecipe(3 if args.rows is None else args.rows, 3 if args.cols is None else args.cols,
                                   tuple(choices[name] for name in (args.rules or DEFAULT_RULES)),
                                   tuple(args.hints or ["cell"]))
        check_demo_size(recipe)
        try:
            if args.selection == "finite":
                # The finite checker imports the example's clue codec. Import
                # it only when requested, after this module is initialized.
                from finite_shading import generate_finite
                clues = generate_finite(recipe, seed=args.seed)
            else:
                clues = generate(recipe, seed=args.seed)
        except InitialCluesNotUniqueError as exc:
            if "cell" not in recipe.clue_kinds:
                hint = "the recipe clue_kinds" if args.recipe is not None else "--hints"
                raise ValueError(f"{exc}. For ambiguous count clues, include cell in {hint} "
                                 "to retain disambiguating clues") from exc
            raise
        record = puzzle_record(recipe, clues, seed=args.seed, selection=args.selection)
        encoded = encode_json(record)
        if args.output is not None:
            args.output.write_bytes(encoded)
        if not args.quiet:
            sys.stdout.buffer.write(encoded)
        return 0
    except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
