"""Trusted registration stays distinct from untrusted component records."""

from copy import deepcopy
from dataclasses import dataclass, FrozenInstanceError, InitVar
import importlib
from itertools import product
import json
from pathlib import Path
import subprocess
import sys

import pytest

from generator import with_constraints
from puzzle import at_least_one
from puzzle_defs import ShadingRecipe

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    api = importlib.import_module("component_registry")
    codec = importlib.import_module("composed_shading_recipe")
    custom = importlib.import_module("custom_row_band")
    demo = importlib.import_module("generate_composed_shading")


def _record():
    return json.loads((EXAMPLES / "custom-row-band-recipe.json").read_text(encoding="utf-8"))


def _white_connected(bits):
    whites = {i for i, bit in enumerate(bits) if bit == 0}
    if not whites:
        return False
    seen, todo = set(), [min(whites)]
    while todo:
        i = todo.pop()
        if i not in seen:
            seen.add(i)
            todo.extend(j for j in whites-seen if abs(i//3-j//3)+abs(i%3-j%3) == 1)
    return seen == whites


def _answers(recipe):
    puzzle = recipe.create_empty()
    result = set()
    while (solution := puzzle.solve()) is not None:
        values = tuple(solution.value(puzzle.black[c]) for c in puzzle.board.cells)
        assert values not in result
        result.add(values)
        puzzle.add(at_least_one(puzzle.black[c] != v for c, v in zip(puzzle.board.cells, values)))
    return result


def test_custom_component_round_trip_matches_independent_64_board_oracle():
    data = _record()
    recipe = codec.read_recipe(data, registry=custom.COMPONENTS)
    assert codec.recipe_record(recipe, registry=custom.COMPONENTS) == data
    expected = {b for b in product((0, 1), repeat=6) if sum(b) == 2 and _white_connected(b)
                and sum(b[:3]) <= 1 and sum(b[3:]) <= 1}
    base = {b for b in product((0, 1), repeat=6) if sum(b) == 2 and _white_connected(b)}
    assert len(expected) == 4 and expected < base
    assert _answers(recipe) == expected
    restored = codec.read_recipe(json.loads(json.dumps(codec.recipe_record(recipe, registry=custom.COMPONENTS))),
                                 registry=custom.COMPONENTS)
    assert _answers(restored) == expected


@pytest.mark.parametrize("seed", [0, 1])
def test_saved_custom_problem_is_independently_unique_and_irreducible(seed):
    data = demo.generate_record(_record(), seed=seed, registry=custom.COMPONENTS)
    assert demo.verify(data, registry=custom.COMPONENTS)["valid"]
    with pytest.raises(ValueError, match="Unknown component"):
        demo.verify(data)  # No automatic module selection from the component ID.
    expected = {b for b in product((0, 1), repeat=6) if sum(b) == 2 and _white_connected(b)
                and sum(b[:3]) <= 1 and sum(b[3:]) <= 1}

    def matches(clues):
        def satisfied(bits, clue):
            if clue["type"] == "cell":
                return bits[3*clue["row"]+clue["col"]] == clue["value"]
            if clue["type"] == "row-count":
                return sum(bits[3*clue["row"]:3*clue["row"]+3]) == clue["count"]
            return sum(bits[clue["col"]::3]) == clue["count"]
        return [bits for bits in expected if all(satisfied(bits, c) for c in clues)]
    clues = data["clues"]
    assert matches(clues) == [tuple(v for row in data["solution"] for v in row)]
    assert all(len(matches(clues[:i]+clues[i+1:])) > 1 for i in range(len(clues)))
    wrong = deepcopy(data)
    wrong["recipe"]["components"][1]["maximum"] = 0
    with pytest.raises(ValueError, match="not uniquely"):
        demo.verify(wrong, registry=custom.COMPONENTS)


def test_extensions_are_explicit_immutable_and_do_not_change_builtins():
    builtin_file = json.loads((EXAMPLES / "composed-shading-recipe-sample.json").read_text(encoding="utf-8"))
    assert codec.recipe_record(codec.read_recipe(builtin_file)) == builtin_file
    assert codec.recipe_record(codec.read_recipe(builtin_file, registry=custom.COMPONENTS),
                               registry=custom.COMPONENTS) == builtin_file
    with pytest.raises(ValueError, match="Unknown component"):
        codec.read_recipe(_record())
    with pytest.raises(FrozenInstanceError):
        custom.COMPONENTS._entries = ()
    with pytest.raises(TypeError):
        api.ComponentRegistry(_entries=custom.COMPONENTS._entries)
    with pytest.raises(ValueError, match="unregistered"):
        codec.recipe_record(with_constraints(ShadingRecipe(1, 1, ()), custom.RowBlackBand(0, 1)))


def test_application_rejects_missing_replaced_or_weakened_builtin_schemas():
    empty = api.ComponentRegistry()
    replaced = empty.with_component("cell-count/v1", custom.RowBlackBand,
                                    minimum=api.IntParam(0, 9), maximum=api.IntParam(0, 9))
    weakened = (empty.with_component("cell-count/v1", codec.CellCount,
        color=api.ChoiceParam(("black", "white")), count=api.IntParam(0, 999))
        .with_component("connected-cells/v1", codec.ConnectedCells,
        color=api.ChoiceParam(("black", "white")), nonempty=api.BoolParam()))
    for registry in (empty, replaced, weakened):
        with pytest.raises(ValueError, match="preserve all built-in"):
            codec.read_recipe(_record(), registry=registry)
        with pytest.raises(ValueError, match="preserve all built-in"):
            codec.recipe_record(with_constraints(ShadingRecipe(1, 1, ())), registry=registry)


@pytest.mark.parametrize("identifier,builder_type", [
    ("cell-count/v1", custom.RowBlackBand), ("example/row-black-band/v1", custom.RowBlackBand),
    ("other/alias/v1", codec.CellCount), ("other/row-band/v1", custom.RowBlackBand),
])
def test_registration_collisions_never_replace_existing_entries(identifier, builder_type):
    before = codec.recipe_record(codec.read_recipe(_record(), registry=custom.COMPONENTS), registry=custom.COMPONENTS)
    with pytest.raises(ValueError, match="already registered"):
        custom.COMPONENTS.with_component(identifier, builder_type,
                                         minimum=api.IntParam(0, 9), maximum=api.IntParam(0, 9))
    assert codec.recipe_record(codec.read_recipe(_record(), registry=custom.COMPONENTS), registry=custom.COMPONENTS) == before


@pytest.mark.parametrize("identifier", ["no-version", "Example/rule/v1", "example/rule/v0", "example/rule/v1.py",
                                       "../payload/v1", "__import__('payload')", 1, None])
def test_registration_ids_have_explicit_versions(identifier):
    with pytest.raises(ValueError, match="Component ID"):
        codec.BUILTIN_COMPONENTS.with_component(identifier, custom.RowBlackBand,
                                                minimum=api.IntParam(0, 9), maximum=api.IntParam(0, 9))


@pytest.mark.parametrize("params", [
    {}, {"minimum": api.IntParam(0, 9)},
    {"minimum": api.IntParam(0, 9), "maximum": api.IntParam(0, 9), "extra": api.BoolParam()},
    {"minimum": api.IntParam(0, 9), "maximum": lambda value: True},
])
def test_registration_requires_complete_closed_parameter_schema(params):
    with pytest.raises(ValueError):
        codec.BUILTIN_COMPONENTS.with_component("example/row-band/v1", custom.RowBlackBand, **params)


def test_registration_rejects_unsupported_class_shapes():
    @dataclass
    class Mutable:
        value: int
        def __call__(self, puzzle):
            return []
    @dataclass(frozen=True)
    class NotCallable:
        value: int
    @dataclass(frozen=True)
    class HiddenArgument:
        value: int
        hidden: InitVar[int]
        def __call__(self, puzzle):
            return []
    for cls in [lambda puzzle: [], Mutable, NotCallable, HiddenArgument]:
        with pytest.raises(ValueError):
            api.ComponentRegistry().with_component("example/test/v1", cls, value=api.IntParam(0, 9))


@pytest.mark.parametrize("field,value", [
    ("id", "example/row-black-band/v2"), ("id", "payload.factory"), ("id", {}),
    ("minimum", True), ("minimum", 0.0), ("minimum", -1), ("minimum", []),
    ("maximum", 10), ("maximum", "1"), ("maximum", None),
    ("module", "payload"), ("callable", "run"),
])
def test_custom_input_is_closed_and_typed(field, value):
    record = _record()
    record["components"][1][field] = value
    with pytest.raises(ValueError):
        codec.read_recipe(record, registry=custom.COMPONENTS)


def test_cross_field_validation_and_unregistered_subclasses():
    record = _record()
    record["components"][1].update(minimum=2, maximum=1)
    with pytest.raises(ValueError, match="minimum <= maximum"):
        codec.read_recipe(record, registry=custom.COMPONENTS)
    class ChangedBand(custom.RowBlackBand):
        pass
    with pytest.raises(ValueError, match="unregistered"):
        custom.COMPONENTS.encode(ChangedBand(0, 1))


def test_primitives_are_validated_before_trusted_constructor_is_called():
    calls = []
    @dataclass(frozen=True)
    class Probe:
        count: int
        color: str
        nonempty: bool
        def __post_init__(self):
            calls.append(self.count)
        def __call__(self, puzzle):
            return []
    registry = api.ComponentRegistry().with_component("example/probe/v1", Probe,
        count=api.IntParam(0, 9), color=api.ChoiceParam(("black", "white")), nonempty=api.BoolParam())
    valid = {"id": "example/probe/v1", "count": 1, "color": "black", "nonempty": False}
    for field, value in [("count", True), ("color", "unknown"), ("nonempty", 0), ("module", "payload")]:
        with pytest.raises(ValueError):
            registry.decode({**valid, field: value})
    assert calls == []
    assert registry.encode(registry.decode(valid)) == valid
    assert calls == [1]


def test_constructor_normalization_cannot_silently_change_saved_values():
    @dataclass(frozen=True)
    class Normalized:
        count: int
        def __post_init__(self):
            object.__setattr__(self, "count", min(2, self.count))
        def __call__(self, puzzle):
            return []
    registry = api.ComponentRegistry().with_component("example/normalized/v1", Normalized, count=api.IntParam(0, 9))
    with pytest.raises(ValueError, match="preserve"):
        registry.decode({"id": "example/normalized/v1", "count": 3})


@pytest.mark.parametrize("make", [lambda: api.IntParam(True, 9), lambda: api.IntParam(3, 1),
    lambda: api.ChoiceParam(()), lambda: api.ChoiceParam(("black", "black")),
    lambda: api.ChoiceParam("black"), lambda: api.ChoiceParam((1,))])
def test_invalid_parameter_definitions_are_rejected(make):
    with pytest.raises(ValueError):
        make()


def test_custom_cli_uses_fixed_trusted_code_and_default_cli_refuses_custom_id(tmp_path):
    output = tmp_path / "puzzle.json"
    def run(script, *args):
        return subprocess.run([sys.executable, str(EXAMPLES / script), *map(str, args)],
                              capture_output=True, text=True, timeout=30)
    created = run("custom_row_band.py", "generate", "--recipe", EXAMPLES / "custom-row-band-recipe.json",
                  "--seed", 0, "--output", output)
    assert created.returncode == 0, created.stderr
    verified = run("custom_row_band.py", "verify", output)
    assert verified.returncode == 0 and json.loads(verified.stdout)["valid"], verified.stderr
    default = run("generate_composed_shading.py", "verify", output)
    assert default.returncode == 2 and "Unknown component" in default.stderr
    assert "Traceback" not in default.stderr
    before = output.read_bytes()
    created = run("custom_row_band.py", "generate", "--recipe", EXAMPLES / "custom-row-band-recipe.json",
                  "--output", output)
    assert created.returncode == 2 and output.read_bytes() == before
