from typing import NamedTuple


class Cell(NamedTuple):
    row: int
    col: int


class Vertex(NamedTuple):
    row: int
    col: int


class Edge(NamedTuple):
    v1: Vertex
    v2: Vertex


def _make_edge(a: Vertex, b: Vertex) -> Edge:
    return Edge(min(a, b), max(a, b))


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

    @property
    def vertices(self) -> list[Vertex]:
        return [
            Vertex(r, c)
            for r in range(self._rows + 1)
            for c in range(self._cols + 1)
        ]

    @property
    def edges(self) -> list[Edge]:
        result: list[Edge] = []
        # Horizontal edges
        for r in range(self._rows + 1):
            for c in range(self._cols):
                result.append(_make_edge(Vertex(r, c), Vertex(r, c + 1)))
        # Vertical edges
        for r in range(self._rows):
            for c in range(self._cols + 1):
                result.append(_make_edge(Vertex(r, c), Vertex(r + 1, c)))
        return result

    def edges_around(self, cell: Cell) -> list[Edge]:
        r, c = cell.row, cell.col
        return [
            _make_edge(Vertex(r, c), Vertex(r, c + 1)),      # top
            _make_edge(Vertex(r + 1, c), Vertex(r + 1, c + 1)),  # bottom
            _make_edge(Vertex(r, c), Vertex(r + 1, c)),      # left
            _make_edge(Vertex(r, c + 1), Vertex(r + 1, c + 1)),  # right
        ]

    def edges_incident(self, vertex: Vertex) -> list[Edge]:
        r, c = vertex.row, vertex.col
        result: list[Edge] = []
        if r > 0:
            result.append(_make_edge(Vertex(r - 1, c), Vertex(r, c)))
        if r < self._rows:
            result.append(_make_edge(Vertex(r, c), Vertex(r + 1, c)))
        if c > 0:
            result.append(_make_edge(Vertex(r, c - 1), Vertex(r, c)))
        if c < self._cols:
            result.append(_make_edge(Vertex(r, c), Vertex(r, c + 1)))
        return result


def square_grid(rows: int, cols: int) -> SquareGrid:
    return SquareGrid(rows, cols)
