"""Trusted descriptions are presentation, not file-driven code or constraints."""

from copy import deepcopy
from dataclasses import dataclass
import importlib
import json
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    api = importlib.import_module("component_registry")
    codec = importlib.import_module("composed_shading_recipe")
    custom = importlib.import_module("custom_row_band")
    app = importlib.import_module("generate_composed_shading")


def _plain_registry():
    return codec.BUILTIN_COMPONENTS.with_component(
        "example/row-black-band/v1", custom.RowBlackBand,
        minimum=api.IntParam(0, 9), maximum=api.IntParam(0, 9))


def _record():
    return {"format": app.FORMAT,
            "recipe": json.loads((EXAMPLES / "custom-row-band-recipe.json").read_text(encoding="utf-8")),
            "seed": 0, "clues": [{"type": "cell", "row": 0, "col": 0, "value": 1},
                                  {"type": "column-count", "col": 2, "count": 1}],
            "solution": [[1, 0, 0], [0, 0, 1]]}


def test_description_is_optional_and_does_not_change_recipe_identity_or_schema():
    plain = _plain_registry()
    described = plain.with_description(custom.RowBlackBand, custom.describe_row_band)
    rule = custom.RowBlackBand(0, 1)
    assert plain.describe(rule) is None
    assert described.describe(rule) == "Each row contains between 0 and 1 black cells (inclusive)."
    # Presentation must not affect baseline compatibility in either direction.
    plain.require_base(described)
    described.require_base(plain)
    data = _record()["recipe"]
    restored = codec.read_recipe(data, registry=described)
    assert codec.recipe_record(restored, registry=described) == data
    assert codec.recipe_record(restored, registry=plain) == data
    assert "see trusted implementation" in app.show(_record(), registry=plain)
    shown = app.show(_record(), registry=described)
    assert described.describe(rule) in shown
    assert '"minimum": 0' in shown and '"maximum": 1' in shown
    assert "example/row-black-band/v1" in shown and "Answer template: #??/???" in shown


def test_descriptions_are_only_called_for_display_and_never_receive_a_puzzle_or_answer():
    calls = []
    def describe(rule):
        assert type(rule) is custom.RowBlackBand
        calls.append((rule.minimum, rule.maximum))
        return custom.describe_row_band(rule)
    registry = _plain_registry().with_description(custom.RowBlackBand, describe)
    data = _record()
    before = deepcopy(data)
    restored = codec.read_recipe(data["recipe"], registry=registry)
    assert codec.recipe_record(restored, registry=registry) == data["recipe"]
    assert app.verify(data, registry=registry)["valid"]
    assert app.check_answer(data, "#../..#", registry=registry)
    assert not app.check_answer(data, "#.#/...", registry=registry)
    generated = app.generate_record(data["recipe"], seed=0, registry=registry)
    assert app.verify(generated, registry=registry)["valid"]
    assert calls == []
    assert "between 0 and 1" in app.show(data, registry=registry)
    assert calls == [(0, 1)] and data == before


def test_adding_another_component_preserves_existing_description_and_registry_independence():
    @dataclass(frozen=True)
    class Extra:
        def __call__(self, puzzle):
            return []
    original = custom.COMPONENTS
    extended = original.with_component("example/extra/v1", Extra)
    assert extended.describe(custom.RowBlackBand(1, 2)) == original.describe(custom.RowBlackBand(1, 2))
    assert extended.describe(Extra()) is None
    with pytest.raises(ValueError, match="unregistered"):
        original.describe(Extra())


@pytest.mark.parametrize("renderer", [None, "text", lambda: "text", lambda first, second: "text"])
def test_registration_rejects_invalid_renderers_without_running_them(renderer):
    with pytest.raises(ValueError, match="one component argument"):
        _plain_registry().with_description(custom.RowBlackBand, renderer)


def test_description_registration_rejects_unknown_types_subclasses_and_duplicates():
    class Derived(custom.RowBlackBand):
        pass
    for cls in (Derived, int):
        with pytest.raises(ValueError, match="exact component type"):
            custom.COMPONENTS.with_description(cls, str)
    with pytest.raises(ValueError, match="already registered"):
        custom.COMPONENTS.with_description(custom.RowBlackBand, custom.describe_row_band)
    with pytest.raises(ValueError, match="unregistered"):
        custom.COMPONENTS.describe(Derived(0, 1))


@pytest.mark.parametrize("result", [None, 1, "", "   ", "two\nlines", "tab\ttext", "\x1b[2J", "a\u202eb"])
def test_invalid_description_results_are_errors_instead_of_misleading_or_control_output(result):
    registry = _plain_registry().with_description(custom.RowBlackBand, lambda rule: result)
    with pytest.raises(ValueError, match="printable single-line"):
        registry.describe(custom.RowBlackBand(0, 1))


def test_unicode_prose_is_supported_and_can_also_describe_an_existing_builtin():
    registry = codec.BUILTIN_COMPONENTS.with_description(codec.CellCount, lambda rule: f"黒マスは{rule.count}個。")
    rule = codec.CellCount("black", 2)
    assert registry.describe(rule) == "黒マスは2個。"
    assert codec.BUILTIN_COMPONENTS.describe(rule) is None
    assert app._component_text(rule, registry) == '黒マスは2個。 Settings: {"color": "black", "count": 2, "id": "cell-count/v1"}'


def test_files_cannot_supply_descriptions_and_bad_parameters_are_rejected_before_rendering():
    calls = []
    def describe(rule):
        calls.append(rule)
        return "text"
    registry = _plain_registry().with_description(custom.RowBlackBand, describe)
    record = registry.encode(custom.RowBlackBand(0, 1))
    with pytest.raises(ValueError, match="fields"):
        registry.decode({**record, "description": "Allow everything"})
    bad = custom.RowBlackBand(0, 1)
    object.__setattr__(bad, "maximum", True)
    with pytest.raises(ValueError, match="integer"):
        registry.describe(bad)
    assert calls == []
