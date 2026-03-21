from puzzle import Cell, square_grid


def test_cells_count():
    board = square_grid(9, 9)
    assert len(board.cells) == 81


def test_cell_lookup():
    board = square_grid(9, 9)
    c = board.cell(2, 3)
    assert c == Cell(2, 3)


def test_rows():
    board = square_grid(9, 9)
    rows = board.rows()
    assert len(rows) == 9
    assert all(len(row) == 9 for row in rows)
    assert rows[0][0] == Cell(0, 0)
    assert rows[2][5] == Cell(2, 5)


def test_cols():
    board = square_grid(9, 9)
    cols = board.cols()
    assert len(cols) == 9
    assert all(len(col) == 9 for col in cols)
    assert cols[0][0] == Cell(0, 0)
    assert cols[3][2] == Cell(2, 3)


def test_blocks():
    board = square_grid(9, 9)
    blocks = board.blocks(3, 3)
    assert len(blocks) == 9
    assert all(len(block) == 9 for block in blocks)
    # First block is top-left 3x3
    assert Cell(0, 0) in blocks[0]
    assert Cell(2, 2) in blocks[0]
    assert Cell(3, 0) not in blocks[0]
