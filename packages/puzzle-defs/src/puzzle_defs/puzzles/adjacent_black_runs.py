"""Tapa's local cyclic run clues, separate from global wall constraints."""

from dataclasses import dataclass
from functools import lru_cache
from typing import ClassVar

from puzzle import Cell, Puzzle, SquareGrid, VarMap, one_of, sum_expr
from puzzle_defs.run_clue_layout import DEFAULT_BLACK_RUN_CLUES, RunClue, RunClueGrid, run_clue_grid
from puzzle_defs.ui import RuleUi, UiChannel, UiParameter, UiRequirements

# Fixed eight positions: outside cells are white gaps, never compressed away.
OFFSETS = ((-1,0),(-1,1),(0,1),(1,1),(1,0),(1,-1),(0,-1),(-1,-1))


@lru_cache(maxsize=32)
def _matching_masks(clue: RunClue) -> tuple[int, ...]:
    accepted = []
    for mask in range(256):
        if mask == 255:
            runs = (8,)
        elif mask == 0:
            runs = (0,)
        else:
            lengths = []
            for i in range(8):
                if mask & (1 << i) and not mask & (1 << ((i-1)%8)):
                    length = 1
                    while mask & (1 << ((i+length)%8)):
                        length += 1
                    lengths.append(length)
            runs = tuple(sorted(lengths))
        if runs == clue:
            accepted.append(mask)
    return tuple(accepted)


@dataclass(frozen=True)
class AdjacentBlackRuns:
    """Clue cells are white; their cyclic eight-neighbor black runs match.

    Run order is irrelevant, repeated lengths matter, None is absent, and
    (0,) forbids neighboring black. Global connectivity/2x2 rules are separate.
    """

    ui: ClassVar[RuleUi] = RuleUi(
        "adjacent-black-runs", "周囲8マスの黒い連続長を指定",
        "ヒントマスは白。周囲8マスを一周する黒い連続区間の長さを指定します。順序は不問、0は黒なし、. はヒントなしです。",
        (UiParameter("run_clues", "黒の連続長（複数は1,2、なしは.、黒0個は0）", "run-clue-grid", DEFAULT_BLACK_RUN_CLUES),),
        UiRequirements(channels=(UiChannel("answer", "binary-cells"), UiChannel("black-runs", "cell-black-runs"))),
    )
    run_clues: RunClueGrid

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_clues", run_clue_grid(self.run_clues))

    def apply(self, puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None:
        run_clue_grid(self.run_clues, rows=len(board.rows()), cols=len(board.cols()))
        cells = set(board.cells)
        for origin in board.cells:
            clue = self.run_clues[origin.row][origin.col]
            if clue is None:
                continue
            puzzle.add(black[origin] == 0)
            ring = [Cell(origin.row+dr, origin.col+dc) for dr,dc in OFFSETS]
            allowed = []
            for mask in _matching_masks(clue):
                if any(mask & (1 << i) for i,c in enumerate(ring) if c not in cells):
                    continue
                mismatch = [~black[c] if mask & (1 << i) else black[c]
                            for i,c in enumerate(ring) if c in cells]
                allowed.append(sum_expr(mismatch) == 0)
            # Complete assignments are disjoint, so exactly one matching mask
            # is equivalent to accepting this clue (including impossible edges).
            puzzle.add(one_of(*allowed))
