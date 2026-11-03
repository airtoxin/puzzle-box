from itertools import product

import pytest

from puzzle import Puzzle


@pytest.mark.parametrize("left,right,pairs,message", [
    (["a", "a"], ["b"], [("a", "b")], "left"),
    (["a"], ["b", "b"], [("a", "b")], "right"),
    (["a"], ["b"], [("a", "b"), ("a", "b")], "duplicate"),
    (["a"], ["b"], [("a", "b"), ("ghost", "b")], "declared"),
    (["a"], ["b"], [("a", "b"), ("a", "ghost")], "declared"),
    ([], ["b"], [("ghost", "b")], "declared"),
    (["a"], [], [("a", "ghost")], "declared"),
])
def test_invalid_graph_is_rejected_before_any_variable_is_created(left, right, pairs, message):
    p = Puzzle("invalid graph")
    p.bool_var_map("existing", [0])
    before = str(p._model.proto)
    variable_count = len(p._vars)
    with pytest.raises(ValueError, match=message):
        p.match_var_map("match", left, right, pairs)
    assert str(p._model.proto) == before
    assert len(p._vars) == variable_count
    assert p.solve() is not None


def test_the_same_label_can_be_used_on_both_sides():
    p = Puzzle("same labels")
    match = p.match_var_map("m", ["a"], ["a"], [("a", "a")])
    p.add(match.left_degree_eq(1))
    p.add(match.right_degree_eq(1))
    solution = p.solve()
    assert solution is not None and solution.value(match["a", "a"]) == 1


@pytest.mark.parametrize("side", ["left", "right"])
@pytest.mark.parametrize("relation", ["eq", "le"])
@pytest.mark.parametrize("bound", [-1, 0, 1])
def test_isolated_vertex_degree_is_zero(side: str, relation: str, bound: int):
    p = Puzzle("isolated")
    match = p.match_var_map("m", ["a"], ["b"], [])
    constraint = getattr(match, f"{side}_degree_{relation}")(bound)
    p.add(constraint)
    expected = 0 == bound if relation == "eq" else 0 <= bound
    assert (p.solve() is not None) == expected


def test_empty_graph_has_one_empty_matching():
    p = Puzzle("empty")
    match = p.match_var_map("m", [], [], [])
    p.add(match.left_degree_eq(1))
    p.add(match.right_degree_eq(1))
    assert p.solve() is not None  # No vertices to constrain.


@pytest.mark.parametrize("allowed_mask", range(16))
def test_two_by_two_matchings_against_an_exhaustive_graph_oracle(allowed_mask: int):
    all_pairs = [(0, 0), (0, 1), (1, 0), (1, 1)]
    allowed = [pair for idx, pair in enumerate(all_pairs) if allowed_mask & (1 << idx)]
    for bits in product([0, 1], repeat=len(allowed)):
        # Graph-theoretic oracle independent of the DSL and CP-SAT encoding.
        chosen = {pair for pair, bit in zip(allowed, bits) if bit}
        expected = (
            all(sum(a == vertex for a, _ in chosen) == 1 for vertex in [0, 1])
            and all(sum(b == vertex for _, b in chosen) <= 1 for vertex in [0, 1])
        )
        p = Puzzle("oracle")
        match = p.match_var_map("m", [0, 1], [0, 1], allowed)
        p.add(match.left_degree_eq(1))
        p.add(match.right_degree_le(1))
        for pair, bit in zip(allowed, bits):
            p.add(match[pair] == bit)
        assert (p.solve() is not None) == expected, (allowed, chosen)


def test_candidate_order_and_input_lists_are_preserved():
    left, right = ["b", "a"], [2, 1]
    pairs = [("b", 2), ("a", 1)]
    p = Puzzle("ordering")
    match = p.match_var_map("m", left, right, pairs)
    p.add(match.left_degree_eq(1))
    solution = p.solve()
    assert solution is not None
    assert [solution.value(match[pair]) for pair in pairs] == [1, 1]
    assert left == ["b", "a"] and right == [2, 1]
    assert pairs == [("b", 2), ("a", 1)]
