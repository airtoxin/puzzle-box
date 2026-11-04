import operator

import pytest

from puzzle import (
    Puzzle, all_different, connected, exactly_one, one_of, single_cycle,
    square_grid, sum_expr,
)
from puzzle.constraints import CompoundConstraint, NoBoundaryCrossConstraint, ShapeAcrossConstraint


def _pair():
    local, foreign = Puzzle("local"), Puzzle("foreign")
    x = local.int_var_map("x", [0], 0, 1)[0]
    y = foreign.int_var_map("y", [0], 0, 1)[0]
    return local, foreign, x, y


@pytest.mark.parametrize("op", [operator.eq, operator.ne, operator.lt, operator.le,
                               operator.gt, operator.ge, operator.or_])
@pytest.mark.parametrize("summed", [False, True])
def test_foreign_operands_are_rejected_before_model_mutation(op, summed: bool):
    local, foreign, x, y = _pair()
    left, right = (sum_expr([x]), sum_expr([y])) if summed else (x, y)
    before = (str(local._model.proto), str(foreign._model.proto))
    with pytest.raises(ValueError, match="same Puzzle"):
        op(left, right)
    assert (str(local._model.proto), str(foreign._model.proto)) == before


def test_sum_rejects_foreign_variables_before_indices_can_collapse():
    local, foreign, x, y = _pair()
    # x and y both have index 0. Comparing integer indices cannot detect this.
    with pytest.raises(ValueError, match="same Puzzle"):
        sum_expr(v for v in [x, y])
    assert local.solve() is not None
    assert foreign.solve() is not None


@pytest.mark.parametrize("op", [operator.eq, operator.ne])
@pytest.mark.parametrize("reverse", [False, True])
def test_mixed_var_and_sum_comparisons_reject_foreign_operands(op, reverse: bool):
    _, _, x, y = _pair()
    summed = sum_expr([y])
    with pytest.raises(ValueError, match="same Puzzle"):
        op(summed, x) if reverse else op(x, summed)


def test_nested_sum_of_boolean_expressions_rejects_foreign_model():
    _, _, x, y = _pair()
    local_sum = sum_expr([x == 1])
    foreign_sum = sum_expr([~y])
    with pytest.raises(ValueError, match="same Puzzle"):
        sum_expr([local_sum, foreign_sum])


@pytest.mark.parametrize("kind", ["bool", "negated", "linear", "all_different", "one_of", "compound"])
def test_add_rejects_foreign_constraints_without_changing_local_model(kind: str):
    local, foreign, x, y = _pair()
    if kind == "bool":
        constraint = y == 1
    elif kind == "negated":
        constraint = ~y
    elif kind == "linear":
        constraint = sum_expr([y]) == 1
    elif kind == "all_different":
        constraint = all_different([x, y])
    elif kind == "one_of":
        constraint = one_of(sum_expr([x]) == 0, sum_expr([y]) == 1)
    else:
        # The first member would fix x=0 if validation happened incrementally.
        constraint = CompoundConstraint([sum_expr([x]) == 0, sum_expr([y]) == 1])
    before = str(local._model.proto)
    with pytest.raises(ValueError, match="same Puzzle"):
        local.add(constraint)
    assert str(local._model.proto) == before
    local.add(x == 1)
    assert local.solve() is not None


@pytest.mark.parametrize("kind", ["connected", "cycle", "shape", "boundary"])
def test_topology_constraints_reject_foreign_variables(kind: str):
    local, foreign = Puzzle("local"), Puzzle("foreign")
    board = square_grid(1, 1)
    local.bool_var_map("local", board.edges)
    foreign_cells = foreign.bool_var_map("cell", board.cells)
    foreign_edges = foreign.bool_var_map("edge", board.edges)
    local.add_feature("region_partition")
    local.add_feature("shape_class")
    if kind == "connected":
        constraint = connected(board.cells, lambda c: ~foreign_cells[c])
    elif kind == "cycle":
        constraint = single_cycle(foreign_edges, board)
    elif kind == "shape":
        constraint = ShapeAcrossConstraint([(board.edges[0], board.edges[1])], foreign_edges)
    else:
        constraint = NoBoundaryCrossConstraint([[board.edges[0]]], foreign_edges)
    before = str(local._model.proto)
    with pytest.raises(ValueError, match="same Puzzle"):
        local.add(constraint)
    assert str(local._model.proto) == before


def test_matching_rejects_foreign_selected_variables():
    local, foreign = Puzzle("local"), Puzzle("foreign")
    match = local.match_var_map("m", ["a"], ["b"], [("a", "b")])
    selected = foreign.bool_var_map("selected", ["b"])
    before = (str(local._model.proto), str(foreign._model.proto))
    with pytest.raises(ValueError, match="same Puzzle"):
        match.right_selected_iff(selected)
    assert (str(local._model.proto), str(foreign._model.proto)) == before


def test_connected_rejects_foreign_boolean_variables_before_model_mutation():
    local, foreign = Puzzle("local"), Puzzle("foreign")
    board = square_grid(1, 3)
    local.bool_var_map("local", board.cells)
    selected = foreign.bool_var_map("selected", board.cells)
    constraint = connected(board.cells, lambda c: selected[c])
    before = (str(local._model.proto), str(foreign._model.proto))
    with pytest.raises(ValueError, match="same Puzzle"):
        local.add(constraint)
    assert (str(local._model.proto), str(foreign._model.proto)) == before


@pytest.mark.parametrize("values, feasible", [([1, 1, 0], True), ([1, 0, 1], False)])
def test_connected_accepts_local_boolean_variable_predicate(values: list[int], feasible: bool):
    p = Puzzle("local connectivity")
    board = square_grid(1, 3)
    selected = p.bool_var_map("selected", board.cells)
    p.add(connected(board.cells, lambda c: selected[c]))
    for cell, value in zip(board.cells, values):
        p.add(selected[cell] == value)
    assert (p.solve() is not None) == feasible


def test_local_expressions_and_neutral_empty_sums_still_work():
    p = Puzzle("local")
    values = p.int_var_map("v", [0, 1], 0, 1)
    x, y = values[0], values[1]
    p.add(exactly_one([x, y]))
    p.add(sum_expr([]) == x)
    p.add(sum_expr([x]) < sum_expr([y]))
    p.add(x | y)
    solution = p.solve()
    assert solution is not None
    assert (solution.value(x), solution.value(y)) == (0, 1)


def test_one_local_constraint_can_be_added_repeatedly():
    p = Puzzle("repeat")
    x = p.int_var_map("x", [0], 0, 1)[0]
    constraint = sum_expr([x]) == 1
    p.add(constraint)
    p.add(constraint)
    solution = p.solve()
    assert solution is not None and solution.value(x) == 1
