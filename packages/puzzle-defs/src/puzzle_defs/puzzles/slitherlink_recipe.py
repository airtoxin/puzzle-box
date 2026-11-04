"""A fixed Slitherlink recipe with cell-count and explicit edge-state clues."""

from dataclasses import dataclass
from typing import ClassVar, Literal, Sequence

from puzzle import Cell, Edge, Solution, Vertex, at_least_one, sum_expr
from puzzle_defs.puzzles.slitherlink import SlitherlinkPuzzle
from puzzle_defs.ui import ClueUi, RuleUi, UiChannel, UiParameter, UiRequirements

LOOP_UI = UiRequirements(channels=(UiChannel("answer", "binary-edges"),), max_cells=4)


def _coordinate(value: object) -> bool:
    return type(value) is int and value >= 0


@dataclass(frozen=True)
class CellEdgeCountClue:
    ui: ClassVar[ClueUi] = ClueUi("cell-count", "セルを囲む辺の数",
        UiRequirements(channels=(UiChannel("cell-counts", "cell-edge-counts"),), max_cells=4))
    cell: Cell
    count: int

    def __post_init__(self) -> None:
        if not isinstance(self.cell, Cell) or not all(_coordinate(v) for v in self.cell):
            raise ValueError("Cell coordinates must be nonnegative integers")
        if type(self.count) is not int or not 0 <= self.count <= 4:
            raise ValueError("A cell edge count must be an integer from 0 to 4")


@dataclass(frozen=True)
class EdgeStateClue:
    ui: ClassVar[ClueUi] = ClueUi("edge", "線の有無を固定するヒント",
        UiRequirements(channels=(UiChannel("edge-givens", "edge-givens"),), max_cells=4))
    edge: Edge
    used: int

    def __post_init__(self) -> None:
        if (not isinstance(self.edge, Edge)
                or any(not isinstance(v, Vertex) or not all(_coordinate(n) for n in v) for v in self.edge)):
            raise ValueError("An edge needs two vertices with nonnegative integer coordinates")
        a, b = self.edge
        if abs(a.row - b.row) + abs(a.col - b.col) != 1:
            raise ValueError("An edge must join orthogonally adjacent vertices")
        if type(self.used) is not int or self.used not in (0, 1):
            raise ValueError("An edge state must be 0 (unused) or 1 (used)")
        object.__setattr__(self, "edge", Edge(min(a, b), max(a, b)))


LoopClue = CellEdgeCountClue | EdgeStateClue
LoopClueKind = Literal["cell-count", "edge"]
LOOP_CLUE_KINDS: tuple[LoopClueKind, ...] = ("cell-count", "edge")


@dataclass(frozen=True)
class SlitherlinkRecipe:
    """Keep the grid, nonempty loop and optional length fixed during reduction.

    Edge clues fix the full visible answer when counts alone are ambiguous.
    This adapter deliberately has no shared rule interface with shading recipes.
    """

    ui: ClassVar[UiRequirements] = LOOP_UI
    rule_ui: ClassVar[tuple[RuleUi, ...]] = (
        RuleUi("single-loop", "空でない1本のループ", "交差や分岐のない1本の輪を描きます。必須です。",
               requirements=LOOP_UI, required=True),
        RuleUi("loop-length", "ループの長さ", "使用する辺の本数を指定します。",
               (UiParameter("length", "辺の本数", "integer", 8, maximum="edges"),), LOOP_UI),
    )

    rows: int
    cols: int
    loop_length: int | None = None
    clue_kinds: tuple[LoopClueKind, ...] = LOOP_CLUE_KINDS

    def __post_init__(self) -> None:
        if not _coordinate(self.rows) or not _coordinate(self.cols) or not self.rows or not self.cols:
            raise ValueError("Rows and columns must be positive integers")
        edge_count = 2 * self.rows * self.cols + self.rows + self.cols
        if self.loop_length is not None and (
            not _coordinate(self.loop_length) or self.loop_length > edge_count
        ):
            raise ValueError("Loop length must be an integer between 0 and the number of grid edges")
        kinds = tuple(self.clue_kinds)
        if any(k not in LOOP_CLUE_KINDS for k in kinds) or len(set(kinds)) != len(kinds):
            raise ValueError("Clue kinds must be distinct cell-count or edge values")
        object.__setattr__(self, "clue_kinds", kinds)

    def create_empty(self) -> SlitherlinkPuzzle:
        return self.build_from_clues([])

    def build_from_clues(self, clues: Sequence[LoopClue]) -> SlitherlinkPuzzle:
        for clue in clues:
            if isinstance(clue, CellEdgeCountClue):
                if clue.cell.row >= self.rows or clue.cell.col >= self.cols:
                    raise ValueError("Cell clue is outside the board")
            elif isinstance(clue, EdgeStateClue):
                if any(v.row > self.rows or v.col > self.cols for v in clue.edge):
                    raise ValueError("Edge clue is outside the board")
            else:
                raise ValueError("Expected a CellEdgeCountClue or EdgeStateClue")
        puzzle = SlitherlinkPuzzle.create_empty(self.rows, self.cols)
        edges = puzzle.board.edges
        puzzle.set_solution_vars(puzzle.edge_on[e] for e in edges)
        # The existing DSL allows an empty cycle; this recipe explicitly does not.
        puzzle.add(at_least_one(puzzle.edge_on[e] for e in edges))
        if self.loop_length is not None:
            puzzle.add(sum_expr(puzzle.edge_on[e] for e in edges) == self.loop_length)
        for clue in clues:
            if isinstance(clue, CellEdgeCountClue):
                # Keep grid metadata useful, but add every occurrence as a
                # constraint so conflicting duplicates remain contradictory.
                puzzle.grid[clue.cell.row][clue.cell.col] = clue.count
                puzzle.add(sum_expr(puzzle.edge_on[e] for e in puzzle.board.edges_around(clue.cell)) == clue.count)
            else:
                puzzle.add(puzzle.edge_on[clue.edge] == clue.used)
        return puzzle

    def extract_clues(self, solution: Solution, puzzle: SlitherlinkPuzzle) -> list[LoopClue]:
        if (puzzle.rows, puzzle.cols) != (self.rows, self.cols):
            raise ValueError("Source puzzle dimensions must match the recipe")
        clues: list[LoopClue] = []
        for kind in self.clue_kinds:
            if kind == "cell-count":
                clues.extend(CellEdgeCountClue(cell, count)
                             for cell, count in SlitherlinkPuzzle.extract_clues(solution, puzzle))
            else:
                clues.extend(EdgeStateClue(e, solution.value(puzzle.edge_on[e])) for e in puzzle.board.edges)
        return clues
