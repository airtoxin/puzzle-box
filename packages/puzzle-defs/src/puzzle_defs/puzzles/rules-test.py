import pytest

from puzzle_defs import (
    NurikabePuzzle, ShikakuPuzzle, TentsPuzzle, TilingPuzzle, YajilinPuzzle,
    polyomino,
)


def test_nurikabe_separates_distinct_islands():
    assert NurikabePuzzle([[1, 1]]).solve() is None
    assert NurikabePuzzle([[2, None, 1]]).solve() is None


def test_nurikabe_allows_islands_separated_by_sea():
    p = NurikabePuzzle([[1, None, 1]])
    solution = p.solve()
    assert solution is not None
    assert p.result(solution) == [[1, 0, 2]]


@pytest.mark.parametrize("grid", [[[None]], [[1, None]]])
def test_shikaku_infeasibility_is_in_the_model(grid: list[list[int | None]]):
    p = ShikakuPuzzle(grid)
    assert p.solve() is None


def test_tiling_without_placements_is_infeasible():
    assert TilingPuzzle(1, 1, []).solve() is None


def test_tiling_with_an_uncovered_cell_is_infeasible():
    horizontal = polyomino("D", [(0, 0), (0, 1)], allow_rotate=False)
    from puzzle import Cell

    # The top row can be covered; the isolated bottom-left cell cannot.
    p = TilingPuzzle(2, 2, [horizontal], board_cells={Cell(0, 0), Cell(0, 1), Cell(1, 0)})
    assert p.solve() is None


def test_yajilin_empty_arrow_ray_with_positive_count_is_infeasible():
    p = YajilinPuzzle([
        [("up", 1), None, None],
        [None, None, None],
        [None, None, None],
    ])
    assert p.solve() is None


def test_yajilin_empty_arrow_ray_with_zero_count_is_valid():
    p = YajilinPuzzle([
        [("up", 0), None, None],
        [None, None, None],
        [None, None, None],
    ])
    assert p.solve() is not None


@pytest.mark.parametrize("count", [1, -1])
def test_tents_enforces_counts_in_tree_only_columns(count: int):
    p = TentsPuzzle([list("T.")], row_counts=[1], col_counts=[count, 1])
    assert p.solve() is None


@pytest.mark.parametrize("count", [1, -1])
def test_tents_enforces_counts_in_tree_only_rows(count: int):
    p = TentsPuzzle([["T"], ["."]], row_counts=[count, 1], col_counts=[1])
    assert p.solve() is None


def test_tents_accepts_zero_count_for_tree_only_column():
    p = TentsPuzzle([list("T.")], row_counts=[1], col_counts=[0, 1])
    solution = p.solve()
    assert solution is not None
    assert p.result(solution) == [list("TA")]
