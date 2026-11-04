"""Unsupported extensions must not receive built-in-only guarantees."""

from copy import deepcopy
import importlib
from itertools import product
from pathlib import Path

import pytest

from generator import with_constraints
from puzzle import Cell, Puzzle
from puzzle_defs import BlackCount, ShadingRecipe

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    custom = importlib.import_module("custom_row_band")
    codec = importlib.import_module("shading_recipe")
    composed = importlib.import_module("composed_shading_recipe")
    saved = importlib.import_module("generate_composed_shading")
    display = importlib.import_module("generate_shading")
    oracle = importlib.import_module("analyze_shading")
    finite = importlib.import_module("finite_shading")
    diagnosis = importlib.import_module("diagnose_shading_rules")

BAND = custom.COMPONENTS.decode({"id": "example/row-black-band/v1", "minimum": 1, "maximum": 1})


class RegisteredRecipe(ShadingRecipe):
    """A natural Python adapter; its extra semantics cannot fit the old format."""
    def build_from_clues(self, clues):
        puzzle = super().build_from_clues(clues)
        for constraint in BAND(puzzle):
            puzzle.add(constraint)
        return puzzle


def test_subclass_counterexample_is_not_diagnosed_or_exported_as_its_base():
    recipe = RegisteredRecipe(2, 2, (BlackCount(2),))
    # Independent check: two black total and exactly one in each row.
    expected = {bits for bits in product((0, 1), repeat=4)
                if sum(bits) == 2 and sum(bits[:2]) == sum(bits[2:]) == 1}
    actual = {bits for bits in product((0, 1), repeat=4)
              if recipe.build_from_clues([(Cell(i//2, i%2), v) for i, v in enumerate(bits)]).solve() is not None}
    assert actual == expected and len(actual) == 4
    assert oracle.analyze(ShadingRecipe(2, 2, recipe.rules))["completion_count"] == 6
    # Previously analyze and export silently reported/preserved those six boards.
    with pytest.raises(ValueError, match="exact ShadingRecipe"):
        oracle.analyze(recipe)
    with pytest.raises(ValueError, match="exact ShadingRecipe"):
        codec.recipe_record(recipe)


@pytest.mark.parametrize("kind", ["composed", "subclass"])
@pytest.mark.parametrize("operation", ["analyze", "eligible", "generate", "export"])
def test_unsupported_recipe_is_rejected_before_running_its_code(kind, operation, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Unsupported recipes must be rejected before building or solving")
    base = ShadingRecipe(2, 2, (BlackCount(2),))
    recipe = with_constraints(base, BAND) if kind == "composed" else RegisteredRecipe(2, 2, base.rules)
    monkeypatch.setattr(ShadingRecipe, "build_from_clues", forbidden)
    monkeypatch.setattr(Puzzle, "solve", forbidden)
    actions = {"analyze": oracle.analyze, "eligible": finite.identifiable_completions,
               "generate": finite.generate_finite, "export": codec.recipe_record}
    with pytest.raises(ValueError, match="exact ShadingRecipe"):
        actions[operation](recipe)


def _legacy_record(version):
    data = {"format": display.FORMAT if version == 1 else display.MIXED_FORMAT,
            "rows": 1, "cols": 1, "rules": [{"type": "count", "count": 0}],
            "clues": [], "solution": [[0]]}
    if version == 2:
        data["clue_kinds"] = ["cell"]
    return data


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("field", ["components", "recipe", "extensions"])
def test_legacy_verification_and_display_reject_unknown_semantics(version, field, monkeypatch):
    data = _legacy_record(version)
    data[field] = [{"id": "example/row-black-band/v1", "minimum": 1, "maximum": 1}]
    # The base has the unique white answer, but the extension would require black.
    assert with_constraints(ShadingRecipe(1, 1, (BlackCount(0),)), BAND).create_empty().solve() is None
    monkeypatch.setattr(Puzzle, "solve", lambda *a, **k: pytest.fail("Reject unknown fields before solving"))
    for operation in (display.verify, display.show):
        with pytest.raises(ValueError, match="Missing or unknown puzzle fields"):
            operation(data)


@pytest.mark.parametrize("version", [1, 2])
def test_unknown_top_level_metadata_is_not_implicitly_migrated(version, monkeypatch):
    data = _legacy_record(version)
    data["extra_metadata"] = {"ratio": 1.25, "label": "日本語"}
    before = deepcopy(data)
    monkeypatch.setattr(Puzzle, "solve", lambda *a, **k: pytest.fail("Reject unknown fields before solving"))
    for operation in (display.verify, display.show, lambda record: display.check_answer(record, ".")):
        with pytest.raises(ValueError, match="Missing or unknown puzzle fields"):
            operation(data)
    assert data == before


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("metadata", [None, {"ratio": 1.25, "label": "日本語"}],
                         ids=["no-metadata", "environment-metadata"])
def test_legacy_optional_metadata_remains_accepted(version, metadata):
    data = _legacy_record(version)
    if metadata is not None:
        data.update(seed=0, environment={"completion_selection": "finite-identifiable-v1", **metadata})
    before = deepcopy(data)
    assert display.verify(data) == {"valid": True, "unique": True, "irreducible": True, "clue_count": 0}
    assert "Shading puzzle" in display.show(data)
    assert display.check_answer(data, ".")
    assert data == before


def test_supported_custom_generation_stays_separate_from_builtin_diagnostics(monkeypatch):
    recipe = with_constraints(ShadingRecipe(2, 2, (BlackCount(2),)), BAND)
    record = saved.generate_record(composed.recipe_record(recipe, registry=custom.COMPONENTS),
                                   seed=0, registry=custom.COMPONENTS)
    assert saved.verify(record, registry=custom.COMPONENTS)["valid"] is True
    monkeypatch.setattr(Puzzle, "solve", lambda *a, **k: pytest.fail("Unsupported formats must not solve"))
    for operation in (display.verify, display.show, diagnosis.diagnose):
        with pytest.raises(ValueError, match="format|shading-v1"):
            operation(record)
