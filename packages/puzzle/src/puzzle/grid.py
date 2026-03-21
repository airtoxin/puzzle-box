from typing import NamedTuple


class Cell(NamedTuple):
    row: int
    col: int


class SquareGrid:
    def __init__(self, rows: int, cols: int) -> None:
        self._rows = rows
        self._cols = cols
        self._cells = [Cell(r, c) for r in range(rows) for c in range(cols)]

    @property
    def cells(self) -> list[Cell]:
        return list(self._cells)

    def cell(self, row: int, col: int) -> Cell:
        return Cell(row, col)

    def rows(self) -> list[list[Cell]]:
        return [
            [Cell(r, c) for c in range(self._cols)]
            for r in range(self._rows)
        ]

    def cols(self) -> list[list[Cell]]:
        return [
            [Cell(r, c) for r in range(self._rows)]
            for c in range(self._cols)
        ]

    def blocks(self, block_rows: int, block_cols: int) -> list[list[Cell]]:
        blocks: list[list[Cell]] = []
        for br in range(self._rows // block_rows):
            for bc in range(self._cols // block_cols):
                block = [
                    Cell(br * block_rows + r, bc * block_cols + c)
                    for r in range(block_rows)
                    for c in range(block_cols)
                ]
                blocks.append(block)
        return blocks


def square_grid(rows: int, cols: int) -> SquareGrid:
    return SquareGrid(rows, cols)
