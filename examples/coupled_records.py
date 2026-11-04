"""Bounded data-only input for saved Yajilin and experimental coupled puzzles."""

import json
from pathlib import Path
from typing import Any

from puzzle_defs import YajilinAnswer, YajilinRecipe
from puzzle_defs.puzzles.yajilin_recipe import YajilinClue
from coupled_oracle import HINTS, rule_names
from generate_yajilin import FORMAT as YAJILIN_FORMAT, read_record

FORMAT = "puzzle-box/coupled-puzzle-v1"
MAX_BYTES = 65536
MAX_CLUES = 32


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> Any:
    raise ValueError(f"Non-finite JSON number: {value}")


def load_puzzle(path: Path) -> Any:
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Puzzle file must be at most 65536 bytes")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_object, parse_constant=_constant)
    except RecursionError as exc:
        raise ValueError("Puzzle JSON is nested too deeply") from exc


def check_output(source: Path, output: Path) -> None:
    if source.resolve() == output.resolve() or (output.exists() and source.samefile(output)):
        raise ValueError("Input and output must use different files")


def _array(value: Any, name: str, limit: int) -> None:
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError(f"{name} must be an array of at most {limit} entries")


def read_puzzle(data: Any) -> tuple[YajilinRecipe, int, list[YajilinClue], YajilinAnswer]:
    if not isinstance(data, dict) or data.get("format") not in (FORMAT, YAJILIN_FORMAT):
        raise ValueError("Use a saved coupled-puzzle-v1 or yajilin-v1 puzzle, not an exploration report")
    fields = {"format", "rows", "cols", "arrow_sites", "clue_kinds", "clues", "solution"}
    required = fields | ({"rule_mask"} if data["format"] == FORMAT else set())
    if not required <= set(data) or set(data) - required - {"seed", "environment", "generation"}:
        raise ValueError("Missing or unknown puzzle fields")
    if (any(type(data[k]) is not int or data[k] < 2 for k in ("rows", "cols"))
            or data["rows"] * data["cols"] > 8):
        raise ValueError("Stored coupled diagnostics support at most 8 cells, both dimensions >= 2")
    mask = data.get("rule_mask", 7)
    rule_names(mask)
    _array(data["arrow_sites"], "arrow_sites", 8)
    _array(data["clue_kinds"], "clue_kinds", 3)
    if any(type(k) is not str or k not in HINTS for k in data["clue_kinds"]):
        raise ValueError("clue_kinds must contain arrow, black or edge")
    _array(data["clues"], "clues", MAX_CLUES)
    answer = data["solution"]
    if not isinstance(answer, dict) or set(answer) != {"black_cells", "loop_edges"}:
        raise ValueError("Solution must contain black_cells and loop_edges")
    _array(answer["black_cells"], "black_cells", 8)
    _array(answer["loop_edges"], "loop_edges", 10)
    if "seed" in data and (type(data["seed"]) is not int or not 0 <= data["seed"] <= 2**31 - 1):
        raise ValueError("Seed must be an integer from 0 to 2147483647")
    if "environment" in data and not isinstance(data["environment"], dict):
        raise ValueError("Environment metadata must be an object")
    if "generation" in data:
        history = data["generation"]
        if not isinstance(history, dict) or set(history) != {"initial_seed", "attempt_limit", "attempts_used"}:
            raise ValueError("Invalid generation metadata fields")
        start, limit, used = (history[k] for k in ("initial_seed", "attempt_limit", "attempts_used"))
        if (any(type(n) is not int for n in (start, limit, used)) or not 1 <= used <= limit <= 32
                or not 0 <= start <= 2**31 - limit or data.get("seed") != start + used - 1):
            raise ValueError("Generation metadata must agree with the successful seed")
    # Reuse the existing topology/clue/answer readers, independently of #14's
    # optional history parser. Rule feasibility is checked by the finite model.
    core = {k: data[k] for k in fields}
    core["format"] = YAJILIN_FORMAT
    recipe, clues, expected = read_record(core)
    recipe.build_from_clues(clues)  # Reuse coordinate/ray validation, without solving its fixed rules.
    return recipe, mask, clues, expected
