"""Composable rules sharing a rectangular grid of black/white answer cells."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from puzzle import (
    Cell, Puzzle, Solution, SquareGrid, VarMap, at_least_one,
    connected, non_touching, square_grid, sum_expr,
)

Clue = tuple[Cell, int]  # 0 = white, 1 = black


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
        for cell, value in clues:
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
    """

    rows: int
    cols: int
    rules: tuple[ShadingRule, ...]

    def __post_init__(self) -> None:
        _check_size(self.rows, self.cols)
        object.__setattr__(self, "rules", tuple(self.rules))

    def create_empty(self) -> ShadingPuzzle:
        return self.build_from_clues([])

    def extract_clues(self, solution: Solution, puzzle: ShadingPuzzle) -> list[Clue]:
        return [(c, solution.value(puzzle.black[c])) for c in puzzle.board.cells]

    def build_from_clues(self, clues: list[Clue]) -> ShadingPuzzle:
        return ShadingPuzzle(self.rows, self.cols, self.rules, clues)
