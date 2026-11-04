"""Validate complete Web answers against submitted rules and hints, not a claimed solution."""

from typing import Any

from puzzle_defs import SlitherlinkRecipe
from generate_shading import read_clue as shading_clue
from generate_slitherlink import read_clue as loop_clue
from web_catalog import read_request

FORMAT = "puzzle-box/web-answer-v1"


def read_check(data: Any):
    if type(data) is not dict or set(data) != {"format", "request", "clues", "answer"} or data["format"] != FORMAT:
        raise ValueError("Unsupported answer format or missing/unknown fields")
    request = read_request(data["request"])
    recipe = request.recipe
    count = 2*recipe.rows*recipe.cols+recipe.rows+recipe.cols if isinstance(recipe, SlitherlinkRecipe) else recipe.rows*recipe.cols
    if (type(data["answer"]) is not list or len(data["answer"]) != count
            or any(type(v) is not int or v not in (0, 1) for v in data["answer"])):
        raise ValueError("answer must contain one 0 or 1 for every cell or edge")
    if type(data["clues"]) is not list or len(data["clues"]) > recipe.rows*recipe.cols+count+recipe.rows+recipe.cols:
        raise ValueError("clues must be a bounded array")
    # Check hint kinds before constructing the typed recipe's constraints.
    kinds = set(recipe.clue_kinds)
    for clue in data["clues"]:
        if type(clue) is not dict or type(clue.get("type")) is not str or clue["type"] not in kinds:
            raise ValueError("Clue kind is not enabled by this recipe")
    if isinstance(recipe, SlitherlinkRecipe):
        clues = [loop_clue(c) for c in data["clues"]]
        recipe.build_from_clues(clues)
    else:
        clues = [shading_clue(c) for c in data["clues"]]
        recipe.build_from_clues(clues)
    if len(set(clues)) != len(clues): raise ValueError("Duplicate clues are not supported")
    return request


def check_answer(data: Any) -> dict[str, Any]:
    request = read_check(data)
    recipe = request.recipe
    if isinstance(recipe, SlitherlinkRecipe):
        from web_loop import completions, full_clues
        edges, answers = completions(recipe)
        answer = frozenset(e for e, bit in zip(edges, data["answer"]) if bit)
        clues = [loop_clue(c) for c in data["clues"]]
        correct = answer in answers and set(clues) <= set(full_clues(recipe, answer))
        if not correct: return {"status": "ok", "correct": False}
        puzzle = recipe.build_from_clues(clues)
        for edge, bit in zip(edges, data["answer"]): puzzle.add(puzzle.edge_on[edge] == bit)
    else:
        from analyze_shading import finite_space, full_clues as shading_full_clues
        _, boards, masks = finite_space(recipe)
        answer = tuple(data["answer"])
        clues = [shading_clue(c) for c in data["clues"]]
        index = boards.index(answer)
        correct = all(index in mask for mask in masks) and set(clues) <= set(shading_full_clues(recipe, answer))
        if not correct: return {"status": "ok", "correct": False}
        puzzle = recipe.build_from_clues(clues)
        for cell, bit in zip(puzzle.board.cells, answer): puzzle.add(puzzle.black[cell] == bit)
    # A failed/inconclusive solver confirmation is not a verdict against the user.
    return {"status": "ok", "correct": True} if puzzle.solve(seed=request.seed) is not None else {"status": "unconfirmed"}
