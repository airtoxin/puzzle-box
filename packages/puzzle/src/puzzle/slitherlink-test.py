from puzzle import Puzzle, one_of, single_cycle, square_grid, sum_expr


def _define_slitherlink(
    rows: int, cols: int, clues: dict[tuple[int, int], int]
) -> tuple:
    p = Puzzle("slitherlink")
    board = square_grid(rows, cols)

    edge_on = p.bool_var_map("edge_on", board.edges)

    for cell in board.cells:
        clue = clues.get((cell.row, cell.col))
        if clue is not None:
            p.add(sum_expr(edge_on[e] for e in board.edges_around(cell)) == clue)

    for v in board.vertices:
        deg = sum_expr(edge_on[e] for e in board.edges_incident(v))
        p.add(one_of(deg == 0, deg == 2))

    p.add(single_cycle(edge_on, board))

    return p, board, edge_on


def _validate_solution(
    board, edge_on, solution, clues: dict[tuple[int, int], int]
) -> None:
    for cell in board.cells:
        clue = clues.get((cell.row, cell.col))
        if clue is not None:
            count = sum(solution.value(edge_on[e]) for e in board.edges_around(cell))
            assert count == clue, f"Cell ({cell.row},{cell.col}): expected {clue}, got {count}"

    for v in board.vertices:
        deg = sum(solution.value(edge_on[e]) for e in board.edges_incident(v))
        assert deg in (0, 2), f"Vertex ({v.row},{v.col}): degree {deg}"

    total = sum(solution.value(edge_on[e]) for e in board.edges)
    assert total > 0, "No edges selected"


def test_slitherlink_2x2_single_cell_loop():
    """Loop around a single cell.

    Clues:
      4 1
      1 0
    """
    clues = {
        (0, 0): 4,
        (0, 1): 1,
        (1, 0): 1,
        (1, 1): 0,
    }
    p, board, edge_on = _define_slitherlink(2, 2, clues)
    solution = p.solve()
    assert solution is not None
    _validate_solution(board, edge_on, solution, clues)


def test_slitherlink_2x2_outer_boundary():
    """Loop is the full outer boundary.

    Clues:
      2 2
      2 2
    """
    clues = {(r, c): 2 for r in range(2) for c in range(2)}
    p, board, edge_on = _define_slitherlink(2, 2, clues)
    solution = p.solve()
    assert solution is not None
    _validate_solution(board, edge_on, solution, clues)


def test_slitherlink_3x3():
    """3x3 puzzle — outer boundary loop.

    Clues:
      2 1 2
      1 0 1
      2 1 2
    """
    clues = {
        (0, 0): 2, (0, 1): 1, (0, 2): 2,
        (1, 0): 1, (1, 1): 0, (1, 2): 1,
        (2, 0): 2, (2, 1): 1, (2, 2): 2,
    }
    p, board, edge_on = _define_slitherlink(3, 3, clues)
    solution = p.solve()
    assert solution is not None
    _validate_solution(board, edge_on, solution, clues)


def test_slitherlink_no_clues_all_zero():
    """All clues are 0 — no edges, trivially satisfied."""
    clues = {(r, c): 0 for r in range(2) for c in range(2)}
    p, board, edge_on = _define_slitherlink(2, 2, clues)
    solution = p.solve()
    assert solution is not None
    for e in board.edges:
        assert solution.value(edge_on[e]) == 0
