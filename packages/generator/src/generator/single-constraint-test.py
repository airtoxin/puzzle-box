from dataclasses import dataclass
import importlib
from itertools import product
import json
from pathlib import Path
import subprocess
import sys

import pytest

from generator import generate, with_constraints
from puzzle import Cell, CompoundConstraint, non_touching, one_of, sum_expr, unique
from puzzle_defs import BlackCount, ShadingRecipe, SlitherlinkRecipe

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    demo = importlib.import_module("compose_connected_shading")
    registry_api = importlib.import_module("component_registry")
    codec = importlib.import_module("composed_shading_recipe")
    saved = importlib.import_module("generate_composed_shading")


def _connected(cells):
    if not cells:
        return True
    seen, todo = set(), [next(iter(cells))]
    while todo:
        r, c = todo.pop()
        if (r, c) not in seen:
            seen.add((r, c))
            todo.extend(n for n in ((r-1, c), (r+1, c), (r, c-1), (r, c+1)) if n in cells - seen)
    return seen == cells


def _boards():
    all_cells = {(r, c) for r in range(2) for c in range(3)}
    return [bits for bits in product((0, 1), repeat=6) if sum(bits) == 2
            and _connected({(i//3, i%3) for i, b in enumerate(bits) if b})
            and _connected(all_cells - {(i//3, i%3) for i, b in enumerate(bits) if b})]


def test_single_connected_component_matches_every_two_by_three_board():
    recipe = demo.make_recipe()
    valid = _boards()
    assert len(valid) == 6
    for bits in product((0, 1), repeat=6):
        clues = [(Cell(i//3, i%3), bit) for i, bit in enumerate(bits)]
        assert (recipe.build_from_clues(clues).solve() is not None) == (bits in valid)
    # This connected white board was legal before adding black connectivity.
    separated = [(Cell(i//3, i%3), bit) for i, bit in enumerate((1, 0, 1, 0, 0, 0))]
    assert recipe.base.build_from_clues(separated).solve() is not None
    assert recipe.build_from_clues(separated).solve() is None


@pytest.mark.parametrize("seed", [0, 1])
def test_new_combination_generates_unique_irreducible_clues(seed):
    recipe = demo.make_recipe()
    clues = generate(recipe, seed=seed)
    def matches(hints):
        return [bits for bits in _boards() if all(bits[c.row*3+c.col] == v for c, v in hints)]
    assert len(matches(clues)) == 1
    assert all(len(matches(clues[:i]+clues[i+1:])) > 1 for i in range(len(clues)))
    puzzle = recipe.build_from_clues(clues)
    puzzle.add(unique())
    solution = puzzle.solve()
    assert solution is not None
    assert tuple(v for row in puzzle.result(solution) for v in row) == matches(clues)[0]


def test_single_compound_rule_is_applied_and_can_expose_an_incompatible_combination():
    def separated(p):
        return non_touching(p.black, p.board.adjacent_cell_pairs())
    recipe = with_constraints(ShadingRecipe(1, 3, (BlackCount(2),)), separated)
    assert generate(recipe, seed=0) == []  # Only 1,0,1 satisfies the actual compound rule.
    puzzle = recipe.create_empty()
    solution = puzzle.solve()
    assert solution is not None and puzzle.result(solution) == [[1, 0, 1]]
    conflicting = with_constraints(demo.make_recipe(), separated)
    assert conflicting.create_empty().solve() is None
    with pytest.raises(RuntimeError, match="Failed to generate"):
        generate(conflicting, seed=0)


@pytest.mark.parametrize("shape", ["single", "list", "tuple", "generator"])
def test_one_or_many_return_forms_preserve_the_same_loop_generation(shape):
    def builder(p):
        constraint = sum_expr(p.edge_on[e] for e in p.board.edges) == 6
        if shape == "single":
            return constraint
        if shape == "list":
            return [constraint]
        if shape == "tuple":
            return (constraint,)
        return (c for c in [constraint])
    recipe = with_constraints(SlitherlinkRecipe(1, 2), builder)
    assert generate(recipe, seed=0) == []
    puzzle = recipe.build_from_clues([])
    puzzle.add(unique())
    solution = puzzle.solve()
    assert solution is not None and len(puzzle.result(solution)) == 6


@pytest.mark.parametrize("value", [None, False, True, 7, "", "oops", b"", bytearray()])
def test_invalid_direct_returns_have_an_actionable_error(value):
    recipe = with_constraints(ShadingRecipe(1, 1, ()), lambda p: value)
    with pytest.raises(TypeError, match="return a DSL constraint or an iterable"):
        recipe.create_empty()


def test_direct_uniqueness_query_is_still_rejected():
    recipe = with_constraints(ShadingRecipe(1, 1, ()), lambda p: unique())
    with pytest.raises(ValueError, match="unique"):
        recipe.create_empty()


def test_direct_constraint_still_checks_model_ownership():
    base = ShadingRecipe(1, 1, ())
    foreign = base.create_empty()
    recipe = with_constraints(base, lambda p: foreign.black[Cell(0, 0)] == 1)
    with pytest.raises(ValueError, match="same Puzzle"):
        recipe.create_empty()


def test_direct_boolean_dsl_expression_is_applied():
    recipe = with_constraints(ShadingRecipe(1, 1, ()), lambda p: ~p.black[Cell(0, 0)])
    assert generate(recipe, seed=0) == []
    puzzle = recipe.create_empty()
    solution = puzzle.solve()
    assert solution is not None and puzzle.result(solution) == [[0]]


@pytest.mark.parametrize("target", [0, 1])
def test_direct_constant_constraint_is_not_confused_with_a_python_bool(target):
    recipe = with_constraints(ShadingRecipe(1, 1, ()), lambda p: sum_expr([]) == target)
    assert (recipe.create_empty().solve() is not None) == (target == 0)


def test_forgotten_return_is_not_treated_as_a_valid_side_effect_builder():
    def mistaken(p):
        p.add(p.black[Cell(0, 0)] == 1)
    recipe = with_constraints(ShadingRecipe(1, 1, ()), mistaken)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="return a DSL constraint or an iterable"):
        recipe.build_from_clues([])


def test_demo_outputs_actual_clues_that_determine_the_reported_answer():
    run = subprocess.run([sys.executable, str(EXAMPLES / "compose_connected_shading.py")],
                         capture_output=True, text=True, timeout=20)
    assert run.returncode == 0, run.stderr
    report = json.loads(run.stdout)
    assert report["format"] == "puzzle-box/connected-shading-demo-v1"
    matches = [bits for bits in _boards() if all(bits[c[0]*3+c[1]] == v for c, v in report["clues"])]
    assert matches == [tuple(v for row in report["answer"] for v in row)]


def test_direct_constraint_cannot_bypass_the_answer_projection_guard():
    def changed(puzzle):
        puzzle.set_solution_vars([])
        return puzzle.black[Cell(0, 0)] == 0
    recipe = with_constraints(ShadingRecipe(1, 1, ()), changed)
    with pytest.raises(ValueError, match="answer projection"):
        recipe.create_empty()


def test_registered_component_can_return_one_constraint_after_recipe_round_trip():
    @dataclass(frozen=True)
    class SingleCount:
        count: int
        def __call__(self, puzzle):
            return sum_expr(puzzle.black[c] for c in puzzle.board.cells) == self.count
    registry = codec.BUILTIN_COMPONENTS.with_component(
        "example/single-count/v1", SingleCount, count=registry_api.IntParam(0, 2))
    recipe = with_constraints(ShadingRecipe(1, 2, ()), SingleCount(1))
    data = codec.recipe_record(recipe, registry=registry)
    restored = codec.read_recipe(data, registry=registry)
    for values in product((0, 1), repeat=2):
        clues = [(Cell(0, i), value) for i, value in enumerate(values)]
        assert (restored.build_from_clues(clues).solve() is not None) == (sum(values) == 1)
    record = saved.generate_record(data, registry=registry)
    assert saved.verify(record, registry=registry)["valid"]


@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("outer", ["compound", "one-of"])
@pytest.mark.parametrize("with_clues", [False, True])
def test_nested_uniqueness_queries_are_rejected_before_compilation(wrapped, outer, with_clues):
    def builder(puzzle):
        # Deliberately malformed nested input must not activate a solve query.
        inner = CompoundConstraint([unique()])  # type: ignore[arg-type]
        result = CompoundConstraint([inner]) if outer == "compound" else one_of(inner)  # type: ignore[arg-type]
        return [result] if wrapped else result
    recipe = with_constraints(ShadingRecipe(1, 1, ()), builder)
    with pytest.raises(ValueError, match="unique"):
        if with_clues:
            recipe.build_from_clues([(Cell(0, 0), 0)])
        else:
            recipe.create_empty()
