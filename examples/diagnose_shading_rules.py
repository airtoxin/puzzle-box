"""Compare rule contributions with a saved puzzle's actual and full candidate clues."""

import argparse
import json
from pathlib import Path
import platform
from typing import Any

import ortools

from puzzle_defs import ColumnCountClue, RowCountClue, ShadingRecipe
from puzzle_defs.puzzles.shading import Clue
from analyze_shading import finite_space, full_clues
from generate_shading import FORMAT, MIXED_FORMAT, clue_record, read_clue
from shading_recipe import RECIPE_FORMAT, check_distinct_paths, load_json, read_recipe, rule_record


def _read_puzzle(data: Any) -> tuple[ShadingRecipe, list[Clue], list[list[int]]]:
    if not isinstance(data, dict) or data.get("format") not in (FORMAT, MIXED_FORMAT):
        raise ValueError("Use a generated shading-v1 or shading-v2 puzzle, not a recipe or report")
    legacy = data["format"] == FORMAT
    required = {"format", "rows", "cols", "rules", "clues", "solution"}
    if not legacy:
        required.add("clue_kinds")
    if not required <= set(data) or set(data) - required - {"seed", "environment"}:
        raise ValueError("Missing or unknown puzzle fields")
    recipe = read_recipe({"format": RECIPE_FORMAT, "rows": data["rows"], "cols": data["cols"],
                          "rules": data["rules"], "clue_kinds": ["cell"] if legacy else data["clue_kinds"]})
    if recipe.rows * recipe.cols > 9:
        raise ValueError("Stored-clue diagnostics support at most 9 cells")
    raw_clues = data["clues"]
    if not isinstance(raw_clues, list) or len(raw_clues) > 32:
        raise ValueError("Stored clues must be an array of at most 32 clue occurrences")
    if legacy and any(not isinstance(c, list) or len(c) != 3 for c in raw_clues):
        raise ValueError("A v1 cell clue must be an array of row, column and value")
    clues = [read_clue(c, legacy=legacy) for c in raw_clues]
    for clue in clues:
        kind = "row-count" if isinstance(clue, RowCountClue) else (
            "column-count" if isinstance(clue, ColumnCountClue) else "cell")
        if kind not in recipe.clue_kinds:
            raise ValueError("Stored clue type is not enabled by clue_kinds")
    answer = data["solution"]
    if (not isinstance(answer, list) or len(answer) != recipe.rows
            or any(not isinstance(row, list) or len(row) != recipe.cols
                   or any(type(v) is not int or v not in (0, 1) for v in row) for row in answer)):
        raise ValueError("Invalid stored solution grid")
    recipe.build_from_clues(clues)  # Validate coordinates, counts and cell values with the real builder.
    return recipe, clues, answer


def diagnose(data: Any) -> dict[str, Any]:
    recipe, clues, answer = _read_puzzle(data)
    _, boards, masks = finite_space(recipe)
    signatures = [set(full_clues(recipe, bits)) for bits in boards]

    def matches(hints: list[Clue] | tuple[Clue, ...]) -> set[int]:
        required = set(hints)
        return {i for i, signature in enumerate(signatures) if required <= signature}

    def allowed(without: int | None = None) -> set[int]:
        result = set(range(len(boards)))
        for i, mask in enumerate(masks):
            if i != without:
                result.intersection_update(mask)
        return result

    def grid(index: int) -> list[list[int]]:
        bits = boards[index]
        return [list(bits[r*recipe.cols:(r+1)*recipe.cols]) for r in range(recipe.rows)]

    base = allowed()
    stored_matches = matches(clues)
    answers = base & stored_matches
    if not answers:
        raise ValueError("Stored rules and clues are infeasible (0 answers)")
    if len(answers) != 1:
        raise ValueError(f"Stored clues are not uniquely solvable ({len(answers)} answers)")
    original = next(iter(answers))
    if grid(original) != answer:
        raise ValueError("Stored solution does not match the uniquely determined answer")
    # Keep the hints of the original answer fixed, even after removing a rule.
    full = full_clues(recipe, boards[original])
    full_matches = matches(full)
    removable_clues = [i+1 for i in range(len(clues))
                       if len(base & matches(clues[:i] + clues[i+1:])) == 1]
    removals = []
    for i, rule in enumerate(recipe.rules):
        relaxed = allowed(without=i)
        stored_answers, full_answers = relaxed & stored_matches, relaxed & full_matches
        stored_added, full_added = stored_answers - answers, full_answers - answers
        removals.append({"rule_index": i+1, "rule": rule_record(rule),
            "answers_with_stored_clues": len(stored_answers),
            "necessary_with_stored_clues": bool(stored_added),
            "stored_clue_alternative": grid(min(stored_added)) if stored_added else None,
            "answers_with_full_candidate_clues": len(full_answers),
            "necessary_with_full_candidate_clues": bool(full_added),
            "full_clue_alternative": grid(min(full_added)) if full_added else None,
            "needed_with_stored_but_not_full_clues": bool(stored_added) and not full_added})
    return {"format": "puzzle-box/shading-stored-rule-analysis-v1", "rows": recipe.rows, "cols": recipe.cols,
        "source_format": data["format"], "clue_kinds": list(recipe.clue_kinds),
        "answer": answer, "stored_clues": [clue_record(c) for c in clues],
        "full_candidate_clues": [clue_record(c) for c in full],
        "enumerated_boards": len(boards), "original_answer_count": len(answers),
        "stored_clues_irreducible": not removable_clues, "removable_clue_indices": removable_clues,
        "comparison_is_for_stored_answer_only": True, "removals": removals,
        "environment": {"python": platform.python_version(), "ortools": ortools.__version__}}


def explain(report: dict[str, Any]) -> str:
    def picture(board: list[list[int]]) -> str:
        return "/".join("".join("#" if v else "." for v in row) for row in board)

    lines = [f"Stored puzzle: {report['rows']} rows x {report['cols']} columns; exactly 1 answer.",
        f"Checked {report['enumerated_boards']} boards; original answer: {picture(report['answer'])}",
        "Stored clues: " + json.dumps(report["stored_clues"], sort_keys=True),
        f"Full candidate clues: {len(report['full_candidate_clues'])}; compared only for this original answer.",
        f"Stored clues irreducible: {report['stored_clues_irreducible']}; removable occurrences: {report['removable_clue_indices']}",
        "", "Remove rule | Full candidate hints: answers / role | Stored hints: answers / role"]
    for removal in report["removals"]:
        full_role = "necessary" if removal["necessary_with_full_candidate_clues"] else "redundant"
        stored_role = "necessary" if removal["necessary_with_stored_clues"] else "redundant"
        lines.append(f"{removal['rule_index']}: {json.dumps(removal['rule'], sort_keys=True)} | "
                     f"{removal['answers_with_full_candidate_clues']} / {full_role} | "
                     f"{removal['answers_with_stored_clues']} / {stored_role}")
        if removal["stored_clue_alternative"] is not None:
            lines.append("  Alternative with the SAME stored clues: " + picture(removal["stored_clue_alternative"]))
        if removal["full_clue_alternative"] is not None:
            lines.append("  Alternative even with ALL candidate clues: " + picture(removal["full_clue_alternative"]))
    lines.extend(["", "Each rule is removed separately; all other rules and the original clues stay fixed.",
        "Do not delete all individually redundant rules or clues together. No input is modified.",
        "This is a finite-board uniqueness comparison, not a human solving strategy or a minimum rule set."])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="A generated shading puzzle; the report reveals answers")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path, help="Save the JSON report, including alternative answers")
    args = parser.parse_args()
    try:
        if args.output is not None:
            check_distinct_paths(args.file, args.output)
        report = diagnose(load_json(args.file, label="Puzzle"))
        encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded if args.json else explain(report), end="" if args.json else "\n")
        return 0
    except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
