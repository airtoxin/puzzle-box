"""Couple cell shading and a loop through cell centers using Yajilin rules."""

from dataclasses import dataclass
from typing import Literal, Sequence

from puzzle import Cell, Edge, Solution, at_least_one, sum_expr
from puzzle_defs.puzzles.slitherlink_recipe import EdgeStateClue
from puzzle_defs.puzzles.yajilin import DIRECTIONS, YajilinPuzzle


def _cell(cell: Cell) -> bool:
    return isinstance(cell, Cell) and all(type(n) is int and n >= 0 for n in cell)


@dataclass(frozen=True)
class ArrowSite:
    cell: Cell
    direction: str

    def __post_init__(self) -> None:
        if not _cell(self.cell) or not isinstance(self.direction, str) or self.direction not in DIRECTIONS:
            raise ValueError("An arrow site needs nonnegative cell coordinates and up/down/left/right")


@dataclass(frozen=True)
class ArrowCountClue:
    cell: Cell
    count: int

    def __post_init__(self) -> None:
        if not _cell(self.cell) or type(self.count) is not int or self.count < 0:
            raise ValueError("An arrow count needs nonnegative integer coordinates and count")


@dataclass(frozen=True)
class BlackCellClue:
    cell: Cell
    black: int

    def __post_init__(self) -> None:
        if not _cell(self.cell) or type(self.black) is not int or self.black not in (0, 1):
            raise ValueError("A black-cell clue needs nonnegative coordinates and a 0/1 state")


@dataclass(frozen=True)
class YajilinAnswer:
    black_cells: frozenset[Cell]
    loop_edges: frozenset[Edge]


YajilinClue = ArrowCountClue | BlackCellClue | EdgeStateClue
YajilinClueKind = Literal["arrow", "black", "edge"]
YAJILIN_CLUE_KINDS: tuple[YajilinClueKind, ...] = ("arrow", "black", "edge")


@dataclass(frozen=True)
class YajilinRecipe:
    """Fixed arrow sites; reduce counts, cell states and edge states only.

    The shared generator can remove these constraints monotonically. Edge
    coordinates refer to cell centers, not the corners used by Slitherlink.
    """

    rows: int
    cols: int
    arrow_sites: tuple[ArrowSite, ...] = ()
    clue_kinds: tuple[YajilinClueKind, ...] = YAJILIN_CLUE_KINDS

    def __post_init__(self) -> None:
        if any(type(n) is not int or n < 2 for n in (self.rows, self.cols)):
            raise ValueError("Yajilin recipe rows and columns must be integers of at least 2")
        sites = tuple(self.arrow_sites)
        if any(not isinstance(s, ArrowSite) or not self._inside(s.cell) for s in sites):
            raise ValueError("Arrow sites must be inside the board")
        if len({s.cell for s in sites}) != len(sites):
            raise ValueError("Arrow sites must have distinct cells")
        kinds = tuple(self.clue_kinds)
        if any(k not in YAJILIN_CLUE_KINDS for k in kinds) or len(set(kinds)) != len(kinds):
            raise ValueError("Clue kinds must be distinct arrow, black or edge values")
        object.__setattr__(self, "arrow_sites", sites)
        object.__setattr__(self, "clue_kinds", kinds)

    def _inside(self, cell: Cell) -> bool:
        return cell.row < self.rows and cell.col < self.cols

    def ray(self, site: ArrowSite) -> tuple[Cell, ...]:
        """All ordinary cells strictly ahead; other arrow sites are skipped."""
        if site not in self.arrow_sites:
            raise ValueError("Arrow site is not in this recipe")
        blocked = {s.cell for s in self.arrow_sites}
        dr, dc = DIRECTIONS[site.direction]
        r, c = site.cell
        cells = []
        r, c = r + dr, c + dc
        while 0 <= r < self.rows and 0 <= c < self.cols:
            cell = Cell(r, c)
            if cell not in blocked:
                cells.append(cell)
            r, c = r + dr, c + dc
        return tuple(cells)

    def create_empty(self) -> YajilinPuzzle:
        return self.build_from_clues([])

    def build_from_clues(self, clues: Sequence[YajilinClue]) -> YajilinPuzzle:
        sites = {s.cell: s for s in self.arrow_sites}
        for clue in clues:
            if isinstance(clue, ArrowCountClue):
                if clue.cell not in sites or clue.count > len(self.ray(sites[clue.cell])):
                    raise ValueError("Arrow count must fit a configured arrow site's ray")
            elif isinstance(clue, BlackCellClue):
                if not self._inside(clue.cell) or clue.cell in sites:
                    raise ValueError("Black-cell clues must refer to ordinary cells inside the board")
            elif isinstance(clue, EdgeStateClue):
                if any(v.row >= self.rows or v.col >= self.cols for v in clue.edge):
                    raise ValueError("Loop edge endpoints must be cell centers inside the board")
            else:
                raise ValueError("Expected an ArrowCountClue, BlackCellClue or EdgeStateClue")
        puzzle = YajilinPuzzle([[None] * self.cols for _ in range(self.rows)], reserved_clue_cells=sites)
        cells = [c for c in puzzle.board.cells if c not in sites]
        edges = puzzle.loop_board.edges
        puzzle.set_solution_vars([puzzle.is_black[c] for c in cells] + [puzzle.edge_on[e] for e in edges])
        puzzle.add(at_least_one(puzzle.edge_on[e] for e in edges))
        for clue in clues:
            if isinstance(clue, ArrowCountClue):
                puzzle.grid[clue.cell.row][clue.cell.col] = (sites[clue.cell].direction, clue.count)
                puzzle.add(sum_expr(puzzle.is_black[c] for c in self.ray(sites[clue.cell])) == clue.count)
            elif isinstance(clue, BlackCellClue):
                puzzle.add(puzzle.is_black[clue.cell] == clue.black)
            else:
                puzzle.add(puzzle.edge_on[clue.edge] == clue.used)
        return puzzle

    def answer(self, solution: Solution, puzzle: YajilinPuzzle) -> YajilinAnswer:
        if ((puzzle.height, puzzle.width) != (self.rows, self.cols)
                or puzzle.clue_cells != {s.cell for s in self.arrow_sites}):
            raise ValueError("Source puzzle dimensions and reserved cells must match the recipe")
        return YajilinAnswer(
            frozenset(c for c in puzzle.board.cells
                      if c not in puzzle.clue_cells and solution.value(puzzle.is_black[c])),
            frozenset(e for e in puzzle.loop_board.edges if solution.value(puzzle.edge_on[e])),
        )

    def extract_clues(self, solution: Solution, puzzle: YajilinPuzzle) -> list[YajilinClue]:
        answer = self.answer(solution, puzzle)
        clues: list[YajilinClue] = []
        for kind in self.clue_kinds:
            if kind == "arrow":
                clues.extend(ArrowCountClue(s.cell, sum(c in answer.black_cells for c in self.ray(s)))
                             for s in self.arrow_sites)
            elif kind == "black":
                clues.extend(BlackCellClue(c, int(c in answer.black_cells)) for c in puzzle.board.cells
                             if c not in puzzle.clue_cells)
            else:
                clues.extend(EdgeStateClue(e, int(e in answer.loop_edges)) for e in puzzle.loop_board.edges)
        return clues
