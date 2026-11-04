"""Python truth tests must not silently drop symbolic puzzle conditions."""
from itertools import product

import pytest

from puzzle import (
    CompoundConstraint, NoBoundaryCrossConstraint, Puzzle, ShapeAcrossConstraint,
    all_different, at_least_one, connected, non_touching, one_of, single_cycle,
    square_grid, sum_expr, unique,
)


def _objects():
    p = Puzzle("symbolic objects")
    board = square_grid(1, 2)
    black = p.bool_var_map("black", board.cells)
    edges = p.bool_var_map("edges", board.edges)
    x = black[board.cells[0]]
    return p, {
        "variable": x, "expression": sum_expr([x]), "zero-expression": sum_expr([]),
        "comparison": x == 1, "negation": ~x, "linear": sum_expr([x]) >= 1,
        "constant-true": sum_expr([]) == 0, "constant-false": sum_expr([]) == 1,
        "all-different": all_different([x]), "unique": unique(), "one-of": one_of(x == 1),
        "cycle": single_cycle(edges, board), "connected": connected(board.cells, lambda c: black[c]),
        "shape": ShapeAcrossConstraint([], edges), "boundary": NoBoundaryCrossConstraint([], edges),
        "compound": non_touching(black, board.adjacent_cell_pairs()),
    }


@pytest.mark.parametrize("kind", [
    "variable", "expression", "zero-expression", "comparison", "negation", "linear",
    "constant-true", "constant-false", "all-different", "unique", "one-of", "cycle",
    "connected", "shape", "boundary", "compound",
])
def test_symbolic_objects_reject_truth_conversion_without_changing_the_model(kind):
    p, objects = _objects()
    before = str(p._model.proto)
    with pytest.raises(TypeError, match="Python truth value"):
        bool(objects[kind])
    assert str(p._model.proto) == before


@pytest.mark.parametrize("operation", [
    lambda x, y: (x == 1) and (y == 1),
    lambda x, y: (x == 1) or (y == 1),
    lambda x, y: not x,
    lambda x, y: any([x, y]),
    lambda x, y: all([x, y]),
    lambda x, y: 1 <= sum_expr([x, y]) <= 2,
    lambda x, y: x == y == 1,
    lambda x, y: 1 if x else 0,
], ids=["and", "or", "not", "any", "all", "range", "equality-chain", "if"])
def test_python_boolean_operations_cannot_silently_lose_conditions(operation):
    p = Puzzle("bad syntax")
    variables = p.bool_var_map("x", [0, 1])
    with pytest.raises(TypeError, match="Python truth value"):
        operation(variables[0], variables[1])


@pytest.mark.parametrize("value", [False, True, None, 0, 1, [], (), {}, ""])
def test_add_rejects_non_constraints_instead_of_silently_ignoring_them(value):
    p = Puzzle("invalid constraint")
    before = str(p._model.proto)
    with pytest.raises(TypeError, match="expects a DSL constraint"):
        p.add(value)
    assert str(p._model.proto) == before


@pytest.mark.parametrize("container", [CompoundConstraint, one_of])
def test_invalid_compound_members_are_rejected_before_compiling_any_member(container):
    p = Puzzle("preflight")
    x = p.bool_var_map("x", [0])[0]
    valid = sum_expr([x]) == 1
    bad = CompoundConstraint([valid, False]) if container is CompoundConstraint else one_of(valid, False)  # type: ignore[arg-type]
    before = str(p._model.proto)
    with pytest.raises(TypeError, match="expects a DSL constraint"):
        p.add(bad)
    assert str(p._model.proto) == before


@pytest.mark.parametrize("a,b", product((0, 1), repeat=2))
def test_supported_boolean_dsl_preserves_its_truth_table(a, b):
    p = Puzzle("inclusive or and negation")
    variables = p.bool_var_map("x", [0, 1])
    x, y = variables[0], variables[1]
    p.add(x == a)
    p.add(y == b)
    p.add(x | ~y)
    assert (p.solve() is not None) == bool(a or not b)


def test_constants_and_explicit_adds_keep_solver_semantics():
    p = Puzzle("constant constraints")
    p.add(sum_expr([]) == 0)
    p.add(unique())
    assert p.solve() is not None
    p.add(sum_expr([]) == 1)
    assert p.solve() is None
    assert not [] and bool([at_least_one([])])  # Container emptiness remains a Python operation.
