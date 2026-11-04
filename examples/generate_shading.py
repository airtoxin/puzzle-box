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
    BlackCount, ConnectedWhite, NonTouchingBlack, NoWhite2x2, ShadingRecipe,
)
from puzzle_defs.puzzles.shading import Clue, ShadingRule

FORMAT = "puzzle-box/shading-v1"
RULES = ("count", "non-touching", "connected-white", "no-white-2x2")


def rule_record(rule: ShadingRule) -> dict[str, Any]:
    if isinstance(rule, BlackCount):
        return {"type": "count", "count": rule.count}
    if isinstance(rule, NonTouchingBlack):
        return {"type": "non-touching", "diagonal": rule.diagonal}
    if isinstance(rule, ConnectedWhite):
        return {"type": "connected-white", "nonempty": rule.nonempty}
    if isinstance(rule, NoWhite2x2):
        return {"type": "no-white-2x2"}
    raise ValueError("This file format supports the four built-in shading rules only")


def read_rule(data: dict[str, Any]) -> ShadingRule:
    kind = data["type"]
    if kind == "count" and set(data) == {"type", "count"}:
        return BlackCount(data["count"])
    if kind == "non-touching" and set(data) == {"type", "diagonal"}:
        if type(data["diagonal"]) is bool:
            return NonTouchingBlack(data["diagonal"])
    if kind == "connected-white" and set(data) == {"type", "nonempty"}:
        if type(data["nonempty"]) is bool:
            return ConnectedWhite(data["nonempty"])
    if kind == "no-white-2x2" and set(data) == {"type"}:
        return NoWhite2x2()
    raise ValueError("Unknown rule or invalid rule parameters")


def check_demo_size(recipe: ShadingRecipe) -> None:
    if recipe.rows * recipe.cols > 25:
        raise ValueError("This small-board demo supports at most 25 cells")


def verify(data: dict[str, Any]) -> dict[str, Any]:
    if data["format"] != FORMAT:
        raise ValueError("Unsupported puzzle format")
    recipe = ShadingRecipe(data["rows"], data["cols"], tuple(read_rule(r) for r in data["rules"]))
    check_demo_size(recipe)
    clues: list[Clue] = []
    for row, col, value in data["clues"]:
        if type(row) is not int or type(col) is not int:
            raise ValueError("Clue coordinates must be integers")
        clues.append((Cell(row, col), value))
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
    make.add_argument("--rows", type=int, default=3)
    make.add_argument("--cols", type=int, default=3)
    make.add_argument("--rules", nargs="+", choices=RULES, default=list(RULES))
    make.add_argument("--black-count", type=int, default=3)
    make.add_argument("--diagonal", action="store_true")
    make.add_argument("--allow-empty-white", action="store_true")
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
        choices: dict[str, ShadingRule] = {
            "count": BlackCount(args.black_count),
            "non-touching": NonTouchingBlack(args.diagonal),
            "connected-white": ConnectedWhite(nonempty=not args.allow_empty_white),
            "no-white-2x2": NoWhite2x2(),
        }
        recipe = ShadingRecipe(args.rows, args.cols, tuple(choices[name] for name in args.rules))
        check_demo_size(recipe)
        clues = generate(recipe, seed=args.seed)
        puzzle = recipe.build_from_clues(clues)
        puzzle.add(unique())
        solution = puzzle.solve()
        if solution is None:
            raise ValueError("Generated clues did not determine a unique answer")
        record = {
            "format": FORMAT, "rows": recipe.rows, "cols": recipe.cols,
            "rules": [rule_record(rule) for rule in recipe.rules], "seed": args.seed,
            "clues": [[cell.row, cell.col, value] for cell, value in clues],
            "solution": puzzle.result(solution),
            "environment": {"python": platform.python_version(), "ortools": ortools.__version__,
                            "seeded_search_workers": 1},
        }
        encoded = json.dumps(record, indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
    except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
