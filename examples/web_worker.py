"""One trusted Web generation job; parent enforces its wall-time budget."""

import json
import sys
from typing import Any
from puzzle import Cell, Var
from puzzle_defs import ShadingPuzzle, SlitherlinkRecipe, YajilinRecipe

from generator.search import generate_bounded
from generate_shading import clue_record, encode_record
from web_catalog import read_request
from web_limits import MAX_BODY


def _shading_answer_variables(puzzle: ShadingPuzzle) -> dict[Cell, Var]:
    # Coordinates are stable across models; auxiliary rule witnesses are not
    # part of the shading answer. The generator verifies the full projection.
    return {cell: puzzle.black[cell] for cell in puzzle.board.cells}


def generate_request(data: Any) -> dict[str, Any]:
    request = read_request(data)
    recipe = request.recipe
    if isinstance(recipe, YajilinRecipe):
        from web_coupled import generate_coupled
        return generate_coupled(request, data)
    if isinstance(recipe, SlitherlinkRecipe):
        from web_loop import generate_loop
        return generate_loop(request, data)
    result = generate_bounded(recipe, seed=request.seed, budget=request.budget,
                              answer_variables=_shading_answer_variables)
    evidence = {"method": "cp-sat", "candidates": result.candidates,
                "unique": result.unique, "irreducible": result.irreducible}
    if result.status != "ok":
        return {"status": result.status, "evidence": evidence}
    clues = list(result.clues)
    assert result.puzzle is not None and result.solution is not None
    record = encode_record(recipe, clues, result.puzzle.result(result.solution), seed=request.seed)
    return {"status": "ok", "plan": request.plan, "record": record,
            "clues": [clue_record(clue) for clue in clues],
            "evidence": evidence, "request": data}


if __name__ == "__main__":
    try:
        # The parent re-encodes JSON with ASCII escapes, which can expand a
        # single UTF-8 byte into at most six characters. Keep stdin bounded.
        data = json.loads(sys.stdin.read(6 * MAX_BODY + 1))
        if sys.argv[1:] == ["--check"]:
            from web_answers import check_answer
            result = check_answer(data)
        else:
            result = generate_request(data)
    except Exception:
        # Preserve uncertainty without exposing internal tracebacks/paths or
        # interpreting an implementation/solver error as a mathematical result.
        result = {"status": "unconfirmed"}
    print(json.dumps(result, allow_nan=False))
