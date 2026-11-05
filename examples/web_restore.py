"""Restore a bounded, solution-free web puzzle and prove visible-answer uniqueness."""
from typing import Any
import platform
import ortools
from puzzle_defs import ShadingPuzzle, SlitherlinkPuzzle, SlitherlinkRecipe, YajilinPuzzle, YajilinRecipe
from web_catalog import read_request
from web_answers import read_clues
from generate_shading import encode_record
from generate_slitherlink import edge_record
from web_loop import edges_for

FORMAT = "puzzle-box/web-puzzle-v1"

def read_restore(data: Any):
    if type(data) is not dict or set(data) != {"format", "request", "clues"} or data["format"] != FORMAT:
        raise ValueError("Unsupported puzzle format")
    request = read_request(data["request"])
    recipe = request.recipe
    rows, cols = recipe.rows, recipe.cols
    count = (rows*cols + 2*rows*cols-rows-cols if isinstance(recipe, YajilinRecipe)
             else 2*rows*cols+rows+cols if isinstance(recipe, SlitherlinkRecipe) else rows*cols)
    read_clues(recipe, data["clues"], count)
    return request

def restore(data: Any) -> dict[str, Any]:
    request = read_restore(data)
    recipe = request.recipe
    rows, cols = recipe.rows, recipe.cols
    count = (rows*cols + 2*rows*cols-rows-cols if isinstance(recipe, YajilinRecipe)
             else 2*rows*cols+rows+cols if isinstance(recipe, SlitherlinkRecipe) else rows*cols)
    clues = read_clues(recipe, data["clues"], count)
    puzzle = recipe.build_from_clues(clues)
    result = puzzle.solve_result(seed=request.seed, time_limit=request.budget, check_unique=True)
    if result.status == "unknown" or result.uniqueness == "unknown": return {"status": "unconfirmed"}
    if result.status != "sat" or result.uniqueness != "unique" or result.solution is None:
        return {"status": "invalid_puzzle"}
    environment = {"python": platform.python_version(), "ortools": ortools.__version__, "seeded_search_workers": 1}
    response = {"status": "ok", "request": data["request"], "plan": request.plan, "clues": data["clues"]}
    if isinstance(recipe, YajilinRecipe):
        assert isinstance(puzzle, YajilinPuzzle)
        answer = recipe.answer(result.solution, puzzle)
        cells = list(puzzle.board.cells); edges = edges_for(rows-1, cols-1)
        response["cells"] = [list(c) for c in cells]; response["edges"] = [edge_record(e) for e in edges]
        response["record"] = {"format": "puzzle-box/yajilin-v1", "rows": rows, "cols": cols,
            "arrow_sites": [], "clue_kinds": list(recipe.clue_kinds), "clues": data["clues"], "seed": request.seed,
            "solution": {"black_cells": [list(c) for c in cells if c in answer.black_cells],
                         "loop_edges": [edge_record(e) for e in edges if e in answer.loop_edges]}, "environment": environment}
    elif isinstance(recipe, SlitherlinkRecipe):
        assert isinstance(puzzle, SlitherlinkPuzzle)
        answer = puzzle.result(result.solution); edges = edges_for(rows, cols)
        response["edges"] = [edge_record(e) for e in edges]
        response["record"] = {"format": "puzzle-box/slitherlink-v1", "rows": rows, "cols": cols,
            "loop_length": recipe.loop_length, "clue_kinds": list(recipe.clue_kinds), "clues": data["clues"],
            "seed": request.seed, "solution": [edge_record(e) for e in edges if e in answer], "environment": environment}
    else:
        assert isinstance(puzzle, ShadingPuzzle)
        response["record"] = encode_record(recipe, clues, puzzle.result(result.solution), seed=request.seed)
    return response
