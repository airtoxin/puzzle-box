"""Generate, display, check and verify a small Slitherlink recipe."""

import argparse
import json
from pathlib import Path
import platform
import sys
from typing import Any

import ortools

from generator import generate
from puzzle import Cell, Edge, Vertex, unique
from puzzle_defs import CellEdgeCountClue, EdgeStateClue, SlitherlinkRecipe
from puzzle_defs.puzzles.slitherlink_recipe import LOOP_CLUE_KINDS, LoopClue
from edge_answers import edge_template, parse_edge_answer
from json_records import encode_json, load_json, read_array

FORMAT = "puzzle-box/slitherlink-v1"


def edge_record(edge: Edge) -> list[int]:
    return [edge.v1.row, edge.v1.col, edge.v2.row, edge.v2.col]


def read_edge(data: Any) -> Edge:
    if not isinstance(data, list) or len(data) != 4:
        raise ValueError("An edge needs [row1, col1, row2, col2]")
    return EdgeStateClue(Edge(Vertex(data[0], data[1]), Vertex(data[2], data[3])), 1).edge


def clue_record(clue: LoopClue) -> dict[str, Any]:
    if isinstance(clue, CellEdgeCountClue):
        return {"type": "cell-count", "row": clue.cell.row, "col": clue.cell.col, "count": clue.count}
    return {"type": "edge", "edge": edge_record(clue.edge), "used": clue.used}


def read_clue(data: Any) -> LoopClue:
    if not isinstance(data, dict):
        raise ValueError("A loop clue must be an object")
    if data.get("type") == "cell-count" and set(data) == {"type", "row", "col", "count"}:
        return CellEdgeCountClue(Cell(data["row"], data["col"]), data["count"])
    if data.get("type") == "edge" and set(data) == {"type", "edge", "used"}:
        return EdgeStateClue(read_edge(data["edge"]), data["used"])
    raise ValueError("Unknown loop clue type or invalid clue fields")


def check_demo_size(recipe: SlitherlinkRecipe) -> None:
    if recipe.rows * recipe.cols > 9:
        raise ValueError("This small loop demo supports at most 9 cells")


def read_record(data: dict[str, Any]) -> tuple[SlitherlinkRecipe, list[LoopClue], set[Edge]]:
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError(f"Unsupported loop puzzle format; expected an object with format {FORMAT}")
    recipe = SlitherlinkRecipe(data["rows"], data["cols"], data["loop_length"],
                              tuple(read_array(data["clue_kinds"], "clue_kinds")))
    check_demo_size(recipe)
    clues = [read_clue(c) for c in read_array(data["clues"], "clues")]
    if any(("cell-count" if isinstance(c, CellEdgeCountClue) else "edge") not in recipe.clue_kinds
           for c in clues):
        raise ValueError("Stored clue type is not enabled by clue_kinds")
    edges = [read_edge(e) for e in read_array(data["solution"], "solution")]
    if len(set(edges)) != len(edges):
        raise ValueError("Solution must not contain duplicate edges")
    if any(v.row > recipe.rows or v.col > recipe.cols for e in edges for v in e):
        raise ValueError("Solution edge is outside the board")
    return recipe, clues, set(edges)


def verify(data: dict[str, Any]) -> dict[str, Any]:
    recipe, clues, expected = read_record(data)
    p = recipe.build_from_clues(clues)
    p.add(unique())
    solution = p.solve()
    if solution is None:
        raise ValueError("Stored clues are not uniquely solvable")
    if p.result(solution) != expected:
        raise ValueError("Stored solution does not match the unique loop")
    for i in range(len(clues)):
        trial = recipe.build_from_clues(clues[:i] + clues[i + 1:])
        trial.add(unique())
        if trial.solve() is not None:
            raise ValueError("Stored clues are not irreducible")
    return {"valid": True, "unique": True, "irreducible": True, "clue_count": len(clues)}


def _parse_answer(text: str, rows: int, cols: int) -> set[Edge]:
    # Slitherlink vertices are cell corners, so each dimension has one extra point.
    return parse_edge_answer(text, rows + 1, cols + 1)


def check_answer(data: dict[str, Any], text: str) -> bool:
    recipe, _, answer = read_record(data)
    candidate = _parse_answer(text, recipe.rows, recipe.cols)
    # A stored answer is only authoritative after proving the saved puzzle's
    # uniqueness, clue irreducibility and agreement with that answer.
    verify(data)
    return candidate == answer


def show(data: dict[str, Any], *, reveal: bool = False) -> str:
    verify(data)
    recipe, clues, answer = read_record(data)
    cell_counts = {c.cell: c.count for c in clues if isinstance(c, CellEdgeCountClue)}
    edge_states = {c.edge: c.used for c in clues if isinstance(c, EdgeStateClue)}

    def mark(edge: Edge, horizontal: bool) -> str:
        state = int(edge in answer) if reveal else edge_states.get(edge)
        if state == 1:
            return "---" if horizontal else "|"
        symbol = " " if reveal else ("x" if state == 0 else "?")
        return f" {symbol} " if horizontal else symbol

    title = "Solution" if reveal else "Loop puzzle"
    lines = [f"{title}: {recipe.rows} rows x {recipe.cols} columns",
             "Draw one nonempty loop along grid edges, without branches or crossings."]
    if recipe.loop_length is not None:
        lines.append(f"Use exactly {recipe.loop_length} edges.")
    lines.append("")
    for r in range(recipe.rows + 1):
        lines.append("+" + "+".join(mark(Edge(Vertex(r, c), Vertex(r, c + 1)), True)
                                      for c in range(recipe.cols)) + "+")
        if r < recipe.rows:
            row = mark(Edge(Vertex(r, 0), Vertex(r + 1, 0)), False)
            for c in range(recipe.cols):
                row += f"{cell_counts.get(Cell(r, c), '.'):^3}"
                row += mark(Edge(Vertex(r, c + 1), Vertex(r + 1, c + 1)), False)
            lines.append(row)
    lines.extend(["", "Numbers count used sides of a cell; . = no number clue.",
                  "--- / | = used edge; x = unused edge clue; ? = unknown edge; + = vertex."])
    if not reveal:
        template = edge_template(recipe.rows + 1, recipe.cols + 1, edge_states)
        lines.extend(["Answer template: " + template,
                      "Edge rows run top to bottom, alternating horizontal and vertical; omit cell numbers.",
                      'Replace every ? with 1 (used) or 0 (unused), then use check FILE --answer "ROWS".'])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("generate")
    make.add_argument("--rows", type=int, default=2)
    make.add_argument("--cols", type=int, default=2)
    make.add_argument("--loop-length", type=int)
    make.add_argument("--hints", nargs="+", choices=LOOP_CLUE_KINDS, default=list(LOOP_CLUE_KINDS))
    make.add_argument("--seed", type=int, default=17)
    make.add_argument("--output", type=Path)
    make.add_argument("--quiet", action="store_true")
    audit = commands.add_parser("verify")
    audit.add_argument("file", type=Path)
    display = commands.add_parser("show")
    display.add_argument("file", type=Path)
    display.add_argument("--solution", action="store_true")
    check = commands.add_parser("check", help="Check a complete loop answer without revealing the solution")
    check.add_argument("file", type=Path)
    check.add_argument("--answer", required=True,
                       help="Alternating horizontal/vertical edge rows separated by '/', using 1 or 0")
    args = parser.parse_args()
    try:
        if args.command in ("verify", "show", "check"):
            data = load_json(args.file)
            if args.command == "check":
                correct = check_answer(data, args.answer)
                print("Correct. All rules and clues are satisfied." if correct else
                      "Not correct. Check the rules and given clues.")
                return 0 if correct else 1
            print(json.dumps(verify(data), sort_keys=True) if args.command == "verify"
                  else show(data, reveal=args.solution))
            return 0
        if args.quiet and args.output is None:
            raise ValueError("Use --output with --quiet")
        if not 0 <= args.seed <= 2**31 - 1:
            raise ValueError("Seed must be between 0 and 2147483647")
        recipe = SlitherlinkRecipe(args.rows, args.cols, args.loop_length, tuple(args.hints))
        check_demo_size(recipe)
        try:
            clues = generate(recipe, seed=args.seed)
        except ValueError as exc:
            raise ValueError(f"{exc}. For ambiguous cell counts, include edge in --hints") from exc
        p = recipe.build_from_clues(clues)
        p.add(unique())
        solution = p.solve()
        if solution is None:
            raise ValueError("Generated clues did not determine a unique loop")
        answer = p.result(solution)
        data = {"format": FORMAT, "rows": recipe.rows, "cols": recipe.cols,
                "loop_length": recipe.loop_length, "clue_kinds": list(recipe.clue_kinds),
                "clues": [clue_record(c) for c in clues], "seed": args.seed,
                "solution": [edge_record(e) for e in p.board.edges if e in answer],
                "environment": {"python": platform.python_version(), "ortools": ortools.__version__,
                                "seeded_search_workers": 1}}
        encoded = encode_json(data)
        if args.output is not None:
            args.output.write_bytes(encoded)
        if not args.quiet:
            sys.stdout.buffer.write(encoded)
        return 0
    except (ValueError, TypeError, KeyError, OSError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
