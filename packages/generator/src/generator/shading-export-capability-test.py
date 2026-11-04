"""Saving a result must not drop semantics supplied by custom Python code."""

import importlib
from pathlib import Path

import pytest

from puzzle import Cell
from puzzle_defs import BlackCount, ShadingRecipe

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    display = importlib.import_module("generate_shading")
    importlib.import_module("finite_shading")  # puzzle_record imports selection metadata lazily.


class ExtraBlack(ShadingRecipe):
    def build_from_clues(self, clues):
        puzzle = super().build_from_clues(clues)
        puzzle.add(puzzle.black[Cell(0, 0)] == 1)
        return puzzle


def test_export_does_not_drop_a_subclass_rule_from_a_unique_answer():
    recipe = ExtraBlack(1, 1, ())
    puzzle = recipe.create_empty()
    solution = puzzle.solve()
    assert solution is not None and puzzle.result(solution) == [[1]]
    # Before the guard this returned a shading-v1 file with rules=[], clues=[],
    # solution=[[1]], which verify() correctly rejected as ambiguous.
    with pytest.raises(ValueError, match="exact ShadingRecipe"):
        display.puzzle_record(recipe, [], seed=0)


def test_export_rejects_a_custom_rule_before_executing_it():
    class CustomRule:
        def apply(self, puzzle, board, black):
            pytest.fail("Unsupported rules must not run while exporting")
    with pytest.raises(ValueError, match="exact built-in"):
        display.puzzle_record(ShadingRecipe(1, 1, (CustomRule(),)), [], seed=0)


@pytest.mark.parametrize("kinds", [("cell",), ("row-count", "column-count")])
def test_supported_exports_still_round_trip_with_selection_metadata(kinds):
    recipe = ShadingRecipe(1, 1, (BlackCount(0),), kinds)
    record = display.puzzle_record(recipe, [], seed=0, selection="finite")
    assert record["environment"]["completion_selection"] == "finite-identifiable-v1"
    assert display.verify(record) == {"valid": True, "unique": True, "irreducible": True, "clue_count": 0}


@pytest.mark.parametrize("cols", [25, 26])
def test_export_enforces_its_readers_board_limit_before_building(cols, monkeypatch):
    recipe = ShadingRecipe(1, cols, (BlackCount(0),))
    if cols == 25:
        record = display.puzzle_record(recipe, [], seed=0)
        assert display.verify(record)["valid"]
    else:
        monkeypatch.setattr(ShadingRecipe, "build_from_clues",
                            lambda *a, **k: pytest.fail("Reject oversized exports before building"))
        with pytest.raises(ValueError, match="at most 25 cells"):
            display.puzzle_record(recipe, [], seed=0)
