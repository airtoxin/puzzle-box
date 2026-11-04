"""Explain bounded shading deductions; stop honestly when they are insufficient."""

import argparse
from itertools import combinations
import json
from pathlib import Path
import sys
from typing import Any

from puzzle_defs import BlackCount, ColumnCountClue, ConnectedWhite, NonTouchingBlack, NoWhite2x2, RowCountClue, ShadingRecipe
from puzzle_defs.puzzles.shading import Clue
from diagnose_shading_rules import _read_puzzle
from generate_shading import verify
from shading_recipe import load_json


def _white_connector(cells: list[tuple[int, int]], known: dict[tuple[int, int], int]) -> tuple[tuple[int, int], dict[str, Any]] | None:
    """Find a vertex whose removal separates two already-white terminals."""
    possible = {c for c in cells if known.get(c) != 1}
    white = {c for c in possible if known.get(c) == 0}
    if len(white) < 2:
        return None
    start = min(white)

    def reachable(allowed):
        seen, pending = set(), [start]
        while pending:
            point = pending.pop()
            if point in seen:
                continue
            seen.add(point)
            r, c = point
            pending.extend(n for n in ((r-1, c), (r+1, c), (r, c-1), (r, c+1)) if n in allowed and n not in seen)
        return seen

    if not white <= reachable(possible):
        raise ValueError("Known white cells have no possible orthogonal connection")
    for candidate in sorted(possible - white):
        reached = reachable(possible - {candidate})
        if separated := white - reached:
            return candidate, {"terminals": [list(start), list(min(separated))],
                               "reachable_without_cell": [list(c) for c in sorted(reached)]}
    return None


def _propagate(recipe: ShadingRecipe, clues: list[Clue]) -> dict[str, Any]:
    """Use validated built-in rules and clues only: no solver or saved answer."""
    cells = [(r, c) for r in range(recipe.rows) for c in range(recipe.cols)]
    known: dict[tuple[int, int], int] = {}
    origins: dict[tuple[int, int], dict[str, Any]] = {}
    givens, constraints, connectivity = [], [], []

    def add(kind, scope, source, target=None):
        constraints.append({"kind": kind, "scope": [list(c) for c in scope],
                            "source": source, "target": target})

    for index, rule in enumerate(recipe.rules, 1):
        source = {"kind": "rule", "index": index}
        if type(rule) is BlackCount:
            add("count", cells, source, rule.count)
        elif type(rule) is NonTouchingBlack:
            for a, b in combinations(cells, 2):
                distance = max(abs(a[0]-b[0]), abs(a[1]-b[1])) if rule.diagonal else abs(a[0]-b[0])+abs(a[1]-b[1])
                if distance == 1:
                    add("non-touching", [a, b], source)
        elif type(rule) is NoWhite2x2:
            for r in range(recipe.rows-1):
                for c in range(recipe.cols-1):
                    add("has-black", [(r, c), (r, c+1), (r+1, c), (r+1, c+1)], source)
        elif type(rule) is ConnectedWhite:
            connectivity.append(source)
        else:
            raise ValueError("Unsupported rule type")
    for index, clue in enumerate(clues, 1):
        source = {"kind": "clue", "index": index}
        if isinstance(clue, RowCountClue):
            add("count", [(clue.row, c) for c in range(recipe.cols)], source, clue.count)
        elif isinstance(clue, ColumnCountClue):
            add("count", [(r, clue.col) for r in range(recipe.rows)], source, clue.count)
        else:
            cell, value = clue
            key = (cell.row, cell.col)
            if key in known and known[key] != value:
                raise ValueError("Conflicting cell givens")
            known[key] = value
            origins.setdefault(key, {"kind": "given", "index": index})
            givens.append({"clue_index": index, "cell": list(key), "value": value})
    # Exhaust simpler local deductions before a graph deduction, then start over.
    for source in connectivity:
        add("connected-white", cells, source)

    steps = []
    while True:
        for constraint in constraints:
            scope = [tuple(c) for c in constraint["scope"]]
            unknown = [c for c in scope if c not in known]
            black = sum(known.get(c, 0) for c in scope)
            kind, target = constraint["kind"], constraint["target"]
            inference: tuple[int, str, str] | None = None
            chosen_cell, witness = None, None
            if kind == "count":
                if black > target or black + len(unknown) < target:
                    raise ValueError("Count constraint conflicts with the known cells")
                if unknown and black == target:
                    inference = (0, "count-satisfied", f"Target {target}; {black} black already known. Every remaining cell in this scope is white.")
                elif unknown and black + len(unknown) == target:
                    inference = (1, "count-fill", f"Target {target}; {black} black and {len(unknown)} unknown. Every unknown cell in this scope must be black.")
            elif kind == "non-touching":
                if black > 1:
                    raise ValueError("Known black cells touch in a forbidden direction")
                if black == 1 and unknown:
                    inference = (0, "black-neighbor", "The other cell in this forbidden neighbor pair is black, so this cell is white.")
            elif kind == "has-black" and black == 0:
                if not unknown:
                    raise ValueError("A 2x2 window is all white")
                if len(unknown) == 1:
                    inference = (1, "last-in-window", "The other three cells of this 2x2 window are white, so its last cell must be black.")
            elif kind == "connected-white":
                if connector := _white_connector(cells, known):
                    chosen_cell, witness = connector
                    a, b = witness["terminals"]
                    inference = (0, "white-connector", f"Making {list(chosen_cell)} black would separate known white cells {a} and {b} even if every other unknown cell were white. This connector must be white.")
            if inference is None:
                continue
            value, technique, reason = inference
            cell = chosen_cell if chosen_cell is not None else unknown[0]
            number = len(steps) + 1
            steps.append({"number": number, "cell": list(cell), "value": value,
                "technique": technique, "reason": reason, "constraint": constraint,
                "premises": [{"cell": list(c), "value": known[c], "origin": origins[c]}
                             for c in scope if c in known],
                "unknown_cells": [list(c) for c in unknown]})
            if witness is not None:
                steps[-1]["connectivity_witness"] = witness
            known[cell] = value
            origins[cell] = {"kind": "step", "index": number}
            break  # Reconsider constraints after exactly one new fact.
        else:
            break
    return {"givens": givens, "steps": steps,
            "cells": [[known.get((r, c)) for c in range(recipe.cols)] for r in range(recipe.rows)],
            "unresolved_cells": [list(c) for c in cells if c not in known],
            "rules_without_deductions": []}


def explain_puzzle(data: Any) -> dict[str, Any]:
    recipe, clues, answer = _read_puzzle(data)
    validation = verify(data)  # Separate artifact check; never passed into propagation.
    try:
        trace = _propagate(recipe, clues)
        if any(value is not None and value != answer[r][c]
               for r, row in enumerate(trace["cells"]) for c, value in enumerate(row)):
            raise RuntimeError("A deduction disagrees with the independently verified answer")
        return {"format": "puzzle-box/shading-deduction-trace-v1", "rows": recipe.rows, "cols": recipe.cols,
                "artifact_verification": validation, "status": "stalled" if trace["unresolved_cells"] else "solved",
                **trace}
    except (ValueError, TypeError, KeyError) as exc:
        # Input validation already succeeded. A contradictory deduction or broken
        # trace is an internal error, never evidence that the candidate is invalid.
        raise RuntimeError(f"Deduction failed after puzzle verification: {exc}") from exc


def explain(report: dict[str, Any]) -> str:
    picture = lambda rows: "/".join("".join("?" if v is None else "#" if v else "." for v in row) for row in rows)
    lines = ["Saved puzzle: unique answer and irreducible clues verified separately.",
             "Coordinates are zero-based; # = black, . = white, ? = unresolved. This trace reveals deductions.",
             "Givens: " + json.dumps(report["givens"])]
    for step in report["steps"]:
        source = step["constraint"]["source"]
        lines.append(f"Step {step['number']}: {step['cell']} = {'black' if step['value'] else 'white'} "
                     f"from {source['kind']} {source['index']}. {step['reason']}")
        lines.append("  Scope: " + json.dumps(step["constraint"]["scope"]) + "; known premises: " + json.dumps(step["premises"]))
        if "connectivity_witness" in step:
            lines.append("  Connectivity witness: " + json.dumps(step["connectivity_witness"]))
    lines.append("State: " + picture(report["cells"]))
    lines.append("Solved by the supported deductions." if report["status"] == "solved" else
                 f"Unresolved: {len(report['unresolved_cells'])} cells. The supported deductions are exhausted; no guesses were made.")
    lines.append(f"Rules checked by artifact verification but without deduction techniques: {report['rules_without_deductions']}.")
    lines.append("A unique answer does not ensure this procedure finishes. This is not a human-difficulty rating.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="A generated shading-v1/v2 puzzle (at most 9 cells); this reveals deductions")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = explain_puzzle(load_json(args.file, label="Puzzle"))
        print(json.dumps(report, indent=2, sort_keys=True) if args.json else explain(report))
        return 0 if report["status"] == "solved" else 1
    except RuntimeError as exc:
        print(f"Internal error: {exc}", file=sys.stderr)
        return 3
    except (ValueError, TypeError, KeyError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
