"""Independent review regressions at composition/registration/file boundaries."""

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
import sys

import pytest

from generator import generate, with_constraints
from puzzle import Cell, Puzzle, unique
from puzzle_defs import BlackCount, ShadingRecipe

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    api = importlib.import_module("component_registry")
    codec = importlib.import_module("composed_shading_recipe")
    demo = importlib.import_module("generate_composed_shading")
    files = importlib.import_module("shading_recipe")


@dataclass(frozen=True)
class ResetProjection:
    def __call__(self, puzzle):
        puzzle.set_solution_vars([])
        return []


def test_component_cannot_turn_two_visible_answers_into_a_unique_empty_projection():
    base = ShadingRecipe(1, 1, ())
    # Direct feasibility checks establish the two distinct visible answers.
    assert all(base.build_from_clues([(Cell(0, 0), value)]).solve() is not None for value in (0, 1))
    recipe = with_constraints(base, ResetProjection())
    registry = codec.BUILTIN_COMPONENTS.with_component("review/reset-projection/v1", ResetProjection)
    record = codec.recipe_record(recipe, registry=registry)
    with pytest.raises(ValueError, match="answer projection"):
        generate(recipe, seed=0)
    with pytest.raises(ValueError, match="answer projection"):
        demo.generate_record(record, registry=registry)
    # This exact false certificate was accepted before the guard.
    saved = {"format": demo.FORMAT, "recipe": record, "seed": 0, "clues": [], "solution": [[0]]}
    with pytest.raises(ValueError, match="answer projection"):
        demo.verify(saved, registry=registry)


@pytest.mark.parametrize("mode", ["subset", "witness", "lazy"])
def test_projection_change_is_rejected_for_clue_models_and_lazy_builders(mode):
    def changed(puzzle):
        if mode == "lazy":
            yield puzzle.black[Cell(0, 0)] == 0
            puzzle.set_solution_vars([])
        elif mode == "subset":
            puzzle.set_solution_vars([puzzle.black[Cell(0, 0)]])
        else:
            helper = puzzle.bool_var_map("helper", [0])
            puzzle.set_solution_vars([helper[0]])
    recipe = with_constraints(ShadingRecipe(1, 2, ()), changed)
    with pytest.raises(ValueError, match="answer projection"):
        recipe.build_from_clues([(Cell(0, 0), 0)])


def test_projection_is_checked_between_builders_not_only_after_the_last():
    called = []
    def restore(puzzle):
        called.append(True)
        puzzle.set_solution_vars(puzzle.black[c] for c in puzzle.board.cells)
        return []
    recipe = with_constraints(ShadingRecipe(1, 1, ()), ResetProjection(), restore)
    with pytest.raises(ValueError, match="answer projection"):
        recipe.create_empty()
    assert called == []


def test_reordering_same_projection_and_adding_internal_witness_are_compatible():
    def reordered(puzzle):
        cells = list(reversed(puzzle.board.cells))
        puzzle.set_solution_vars([puzzle.black[c] for c in cells] + [puzzle.black[cells[0]]])
        puzzle.bool_var_map("free_witness", [0])
        return []
    recipe = with_constraints(ShadingRecipe(1, 2, (BlackCount(0),)), reordered)
    assert generate(recipe, seed=0) == []
    puzzle = recipe.create_empty()
    puzzle.add(unique())
    solution = puzzle.solve()
    assert solution is not None and puzzle.result(solution) == [[0, 0]]


def test_default_projection_mode_keeps_its_existing_behavior():
    class Base:
        def create_empty(self):
            puzzle = Puzzle("default answer variables")
            puzzle.bool_var_map("original", [0])
            return puzzle
        def build_from_clues(self, clues):
            return self.create_empty()
        def extract_clues(self, solution, puzzle):
            return []
    def witness(puzzle):
        puzzle.bool_var_map("extra", [0])
        return []
    puzzle = with_constraints(Base(), witness).create_empty()
    assert puzzle.solution_vars is None
    puzzle.add(unique())
    assert puzzle.solve() is None  # Factory variables still count in default mode.
    with pytest.raises(ValueError, match="answer projection"):
        with_constraints(Base(), ResetProjection()).create_empty()


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
