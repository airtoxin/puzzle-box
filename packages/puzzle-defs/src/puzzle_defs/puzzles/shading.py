"""Composable rules sharing a rectangular grid of black/white answer cells."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, Sequence

from puzzle import (
    Cell, Puzzle, Solution, SquareGrid, VarMap, at_least_one,
    connected, non_touching, square_grid, sum_expr,
)

CellClue = tuple[Cell, int]  # 0 = white, 1 = black


def _check_nonnegative(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")


@dataclass(frozen=True)
class RowCountClue:
    row: int
    count: int

    def __post_init__(self) -> None:
        _check_nonnegative(self.row, "Row index")
        _check_nonnegative(self.count, "Row count")


@dataclass(frozen=True)
class ColumnCountClue:
    col: int
    count: int

    def __post_init__(self) -> None:
        _check_nonnegative(self.col, "Column index")
        _check_nonnegative(self.count, "Column count")


Clue = CellClue | RowCountClue | ColumnCountClue
ClueKind = Literal["cell", "row-count", "column-count"]
CLUE_KINDS: tuple[ClueKind, ...] = ("cell", "row-count", "column-count")


class ShadingRule(Protocol):
    """Add base constraints to the shared cells, independently of their clues."""

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None: ...


@dataclass(frozen=True)
class BlackCount:
    count: int

    def __post_init__(self) -> None:
        if type(self.count) is not int or self.count < 0:
            raise ValueError("Black count must be a nonnegative integer")

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        if self.count > len(board.cells):
            raise ValueError("Black count cannot exceed the board area")
        puzzle.add(sum_expr(black[c] for c in board.cells) == self.count)


@dataclass(frozen=True)
class NonTouchingBlack:
    """Black cells cannot share an edge (or a corner if diagonal=True)."""

    diagonal: bool = False

    def __post_init__(self) -> None:
        if type(self.diagonal) is not bool:
            raise ValueError("diagonal must be a boolean")

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        pairs = board.king_neighbor_pairs() if self.diagonal else board.adjacent_cell_pairs()
        puzzle.add(non_touching(black, pairs))


@dataclass(frozen=True)
class ConnectedWhite:
    """White cells are orthogonally connected and, by default, nonempty."""

    nonempty: bool = True

    def __post_init__(self) -> None:
        if type(self.nonempty) is not bool:
            raise ValueError("nonempty must be a boolean")

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        puzzle.add(connected(board.cells, lambda c: ~black[c]))
        if self.nonempty:
            puzzle.add(at_least_one(~black[c] for c in board.cells))


@dataclass(frozen=True)
class NoWhite2x2:
    """Every 2x2 window must contain a black cell."""

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        for window in board.windows(2, 2):
            puzzle.add(at_least_one(black[c] for c in window))


def _check_size(rows: int, cols: int) -> None:
    if type(rows) is not int or type(cols) is not int or rows < 1 or cols < 1:
        raise ValueError("Rows and columns must be positive integers")


class ShadingPuzzle(Puzzle):
    def __init__(
        self, rows: int, cols: int, rules: Sequence[ShadingRule], clues: Sequence[Clue] = (),
    ) -> None:
        _check_size(rows, cols)
        super().__init__("composed shading")
        self.rows, self.cols = rows, cols
        self.board = square_grid(rows, cols)
        self.black = self.bool_var_map("black", self.board.cells)
        # Rules may introduce witnesses; only the shading is an answer.
        self.set_solution_vars(self.black[c] for c in self.board.cells)
        for rule in rules:
            rule.apply(self, self.board, self.black)
        for clue in clues:
            if isinstance(clue, RowCountClue):
                if clue.row >= rows or clue.count > cols:
                    raise ValueError("Row clue index or count exceeds the board dimensions")
                self.add(sum_expr(self.black[Cell(clue.row, c)] for c in range(cols)) == clue.count)
            elif isinstance(clue, ColumnCountClue):
                if clue.col >= cols or clue.count > rows:
                    raise ValueError("Column clue index or count exceeds the board dimensions")
                self.add(sum_expr(self.black[Cell(r, clue.col)] for r in range(rows)) == clue.count)
            else:
                cell, value = clue
                if cell not in self.black:
                    raise ValueError("Clue cell is outside the board")
                if type(value) is not int or value not in (0, 1):
                    raise ValueError("Clue values must be 0 (white) or 1 (black)")
                self.add(self.black[cell] == value)

    def result(self, solution: Solution) -> list[list[int]]:
        return [
            [solution.value(self.black[Cell(r, c)]) for c in range(self.cols)]
            for r in range(self.rows)
        ]


@dataclass(frozen=True)
class ShadingRecipe:
    """Keep dimensions and base rules fixed while generation removes clues.

    Built-in rules are immutable. Custom rules must also keep their configuration
    and answer semantics fixed across calls; removing clues may only relax rules.
    clue_kinds selects candidate hints, not base rules. Include "cell" to ensure
    the initial candidate pool fixes the shading; counts alone can be ambiguous.
    """

    rows: int
    cols: int
    rules: tuple[ShadingRule, ...]
    clue_kinds: tuple[ClueKind, ...] = ("cell",)

    def __post_init__(self) -> None:
        _check_size(self.rows, self.cols)
        object.__setattr__(self, "rules", tuple(self.rules))
        kinds = tuple(self.clue_kinds)
        if any(kind not in CLUE_KINDS for kind in kinds) or len(set(kinds)) != len(kinds):
            raise ValueError("Clue kinds must be distinct cell, row-count or column-count values")
        object.__setattr__(self, "clue_kinds", kinds)

    def create_empty(self) -> ShadingPuzzle:
        return self.build_from_clues([])

    def extract_clues(self, solution: Solution, puzzle: ShadingPuzzle) -> list[Clue]:
        # Including all cell clues makes the candidate pool unique even when
        # row/column counts alone leave several answers. Reduction retains any
        # cell clues that are still necessary; it never changes the base rules.
        values = {c: solution.value(puzzle.black[c]) for c in puzzle.board.cells}
        clues: list[Clue] = []
        for kind in self.clue_kinds:
            if kind == "cell":
                clues.extend(values.items())
            elif kind == "row-count":
                clues.extend(RowCountClue(r, sum(values[Cell(r, c)] for c in range(self.cols)))
                             for r in range(self.rows))
            else:
                clues.extend(ColumnCountClue(c, sum(values[Cell(r, c)] for r in range(self.rows)))
                             for c in range(self.cols))
        return clues

    def build_from_clues(self, clues: Sequence[Clue]) -> ShadingPuzzle:
        return ShadingPuzzle(self.rows, self.cols, self.rules, clues)
