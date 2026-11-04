"""Generate and inspect a small coupled black-cell / loop puzzle."""

import argparse
import json
from pathlib import Path
import platform
from typing import Any

import ortools

from generator import InitialCluesNotUniqueError, generate
from puzzle import Cell, Edge, Vertex, unique
from puzzle_defs import ArrowCountClue, ArrowSite, BlackCellClue, EdgeStateClue, YajilinAnswer, YajilinRecipe
from puzzle_defs.puzzles.yajilin_recipe import YAJILIN_CLUE_KINDS, YajilinClue
from generate_slitherlink import edge_record, read_edge

FORMAT = "puzzle-box/yajilin-v1"
ARROWS = {"up": "^", "down": "v", "left": "<", "right": ">"}


def check_attempts(seed: int, attempts: int) -> None:
    if type(attempts) is not int or not 1 <= attempts <= 32:
        raise ValueError("Attempts must be an integer from 1 to 32")
    if type(seed) is not int or not 0 <= seed <= 2**31 - attempts:
        raise ValueError("All attempted seeds must be between 0 and 2147483647")


def generate_with_attempts(recipe: YajilinRecipe, seed: int, attempts: int) -> tuple[list[YajilinClue], int, int]:
    """Try consecutive seeds, preserving topology and requested hint types."""
    check_attempts(seed, attempts)
    last_error: InitialCluesNotUniqueError | None = None
    for offset in range(attempts):
        try:
            return generate(recipe, seed=seed + offset), seed + offset, offset + 1
        except InitialCluesNotUniqueError as exc:
            last_error = exc
    raise InitialCluesNotUniqueError(
        f"No uniquely solvable clues after {attempts} attempt(s), seeds {seed}..{seed + attempts - 1}; "
        "hint types and arrow sites unchanged"
    ) from last_error


def clue_record(clue: YajilinClue) -> dict[str, Any]:
    if isinstance(clue, ArrowCountClue):
        return {"type": "arrow", "cell": list(clue.cell), "count": clue.count}
    if isinstance(clue, BlackCellClue):
        return {"type": "black", "cell": list(clue.cell), "black": clue.black}
    return {"type": "edge", "edge": edge_record(clue.edge), "used": clue.used}


def read_cell(data: Any) -> Cell:
    if not isinstance(data, list) or len(data) != 2:
        raise ValueError("A cell needs [row, col]")
    return BlackCellClue(Cell(*data), 0).cell


def read_clue(data: Any) -> YajilinClue:
    if not isinstance(data, dict):
        raise ValueError("A Yajilin clue must be an object")
    if data.get("type") == "arrow" and set(data) == {"type", "cell", "count"}:
        return ArrowCountClue(read_cell(data["cell"]), data["count"])
    if data.get("type") == "black" and set(data) == {"type", "cell", "black"}:
        return BlackCellClue(read_cell(data["cell"]), data["black"])
    if data.get("type") == "edge" and set(data) == {"type", "edge", "used"}:
        return EdgeStateClue(read_edge(data["edge"]), data["used"])
    raise ValueError("Unknown Yajilin clue type or invalid clue fields")


def check_size(recipe: YajilinRecipe) -> None:
    if recipe.rows * recipe.cols > 12:
        raise ValueError("This coupled puzzle demo supports at most 12 cells")


def read_record(data: dict[str, Any]) -> tuple[YajilinRecipe, list[YajilinClue], YajilinAnswer]:
    if data["format"] != FORMAT:
        raise ValueError("Unsupported Yajilin puzzle format")
    if "generation" in data:
        history = data["generation"]
        if not isinstance(history, dict) or set(history) != {"initial_seed", "attempt_limit", "attempts_used"}:
            raise ValueError("Invalid generation metadata fields")
        check_attempts(history["initial_seed"], history["attempt_limit"])
        used = history["attempts_used"]
        if (type(used) is not int or not 1 <= used <= history["attempt_limit"]
                or type(data["seed"]) is not int or data["seed"] != history["initial_seed"] + used - 1):
            raise ValueError("Generation metadata must agree with the successful seed")
    sites = []
    for site in data["arrow_sites"]:
        if not isinstance(site, dict) or set(site) != {"cell", "direction"}:
            raise ValueError("Invalid arrow site fields")
        sites.append(ArrowSite(read_cell(site["cell"]), site["direction"]))
    recipe = YajilinRecipe(data["rows"], data["cols"], tuple(sites), tuple(data["clue_kinds"]))
    check_size(recipe)
    clues = [read_clue(c) for c in data["clues"]]
    for clue in clues:
        kind = "arrow" if isinstance(clue, ArrowCountClue) else "black" if isinstance(clue, BlackCellClue) else "edge"
        if kind not in recipe.clue_kinds:
            raise ValueError("Stored clue type is not enabled by clue_kinds")
    expected = data["solution"]
    if not isinstance(expected, dict) or set(expected) != {"black_cells", "loop_edges"}:
        raise ValueError("Solution must contain black_cells and loop_edges")
    black = [read_cell(c) for c in expected["black_cells"]]
    edges = [read_edge(e) for e in expected["loop_edges"]]
    if len(set(black)) != len(black) or len(set(edges)) != len(edges):
        raise ValueError("Solution must not contain duplicate cells or edges")
    blocked = {s.cell for s in sites}
    if any(c.row >= recipe.rows or c.col >= recipe.cols or c in blocked for c in black):
        raise ValueError("Black answer cells must be ordinary cells inside the board")
    if any(v.row >= recipe.rows or v.col >= recipe.cols for e in edges for v in e):
        raise ValueError("Answer edges must connect cell centers inside the board")
    return recipe, clues, YajilinAnswer(frozenset(black), frozenset(edges))


def verify(data: dict[str, Any]) -> dict[str, Any]:
    recipe, clues, expected = read_record(data)
    puzzle = recipe.build_from_clues(clues)
    puzzle.add(unique())
    solution = puzzle.solve()
    if solution is None:
        raise ValueError("Stored clues are not uniquely solvable")
    if recipe.answer(solution, puzzle) != expected:
        raise ValueError("Stored black cells or loop edges do not match the unique answer")
    for i in range(len(clues)):
        trial = recipe.build_from_clues(clues[:i] + clues[i+1:])
        trial.add(unique())
        if trial.solve() is not None:
            raise ValueError("Stored clues are not irreducible")
    return {"valid": True, "unique": True, "irreducible": True, "clue_count": len(clues)}


def show(data: dict[str, Any], *, reveal: bool = False) -> str:
    verify(data)
    recipe, clues, answer = read_record(data)
    sites = {s.cell: s for s in recipe.arrow_sites}
    counts = {c.cell: c.count for c in clues if isinstance(c, ArrowCountClue)}
    black = {c.cell: c.black for c in clues if isinstance(c, BlackCellClue)}
    edges = {c.edge: c.used for c in clues if isinstance(c, EdgeStateClue)}

    def cell_text(cell: Cell) -> str:
        if cell in sites:
            return ARROWS[sites[cell].direction] + str(counts.get(cell, "?"))
        state = int(cell in answer.black_cells) if reveal else black.get(cell)
        return "#" if state == 1 else "o" if state == 0 else "."

    def edge_text(a: Vertex, b: Vertex, horizontal: bool) -> str:
        edge = Edge(a, b)
        if Cell(*a) in sites or Cell(*b) in sites:
            return "   "
        state = int(edge in answer.loop_edges) if reveal else edges.get(edge)
        if state == 1:
            return "---" if horizontal else " | "
        return "   " if reveal else " x " if state == 0 else " ? "

    title = "Solution" if reveal else "Coupled puzzle"
    lines = [f"{title}: {recipe.rows} rows x {recipe.cols} columns",
             "Shade nonadjacent black cells; draw one nonempty loop through every other ordinary cell.",
             "Arrow cells are fixed obstacles. Counts give black cells strictly ahead, skipping arrow cells.", ""]
    for r in range(recipe.rows):
        row = f"{cell_text(Cell(r, 0)):^3}"
        for c in range(1, recipe.cols):
            row += edge_text(Vertex(r, c-1), Vertex(r, c), True) + f"{cell_text(Cell(r, c)):^3}"
        lines.append(row.rstrip())
        if r < recipe.rows - 1:
            lines.append("   ".join(edge_text(Vertex(r, c), Vertex(r+1, c), False)
                                    for c in range(recipe.cols)).rstrip())
    lines.extend(["", "# = black; o = on loop; . = unknown cell. Arrows with ? remain blocked (no count).",
                  "--- / | = used edge; x = unused edge clue; ? between cells = unknown edge.",
                  "Edges join cell centers, not cell corners. Coordinates in JSON are zero-based."])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("generate")
    make.add_argument("--rows", type=int, default=3)
    make.add_argument("--cols", type=int, default=4)
    make.add_argument("--arrow", nargs=3, action="append", metavar=("ROW", "COL", "DIRECTION"),
                      help="Repeat for multiple fixed sites; default: 1 0 right")
    make.add_argument("--hints", nargs="+", choices=YAJILIN_CLUE_KINDS, default=["arrow", "edge"])
    make.add_argument("--seed", type=int, default=6)
    make.add_argument("--attempts", type=int, default=1,
                      help="Try up to 1..32 consecutive seeds without changing hints or arrow sites (default: 1)")
    make.add_argument("--output", type=Path)
    make.add_argument("--quiet", action="store_true")
    audit = commands.add_parser("verify")
    audit.add_argument("file", type=Path)
    display = commands.add_parser("show")
    display.add_argument("file", type=Path)
    display.add_argument("--solution", action="store_true")
    args = parser.parse_args()
    try:
        if args.command in ("verify", "show"):
            data = json.loads(args.file.read_text(encoding="utf-8"))
            print(json.dumps(verify(data), sort_keys=True) if args.command == "verify"
                  else show(data, reveal=args.solution))
            return 0
        if args.quiet and args.output is None:
            raise ValueError("Use --output with --quiet")
        check_attempts(args.seed, args.attempts)
        sites = tuple(ArrowSite(Cell(int(r), int(c)), d) for r, c, d in (args.arrow or [(1, 0, "right")]))
        recipe = YajilinRecipe(args.rows, args.cols, sites, tuple(args.hints))
        check_size(recipe)
        try:
            clues, successful_seed, attempts_used = generate_with_attempts(recipe, args.seed, args.attempts)
        except InitialCluesNotUniqueError as exc:
            raise ValueError(f"{exc}. Try a larger --attempts or include edge in --hints") from exc
        puzzle = recipe.build_from_clues(clues)
        puzzle.add(unique())
        solution = puzzle.solve()
        if solution is None:
            raise ValueError("Generated clues did not determine a unique coupled answer")
        answer = recipe.answer(solution, puzzle)
        data = {"format": FORMAT, "rows": recipe.rows, "cols": recipe.cols,
                "arrow_sites": [{"cell": list(s.cell), "direction": s.direction} for s in recipe.arrow_sites],
                "clue_kinds": list(recipe.clue_kinds), "clues": [clue_record(c) for c in clues],
                "seed": successful_seed,
                "solution": {"black_cells": [list(c) for c in sorted(answer.black_cells)],
                             "loop_edges": [edge_record(e) for e in puzzle.loop_board.edges if e in answer.loop_edges]},
                "environment": {"python": platform.python_version(), "ortools": ortools.__version__,
                                "seeded_search_workers": 1}}
        if args.attempts > 1:
            data["generation"] = {"initial_seed": args.seed, "attempt_limit": args.attempts,
                                  "attempts_used": attempts_used}
        encoded = json.dumps(data, indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            args.output.write_text(encoded, encoding="utf-8")
        if not args.quiet:
            print(encoded, end="")
        return 0
    except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
