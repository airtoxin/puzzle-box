"""Generate and verify small shading files retaining known added components."""

import argparse
import json
from pathlib import Path
from typing import Any

from generator import generate
from puzzle import unique
from puzzle_defs.puzzles.shading import ColumnCountClue, RowCountClue
from component_registry import ComponentRegistry
from composed_shading_recipe import BUILTIN_COMPONENTS, load_recipe, read_recipe, recipe_record
from generate_shading import clue_record, read_clue
from json_records import encode_json
from shading_recipe import check_distinct_paths, load_json

FORMAT = "puzzle-box/composed-shading-v1"


def _seed(value: Any) -> None:
    if type(value) is not int or not 0 <= value <= 2**31 - 1:
        raise ValueError("Seed must be an integer between 0 and 2147483647")


def generate_record(data: Any, *, seed: int = 0, registry: ComponentRegistry = BUILTIN_COMPONENTS) -> dict[str, Any]:
    recipe = read_recipe(data, registry=registry)
    _seed(seed)
    clues = generate(recipe, seed=seed)
    puzzle = recipe.build_from_clues(clues)
    puzzle.add(unique())
    solution = puzzle.solve()
    if solution is None:
        raise ValueError("Generated clues did not determine a unique answer")
    return {"format": FORMAT, "recipe": recipe_record(recipe, registry=registry), "seed": seed,
            "clues": [clue_record(clue) for clue in clues], "solution": puzzle.result(solution)}


def verify(data: Any, *, registry: ComponentRegistry = BUILTIN_COMPONENTS) -> dict[str, Any]:
    if not isinstance(data, dict) or set(data) != {"format", "recipe", "seed", "clues", "solution"}:
        raise ValueError("Composed puzzle must contain exactly format, recipe, seed, clues and solution")
    if data["format"] != FORMAT:
        raise ValueError("Unsupported composed puzzle format/version")
    recipe = read_recipe(data["recipe"], registry=registry)
    _seed(data["seed"])
    # read_recipe validates these dimensions and clue kinds; no stored validity
    # flags or stored answers are used as evidence of satisfiability/uniqueness.
    rows, cols = data["recipe"]["base"]["rows"], data["recipe"]["base"]["cols"]
    raw_clues = data["clues"]
    if not isinstance(raw_clues, list) or len(raw_clues) > rows * cols + rows + cols:
        raise ValueError("Clues must be an array within the cell/row/column clue limit")
    clues = [read_clue(clue) for clue in raw_clues]
    enabled = data["recipe"]["base"]["clue_kinds"]
    for clue in clues:
        kind = "row-count" if isinstance(clue, RowCountClue) else (
            "column-count" if isinstance(clue, ColumnCountClue) else "cell")
        if kind not in enabled:
            raise ValueError("Stored clue type is not enabled by clue_kinds")
    answer = data["solution"]
    if (not isinstance(answer, list) or len(answer) != rows
            or any(not isinstance(row, list) or len(row) != cols
                   or any(type(v) is not int or v not in (0, 1) for v in row) for row in answer)):
        raise ValueError("Invalid solution grid")
    puzzle = recipe.build_from_clues(clues)
    puzzle.add(unique())
    solution = puzzle.solve()
    if solution is None:
        raise ValueError("Stored clues are not uniquely solvable with the composed recipe")
    if puzzle.result(solution) != answer:
        raise ValueError("Stored solution does not match the uniquely determined answer")
    for i in range(len(clues)):
        trial = recipe.build_from_clues(clues[:i] + clues[i+1:])
        trial.add(unique())
        if trial.solve() is not None:
            raise ValueError("Stored clues are not irreducible")
    return {"valid": True, "unique": True, "irreducible": True, "clue_count": len(clues)}


def main(*, registry: ComponentRegistry = BUILTIN_COMPONENTS) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("generate")
    make.add_argument("--recipe", type=Path, required=True)
    make.add_argument("--seed", type=int, default=0)
    make.add_argument("--output", type=Path, required=True, help="Create a new file; never overwrite")
    audit = commands.add_parser("verify")
    audit.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "verify":
            print(json.dumps(verify(load_json(args.file, label="Composed puzzle"), registry=registry), sort_keys=True))
        else:
            check_distinct_paths(args.recipe, args.output)
            if args.output.exists():
                raise ValueError("Output already exists; choose a new file")
            recipe = load_recipe(args.recipe, registry=registry)
            record = generate_record(recipe_record(recipe, registry=registry), seed=args.seed, registry=registry)
            encoded = encode_json(record, label="Generated composed puzzle")
            # Exclusive creation also covers a file appearing while solving.
            # Write exactly the checked bytes, without newline expansion.
            with args.output.open("xb") as stream:
                stream.write(encoded)
            print("Saved composed puzzle. Use verify to check it; the JSON contains its answer.")
        return 0
    except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
