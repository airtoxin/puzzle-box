"""Finite, independent edge-subset oracle for the trusted <=4-cell Web recipe."""

from itertools import product
import platform
import random
from typing import Any

import ortools
from generator import reduce_clues
from puzzle import Cell, Edge, Vertex, unique
from puzzle_defs import CellEdgeCountClue, EdgeStateClue, SlitherlinkRecipe
from puzzle_defs.puzzles.slitherlink_recipe import LoopClue
from generate_slitherlink import FORMAT, clue_record, edge_record
from web_catalog import Request


def edges_for(rows: int, cols: int) -> list[Edge]:
    # Explicit horizontal rows followed by vertical rows; no solver/grid helper.
    return ([Edge(Vertex(r, c), Vertex(r, c+1)) for r in range(rows+1) for c in range(cols)]
            + [Edge(Vertex(r, c), Vertex(r+1, c)) for r in range(rows) for c in range(cols+1)])


def completions(recipe: SlitherlinkRecipe) -> tuple[list[Edge], list[frozenset[Edge]]]:
    if recipe.rows * recipe.cols > 4:
        raise ValueError("Finite loop validation supports at most 4 cells")
    edges = edges_for(recipe.rows, recipe.cols)
    answers = []
    for bits in product((0, 1), repeat=len(edges)):
        if not any(bits) or (recipe.loop_length is not None and sum(bits) != recipe.loop_length):
            continue
        selected = frozenset(e for e, bit in zip(edges, bits) if bit)
        neighbors: dict[Vertex, list[Vertex]] = {}
        for a, b in selected:
            neighbors.setdefault(a, []).append(b); neighbors.setdefault(b, []).append(a)
        if any(len(ns) != 2 for ns in neighbors.values()): continue
        seen, todo = set(), [next(iter(neighbors))]
        while todo:
            v = todo.pop()
            if v not in seen:
                seen.add(v); todo.extend(neighbors[v])
        if seen == set(neighbors): answers.append(selected)
    return edges, answers


def full_clues(recipe: SlitherlinkRecipe, answer: frozenset[Edge]) -> list[LoopClue]:
    clues: list[LoopClue] = []
    for kind in recipe.clue_kinds:
        if kind == "edge":
            clues.extend(EdgeStateClue(e, int(e in answer)) for e in edges_for(recipe.rows, recipe.cols))
        else:
            for r in range(recipe.rows):
                for c in range(recipe.cols):
                    corners = {Vertex(r, c), Vertex(r+1, c), Vertex(r, c+1), Vertex(r+1, c+1)}
                    clues.append(CellEdgeCountClue(Cell(r, c), sum(a in corners and b in corners for a, b in answer)))
    return clues


def generate_loop(request: Request, data: Any) -> dict[str, Any]:
    recipe = request.recipe
    assert isinstance(recipe, SlitherlinkRecipe)
    edges, answers = completions(recipe)
    evidence = {"enumerated_boards": 2**len(edges), "completion_count": len(answers)}
    if not answers: return {"status": "unsatisfiable", "evidence": evidence}
    groups: dict[tuple[LoopClue, ...], list[frozenset[Edge]]] = {}
    for answer in answers: groups.setdefault(tuple(full_clues(recipe, answer)), []).append(answer)
    eligible = [group[0] for group in groups.values() if len(group) == 1]
    if not eligible: return {"status": "insufficient_hints", "evidence": evidence}
    answer = random.Random(request.seed).choice(eligible)
    clues = full_clues(recipe, answer)
    puzzle = recipe.build_from_clues(clues); puzzle.add(unique())
    solution = puzzle.solve(seed=request.seed)
    if solution is None or puzzle.result(solution) != answer:
        raise RuntimeError("Finite loop and DSL uniqueness disagree")
    if set(recipe.extract_clues(solution, puzzle)) != set(clues):
        raise RuntimeError("Finite loop and DSL clue extraction disagree")
    clues = reduce_clues(recipe, clues, seed=request.seed)
    matching = lambda hints: [a for a in answers if set(hints) <= set(full_clues(recipe, a))]
    if matching(clues) != [answer] or any(len(matching(clues[:i]+clues[i+1:])) < 2 for i in range(len(clues))):
        raise RuntimeError("Reduced loop and finite uniqueness/irreducibility disagree")
    record = {"format": FORMAT, "rows": recipe.rows, "cols": recipe.cols, "loop_length": recipe.loop_length,
              "clue_kinds": list(recipe.clue_kinds), "clues": [clue_record(c) for c in clues],
              "seed": request.seed, "solution": [edge_record(e) for e in edges if e in answer],
              "environment": {"python": platform.python_version(), "ortools": ortools.__version__,
                              "seeded_search_workers": 1}}
    return {"status": "ok", "plan": request.plan, "record": record, "clues": record["clues"],
            "edges": [edge_record(e) for e in edges],
            "evidence": {**evidence, "unique": True, "irreducible": True}, "request": data}
