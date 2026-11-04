"""One trusted, finite Web generation job; parent enforces its wall-time budget."""

import json
import sys
from typing import Any
from puzzle_defs import SlitherlinkRecipe, YajilinRecipe

from analyze_shading import finite_space, full_clues
from finite_shading import generate_finite
from generate_shading import clue_record, puzzle_record
from web_catalog import read_request


def generate_request(data: Any) -> dict[str, Any]:
    request = read_request(data)
    recipe = request.recipe
    if isinstance(recipe, YajilinRecipe):
        from web_coupled import generate_coupled
        return generate_coupled(request, data)
    if isinstance(recipe, SlitherlinkRecipe):
        from web_loop import generate_loop
        return generate_loop(request, data)
    _, boards, masks = finite_space(recipe)
    allowed = set(range(len(boards)))
    for mask in masks:
        allowed.intersection_update(mask)
    completions = [boards[i] for i in sorted(allowed)]
    evidence = {"enumerated_boards": len(boards), "completion_count": len(completions)}
    if not completions:
        return {"status": "unsatisfiable", "evidence": evidence}
    groups: dict[tuple, int] = {}
    for bits in completions:
        hints = full_clues(recipe, bits)
        groups[hints] = groups.get(hints, 0) + 1
    if not any(count == 1 for count in groups.values()):
        return {"status": "insufficient_hints", "evidence": evidence}
    clues = generate_finite(recipe, seed=request.seed)
    record = puzzle_record(recipe, clues, seed=request.seed, selection="finite")
    answer = tuple(v for row in record["solution"] for v in row)
    # Independently check the final reduced puzzle over the complete known-rule
    # answer space. In particular, solver None is never proof of no completion.
    def matches(bits, hints):
        candidates = set(full_clues(recipe, bits))
        return all(clue in candidates for clue in hints)
    if [bits for bits in completions if matches(bits, clues)] != [answer]:
        raise RuntimeError("Finite and DSL uniqueness disagree")
    if any(sum(matches(bits, clues[:i]+clues[i+1:]) for bits in completions) < 2 for i in range(len(clues))):
        raise RuntimeError("Finite and DSL irreducibility disagree")
    return {"status": "ok", "plan": request.plan, "record": record,
            "clues": [clue_record(clue) for clue in clues],
            "evidence": {**evidence, "unique": True, "irreducible": True}, "request": data}


if __name__ == "__main__":
    try:
        data = json.loads(sys.stdin.read(8193))
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
