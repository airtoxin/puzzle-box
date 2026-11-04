"""Exhaustively diagnose small recipes using the four built-in shading rules."""

import argparse
from collections.abc import Iterable
from itertools import combinations, product
import json
from pathlib import Path
import platform
from typing import Any

import ortools

from puzzle import Cell
from puzzle_defs import (BlackCount, ColumnCountClue, ConnectedWhite, NonTouchingBlack,
                         NoWhite2x2, RowCountClue, ShadingPuzzle, ShadingRecipe)
from puzzle_defs.puzzles.shading import CLUE_KINDS, Clue, ShadingRule
from generate_shading import RULES, clue_record, rule_record

BUILT_INS = (BlackCount, NonTouchingBlack, ConnectedWhite, NoWhite2x2)
Bits = tuple[int, ...]


def accepts(rule: ShadingRule, bits: Bits, rows: int, cols: int) -> bool:
    """A finite checker independent of the constraint encoding, not a new DSL."""
    black = {(r, c) for r in range(rows) for c in range(cols) if bits[r * cols + c]}
    if type(rule) is BlackCount:
        return len(black) == rule.count
    if type(rule) is NonTouchingBlack:
        return not any((max(abs(r-s), abs(c-t)) if rule.diagonal else abs(r-s)+abs(c-t)) == 1
                       for (r, c), (s, t) in combinations(black, 2))
    if type(rule) is ConnectedWhite:
        white = {(r, c) for r in range(rows) for c in range(cols)} - black
        seen: set[tuple[int, int]] = set()
        todo: list[tuple[int, int]] = [min(white)] if white else []
        while todo:
            r, c = todo.pop()
            if (r, c) not in seen:
                seen.add((r, c))
                todo.extend(v for v in [(r-1, c), (r+1, c), (r, c-1), (r, c+1)] if v in white)
        return seen == white and (bool(white) or not rule.nonempty)
    if type(rule) is NoWhite2x2:
        return all(any((r+dr, c+dc) in black for dr in (0, 1) for dc in (0, 1))
                   for r in range(rows-1) for c in range(cols-1))
    raise ValueError("Diagnostics support exact built-in rule types only, not custom rules or subclasses")


def full_clues(recipe: ShadingRecipe, bits: Bits) -> tuple[Clue, ...]:
    clues: list[Clue] = []
    for kind in recipe.clue_kinds:
        if kind == "cell":
            clues.extend((Cell(r, c), bits[r*recipe.cols+c])
                         for r in range(recipe.rows) for c in range(recipe.cols))
        elif kind == "row-count":
            clues.extend(RowCountClue(r, sum(bits[r*recipe.cols:(r+1)*recipe.cols]))
                         for r in range(recipe.rows))
        else:
            clues.extend(ColumnCountClue(c, sum(bits[r*recipe.cols+c] for r in range(recipe.rows)))
                         for c in range(recipe.cols))
    return tuple(clues)


def finite_space(recipe: ShadingRecipe) -> tuple[ShadingPuzzle, list[Bits], list[set[int]]]:
    """Validate once and cache which finite boards satisfy each rule occurrence."""
    if recipe.rows * recipe.cols > 9 or len(recipe.rules) > 8:
        raise ValueError("Diagnostics support at most 9 cells and 8 rule occurrences")
    if any(type(rule) not in BUILT_INS for rule in recipe.rules):
        raise ValueError("Diagnostics support exact built-in rule types only, not custom rules or subclasses")
    # Validate the recipe with the real builder, including count <= area.
    puzzle = recipe.create_empty()
    boards = list(product([0, 1], repeat=recipe.rows * recipe.cols))
    masks = [{i for i, bits in enumerate(boards) if accepts(rule, bits, recipe.rows, recipe.cols)}
             for rule in recipe.rules]
    return puzzle, boards, masks


def analyze(recipe: ShadingRecipe, *, seed_start: int = 0, seed_count: int = 0) -> dict[str, Any]:
    puzzle, boards, masks = finite_space(recipe)
    if (type(seed_count) is not int or not 0 <= seed_count <= 32
            or type(seed_start) is not int or not 0 <= seed_start <= 2**31 - max(seed_count, 1)):
        raise ValueError("Use 0..32 seeds, all between 0 and 2147483647")

    def allowed(indices: Iterable[int]) -> set[int]:
        result = set(range(len(boards)))
        for index in indices:
            result.intersection_update(masks[index])
        return result

    valid = allowed(range(len(recipe.rules)))
    conflicts: list[tuple[int, ...]] = []
    if not valid:
        for size in range(1, len(recipe.rules)+1):
            for indices in combinations(range(len(recipe.rules)), size):
                if not any(set(core) <= set(indices) for core in conflicts) and not allowed(indices):
                    conflicts.append(indices)
    groups: dict[tuple[Clue, ...], list[Bits]] = {}
    for index in sorted(valid):
        bits = boards[index]
        groups.setdefault(full_clues(recipe, bits), []).append(bits)
    identifiable = sum(len(group) == 1 for group in groups.values())
    policy = ("no_completion" if not valid else "none_identifiable" if not identifiable
              else "all_identifiable" if identifiable == len(valid) else "some_identifiable")

    def grid(bits: Bits) -> list[list[int]]:
        return [list(bits[r*recipe.cols:(r+1)*recipe.cols]) for r in range(recipe.rows)]

    ambiguity = next(({"clues": [clue_record(c) for c in clues], "answer_count": len(group),
                       "witnesses": [grid(bits) for bits in group[:2]]}
                      for clues, group in groups.items() if len(group) > 1), None)
    attempts = []
    observed: dict[Bits, int] = {}
    for seed in range(seed_start, seed_start+seed_count) if valid else ():
        solution = puzzle.solve(seed=seed)
        if solution is None:
            raise RuntimeError("Solver returned no completion despite the finite checker finding one")
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        if bits not in groups.get(full_clues(recipe, bits), []):
            raise RuntimeError("Solver completion disagrees with the finite rule checker")
        actual_clues = tuple(recipe.extract_clues(solution, puzzle))
        if actual_clues != full_clues(recipe, bits):
            raise RuntimeError("Extracted clues disagree with the finite clue checker")
        answer_id = observed.setdefault(bits, len(observed)+1)
        attempts.append({"seed": seed, "answer_id": answer_id,
                         "answers_with_same_full_clues": len(groups[actual_clues])})
    return {
        "format": "puzzle-box/shading-analysis-v1", "rows": recipe.rows, "cols": recipe.cols,
        "rules": [rule_record(r) for r in recipe.rules], "clue_kinds": list(recipe.clue_kinds),
        "enumerated_boards": len(boards), "completion_count": len(valid),
        "minimal_conflicts": [[i+1 for i in core] for core in conflicts],
        "hint_policy": policy, "full_clue_groups": len(groups),
        "identifiable_completions": identifiable, "ambiguous_completions": len(valid)-identifiable,
        "ambiguous_example": ambiguity,
        "seed_probe": {"start": seed_start, "requested": seed_count, "attempts": attempts,
                       "distinct_completions": len(observed),
                       "identifiable_attempts": sum(a["answers_with_same_full_clues"] == 1 for a in attempts),
                       "observed_answers": [grid(bits) for bits in observed]},
        "environment": {"python": platform.python_version(), "ortools": ortools.__version__,
                        "seeded_search_workers": 1},
    }


def explain(report: dict[str, Any]) -> str:
    total, eligible = report["completion_count"], report["identifiable_completions"]
    lines = [f"Shading recipe: {report['rows']} rows x {report['cols']} columns",
             f"Exhaustively checked {report['enumerated_boards']} black/white boards.",
             f"Visible completions: {total}.", "Rules (1-based indices):"]
    lines.extend(f"  {i}: {json.dumps(rule, sort_keys=True)}" for i, rule in enumerate(report["rules"], 1))
    if not total:
        lines.append("No completion satisfies these rules. Changing seeds or clues cannot fix this recipe.")
        for conflict in report["minimal_conflicts"]:
            lines.append(f"  Conflicting rule indices: {conflict}; removing any one makes this subset feasible.")
    else:
        lines.append(f"Full candidate hints identify {eligible} of {total} completions uniquely.")
        if not eligible:
            lines.append("No seed can make this hint policy unique; change hints or rules.")
        elif eligible < total:
            lines.append("Some completions need additional hints; another seed may help, without a success guarantee.")
        else:
            lines.append("Every completion can be identified by this full candidate hint pool.")
        if (example := report["ambiguous_example"]) is not None:
            lines.append(f"Two different answers share these full clues ({example['answer_count']} answers total):")
            lines.append("  " + json.dumps(example["clues"], sort_keys=True))
            lines.extend("  " + "/".join("".join("#" if v else "." for v in row) for row in board)
                         for board in example["witnesses"])
    probe = report["seed_probe"]
    if probe["requested"] and not total:
        lines.append("Seed probe skipped because the rule set has no completion.")
    elif probe["requested"]:
        lines.append(f"Seed probe: {len(probe['attempts'])} solved, {probe['distinct_completions']} distinct answers, "
                     f"{probe['identifiable_attempts']} with uniquely identifying full hints.")
        lines.append("Observed diversity is not a sampling probability or human-difficulty estimate; symmetries count separately.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=2)
    parser.add_argument("--cols", type=int, default=2)
    parser.add_argument("--rules", nargs="*", choices=RULES, default=["count", "non-touching"])
    parser.add_argument("--hints", nargs="*", choices=CLUE_KINDS, default=["row-count", "column-count"])
    parser.add_argument("--black-count", type=int, default=2)
    parser.add_argument("--diagonal", action="store_true")
    parser.add_argument("--allow-empty-white", action="store_true")
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--seed-count", type=int, default=0)
    parser.add_argument("--json", action="store_true", help="Print the full report, including witness answers")
    parser.add_argument("--output", type=Path, help="Save the JSON report (includes witness answers)")
    args = parser.parse_args()
    try:
        choices: dict[str, ShadingRule] = {"count": BlackCount(args.black_count),
            "non-touching": NonTouchingBlack(args.diagonal),
            "connected-white": ConnectedWhite(not args.allow_empty_white), "no-white-2x2": NoWhite2x2()}
        recipe = ShadingRecipe(args.rows, args.cols, tuple(choices[r] for r in args.rules), tuple(args.hints))
        report = analyze(recipe, seed_start=args.seed_start, seed_count=args.seed_count)
        encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded if args.json else explain(report), end="" if args.json else "\n")
        return 0  # Diagnosed contradictions/ambiguity are results, not input errors.
    except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
