import pytest

from puzzle import Puzzle, connected, single_cycle, square_grid, unique
from puzzle_defs import SlitherlinkPuzzle, TentsPuzzle


def test_unique_loop_ignores_orientation():
    p = SlitherlinkPuzzle([[4]])
    p.add(unique())
    for _ in range(2):
        solution = p.solve()
        assert solution is not None
        assert p.result(solution) == set(p.board.edges)


@pytest.mark.parametrize("active", [0, 1])
def test_unique_connected_cells_ignore_spanning_tree_witnesses(active: int):
    p = Puzzle("connected")
    board = square_grid(2, 2)
    values = p.int_var_grid("active", board.cells, active, active)
    p.add(connected(board.cells, lambda c: values[c] == 1))
    p.add(unique())
    assert p.solve() is not None


def test_unique_rejects_distinct_edge_sets():
    p = Puzzle("two loops")
    board = square_grid(1, 2)
    edges = p.bool_var_map("edge", board.edges)
    p.add(single_cycle(edges, board))
    p.add(unique())
    assert p.solve() is None


def test_unique_tents_ignores_alternative_tree_matchings():
    p = TentsPuzzle(
        [list(".T."), list("T.T"), list(".T.")],
        row_counts=[2, 0, 2], col_counts=[2, 0, 2],
    )
    p.add(unique())
    solution = p.solve()
    assert solution is not None
    assert p.result(solution) == [list("ATA"), list("T.T"), list("ATA")]


def test_unique_tents_rejects_distinct_placements():
    p = TentsPuzzle([list(".T.")])
    p.add(unique())
    assert p.solve() is None


def test_projection_ignores_witnesses_and_does_not_mutate_model():
    p = Puzzle("projection")
    values = p.int_var_map("v", ["answer", "witness"], 0, 1)
    p.set_solution_vars([values["answer"]])
    p.add(values["answer"] == 1)
    p.add(unique())
    for _ in range(2):
        solution = p.solve()
        assert solution is not None
        assert solution.value(values["answer"]) == 1
    p.add(values["witness"] == 0)
    assert p.solve() is not None
    p.add(values["witness"] == 1)
    assert p.solve() is None


def test_default_projection_includes_variables_created_after_unique():
    p = Puzzle("default")
    p.add(unique())
    p.int_var_map("free", [0], 0, 1)
    assert p.solve() is None


def test_projection_rejects_foreign_variables_without_changing_selection():
    p = Puzzle("local")
    answer = p.int_var_map("answer", [0], 0, 0)[0]
    p.int_var_map("witness", [0], 0, 1)
    p.set_solution_vars([answer])
    other = Puzzle("other").int_var_map("other", [0], 0, 0)[0]
    with pytest.raises(ValueError, match="belong"):
        p.set_solution_vars([other])
    p.add(unique())
    assert p.solve() is not None


def test_empty_projection_still_requires_a_feasible_solution():
    p = Puzzle("empty projection")
    var = p.int_var_map("witness", [0], 0, 1)[0]
    p.set_solution_vars([])
    p.add(unique())
    assert p.solve() is not None
    p.add(var == 2)
    assert p.solve() is None


def test_puzzle_without_variables_has_one_empty_solution():
    p = Puzzle("empty")
    p.add(unique())
    assert p.solve() is not None
