"""Closed Web catalog built from declarations on trusted puzzle definitions."""

from dataclasses import asdict, dataclass
from typing import Any, cast

from puzzle_defs import BlackCount, ConnectedWhite, NonTouchingBlack, NoWhite2x2, ShadingRecipe
from puzzle_defs.puzzles.shading import CLUE_UI, ClueKind
from puzzle_defs.ui import merge_requirements

FORMAT = "puzzle-box/web-request-v1"
RULE_TYPES = (BlackCount, NonTouchingBlack, ConnectedWhite, NoWhite2x2)
CATALOG = {kind.ui.identifier: kind for kind in RULE_TYPES}
RENDERERS = {"answer": "binary-cells", "givens": "cell-givens",
             "row-counts": "row-counts", "column-counts": "column-counts"}


def catalog() -> dict[str, Any]:
    return {"format": "puzzle-box/web-catalog-v1", "request_format": FORMAT,
            "rules": [kind.ui.record() for kind in RULE_TYPES],
            "clues": [asdict(clue) for clue in CLUE_UI], "renderers": RENDERERS,
            "limits": {"max_cells": 9, "max_rules": 4, "max_budget_seconds": 30},
            "board": asdict(ShadingRecipe.ui)}


def _integer(value: Any, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in {low}..{high}")
    return value


@dataclass(frozen=True)
class Request:
    recipe: ShadingRecipe
    seed: int
    budget: int
    plan: dict[str, Any]


def read_request(data: Any) -> Request:
    fields = {"format", "rows", "cols", "rules", "clue_kinds", "seed", "budget_seconds"}
    if type(data) is not dict or set(data) != fields or data["format"] != FORMAT:
        raise ValueError("Unsupported request format or missing/unknown fields")
    rows = _integer(data["rows"], "rows", 1, 9)
    cols = _integer(data["cols"], "cols", 1, 9)
    seed = _integer(data["seed"], "seed", 0, 2**31-1)
    budget = _integer(data["budget_seconds"], "budget_seconds", 1, 30)
    raw = data["rules"]
    if type(raw) is not list or len(raw) > len(CATALOG):
        raise ValueError("rules must be an array of at most 4 distinct supported rules")
    rules, seen = [], set()
    requirements = [ShadingRecipe.ui]
    for item in raw:
        if type(item) is not dict or set(item) != {"id", "parameters"}:
            raise ValueError("Each rule requires exactly id and parameters")
        identifier, params = item["id"], item["parameters"]
        if type(identifier) is not str or identifier not in CATALOG or identifier in seen:
            raise ValueError("Unknown or duplicate rule ID; custom Python and imports are not supported")
        kind = CATALOG[identifier]
        if type(params) is not dict or set(params) != {p.name for p in kind.ui.parameters}:
            raise ValueError(f"Invalid parameters for {identifier}")
        for parameter in kind.ui.parameters:
            parameter.validate(params[parameter.name], area=rows*cols)
        rules.append(kind(**params))
        requirements.append(kind.ui.requirements)
        seen.add(identifier)
    hints = data["clue_kinds"]
    supported_hints = {item.identifier: item for item in CLUE_UI}
    if (type(hints) is not list or len(hints) > 3 or any(type(h) is not str or h not in supported_hints for h in hints)
            or len(set(hints)) != len(hints)):
        raise ValueError("clue_kinds must be an array of distinct supported hints")
    requirements.extend(supported_hints[h].requirements for h in hints)
    merged = merge_requirements(requirements, supported=RENDERERS)
    if rows * cols > merged.max_cells:
        raise ValueError(f"The combined UI supports at most {merged.max_cells} cells")
    recipe = ShadingRecipe(rows, cols, tuple(rules), tuple(cast(ClueKind, h) for h in hints))
    plan = {"format": "puzzle-box/web-plan-v1", "rows": rows, "cols": cols,
            "requirements": asdict(merged), "rules": raw, "clue_kinds": hints}
    return Request(recipe, seed, budget, plan)
