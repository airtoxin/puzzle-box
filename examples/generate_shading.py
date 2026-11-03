"""Generate and verify small puzzles composed from shared shading rules."""

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


def verify(data: dict[str, Any]) -> dict[str, Any]:
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


def main() -> None:
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
    check = commands.add_parser("verify")
    check.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "verify":
            result = verify(json.loads(args.file.read_text(encoding="utf-8")))
            print(json.dumps(result, sort_keys=True))
            return
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
        print(encoded, end="")
    except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
