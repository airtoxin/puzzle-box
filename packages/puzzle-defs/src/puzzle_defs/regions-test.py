from puzzle import Cell, Puzzle, exactly_one, square_grid
from puzzle_defs import (
    enumerate_connected_regions,
    enumerate_rectangles,
    filter_number_equals_area,
    filter_one_number_per_region,
    filter_same_number_combination,
)


def test_enumerate_connected_regions_size_1():
    board = square_grid(2, 2)
    regions = enumerate_connected_regions(board, size=1)
    assert len(regions) == 4


def test_enumerate_connected_regions_size_2():
    """Dominoes on 2x2: 4 possible."""
    board = square_grid(2, 2)
    regions = enumerate_connected_regions(board, size=2)
    assert len(regions) == 4  # 2 horizontal + 2 vertical


def test_enumerate_connected_regions_size_3():
    """Trominoes on 3x3."""
    board = square_grid(3, 3)
    regions = enumerate_connected_regions(board, size=3)
    # Should include I-trominoes and L-trominoes in all positions
    assert len(regions) > 0
    assert all(len(r.cells) == 3 for r in regions)
    # Verify all are connected
    for r in regions:
        cells = list(r.cells)
        # BFS connectivity
        visited = {cells[0]}
        queue = [cells[0]]
        while queue:
            c = queue.pop()
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                n = Cell(c.row + dr, c.col + dc)
                if n in r.cells and n not in visited:
                    visited.add(n)
                    queue.append(n)
        assert visited == set(cells), f"Disconnected region: {cells}"


def test_enumerate_connected_regions_custom_board():
    """Non-rectangular board."""
    board = square_grid(3, 3)
    board_cells = {Cell(0, 0), Cell(0, 1), Cell(1, 0), Cell(1, 1), Cell(2, 0), Cell(2, 1)}
    regions = enumerate_connected_regions(board, size=3, board_cells=board_cells)
    assert len(regions) > 0
    for r in regions:
        assert r.cells.issubset(board_cells)


def test_enumerate_rectangles():
    board = square_grid(3, 3)
    rects = enumerate_rectangles(board)
    # All possible axis-aligned rectangles on 3x3
    assert len(rects) > 0
    for r in rects:
        cells = sorted(r.cells)
        rows = sorted(set(c.row for c in cells))
        cols = sorted(set(c.col for c in cells))
        assert len(cells) == len(rows) * len(cols)


def test_enumerate_rectangles_with_size():
    board = square_grid(4, 4)
    rects = enumerate_rectangles(board, size=4)
    # 4-cell rectangles: 1x4, 4x1, 2x2
    assert all(len(r.cells) == 4 for r in rects)
    assert len(rects) > 0


def test_filter_one_number_per_region():
    board = square_grid(2, 2)
    regions = enumerate_connected_regions(board, size=2)
    numbers = {Cell(0, 0): 5, Cell(1, 1): 3}
    filtered = filter_one_number_per_region(regions, numbers)
    for r in filtered:
        assert r.clue_cell is not None
        numbered = [c for c in r.cells if c in numbers]
        assert len(numbered) == 1


def test_filter_number_equals_area():
    board = square_grid(3, 3)
    regions = enumerate_connected_regions(board, size=3)
    numbers = {Cell(0, 0): 3}  # number 3 = area 3
    filtered = filter_number_equals_area(regions, numbers)
    for r in filtered:
        assert len(r.cells) == 3
        assert r.clue_cell == Cell(0, 0)
        assert Cell(0, 0) in r.cells

    # number 2 ≠ area 3: no matches
    filtered2 = filter_number_equals_area(regions, {Cell(0, 0): 2})
    assert len(filtered2) == 0


def test_filter_same_number_combination():
    board = square_grid(2, 4)
    regions = enumerate_connected_regions(board, size=4)
    # Numbers: two 1s and two 2s → each of 2 regions gets {1, 2}
    numbers = {Cell(0, 0): 1, Cell(0, 3): 1, Cell(1, 0): 2, Cell(1, 3): 2}
    filtered = filter_same_number_combination(regions, numbers, num_regions=2)
    for r in filtered:
        nums_in_region = sorted(numbers[c] for c in r.cells if c in numbers)
        assert nums_in_region == [1, 2]


def test_filter_same_number_combination_not_divisible():
    """3 numbers with 2 regions — not evenly divisible."""
    board = square_grid(2, 3)
    regions = enumerate_connected_regions(board, size=3)
    numbers = {Cell(0, 0): 1, Cell(0, 1): 1, Cell(0, 2): 1}
    # 3 ones / 2 regions = 1.5 — impossible
    filtered = filter_same_number_combination(regions, numbers, num_regions=2)
    assert len(filtered) == 0


def test_exact_cover_with_regions():
    """2x4 board, divide into 2 connected regions of size 4, each with one number."""
    board = square_grid(2, 4)
    numbers = {Cell(0, 1): 4, Cell(1, 2): 4}

    regions = enumerate_connected_regions(board, size=4)
    regions = filter_number_equals_area(regions, numbers)

    p = Puzzle("test")
    p.add_feature("region_partition")
    use = p.bool_var_map("use", regions)

    for cell in board.cells:
        covering = [r for r in regions if cell in r.cells]
        assert covering
        p.add(exactly_one(use[r] for r in covering))

    solution = p.solve()
    assert solution is not None
    chosen = [r for r in regions if solution.value(use[r])]
    assert len(chosen) == 2
    for r in chosen:
        assert len(r.cells) == 4
        assert r.clue_cell is not None
