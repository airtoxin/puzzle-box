"""Validate complete Web answers against submitted rules and hints, not a claimed solution."""

from typing import Any

from puzzle_defs import (SlitherlinkRecipe, YajilinRecipe, YajilinAnswer,
                         CellEdgeCountClue, EdgeStateClue, RowCountClue, ColumnCountClue,
                         BlackCellClue, ArrowCountClue)
from generate_shading import read_clue as shading_clue
from generate_slitherlink import read_clue as loop_clue
from generate_yajilin import read_clue as coupled_clue
from web_catalog import read_request

FORMAT = "puzzle-box/web-answer-v1"
JOINT_FORMAT = "puzzle-box/web-answer-v2"


def read_check(data: Any):
    if (type(data) is not dict or set(data) != {"format", "request", "clues", "answer"}
            or data["format"] not in (FORMAT, JOINT_FORMAT)):
        raise ValueError("Unsupported answer format or missing/unknown fields")
    request = read_request(data["request"])
    recipe = request.recipe
    def binary(values, size):
        return type(values) is list and len(values) == size and all(type(v) is int and v in (0, 1) for v in values)
    if isinstance(recipe, YajilinRecipe):
        cells, edges = recipe.rows*recipe.cols, 2*recipe.rows*recipe.cols-recipe.rows-recipe.cols
        answer = data["answer"]; count = cells+edges
        if (data["format"] != JOINT_FORMAT or type(answer) is not dict or set(answer) != {"cells", "edges"}
                or not binary(answer["cells"], cells) or not binary(answer["edges"], edges)):
            raise ValueError("A coupled v2 answer needs complete binary cells and edges arrays")
    else:
        count = 2*recipe.rows*recipe.cols+recipe.rows+recipe.cols if isinstance(recipe, SlitherlinkRecipe) else recipe.rows*recipe.cols
        if data["format"] != FORMAT or not binary(data["answer"], count):
            raise ValueError("A v1 answer must contain one 0 or 1 for every cell or edge")
    if type(data["clues"]) is not list or len(data["clues"]) > recipe.rows*recipe.cols+count+recipe.rows+recipe.cols:
        raise ValueError("clues must be a bounded array")
    # Check hint kinds before constructing the typed recipe's constraints.
    kinds = set(recipe.clue_kinds)
    for clue in data["clues"]:
        if type(clue) is not dict or type(clue.get("type")) is not str or clue["type"] not in kinds:
            raise ValueError("Clue kind is not enabled by this recipe")
    if isinstance(recipe, YajilinRecipe):
        clues = [coupled_clue(c) for c in data["clues"]]
        for clue in clues:
            if isinstance(clue, (BlackCellClue, ArrowCountClue)):
                if clue.cell.row >= recipe.rows or clue.cell.col >= recipe.cols:
                    raise ValueError("Cell clue is outside the board")
                if isinstance(clue, ArrowCountClue):
                    site = next((site for site in recipe.arrow_sites if site.cell == clue.cell), None)
                    if site is None or clue.count > len(recipe.ray(site)):
                        raise ValueError("Arrow count must fit a configured arrow site's ray")
                if isinstance(clue, BlackCellClue) and clue.cell in {site.cell for site in recipe.arrow_sites}:
                    raise ValueError("Black clue cannot refer to an arrow site")
            elif isinstance(clue, EdgeStateClue):
                if any(v.row >= recipe.rows or v.col >= recipe.cols for v in clue.edge):
                    raise ValueError("Edge clue is outside the board")
    elif isinstance(recipe, SlitherlinkRecipe):
        clues = [loop_clue(c) for c in data["clues"]]
        for clue in clues:
            if isinstance(clue, CellEdgeCountClue):
                if clue.cell.row >= recipe.rows or clue.cell.col >= recipe.cols:
                    raise ValueError("Cell clue is outside the board")
            elif any(v.row > recipe.rows or v.col > recipe.cols for v in clue.edge):
                raise ValueError("Edge clue is outside the board")
    else:
        clues = [shading_clue(c) for c in data["clues"]]
        for clue in clues:
            if isinstance(clue, RowCountClue):
                if clue.row >= recipe.rows or clue.count > recipe.cols:
                    raise ValueError("Row clue index or count exceeds the board dimensions")
            elif isinstance(clue, ColumnCountClue):
                if clue.col >= recipe.cols or clue.count > recipe.rows:
                    raise ValueError("Column clue index or count exceeds the board dimensions")
            else:
                cell, value = clue
                if not (0 <= cell.row < recipe.rows and 0 <= cell.col < recipe.cols):
                    raise ValueError("Clue cell is outside the board")
                if type(value) is not int or value not in (0, 1):
                    raise ValueError("Clue values must be 0 (white) or 1 (black)")
    if len(set(clues)) != len(clues): raise ValueError("Duplicate clues are not supported")
    return request


def check_answer(data: Any) -> dict[str, Any]:
    request = read_check(data)
    recipe = request.recipe
    if isinstance(recipe, YajilinRecipe):
        from web_coupled import completions, full_clues
        cells, edges, answers = completions(recipe)
        answer = YajilinAnswer(frozenset(c for c, bit in zip(cells, data["answer"]["cells"]) if bit),
                              frozenset(e for e, bit in zip(edges, data["answer"]["edges"]) if bit))
        clues = [coupled_clue(c) for c in data["clues"]]
        if answer not in answers or not set(clues) <= set(full_clues(recipe, answer, cells, edges)):
            return {"status": "ok", "correct": False}
        puzzle = recipe.build_from_clues(clues)
        for cell, bit in zip(cells, data["answer"]["cells"]): puzzle.add(puzzle.is_black[cell] == bit)
        for edge, bit in zip(edges, data["answer"]["edges"]): puzzle.add(puzzle.edge_on[edge] == bit)
    elif isinstance(recipe, SlitherlinkRecipe):
        from web_loop import completions, full_clues
        edges, answers = completions(recipe)
        answer = frozenset(e for e, bit in zip(edges, data["answer"]) if bit)
        clues = [loop_clue(c) for c in data["clues"]]
        correct = answer in answers and set(clues) <= set(full_clues(recipe, answer))
        if not correct: return {"status": "ok", "correct": False}
        puzzle = recipe.build_from_clues(clues)
        for edge, bit in zip(edges, data["answer"]): puzzle.add(puzzle.edge_on[edge] == bit)
    else:
        answer = tuple(data["answer"])
        clues = [shading_clue(c) for c in data["clues"]]
        puzzle = recipe.build_from_clues(clues)
        for cell, bit in zip(puzzle.board.cells, answer): puzzle.add(puzzle.black[cell] == bit)
    result = puzzle.solve_result(seed=request.seed, time_limit=request.budget)
    if result.status == "unknown":
        return {"status": "unconfirmed"}
    return {"status": "ok", "correct": result.status == "sat"}
