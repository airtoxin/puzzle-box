"""No-arrow Yajilin Web slice: two answer channels, one coupled solution."""

import platform
import random
from typing import Any

import ortools
from generator import reduce_clues
from puzzle import Cell, unique
from puzzle_defs import BlackCellClue, EdgeStateClue, SlitherlinkRecipe, YajilinAnswer, YajilinRecipe
from puzzle_defs.puzzles.yajilin_recipe import YajilinClue
from generate_yajilin import FORMAT, clue_record
from generate_slitherlink import edge_record
from web_catalog import Request
from web_loop import completions as corner_cycles


def completions(recipe: YajilinRecipe):
    if recipe.rows*recipe.cols > 9 or recipe.arrow_sites:
        raise ValueError("The coupled Web profile supports at most 9 cells and no arrow sites")
    # Cell centers form the vertices of a smaller corner grid. Reuse the finite
    # edge-subset oracle, not the DSL. Coverage determines the remaining black
    # cells; then independently enforce non-touching black cells.
    edges, cycles = corner_cycles(SlitherlinkRecipe(recipe.rows-1, recipe.cols-1))
    cells = [Cell(r, c) for r in range(recipe.rows) for c in range(recipe.cols)]
    answers = []
    for cycle in cycles:
        black = frozenset(set(cells) - {Cell(*v) for e in cycle for v in e})
        if any(abs(a.row-b.row)+abs(a.col-b.col) == 1 for a in black for b in black): continue
        answers.append(YajilinAnswer(black, cycle))
    return cells, edges, answers


def full_clues(recipe, answer, cells, edges) -> list[YajilinClue]:
    clues: list[YajilinClue] = []
    for kind in recipe.clue_kinds:
        if kind == "black": clues.extend(BlackCellClue(c, int(c in answer.black_cells)) for c in cells)
        elif kind == "edge": clues.extend(EdgeStateClue(e, int(e in answer.loop_edges)) for e in edges)
        else: raise ValueError("Unsupported coupled Web hint")
    return clues


def generate_coupled(request: Request, data: Any) -> dict[str, Any]:
    recipe = request.recipe
    assert isinstance(recipe, YajilinRecipe)
    cells, edges, answers = completions(recipe)
    evidence = {"enumerated_boards": 2**len(edges), "completion_count": len(answers)}
    if not answers: return {"status": "unsatisfiable", "evidence": evidence}
    groups: dict[tuple[YajilinClue, ...], list[YajilinAnswer]] = {}
    for answer in answers: groups.setdefault(tuple(full_clues(recipe, answer, cells, edges)), []).append(answer)
    eligible = [group[0] for group in groups.values() if len(group) == 1]
    if not eligible: return {"status": "insufficient_hints", "evidence": evidence}
    answer = random.Random(request.seed).choice(eligible)
    clues = full_clues(recipe, answer, cells, edges)
    puzzle = recipe.build_from_clues(clues); puzzle.add(unique())
    solution = puzzle.solve(seed=request.seed)
    if solution is None or recipe.answer(solution, puzzle) != answer:
        raise RuntimeError("Finite and DSL joint answers disagree")
    if set(recipe.extract_clues(solution, puzzle)) != set(clues):
        raise RuntimeError("Finite and DSL coupled hints disagree")
    clues = reduce_clues(recipe, clues, seed=request.seed)
    matches = lambda hints: [a for a in answers if set(hints) <= set(full_clues(recipe, a, cells, edges))]
    if matches(clues) != [answer] or any(len(matches(clues[:i]+clues[i+1:])) < 2 for i in range(len(clues))):
        raise RuntimeError("Finite and reduced joint uniqueness/irreducibility disagree")
    record = {"format": FORMAT, "rows": recipe.rows, "cols": recipe.cols, "arrow_sites": [],
              "clue_kinds": list(recipe.clue_kinds), "clues": [clue_record(c) for c in clues], "seed": request.seed,
              "solution": {"black_cells": [list(c) for c in cells if c in answer.black_cells],
                           "loop_edges": [edge_record(e) for e in edges if e in answer.loop_edges]},
              "environment": {"python": platform.python_version(), "ortools": ortools.__version__, "seeded_search_workers": 1}}
    return {"status": "ok", "plan": request.plan, "record": record, "clues": record["clues"],
            "cells": [list(c) for c in cells], "edges": [edge_record(e) for e in edges], "request": data,
            "evidence": {**evidence, "unique": True, "irreducible": True}}
