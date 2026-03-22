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

    def windows(self, win_rows: int, win_cols: int) -> list[list[Cell]]:
        """All overlapping sub-rectangles of the given size."""
        result: list[list[Cell]] = []
        for r in range(self._rows - win_rows + 1):
            for c in range(self._cols - win_cols + 1):
                result.append([
                    Cell(r + dr, c + dc)
                    for dr in range(win_rows)
                    for dc in range(win_cols)
                ])
        return result

    def neighbors(self, cell: Cell) -> list[Cell]:
        """Return orthogonally adjacent cells within the grid."""
        result: list[Cell] = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = cell.row + dr, cell.col + dc
            if 0 <= nr < self._rows and 0 <= nc < self._cols:
                result.append(Cell(nr, nc))
        return result

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


    def king_neighbor_pairs(self) -> list[tuple[Cell, Cell]]:
        """All pairs of king-adjacent cells (8 directions including diagonals)."""
        pairs: list[tuple[Cell, Cell]] = []
        for r in range(self._rows):
            for c in range(self._cols):
                for dr, dc in [(0, 1), (1, 0), (1, 1), (1, -1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self._rows and 0 <= nc < self._cols:
                        pairs.append((Cell(r, c), Cell(nr, nc)))
        return pairs

    def adjacent_cell_pairs(self) -> list[tuple[Cell, Cell]]:
        """All pairs of orthogonally adjacent cells."""
        pairs: list[tuple[Cell, Cell]] = []
        for r in range(self._rows):
            for c in range(self._cols):
                if c + 1 < self._cols:
                    pairs.append((Cell(r, c), Cell(r, c + 1)))
                if r + 1 < self._rows:
                    pairs.append((Cell(r, c), Cell(r + 1, c)))
        return pairs

    def cells_sharing_edge(self, edge: Edge) -> tuple[Cell, Cell]:
        """Return the two cells separated by a grid edge."""
        v1, v2 = edge.v1, edge.v2
        if v1.row == v2.row:
            # Horizontal edge: separates cells vertically
            r, c = v1.row, min(v1.col, v2.col)
            return Cell(r - 1, c), Cell(r, c)
        else:
            # Vertical edge: separates cells horizontally
            r, c = min(v1.row, v2.row), v1.col
            return Cell(r, c - 1), Cell(r, c)


def square_grid(rows: int, cols: int) -> SquareGrid:
    return SquareGrid(rows, cols)
