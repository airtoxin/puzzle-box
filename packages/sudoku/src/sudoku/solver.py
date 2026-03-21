from ortools.sat.python import cp_model

Grid = list[list[int]]


def solve(grid: Grid) -> Grid | None:
    """Solve a 9x9 sudoku puzzle using CP-SAT.

    Args:
        grid: 9x9 grid where 0 represents an empty cell.

    Returns:
        Solved 9x9 grid, or None if no solution exists.
    """
    model = cp_model.CpModel()

    # Create variables
    cells = [
        [model.new_int_var(1, 9, f"cell_{r}_{c}") for c in range(9)]
        for r in range(9)
    ]

    # Fix given values
    for r in range(9):
        for c in range(9):
            if grid[r][c] != 0:
                model.add(cells[r][c] == grid[r][c])

    # Row constraints: all different in each row
    for r in range(9):
        model.add_all_different(cells[r])

    # Column constraints: all different in each column
    for c in range(9):
        model.add_all_different([cells[r][c] for r in range(9)])

    # 3x3 box constraints
    for box_r in range(3):
        for box_c in range(3):
            model.add_all_different([
                cells[box_r * 3 + r][box_c * 3 + c]
                for r in range(3)
                for c in range(3)
            ])

    solver = cp_model.CpSolver()
    status = solver.solve(model)

    if status != cp_model.OPTIMAL and status != cp_model.FEASIBLE:
        return None

    return [
        [solver.value(cells[r][c]) for c in range(9)]
        for r in range(9)
    ]
