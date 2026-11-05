"""Compare bounded shading reduction with and without the known-answer path.

Run separately for each mode/seed, without other CPU-intensive jobs, e.g.:
    python examples/benchmark_bounded_shading.py baseline 0 --budget 30
    python examples/benchmark_bounded_shading.py known-answer 0 --budget 30

This is a local diagnostic, not a benchmark of the hosted worker or a latency
guarantee. The hash allows results to be compared without printing the answer.
"""

import argparse
import hashlib
import json
import time

from generator.search import generate_bounded
from puzzle_defs import BlackCount, ConnectedWhite, NonTouchingBlack, ShadingRecipe
from web_worker import _shading_answer_variables


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("baseline", "known-answer"))
    parser.add_argument("seed", type=int)
    parser.add_argument("--budget", type=float, default=30)
    args = parser.parse_args()
    recipe = ShadingRecipe(10, 10, (BlackCount(25), NonTouchingBlack(), ConnectedWhite()),
                           ("cell", "row-count", "column-count"))
    start = time.perf_counter()
    result = generate_bounded(recipe, seed=args.seed, budget=args.budget,
                              answer_variables=_shading_answer_variables if args.mode == "known-answer" else None)
    elapsed = time.perf_counter() - start
    answer = ([result.solution.value(result.puzzle.black[cell]) for cell in result.puzzle.board.cells]
              if result.solution is not None and result.puzzle is not None else None)
    digest = hashlib.sha256(repr((result.clues, answer)).encode()).hexdigest() if answer is not None else None
    print(json.dumps({"mode": args.mode, "seed": args.seed, "budget_seconds": args.budget,
                      "elapsed_seconds": round(elapsed, 3), "status": result.status,
                      "unique": result.unique, "irreducible": result.irreducible,
                      "clue_count": len(result.clues), "result_hash": digest}))


if __name__ == "__main__":
    main()
