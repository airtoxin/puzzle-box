from solvers.sudoku import solve as solve_sudoku
from solvers.slitherlink import solve as solve_slitherlink
from solvers.nurikabe import solve as solve_nurikabe
from solvers.yajilin import solve as solve_yajilin
from solvers.tiling import solve as solve_tiling
from solvers.shikaku import solve as solve_shikaku
from solvers.hitori import solve as solve_hitori
from solvers.tents import solve as solve_tents

__all__ = [
    "solve_sudoku",
    "solve_slitherlink",
    "solve_nurikabe",
    "solve_yajilin",
    "solve_tiling",
    "solve_shikaku",
    "solve_hitori",
    "solve_tents",
]
