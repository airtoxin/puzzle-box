import pytest

from puzzle import Puzzle, one_of, sum_expr


@pytest.mark.parametrize("value", [-1, 0, 1, 2, 3])
@pytest.mark.parametrize("kind", ["overlap", "equal", "unequal", "mixed", "strict"])
def test_exactly_one_condition_must_actually_hold(value: int, kind: str):
    p = Puzzle("one_of")
    x = p.int_var_map("x", [0], value, value)[0]
    s = sum_expr([x])
    if kind == "overlap":
        conditions = [s >= 0, s <= 2]
        truths = [value >= 0, value <= 2]
    elif kind == "equal":
        conditions = [s == 0, s == 2]
        truths = [value == 0, value == 2]
    elif kind == "unequal":
        conditions = [s != 0, s != 2]
        truths = [value != 0, value != 2]
    elif kind == "mixed":
        conditions = [x == 1, s >= 0]
        truths = [value == 1, value >= 0]
    else:
        conditions = [s < 1, s > 0]
        truths = [value < 1, value > 0]
    p.add(one_of(*conditions))
    assert (p.solve() is not None) == (sum(truths) == 1)


def test_empty_one_of_is_infeasible():
    p = Puzzle("empty one_of")
    p.add(one_of())
    assert p.solve() is None


def test_duplicate_true_condition_is_not_exclusive():
    p = Puzzle("duplicate")
    x = p.int_var_map("x", [0], 1, 1)[0]
    condition = sum_expr([x]) == 1
    p.add(one_of(condition, condition))
    assert p.solve() is None


@pytest.mark.parametrize("values", [(0, 1), (1, 1), (2, 1)])
def test_comparisons_between_expressions(values: tuple[int, int]):
    p = Puzzle("two expressions")
    x = p.int_var_map("x", [0], values[0], values[0])[0]
    y = p.int_var_map("y", [0], values[1], values[1])[0]
    p.add(one_of(sum_expr([x]) >= y, sum_expr([x]) <= y))
    assert (p.solve() is not None) == (values[0] != values[1])
