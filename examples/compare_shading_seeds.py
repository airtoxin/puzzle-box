"""Compare actual reduced puzzles from a bounded list of finite-selection seeds."""

import argparse
from collections.abc import Sequence
import json
from pathlib import Path
from typing import Any

from puzzle_defs import ShadingRecipe
from analyze_shading import analyze
from diagnose_shading_rules import diagnose
from finite_shading import generate_finite
from generate_shading import puzzle_record, verify
from shading_recipe import check_distinct_paths, load_recipe, recipe_record

MAX_SEEDS = 8


def compare(recipe: ShadingRecipe, seeds: Sequence[int]) -> dict[str, Any]:
    """Compare fixed hints after reduction, without ranking or changing rules."""
    if (not 1 <= len(seeds) <= MAX_SEEDS
            or any(type(seed) is not int or not 0 <= seed <= 2**31 - 1 for seed in seeds)
            or len(set(seeds)) != len(seeds)):
        raise ValueError("Use 1..8 distinct integer seeds between 0 and 2147483647")
    source = recipe_record(recipe)
    analysis = analyze(recipe)  # Validates the finite 9-cell / 8-rule scope.
    attempts = []
    answers: dict[tuple[int, ...], int] = {}
    if analysis["identifiable_completions"]:
        for seed in seeds:
            clues = generate_finite(recipe, seed=seed)
            record = puzzle_record(recipe, clues, seed=seed, selection="finite")
            validation = verify(record)
            diagnostic = diagnose(record)
            if not diagnostic["stored_clues_irreducible"]:
                raise RuntimeError("Finite diagnostics disagree with the DSL irreducibility check")
            answer = tuple(v for row in record["solution"] for v in row)
            attempts.append({"seed": seed, "answer_id": answers.setdefault(answer, len(answers)+1),
                "clue_count": len(clues), "puzzle": record, "verification": validation,
                "necessary_rule_indices": [r["rule_index"] for r in diagnostic["removals"]
                                           if r["necessary_with_stored_clues"]],
                "redundant_rule_indices": [r["rule_index"] for r in diagnostic["removals"]
                                           if not r["necessary_with_stored_clues"]],
                "diagnostic": diagnostic})
    return {"format": "puzzle-box/shading-seed-comparison-v1", "recipe": source,
            "requested_seeds": list(seeds), "analysis": analysis, "attempts": attempts,
            "distinct_answers": len(answers)}


def explain(report: dict[str, Any]) -> str:
    analysis = report["analysis"]
    lines = [f"Checked {analysis['enumerated_boards']} boards: {analysis['completion_count']} completions; "
             f"{analysis['identifiable_completions']} identifiable with full candidate hints."]
    if not report["attempts"]:
        if not analysis["completion_count"]:
            lines.append("No completion: change the rules. Changing seeds or hints cannot fix contradictory rules.")
            lines.append(f"Minimal conflicting rule indices: {analysis['minimal_conflicts']}")
        else:
            lines.append("No identifiable completion: change the hint kinds or rules; changing seeds cannot help.")
        lines.append("No generation attempted.")
        return "\n".join(lines)
    lines.append("Rules (1-based indices):")
    lines.extend(f"  {i}: {json.dumps(rule, sort_keys=True)}" for i, rule in enumerate(report["recipe"]["rules"], 1))
    lines.extend(["", "Seed | Answer ID | Clues | Necessary rules / Individually redundant rules (remaining clues)"])
    for attempt in report["attempts"]:
        necessary = "+".join(map(str, attempt["necessary_rule_indices"])) or "-"
        redundant = "+".join(map(str, attempt["redundant_rule_indices"])) or "-"
        lines.append(f"{attempt['seed']} | {attempt['answer_id']} | {attempt['clue_count']} | {necessary} / {redundant}")
    lines.extend(["", f"Distinct visible answers in these attempts: {report['distinct_answers']}.",
        "Every generated puzzle passed uniqueness and clue-irreducibility checks.",
        "Each rule is removed separately with the SAME remaining clues. Do not remove redundant rules together.",
        "This is a bounded seed sample, not a difficulty ranking, probability, or proof about other seeds.",
        "Use --export-seed N --export-puzzle FILE to save one checked puzzle. --json reveals answers and witnesses."])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    parser.add_argument("--json", action="store_true", help="Include puzzles and diagnostic counterexamples")
    parser.add_argument("--export-seed", type=int)
    parser.add_argument("--export-puzzle", type=Path, help="Create a new puzzle file; existing files are never overwritten")
    args = parser.parse_args()
    try:
        if (args.export_seed is None) != (args.export_puzzle is None):
            raise ValueError("Use --export-seed and --export-puzzle together")
        if args.export_puzzle is not None:
            check_distinct_paths(args.recipe, args.export_puzzle)
            if args.export_puzzle.exists():
                raise ValueError("Export file already exists; choose a new path")
            if args.export_seed not in args.seeds:
                raise ValueError("The export seed must be in --seeds")
        report = compare(load_recipe(args.recipe), args.seeds)
        rendered = json.dumps(report, indent=2, sort_keys=True) if args.json else explain(report)
        if args.export_puzzle is not None:
            chosen = next((a for a in report["attempts"] if a["seed"] == args.export_seed), None)
            if chosen is None:
                raise ValueError("No generated puzzle to export; inspect the recipe without export options")
            encoded = json.dumps(chosen["puzzle"], indent=2, sort_keys=True) + "\n"
            # Exclusive creation also protects a file created after the preflight check.
            with args.export_puzzle.open("x", encoding="utf-8") as stream:
                stream.write(encoded)
        print(rendered)
        return 0
    except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
