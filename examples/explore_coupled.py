"""Compare eight cell/loop rule sets and eight full-candidate hint policies."""

import argparse
import json
from typing import Any, Sequence, cast

from ortools.sat.python import cp_model

from puzzle import Cell, Puzzle, Vertex, at_least_one, non_touching, one_of, single_cycle, square_grid, sum_expr
from puzzle_defs import ArrowSite, YajilinAnswer, YajilinRecipe
from puzzle_defs.puzzles.yajilin_recipe import YajilinClueKind

from coupled_oracle import HINTS, RULES, accepts, answer_key, check_size, groups, rule_names, universe
from generate_yajilin import clue_record
from generate_slitherlink import edge_record


class CoupledModel(Puzzle):
    """Experiment model; rule removal deliberately permits non-Yajilin answers."""

    def __init__(self, recipe: YajilinRecipe, mask: int):
        check_size(recipe)
        rule_names(mask)
        super().__init__("coupled rule experiment")
        board = square_grid(recipe.rows, recipe.cols)
        loop_board = square_grid(recipe.rows - 1, recipe.cols - 1)
        blocked = {s.cell for s in recipe.arrow_sites}
        self.cells = [c for c in board.cells if c not in blocked]
        self.edges = loop_board.edges
        self.black = self.bool_var_map("black", self.cells)
        self.edge_on = self.bool_var_map("edge", self.edges)
        self.set_solution_vars([self.black[c] for c in self.cells] + [self.edge_on[e] for e in self.edges])
        self.add(at_least_one(self.edge_on[e] for e in self.edges))
        for cell in board.cells:
            terms = [self.edge_on[e] for e in loop_board.edges_incident(Vertex(*cell))]
            if cell in blocked:
                self.add(sum_expr(terms) == 0)
            else:
                degree = sum_expr(terms)
                self.add(one_of(degree == 0, degree == 2))
                if mask & 1:
                    self.add(sum_expr(terms + [self.black[cell], self.black[cell]]) == 2)
        if mask & 2:
            self.add(non_touching(self.black, board.adjacent_cell_pairs()))
        if mask & 4:
            self.add(single_cycle(self.edge_on, loop_board))


def model_answers(puzzle: CoupledModel, *, time_limit: float = 10) -> tuple[set[YajilinAnswer], int]:
    """Enumerate a bounded CP-SAT model, deduplicating visible joint answers.

    Auxiliary orientations may have multiple assignments. This diagnostic uses
    the low-level model only to verify the oracle, never as a uniqueness count.
    """
    class Collector(cp_model.CpSolverSolutionCallback):
        def __init__(self):
            super().__init__()
            self.answers: set[YajilinAnswer] = set()
            self.raw = 0

        def on_solution_callback(self) -> None:
            self.raw += 1
            self.answers.add(YajilinAnswer(
                frozenset(c for c in puzzle.cells if self.value(puzzle.black[c]._internal)),
                frozenset(e for e in puzzle.edges if self.value(puzzle.edge_on[e]._internal)),
            ))

    collector = Collector()
    solver = cp_model.CpSolver()
    solver.parameters.enumerate_all_solutions = True
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = time_limit
    status = solver.solve(puzzle._model, collector)
    if status not in (cp_model.OPTIMAL, cp_model.INFEASIBLE):
        raise RuntimeError("Model enumeration did not finish; completeness is not verified")
    return collector.answers, collector.raw


def answer_record(answer: YajilinAnswer) -> dict[str, Any]:
    return {"black_cells": [list(c) for c in sorted(answer.black_cells)],
            "loop_edges": [edge_record(e) for e in sorted(answer.loop_edges)]}


def analyze(rows: int, cols: int, sites: Sequence[ArrowSite] = (), *, verify_models: bool = False) -> dict[str, Any]:
    recipe = YajilinRecipe(rows, cols, tuple(sites))
    check_size(recipe)
    space = universe(recipe)
    answers = {mask: tuple(a for a in space if accepts(recipe, mask, a)) for mask in range(8)}
    policies: list[tuple[YajilinClueKind, ...]] = [
        tuple(k for i, k in enumerate(HINTS) if mask & (1 << i)) for mask in range(8)]
    grouped = {(mask, kinds): groups(recipe, answers[mask], kinds)
               for mask in range(8) for kinds in policies}
    results = []
    for mask in range(8):
        removed = [i for i in range(3) if mask & (1 << i)]
        row: dict[str, Any] = {
            "mask": mask, "rules": rule_names(mask), "answer_count": len(answers[mask]),
            "black_pattern_count": len({a.black_cells for a in answers[mask]}),
            "edge_pattern_count": len({a.loop_edges for a in answers[mask]}),
            "minimal_conflict": bool(mask and not answers[mask]
                                     and all(answers[mask ^ (1 << i)] for i in removed)),
            "removals": [], "hints": [],
        }
        for i in removed:
            extra = set(answers[mask ^ (1 << i)]) - set(answers[mask])
            row["removals"].append({"rule": RULES[i], "added_answers": len(extra),
                                    "redundant_on_this_layout": not extra,
                                    "witness": answer_record(min(extra, key=answer_key)) if extra else None})
        for kinds in policies:
            buckets = grouped[mask, kinds]
            false_unique = [(clues, group) for clues, group in buckets.items()
                            if len(group) > 1 and len({a.black_cells for a in group}) == 1]
            counterexample = None
            if false_unique:
                clues, group = false_unique[0]
                counterexample = {"clues": [clue_record(c) for c in clues],
                                  "answers": [answer_record(a) for a in group[:2]]}
            row["hints"].append({
                "kinds": list(kinds), "signature_count": len(buckets),
                "unique_joint_groups": sum(len(g) == 1 for g in buckets.values()),
                "unique_black_groups": sum(len({a.black_cells for a in g}) == 1 for g in buckets.values()),
                "false_unique_black_groups": len(false_unique),
                "projection_counterexample": counterexample,
                "unique_groups_lost_if_removed": {
                    RULES[i]: sum(len(group) == 1 and len(grouped[mask ^ (1 << i), kinds][clues]) > 1
                                  for clues, group in buckets.items()) for i in removed},
            })
        if verify_models:
            actual, raw = model_answers(CoupledModel(recipe, mask))
            if actual != set(answers[mask]):
                raise RuntimeError(f"Rule mask {mask}: model answers differ from the finite oracle")
            row["model_verification"] = {"equal": True, "raw_assignments": raw,
                                          "distinct_joint_answers": len(actual)}
        results.append(row)
    return {"format": "puzzle-box/coupled-exploration-v1", "rows": rows, "cols": cols,
            "arrow_sites": [{"cell": list(s.cell), "direction": s.direction} for s in recipe.arrow_sites],
            "base_answer_count": len(space), "fixed_base_infeasible": not space,
            "answer_projection": ["black_cells", "loop_edges"],
            "hint_scope": "all candidate clues of each selected kind; no clue reduction",
            "models_verified": verify_models, "combinations": results}


def diagram(rows: int, cols: int, sites: Sequence[ArrowSite], answer: dict[str, Any]) -> str:
    black = {tuple(c) for c in answer["black_cells"]}
    loop = {tuple(e) for e in answer["loop_edges"]}
    arrows = {s.cell: {"up": "^", "down": "v", "left": "<", "right": ">"}[s.direction] for s in sites}
    lines = []
    for r in range(rows):
        line = ""
        for c in range(cols):
            line += arrows.get(Cell(r, c), "#" if (r, c) in black else ".")
            if c < cols - 1:
                line += "---" if (r, c, r, c + 1) in loop else "   "
        lines.append(line)
        if r < rows - 1:
            lines.append("   ".join("|" if (r, c, r + 1, c) in loop else " " for c in range(cols)))
    return "\n".join(lines)


def render(report: dict[str, Any], explain: int | None, kinds: Sequence[YajilinClueKind]) -> str:
    lines = ["Coupled rule experiment (full candidate hints; joint cell + edge answers)",
             "Mask bits: 1=coupling, 2=non_touching, 4=single_cycle",
             "Fixed: arrow obstacles, nonempty edges, degree 0 or 2. '-' means no hints.",
             "Each hint column: uniquely determined joint groups / all clue signatures.",
             "mask  answers  black  edge     -       A       B      AB       E      AE      BE     ABE"]
    for row in report["combinations"]:
        counts = " ".join(f"{str(h['unique_joint_groups']) + '/' + str(h['signature_count']):>7}" for h in row["hints"])
        lines.append(f"{row['mask']:>4} {row['answer_count']:>8} {row['black_pattern_count']:>6} {row['edge_pattern_count']:>5} {counts}")
    lines.append(f"Model/oracle comparison: {'verified' if report['models_verified'] else 'not requested'}")
    if explain is not None:
        row = report["combinations"][explain]
        sites = [ArrowSite(Cell(*s["cell"]), s["direction"]) for s in report["arrow_sites"]]
        wanted = [k for k in HINTS if k in kinds]
        hint = next(h for h in row["hints"] if h["kinds"] == wanted)
        lines.extend(["", f"Mask {explain}: {', '.join(row['rules']) or '(no optional rules)'}",
                      f"Minimal conflict on this layout: {row['minimal_conflict']}",
                      f"Hints: {', '.join(wanted) or '(none)'}; false black-only unique groups: {hint['false_unique_black_groups']}",
                      f"Unique groups lost by removing a rule: {hint['unique_groups_lost_if_removed']}"])
        witness = hint["projection_counterexample"]
        if witness:
            lines.append("Same clues and black cells, different edges (# black, . white, arrows blocked):")
            lines.append("Clues: " + json.dumps(witness["clues"], sort_keys=True))
            for i, answer in enumerate(witness["answers"], 1):
                lines.append(f"Answer {i}:\n" + diagram(report["rows"], report["cols"], sites, answer))
        for removal in row["removals"]:
            lines.append(f"Remove {removal['rule']}: {removal['added_answers']} extra answers; redundant={removal['redundant_on_this_layout']}")
            if not row["answer_count"] and removal["witness"]:
                lines.append("Feasible after this removal:\n" + diagram(
                    report["rows"], report["cols"], sites, removal["witness"]))
    lines.append("These finite-layout observations do not establish general rule redundancy or human difficulty.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=2)
    parser.add_argument("--cols", type=int, default=4)
    parser.add_argument("--arrow", nargs=3, action="append", metavar=("ROW", "COL", "DIRECTION"))
    parser.add_argument("--verify-models", action="store_true")
    parser.add_argument("--json", action="store_true", help="Write the complete deterministic report to stdout")
    parser.add_argument("--explain", type=int, choices=range(8))
    parser.add_argument("--hints", nargs="*", choices=HINTS, default=["black"], help="Hint policy to explain; the survey always includes all eight policies")
    args = parser.parse_args()
    try:
        if len(set(args.hints)) != len(args.hints):
            raise ValueError("Hint kinds must be distinct")
        sites = tuple(ArrowSite(Cell(int(r), int(c)), d) for r, c, d in (args.arrow or []))
        report = analyze(args.rows, args.cols, sites, verify_models=args.verify_models)
        print(json.dumps(report, indent=2, sort_keys=True) if args.json
              else render(report, args.explain, cast(list[YajilinClueKind], args.hints)))
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
