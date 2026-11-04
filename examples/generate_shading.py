"""Generate, display, check and verify small composed shading puzzles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
from typing import Any

import ortools

from generator import generate
from puzzle import Cell, unique
from puzzle_defs import (
    BlackCount, ConnectedWhite, NonTouchingBlack, NoWhite2x2,
    ColumnCountClue, RowCountClue, ShadingRecipe,
)
from puzzle_defs.puzzles.shading import CLUE_KINDS, Clue, ShadingRule
from shading_recipe import RULES, check_demo_size, check_distinct_paths, load_recipe, read_rule, rule_record

FORMAT = "puzzle-box/shading-v1"
MIXED_FORMAT = "puzzle-box/shading-v2"


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
    if data["format"] not in (FORMAT, MIXED_FORMAT):
        raise ValueError("Unsupported puzzle format")
    legacy = data["format"] == FORMAT
    recipe = ShadingRecipe(data["rows"], data["cols"], tuple(read_rule(r) for r in data["rules"]),
                           ("cell",) if legacy else tuple(data["clue_kinds"]))
    check_demo_size(recipe)
    clues = [read_clue(clue, legacy=legacy) for clue in data["clues"]]
    for clue in clues:
        kind = "row-count" if isinstance(clue, RowCountClue) else (
            "column-count" if isinstance(clue, ColumnCountClue) else "cell")
        if kind not in recipe.clue_kinds:
            raise ValueError("Stored clue type is not enabled by clue_kinds")
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
    for idx in range(len(clues)):
        trial = recipe.build_from_clues(clues[:idx] + clues[idx + 1:])
        trial.add(unique())
        if trial.solve() is not None:
            raise ValueError("Stored clues are not irreducible: a clue can still be removed")
    return {"valid": True, "unique": True, "irreducible": True, "clue_count": len(clues)}


def _rule_text(rule: ShadingRule) -> str:
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
    raise ValueError("Cannot display an unknown rule")


def show(data: dict[str, Any], *, reveal: bool = False) -> str:
    # Verify before displaying a puzzle or revealing a stored answer. Metadata
    # alone is not evidence that the saved problem is uniquely solvable.
    verify(data)
    recipe, clues, answer = _read_record(data)
    cells = [["?" for _ in range(recipe.cols)] for _ in range(recipe.rows)]
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
    lines = [f"{title}: {recipe.rows} rows x {recipe.cols} columns", "", "Rules:"]
    lines.extend(f"- {_rule_text(rule)}" for rule in recipe.rules)
    if not recipe.rules:
        lines.append("- No additional rules.")
    lines.extend([
        "", f"{'column':>11} " + " ".join(f"{c+1:>2}" for c in range(recipe.cols)),
        f"{'count':>11} " + " ".join(f"{col_counts.get(c, '-'):>2}" for c in range(recipe.cols)),
        f"{'row':>3} {'count':>5} |",
    ])
    lines.extend(f"{r+1:>3} {row_counts.get(r, '-'):>5} | " + " ".join(f"{v:>2}" for v in row)
                 for r, row in enumerate(cells))
    lines.extend(["", "# = black, . = white, ? = unknown; - = no count clue.",
                  "Displayed row and column numbers start at 1."])
    if not reveal:
        lines.extend(["Answer template: " + "/".join("".join(row) for row in cells),
                      'Replace every ? with . or #, then use check FILE --answer "ROWS".'])
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
            result = verify(json.loads(args.file.read_text(encoding="utf-8")))
            print(json.dumps(result, sort_keys=True))
            return 0
        if args.command == "show":
            print(show(json.loads(args.file.read_text(encoding="utf-8")), reveal=args.solution))
            return 0
        if args.command == "check":
            correct = check_answer(json.loads(args.file.read_text(encoding="utf-8")), args.answer)
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
            choices: dict[str, ShadingRule] = {
                "count": BlackCount(3 if args.black_count is None else args.black_count),
                "non-touching": NonTouchingBlack(bool(args.diagonal)),
                "connected-white": ConnectedWhite(nonempty=not args.allow_empty_white),
                "no-white-2x2": NoWhite2x2(),
            }
            recipe = ShadingRecipe(3 if args.rows is None else args.rows, 3 if args.cols is None else args.cols,
                                   tuple(choices[name] for name in (args.rules or RULES)),
                                   tuple(args.hints or ["cell"]))
        check_demo_size(recipe)
        try:
            clues = generate(recipe, seed=args.seed)
        except ValueError as exc:
            if "cell" not in recipe.clue_kinds:
                hint = "the recipe clue_kinds" if args.recipe is not None else "--hints"
                raise ValueError(f"{exc}. For ambiguous count clues, include cell in {hint} "
                                 "to retain disambiguating clues") from exc
            raise
        puzzle = recipe.build_from_clues(clues)
        puzzle.add(unique())
        solution = puzzle.solve()
        if solution is None:
            raise ValueError("Generated clues did not determine a unique answer")
        legacy = recipe.clue_kinds == ("cell",)
        record = {
            "format": FORMAT if legacy else MIXED_FORMAT,
            "rows": recipe.rows, "cols": recipe.cols,
            "rules": [rule_record(rule) for rule in recipe.rules], "seed": args.seed,
            "clues": [clue_record(clue, legacy=legacy) for clue in clues],
            "solution": puzzle.result(solution),
            "environment": {"python": platform.python_version(), "ortools": ortools.__version__,
                            "seeded_search_workers": 1},
        }
        if not legacy:
            record["clue_kinds"] = list(recipe.clue_kinds)
        encoded = json.dumps(record, indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            args.output.write_text(encoded, encoding="utf-8")
        if not args.quiet:
            print(encoded, end="")
        return 0
    except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
