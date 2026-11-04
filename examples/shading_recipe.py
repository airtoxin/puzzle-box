"""Strict data-only interchange for the small built-in shading recipes."""

from pathlib import Path
from typing import Any

from puzzle_defs import BlackCount, ConnectedWhite, NonTouchingBlack, NoWhite2x2, ShadingRecipe
from puzzle_defs.puzzles.shading import CLUE_KINDS, ShadingRule
from json_records import MAX_BYTES as MAX_RECIPE_BYTES, load_json as _load_json

RECIPE_FORMAT = "puzzle-box/shading-recipe-v1"
MAX_RECIPE_RULES = 8
RULES = ("count", "non-touching", "connected-white", "no-white-2x2")


def rule_record(rule: ShadingRule) -> dict[str, Any]:
    # A subclass may change apply(); serializing only its parent would lose rules.
    if type(rule) is BlackCount:
        return {"type": "count", "count": rule.count}
    if type(rule) is NonTouchingBlack:
        return {"type": "non-touching", "diagonal": rule.diagonal}
    if type(rule) is ConnectedWhite:
        return {"type": "connected-white", "nonempty": rule.nonempty}
    if type(rule) is NoWhite2x2:
        return {"type": "no-white-2x2"}
    raise ValueError("This file format supports exact built-in shading rules only, not subclasses")


def read_rule(data: Any) -> ShadingRule:
    if not isinstance(data, dict):
        raise ValueError("A rule must be an object")
    kind = data.get("type")
    if kind == "count" and set(data) == {"type", "count"}:
        return BlackCount(data["count"])
    if kind == "non-touching" and set(data) == {"type", "diagonal"}:
        return NonTouchingBlack(data["diagonal"])
    if kind == "connected-white" and set(data) == {"type", "nonempty"}:
        return ConnectedWhite(data["nonempty"])
    if kind == "no-white-2x2" and set(data) == {"type"}:
        return NoWhite2x2()
    raise ValueError("Unknown rule or invalid rule parameters")


def check_demo_size(recipe: ShadingRecipe) -> None:
    if recipe.rows * recipe.cols > 25:
        raise ValueError("This small-board demo supports at most 25 cells")


def read_recipe(data: Any) -> ShadingRecipe:
    fields = {"format", "rows", "cols", "rules", "clue_kinds"}
    if not isinstance(data, dict) or set(data) != fields:
        raise ValueError("Recipe must contain exactly format, rows, cols, rules and clue_kinds")
    if data["format"] != RECIPE_FORMAT:
        raise ValueError("Unsupported recipe format; puzzle artifacts and exploration reports are not recipes")
    if not isinstance(data["rules"], list) or len(data["rules"]) > MAX_RECIPE_RULES:
        raise ValueError("Recipe rules must be an array of at most 8 rule occurrences")
    kinds = data["clue_kinds"]
    if not isinstance(kinds, list) or any(type(k) is not str or k not in CLUE_KINDS for k in kinds):
        raise ValueError("Recipe clue_kinds must be an array of cell, row-count or column-count values")
    recipe = ShadingRecipe(data["rows"], data["cols"], tuple(read_rule(r) for r in data["rules"]), tuple(kinds))
    check_demo_size(recipe)
    if any(type(r) is BlackCount and r.count > recipe.rows * recipe.cols for r in recipe.rules):
        raise ValueError("Black count cannot exceed the board area")
    return recipe


def recipe_record(recipe: ShadingRecipe) -> dict[str, Any]:
    record = {"format": RECIPE_FORMAT, "rows": recipe.rows, "cols": recipe.cols,
              "rules": [rule_record(r) for r in recipe.rules], "clue_kinds": list(recipe.clue_kinds)}
    read_recipe(record)  # Enforce the same bounds for export and import.
    return record


def load_json(path: Path, *, label: str = "Recipe") -> Any:
    """Read bounded JSON without silently accepting duplicate fields or NaN."""
    return _load_json(path, label=label)


def load_recipe(path: Path) -> ShadingRecipe:
    return read_recipe(load_json(path))


def check_distinct_paths(first: Path, second: Path) -> None:
    if first.resolve() == second.resolve() or (first.exists() and second.exists() and first.samefile(second)):
        raise ValueError("Input and output must use different files")
