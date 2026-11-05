"""Solution-free web links reconstruct the same uniquely solvable puzzle."""
import importlib
from pathlib import Path
import pytest
from puzzle_defs import YajilinRecipe

with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(Path(__file__).resolve().parents[4] / "examples"))
    worker = importlib.import_module("web_worker")
    shared = importlib.import_module("web_restore")
    checks = importlib.import_module("web_answers")
    server = importlib.import_module("web_server")
    result_validation = importlib.import_module("web_result")

BASE = {"format": "puzzle-box/web-request-v2", "seed": 0, "budget_seconds": 10}
REQUESTS = [
    {**BASE, "family": "shading", "rows": 2, "cols": 3,
     "rules": [{"id": "count", "parameters": {"count": 2}}, {"id": "connected-white", "parameters": {"nonempty": True}}],
     "clue_kinds": ["cell", "row-count", "column-count"]},
    {**BASE, "family": "slitherlink", "rows": 2, "cols": 2, "seed": 2,
     "rules": [{"id": "single-loop", "parameters": {}}, {"id": "loop-length", "parameters": {"length": 8}}],
     "clue_kinds": ["cell-count", "edge"]},
    {**BASE, "family": "coupled", "rows": 3, "cols": 3,
     "rules": [{"id": r.identifier, "parameters": {}} for r in YajilinRecipe.rule_ui], "clue_kinds": ["black", "edge"]},
]

@pytest.mark.parametrize("puzzle_request", REQUESTS, ids=lambda r: r["family"])
def test_restore_same_puzzle_and_answer(puzzle_request):
    request = puzzle_request
    generated = worker.generate_request(request)
    assert generated["status"] == "ok"
    payload = {"format": shared.FORMAT, "request": request, "clues": generated["clues"]}
    restored = server.run_job(payload, restore=True)
    assert restored["status"] == "ok"
    assert result_validation.same_json(restored["plan"], generated["plan"]) and restored["clues"] == generated["clues"]
    assert restored["record"]["solution"] == generated["record"]["solution"]
    solution = restored["record"]["solution"]
    if request["family"] == "shading":
        answer = [v for row in solution for v in row]; fmt = checks.FORMAT
    elif request["family"] == "slitherlink":
        answer = [int(edge in solution) for edge in restored["edges"]]; fmt = checks.FORMAT
    else:
        answer = {"cells": [int(cell in solution["black_cells"]) for cell in restored["cells"]],
                  "edges": [int(edge in solution["loop_edges"]) for edge in restored["edges"]]}; fmt = checks.JOINT_FORMAT
    answer_data = {"format": fmt, "request": request, "clues": payload["clues"], "answer": answer}
    assert checks.check_answer(answer_data) == {"status": "ok", "correct": True}
    if isinstance(answer, dict):
        answer["cells"][0] ^= 1
    else:
        answer[0] ^= 1
    assert checks.check_answer(answer_data) == {"status": "ok", "correct": False}


def test_invalid_and_nonunique_puzzles_are_rejected():
    request = REQUESTS[0]
    for payload in [{"format": "unknown", "request": request, "clues": []},
                    {"format": shared.FORMAT, "request": request, "clues": [{"type": "cell", "row": 99, "col": 0, "value": 0}]}]:
        with pytest.raises(ValueError): shared.read_restore(payload)
    result = shared.restore({"format": shared.FORMAT, "request": request, "clues": []})
    assert result["status"] == "invalid_puzzle"
