"""Compare all subsets of a small pool of built-in shading rules."""

import argparse
from collections.abc import Sequence
import json
from pathlib import Path
import platform
from typing import Any

import ortools

from puzzle_defs import BlackCount, ConnectedWhite, NonTouchingBlack, NoWhite2x2, ShadingRecipe
from puzzle_defs.puzzles.shading import CLUE_KINDS, Clue, ClueKind, ShadingRule
from analyze_shading import finite_space, full_clues
from generate_shading import RULES, clue_record, rule_record
from shading_recipe import check_distinct_paths, recipe_record


def explore(rows: int, cols: int, candidates: Sequence[ShadingRule],
            clue_kinds: tuple[ClueKind, ...] = ("row-count", "column-count")) -> dict[str, Any]:
    """Rules in candidates are optional occurrences, not a fixed base recipe."""
    recipe = ShadingRecipe(rows, cols, tuple(candidates), clue_kinds)
    _, boards, rule_masks = finite_space(recipe)
    signatures = [full_clues(recipe, bits) for bits in boards]
    allowed = [set(range(len(boards)))]
    for mask in range(1, 2**len(candidates)):
        bit = mask & -mask
        allowed.append(allowed[mask ^ bit] & rule_masks[bit.bit_length()-1])
    groups: list[dict[tuple[Clue, ...], list[int]]] = []
    for answers in allowed:
        grouped: dict[tuple[Clue, ...], list[int]] = {}
        for answer in sorted(answers):
            grouped.setdefault(signatures[answer], []).append(answer)
        groups.append(grouped)

    def grid(index: int) -> list[list[int]]:
        bits = boards[index]
        return [list(bits[r*cols:(r+1)*cols]) for r in range(rows)]

    equivalences: dict[frozenset[int], int] = {}
    combinations = []
    for mask, answers in enumerate(allowed):
        indices = [i for i in range(len(candidates)) if mask & (1 << i)]
        identifiable = sum(len(g) == 1 for g in groups[mask].values())
        removals = []
        for index in indices:
            relaxed = mask ^ (1 << index)
            added = allowed[relaxed] - answers
            # No redundancy or uniqueness claims about an infeasible recipe.
            affected = [a for a in sorted(answers)
                        if len(groups[relaxed][signatures[a]]) > len(groups[mask][signatures[a]])]
            lost = [a for a in affected if len(groups[mask][signatures[a]]) == 1]
            witness = None
            if affected:
                before = (lost or affected)[0]
                alternative = next(a for a in groups[relaxed][signatures[before]] if a in added)
                witness = {"original_answer": grid(before), "new_answer_without_rule": grid(alternative),
                           "clues": [clue_record(c) for c in signatures[before]],
                           "unique_before": before in lost}
            removals.append({"rule_index": index+1, "completions_without_rule": len(allowed[relaxed]),
                "added_completions": len(added),
                "redundant_without_hints": not added if answers else None,
                "redundant_given_full_hints": not affected if answers else None,
                "hint_affected_completions": len(affected) if answers else None,
                "uniqueness_tested_completions": identifiable,
                "uniqueness_lost_completions": len(lost) if identifiable else None,
                "added_answer_witness": grid(min(added)) if added else None,
                "same_hint_witness": witness})
        combinations.append({"mask": mask, "rule_indices": [i+1 for i in indices],
            "completion_count": len(answers), "identifiable_completions": identifiable,
            "equivalence_id": equivalences.setdefault(frozenset(answers), len(equivalences)+1) if answers else None,
            "redundant_without_hints": [r["rule_index"] for r in removals if r["redundant_without_hints"] is True]
                                      if answers else None,
            "redundant_given_full_hints": [r["rule_index"] for r in removals if r["redundant_given_full_hints"] is True]
                                         if answers else None,
            "removals": removals})
    return {"format": "puzzle-box/shading-exploration-v1", "rows": rows, "cols": cols,
        "candidates": [rule_record(r) for r in candidates], "clue_kinds": list(recipe.clue_kinds),
        "enumerated_boards": len(boards), "enumerated_combinations": len(combinations),
        "feasible_combinations": sum(bool(a) for a in allowed),
        "identifiable_combinations": sum(c["identifiable_completions"] > 0 for c in combinations),
        "distinct_feasible_answer_sets": len(equivalences), "combinations": combinations,
        "environment": {"python": platform.python_version(), "ortools": ortools.__version__}}


def explain(report: dict[str, Any], selected: list[int] | None = None) -> str:
    count = len(report["candidates"])
    if selected is not None and (any(type(i) is not int or not 1 <= i <= count for i in selected)
                                 or len(set(selected)) != len(selected)):
        raise ValueError("Explanation indices must be distinct 1-based candidate indices")
    lines = [f"Shading exploration: {report['rows']} rows x {report['cols']} columns",
        f"Checked {report['enumerated_boards']} boards x {report['enumerated_combinations']} rule subsets.",
        f"Feasible subsets: {report['feasible_combinations']}; subsets with identifiable completions: {report['identifiable_combinations']}.",
        "Candidate rules (1-based indices):"]
    lines.extend(f"  {i}: {json.dumps(r, sort_keys=True)}" for i, r in enumerate(report["candidates"], 1))
    lines.extend(["", "Rules | Answers | Unique with full hints | Answer-set class | Redundant: no hints / full hints"])
    for combo in sorted(report["combinations"], key=lambda c: (len(c["rule_indices"]), c["rule_indices"])):
        if selected is not None and combo["rule_indices"] != sorted(selected):
            continue
        def label(values) -> str:
            return "n/a" if values is None else "+".join(map(str, values)) or "-"
        lines.append(f"{label(combo['rule_indices'])} | {combo['completion_count']} | {combo['identifiable_completions']} | "
                     f"{combo['equivalence_id'] or '-'} | {label(combo['redundant_without_hints'])} / {label(combo['redundant_given_full_hints'])}")
        if selected is not None:
            for removal in combo["removals"]:
                lost = removal["uniqueness_lost_completions"]
                lines.append(f"  Remove rule {removal['rule_index']}: {removal['added_completions']} added answers; "
                             f"uniqueness lost for {lost if lost is not None else 'n/a'} / {removal['uniqueness_tested_completions']} previously unique completions.")
                if (witness := removal["same_hint_witness"]) is not None:
                    lines.append("    Shared full hints: " + json.dumps(witness["clues"], sort_keys=True))
                    for key in ("original_answer", "new_answer_without_rule"):
                        lines.append("    " + key + ": " + "/".join("".join("#" if v else "." for v in row)
                                                                 for row in witness[key]))
    lines.extend(["", "Redundancy is relative to this board, this subset and these FULL candidate hints.",
        "Do not remove all individually redundant rules at once. Reduced puzzles may still need them.",
        "n/a means no feasible / previously unique completion to compare; it is not evidence of redundancy.",
        "Answer-set classes compare exact board assignments, not symmetries, difficulty or global rule equivalence."])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=2)
    parser.add_argument("--cols", type=int, default=2)
    parser.add_argument("--candidates", nargs="*", choices=RULES, default=list(RULES))
    parser.add_argument("--black-counts", type=int, nargs="+", default=[2])
    parser.add_argument("--include-diagonal", action="store_true",
                        help="Include a second non-touching candidate that also forbids diagonal contact")
    parser.add_argument("--allow-empty-white", action="store_true")
    parser.add_argument("--hints", nargs="*", choices=CLUE_KINDS, default=["row-count", "column-count"])
    parser.add_argument("--explain", nargs="*", type=int, help="Show removal effects for one subset of 1-based rule indices")
    parser.add_argument("--export-recipe", type=Path, help="Save the subset selected by --explain as a recipe")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path, help="Save the complete JSON report, including witness answers")
    args = parser.parse_args()
    try:
        if args.export_recipe is not None and args.explain is None:
            raise ValueError("Use --explain with explicit rule indices (or no indices) to export a recipe")
        if args.json and args.explain is not None:
            raise ValueError("Use --explain for text details or --json for the complete report")
        if args.include_diagonal and "non-touching" not in args.candidates:
            raise ValueError("--include-diagonal requires the non-touching candidate")
        candidates: list[ShadingRule] = []
        for kind in args.candidates:
            if kind == "count":
                candidates.extend(BlackCount(n) for n in args.black_counts)
            elif kind == "non-touching":
                candidates.append(NonTouchingBlack())
                if args.include_diagonal:
                    candidates.append(NonTouchingBlack(True))
            elif kind == "connected-white":
                candidates.append(ConnectedWhite(not args.allow_empty_white))
            else:
                candidates.append(NoWhite2x2())
        report = explore(args.rows, args.cols, candidates, tuple(args.hints))
        rendered = explain(report, args.explain)  # Validate selection before writing.
        exported = None
        if args.export_recipe is not None:
            if args.output is not None:
                check_distinct_paths(args.export_recipe, args.output)
            selected = tuple(candidates[i-1] for i in sorted(args.explain))
            exported = recipe_record(ShadingRecipe(args.rows, args.cols, selected, tuple(args.hints)))
        encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.export_recipe is not None:
            args.export_recipe.write_text(json.dumps(exported, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args.output is not None:
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded if args.json else rendered, end="" if args.json else "\n")
        return 0
    except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
