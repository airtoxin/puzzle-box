"""Diagnose rules against a saved coupled puzzle's actual remaining clues."""

import argparse
from functools import lru_cache
import json
from pathlib import Path
from typing import Any

from puzzle import Cell, sum_expr
from puzzle_defs import ArrowCountClue, ArrowSite, BlackCellClue, YajilinAnswer, YajilinRecipe
from puzzle_defs.puzzles.yajilin_recipe import YajilinClue
from coupled_oracle import RULES, accepts, answer_key, full_clues, rule_names, universe
from coupled_records import check_output, load_puzzle, read_puzzle
from explore_coupled import CoupledModel, answer_record, diagram, model_answers
from generate_yajilin import clue_record


def build_model(recipe: YajilinRecipe, mask: int, clues: frozenset[YajilinClue]) -> CoupledModel:
    """Compile validated hints with the existing DSL, independently of the oracle."""
    puzzle = CoupledModel(recipe, mask)
    sites = {s.cell: s for s in recipe.arrow_sites}
    for clue in sorted(clues, key=lambda c: json.dumps(clue_record(c), sort_keys=True)):
        if isinstance(clue, ArrowCountClue):
            puzzle.add(sum_expr(puzzle.black[c] for c in recipe.ray(sites[clue.cell])) == clue.count)
        elif isinstance(clue, BlackCellClue):
            puzzle.add(puzzle.black[clue.cell] == clue.black)
        else:
            puzzle.add(puzzle.edge_on[clue.edge] == clue.used)
    return puzzle


def diagnose(data: Any, *, verify_models: bool = False, time_limit: float = 10) -> dict[str, Any]:
    recipe, mask, clues, expected = read_puzzle(data)
    space = universe(recipe)
    signatures = {a: frozenset(full_clues(recipe, a, recipe.clue_kinds)) for a in space}
    checked = 0

    @lru_cache(maxsize=None)
    def answers(current_mask: int, hints: frozenset[YajilinClue]) -> frozenset[YajilinAnswer]:
        nonlocal checked
        result = frozenset(a for a in space if hints <= signatures[a] and accepts(recipe, current_mask, a))
        if verify_models:
            actual, _ = model_answers(build_model(recipe, current_mask, hints), time_limit=time_limit)
            if actual != result:
                raise RuntimeError(f"Rule mask {current_mask}: model answers differ from the finite oracle")
            checked += 1
        return result

    stored = frozenset(clues)
    original = answers(mask, stored)
    if not original:
        raise ValueError("Stored rules and clues are infeasible (0 joint answers)")
    if len(original) != 1:
        raise ValueError(f"Stored clues are not uniquely solvable ({len(original)} joint answers)")
    if expected not in original:
        raise ValueError("Stored black cells or loop edges do not match the uniquely determined answer")
    full = full_clues(recipe, expected, recipe.clue_kinds)
    removable = [i + 1 for i in range(len(clues))
                 if len(answers(mask, frozenset(clues[:i] + clues[i+1:]))) == 1]

    def witness(found: frozenset[YajilinAnswer]) -> dict[str, Any] | None:
        other = found - original
        return answer_record(min(other, key=answer_key)) if other else None

    removals = []
    for bit, name in enumerate(RULES):
        if not mask & (1 << bit):
            continue
        relaxed = mask ^ (1 << bit)
        stored_answers = answers(relaxed, stored)
        all_answers = answers(relaxed, frozenset(full))
        removals.append({"rule": name, "removed_bit": 1 << bit, "remaining_rule_mask": relaxed,
            "answers_with_stored_clues": len(stored_answers),
            "necessary_with_stored_clues": len(stored_answers) > 1,
            "stored_clue_alternative": witness(stored_answers),
            "answers_with_full_candidate_clues": len(all_answers),
            "necessary_with_full_candidate_clues": len(all_answers) > 1,
            "full_clue_alternative": witness(all_answers),
            "needed_with_stored_but_not_full_clues": len(stored_answers) > 1 and len(all_answers) == 1})
    return {"format": "puzzle-box/coupled-stored-rule-analysis-v1", "source_format": data["format"],
        "rows": recipe.rows, "cols": recipe.cols, "rule_mask": mask, "rules": rule_names(mask),
        "arrow_sites": [{"cell": list(s.cell), "direction": s.direction} for s in recipe.arrow_sites],
        "clue_kinds": list(recipe.clue_kinds), "answer_projection": ["black_cells", "loop_edges"],
        "answer": answer_record(expected), "stored_clues": [clue_record(c) for c in clues],
        "full_candidate_clues": [clue_record(c) for c in full], "enumerated_base_answers": len(space),
        "original_answer_count": 1, "stored_clues_irreducible": not removable,
        "removable_clue_indices": removable, "comparison_is_for_stored_answer_only": True,
        "models_verified": verify_models, "model_queries_verified": checked, "removals": removals}


def explain(report: dict[str, Any]) -> str:
    sites = [ArrowSite(Cell(*s["cell"]), s["direction"]) for s in report["arrow_sites"]]

    def picture(answer: dict[str, Any]) -> str:
        return diagram(report["rows"], report["cols"], sites, answer)

    lines = [f"Saved coupled puzzle: {report['rows']} x {report['cols']}; exactly 1 joint cell + edge answer.",
        f"Rules (mask {report['rule_mask']}): {', '.join(report['rules']) or '(none)'}",
        "Fixed: arrow obstacles, nonempty edges, degree 0 or 2. Masks 0..6 are not standard Yajilin.",
        "Stored clues: " + json.dumps(report["stored_clues"], sort_keys=True),
        f"Full candidate clues: {len(report['full_candidate_clues'])}; only this stored answer is compared.",
        f"Irreducible clues: {report['stored_clues_irreducible']}; removable occurrences: {report['removable_clue_indices']}",
        "Original answer (# black, . white, arrows blocked):", picture(report["answer"]), "",
        "Remove rule | All candidate clues: answers | Stored clues: answers"]
    for removal in report["removals"]:
        lines.append(f"{removal['rule']} | {removal['answers_with_full_candidate_clues']} | {removal['answers_with_stored_clues']}")
        for key, label in (("stored_clue_alternative", "SAME stored clues"),
                           ("full_clue_alternative", "SAME full candidate clues")):
            if removal[key] is not None:
                lines.extend([f"Alternative with {label}:", picture(removal[key])])
    lines.extend(["", f"Model/oracle comparison: {'verified' if report['models_verified'] else 'not requested'}",
        "Each rule is removed separately. The other rules, obstacles and original hints stay fixed.",
        "Do not delete all individually redundant rules/clues together. No input is modified.",
        "Finite-board uniqueness only: not human difficulty, a minimum rule set or a general equivalence proof."])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="A saved puzzle; the report reveals the answer and alternatives")
    parser.add_argument("--verify-models", action="store_true", help="Cross-check all reported solution sets with CP-SAT")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path, help="Save the JSON report to a different file")
    args = parser.parse_args()
    try:
        if args.output is not None:
            check_output(args.file, args.output)
        report = diagnose(load_puzzle(args.file), verify_models=args.verify_models)
        encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded if args.json else explain(report), end="" if args.json else "\n")
    except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
