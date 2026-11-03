import pytest

from puzzle import Puzzle, Solution, square_grid, unique


@pytest.mark.parametrize("require_unique", [False, True])
def test_solution_rejects_foreign_variables_with_the_same_index(require_unique: bool):
    local, foreign = Puzzle("local"), Puzzle("foreign")
    x = local.int_var_map("x", [0], 0, 0)[0]
    y = foreign.int_var_map("y", [0], 1, 1)[0]
    if require_unique:
        local.add(unique())
    solution = local.solve()
    assert solution is not None
    with pytest.raises(ValueError, match="same Puzzle"):
        solution.value(y)
    assert solution.value(x) == 0


def test_grid_values_rejects_a_foreign_grid():
    board = square_grid(1, 2)
    local, foreign = Puzzle("local"), Puzzle("foreign")
    values = local.int_var_grid("v", board.cells, 0, 0)
    others = foreign.int_var_grid("v", board.cells, 1, 1)
    solution = local.solve()
    assert solution is not None
    with pytest.raises(ValueError, match="same Puzzle"):
        solution.grid_values(others, 1, 2)
    assert solution.grid_values(values, 1, 2) == [[0, 0]]


def test_solution_rejects_variables_created_after_solving():
    p = Puzzle("later variable")
    x = p.int_var_map("x", [0], 0, 0)[0]
    solution = p.solve()
    assert solution is not None
    y = p.int_var_map("y", [0], 1, 1)[0]
    with pytest.raises(ValueError, match="created after"):
        solution.value(y)
    assert solution.value(x) == 0
    newer = p.solve()
    assert newer is not None and newer.value(y) == 1


def test_existing_solution_remains_a_snapshot_after_model_changes():
    p = Puzzle("snapshot")
    x = p.int_var_map("x", [0], 0, 1)[0]
    solution = p.solve()
    assert solution is not None
    previous = solution.value(x)
    p.add(x != previous)
    newer = p.solve()
    assert newer is not None
    assert newer.value(x) != previous
    assert solution.value(x) == previous


def test_reusing_a_low_level_solver_does_not_change_a_solution_snapshot():
    from ortools.sat.python import cp_model

    p, other = Puzzle("p"), Puzzle("other")
    x = p.int_var_map("x", [0], 0, 0)[0]
    other.int_var_map("y", [0], 1, 1)
    solver = cp_model.CpSolver()
    assert solver.solve(p._model) == cp_model.OPTIMAL
    solution = Solution(solver, p._model)
    assert solver.solve(other._model) == cp_model.OPTIMAL
    assert solution.value(x) == 0


def test_low_level_construction_requires_a_feasible_response():
    from ortools.sat.python import cp_model

    model = cp_model.CpModel()
    model.add(False)
    solver = cp_model.CpSolver()
    assert solver.solve(model) == cp_model.INFEASIBLE
    with pytest.raises(ValueError, match="feasible"):
        Solution(solver, model)
