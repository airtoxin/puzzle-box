"""File readers and writers must agree on shared fixed-grid constraints."""

import importlib
from pathlib import Path

import pytest

from puzzle_defs import (AdjacentBlackCounts, OneFalseAdjacentCountPerRoom,
                         RoomBlackCount, RoomConnectedBlack, ShadingRecipe,
                         WhiteAreaClues, WhiteIslandAreas)

with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(Path(__file__).resolve().parents[4] / "examples"))
    codec = importlib.import_module("shading_recipe")
    saved = importlib.import_module("generate_shading")


@pytest.mark.parametrize("rules,match", [
    ((RoomBlackCount(((0, 0), (1, 1)), 1), RoomConnectedBlack(((0, 1), (0, 1)))),
     "Room rules must share the same partition"),
    ((WhiteIslandAreas(((1, 0), (0, 0))), WhiteAreaClues(((0, 1), (0, 0)))),
     "Island rules must share the same areas"),
    ((AdjacentBlackCounts(((0, None), (None, None))),
      OneFalseAdjacentCountPerRoom(((0, 0), (1, 1)), ((None, 0), (None, None)))),
     "Adjacent-count rules must share the same neighbor counts"),
], ids=["rooms", "areas", "neighbor-counts"])
@pytest.mark.parametrize("clue_kinds", [("cell",), ("row-count",)], ids=["v1", "v2"])
def test_conflicting_grids_are_rejected_at_each_file_boundary_before_solving(monkeypatch, rules, match, clue_kinds):
    recipe = ShadingRecipe(2, 2, rules, clue_kinds)
    serialized = {"format": codec.RECIPE_FORMAT, "rows": 2, "cols": 2,
                  "rules": [codec.rule_record(rule) for rule in rules], "clue_kinds": list(clue_kinds)}
    record = saved.encode_record(recipe, [], [[0, 0], [0, 0]], seed=0)
    monkeypatch.setattr(ShadingRecipe, "build_from_clues", lambda *a, **k: pytest.fail("must validate before solving"))

    with pytest.raises(ValueError, match=match):
        codec.read_recipe(serialized)
    with pytest.raises(ValueError, match=match):
        saved.puzzle_record(recipe, [], seed=0)
    with pytest.raises(ValueError, match=match):
        saved.verify(record)
