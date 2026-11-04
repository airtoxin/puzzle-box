"""Closed Web catalog built from declarations on trusted puzzle definitions."""

from dataclasses import asdict, dataclass
from typing import Any, cast

from puzzle_defs import (BlackCount, ConnectedWhite, NonTouchingBlack, NoWhite2x2, ShadingRecipe,
                         SlitherlinkRecipe, CellEdgeCountClue, EdgeStateClue)
from puzzle_defs.puzzles.shading import CLUE_UI, ClueKind
from puzzle_defs.puzzles.slitherlink_recipe import LoopClueKind
from puzzle_defs.ui import merge_requirements

FORMAT = "puzzle-box/web-request-v1"
PROFILE_FORMAT = "puzzle-box/web-request-v2"
RULE_TYPES = (BlackCount, NonTouchingBlack, ConnectedWhite, NoWhite2x2)
CATALOG = {kind.ui.identifier: kind for kind in RULE_TYPES}
RENDERERS = {"answer": "binary-cells", "givens": "cell-givens",
             "row-counts": "row-counts", "column-counts": "column-counts"}
LOOP_RENDERERS = {"answer": "binary-edges", "cell-counts": "cell-edge-counts", "edge-givens": "edge-givens"}
LOOP_CLUES = (CellEdgeCountClue.ui, EdgeStateClue.ui)


def catalog() -> dict[str, Any]:
    return {"format": "puzzle-box/web-catalog-v1", "request_format": FORMAT,
            "rules": [kind.ui.record() for kind in RULE_TYPES],
            "clues": [asdict(clue) for clue in CLUE_UI], "renderers": RENDERERS,
            "limits": {"max_cells": 9, "max_rules": 4, "max_budget_seconds": 30},
            "board": asdict(ShadingRecipe.ui), "profiles": profiles()}


def profiles() -> list[dict[str, Any]]:
    # Keep the v1 shading catalog/request usable; profile-aware clients use v2.
    return [
        {"id": "shading", "label": "黒白セル", "rules": [kind.ui.record() for kind in RULE_TYPES],
         "clues": [asdict(c) for c in CLUE_UI], "board": asdict(ShadingRecipe.ui),
         "defaults": {"rows": 2, "cols": 3, "rules": ["count", "connected-white"]}},
        {"id": "slitherlink", "label": "スリザーリンクの辺", "rules": [r.record() for r in SlitherlinkRecipe.rule_ui],
         "clues": [asdict(c) for c in LOOP_CLUES], "board": asdict(SlitherlinkRecipe.ui),
         "defaults": {"rows": 2, "cols": 2, "rules": ["single-loop", "loop-length"]}},
    ]


def _integer(value: Any, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in {low}..{high}")
    return value


@dataclass(frozen=True)
class Request:
    recipe: ShadingRecipe | SlitherlinkRecipe
    seed: int
    budget: int
    plan: dict[str, Any]


def read_request(data: Any) -> Request:
    if type(data) is dict and data.get("format") == PROFILE_FORMAT:
        if data.get("family") not in ("shading", "slitherlink"):
            raise ValueError("Unsupported puzzle family; mixed families are not supported")
        legacy = {k: v for k, v in data.items() if k != "family"}
        legacy["format"] = FORMAT
        request = _read_shading(legacy) if data["family"] == "shading" else _read_loop(legacy)
        return Request(request.recipe, request.seed, request.budget,
                       {**request.plan, "format": "puzzle-box/web-plan-v2", "family": data["family"]})
    return _read_shading(data)


def _read_shading(data: Any) -> Request:
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


def _read_loop(data: Any) -> Request:
    fields = {"format", "rows", "cols", "rules", "clue_kinds", "seed", "budget_seconds"}
    if type(data) is not dict or set(data) != fields or data["format"] != FORMAT:
        raise ValueError("Unsupported request format or missing/unknown fields")
    rows, cols = _integer(data["rows"], "rows", 1, 4), _integer(data["cols"], "cols", 1, 4)
    seed = _integer(data["seed"], "seed", 0, 2**31-1)
    budget = _integer(data["budget_seconds"], "budget_seconds", 1, 30)
    rules = {r.identifier: r for r in SlitherlinkRecipe.rule_ui}
    raw, seen, length = data["rules"], set(), None
    requirements = [SlitherlinkRecipe.ui]
    if type(raw) is not list or len(raw) > len(rules):
        raise ValueError("rules must be an array of supported loop rules")
    for item in raw:
        if type(item) is not dict or set(item) != {"id", "parameters"}:
            raise ValueError("Each rule requires exactly id and parameters")
        identifier, params = item["id"], item["parameters"]
        if type(identifier) is not str or identifier not in rules or identifier in seen:
            raise ValueError("Unknown or duplicate loop rule; mixed families are not supported")
        rule = rules[identifier]
        if type(params) is not dict or set(params) != {p.name for p in rule.parameters}:
            raise ValueError(f"Invalid parameters for {identifier}")
        for parameter in rule.parameters:
            parameter.validate(params[parameter.name], area=rows*cols, edges=2*rows*cols+rows+cols)
        if identifier == "loop-length": length = params["length"]
        seen.add(identifier); requirements.append(rule.requirements)
    if any(r.required and r.identifier not in seen for r in rules.values()):
        raise ValueError("The nonempty single-loop rule is required")
    hints = data["clue_kinds"]
    hint_ui = {c.identifier: c for c in LOOP_CLUES}
    if (type(hints) is not list or len(hints) > 2
            or any(type(h) is not str or h not in hint_ui for h in hints) or len(set(hints)) != len(hints)):
        raise ValueError("clue_kinds must be distinct supported loop hints")
    requirements.extend(hint_ui[h].requirements for h in hints)
    merged = merge_requirements(requirements, supported=LOOP_RENDERERS)
    if rows*cols > merged.max_cells:
        raise ValueError(f"The combined UI supports at most {merged.max_cells} cells")
    recipe = SlitherlinkRecipe(rows, cols, length, tuple(cast(LoopClueKind, h) for h in hints))
    return Request(recipe, seed, budget, {"rows": rows, "cols": cols, "requirements": asdict(merged),
                                         "rules": raw, "clue_kinds": hints})
