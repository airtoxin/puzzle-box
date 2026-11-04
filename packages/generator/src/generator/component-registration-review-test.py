"""Registration and saved-output contracts must hold before use."""

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
import sys

import pytest

from generator import with_constraints
from puzzle_defs import BlackCount, ShadingRecipe

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    api = importlib.import_module("component_registry")
    codec = importlib.import_module("composed_shading_recipe")
    demo = importlib.import_module("generate_composed_shading")
    files = importlib.import_module("shading_recipe")


@pytest.mark.parametrize("kind", ["positional-only", "varargs"])
def test_registration_rejects_constructors_that_cannot_receive_parameter_keywords(kind):
    def positional(self, value, /):
        object.__setattr__(self, "value", value)
    def variadic(self, *value):
        object.__setattr__(self, "value", value[0])
    initialize = positional if kind == "positional-only" else variadic
    cls = dataclass(frozen=True, init=False)(type("CustomInit", (), {
        "__annotations__": {"value": int}, "__init__": initialize, "__call__": lambda self, puzzle: [],
    }))
    with pytest.raises(ValueError, match="keyword"):
        codec.BUILTIN_COMPONENTS.with_component("review/custom-init/v1", cls, value=api.IntParam(0, 1))


def test_keyword_only_dataclass_constructor_remains_supported():
    @dataclass(frozen=True, kw_only=True)
    class KeywordOnly:
        value: int
        def __call__(self, puzzle):
            return []
    registry = codec.BUILTIN_COMPONENTS.with_component("review/keyword-only/v1", KeywordOnly, value=api.IntParam(0, 1))
    record = {"id": "review/keyword-only/v1", "value": 1}
    assert registry.encode(registry.decode(record)) == record


def test_constructor_that_accepts_the_declared_keyword_through_varkw_is_supported():
    @dataclass(frozen=True, init=False)
    class KeywordCapture:
        value: int
        def __init__(self, **value):
            object.__setattr__(self, "value", value["value"])
        def __call__(self, puzzle):
            return []
    registry = codec.BUILTIN_COMPONENTS.with_component("review/keyword-capture/v1", KeywordCapture,
                                                       value=api.IntParam(0, 1))
    record = {"id": "review/keyword-capture/v1", "value": 1}
    assert registry.encode(registry.decode(record)) == record


@dataclass(frozen=True)
class Label:
    text: str
    def __call__(self, puzzle):
        return []


def _label_recipe(value):
    registry = codec.BUILTIN_COMPONENTS.with_component("review/label/v1", Label, text=api.ChoiceParam((value,)))
    recipe = with_constraints(ShadingRecipe(1, 1, (BlackCount(0),)), Label(value))
    return codec.recipe_record(recipe, registry=registry), registry


@pytest.mark.parametrize("size", ["unicode-overflow", "exact-boundary", "one-byte-over"])
def test_produced_file_respects_reader_byte_limit_before_creating_output(tmp_path, monkeypatch, size):
    if size == "unicode-overflow":
        label = "界" * 11000
    else:
        empty, registry = _label_recipe("")
        record = demo.generate_record(empty, registry=registry)
        overhead = len((json.dumps(record, sort_keys=True, indent=2) + "\n").encode("utf-8"))
        label = "x" * (files.MAX_RECIPE_BYTES-overhead + (size == "one-byte-over"))
    data, registry = _label_recipe(label)
    source, output = tmp_path / "input.json", tmp_path / "output.json"
    source.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert source.stat().st_size <= files.MAX_RECIPE_BYTES
    assert codec.load_recipe(source, registry=registry) is not None
    monkeypatch.setattr(sys, "argv", ["test", "generate", "--recipe", str(source), "--output", str(output)])
    if size == "exact-boundary":
        assert demo.main(registry=registry) == 0
        assert output.stat().st_size == files.MAX_RECIPE_BYTES
        assert demo.verify(files.load_json(output), registry=registry)["valid"]
    else:
        with pytest.raises(SystemExit) as error:
            demo.main(registry=registry)
        assert error.value.code == 2 and not output.exists()


@dataclass(frozen=True)
class ControlNames:
    identifier: str
    builder_type: int
    self: bool

    def __call__(self, puzzle):
        return []


def test_component_fields_can_share_registration_control_argument_names():
    registry = codec.BUILTIN_COMPONENTS.with_component(
        "review/control-names/v1", ControlNames,
        identifier=api.ChoiceParam(("label",)), builder_type=api.IntParam(0, 2), self=api.BoolParam(),
    )
    record = {"id": "review/control-names/v1", "identifier": "label", "builder_type": 2, "self": True}
    assert registry.encode(registry.decode(record)) == record


def test_equivalent_builtin_schemas_in_different_keyword_order_round_trip_and_generate():
    registry = (api.ComponentRegistry()
        .with_component("connected-cells/v1", codec.ConnectedCells,
                        nonempty=api.BoolParam(), color=api.ChoiceParam(("black", "white")))
        .with_component("cell-count/v1", codec.CellCount,
                        count=api.IntParam(0, codec.MAX_CELLS), color=api.ChoiceParam(("black", "white"))))
    data = json.loads((EXAMPLES / "composed-shading-recipe-sample.json").read_text(encoding="utf-8"))
    restored = codec.read_recipe(data, registry=registry)
    assert codec.recipe_record(restored, registry=registry) == data
    puzzle = demo.generate_record(data, seed=0, registry=registry)
    assert demo.verify(puzzle, registry=registry)["valid"]
