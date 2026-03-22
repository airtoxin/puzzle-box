import pytest

from puzzle import (
    MissingFeatureError,
    Puzzle,
    all_different,
    connected,
    polyomino,
    same_shape_across,
    different_shape_across,
    all_adjacent_different_shape,
    single_cycle,
    square_grid,
    enumerate_placements,
    exactly_one,
)
from puzzle.grid import Vertex, _make_edge


def test_all_different_requires_cell_vars():
    """AllDifferent fails without cell_vars, works with it."""
    # Create vars on a separate puzzle to get Var objects
    p_helper = Puzzle("helper")
    board = square_grid(3, 3)
    cv = p_helper.int_var_grid("cv", board.cells, 1, 9)

    # A fresh puzzle without cell_vars
    p = Puzzle("test")
    with pytest.raises(MissingFeatureError, match="cell_vars"):
        p.add(all_different(cv[c] for c in board.rows()[0]))

    # After defining cell_vars, it works
    p2 = Puzzle("test2")
    cv2 = p2.int_var_grid("cv", board.cells, 1, 9)
    p2.add(all_different(cv2[c] for c in board.rows()[0]))  # should not raise


def test_single_cycle_requires_edge_vars():
    p = Puzzle("test")
    board = square_grid(3, 3)

    # No edge_vars — should fail
    with pytest.raises(MissingFeatureError, match="edge_vars"):
        p.add(single_cycle(None, board))  # type: ignore[arg-type]


def test_connected_requires_cell_vars():
    p = Puzzle("test")
    board = square_grid(3, 3)

    # No cell_vars — should fail
    with pytest.raises(MissingFeatureError, match="cell_vars"):
        p.add(connected(board.cells, lambda c: None))  # type: ignore[arg-type]


def test_shape_across_requires_region_partition_and_shape_class():
    p = Puzzle("test")
    board = square_grid(2, 4)
    edge = _make_edge(Vertex(0, 2), Vertex(1, 2))

    D = polyomino("D", [(0, 0), (0, 1)], allow_rotate=True)
    pls = enumerate_placements(board, D)
    use = p.bool_var_map("use", pls)

    constraint = same_shape_across(edge, use, pls, board)

    # Missing region_partition and shape_class
    with pytest.raises(MissingFeatureError) as exc_info:
        p.add(constraint)
    assert "region_partition" in str(exc_info.value)
    assert "shape_class" in str(exc_info.value)


def test_shape_across_works_with_features():
    p = Puzzle("test")
    p.add_feature("region_partition")
    p.add_feature("shape_class")
    board = square_grid(2, 4)
    edge = _make_edge(Vertex(0, 2), Vertex(1, 2))

    D = polyomino("D", [(0, 0), (0, 1)], allow_rotate=True)
    pls = enumerate_placements(board, D)
    use = p.bool_var_map("use", pls)

    # Should not raise
    p.add(same_shape_across(edge, use, pls, board))


def test_different_shape_requires_features():
    p = Puzzle("test")
    board = square_grid(2, 4)
    edge = _make_edge(Vertex(0, 2), Vertex(1, 2))

    D = polyomino("D", [(0, 0), (0, 1)], allow_rotate=True)
    pls = enumerate_placements(board, D)
    use = p.bool_var_map("use", pls)

    with pytest.raises(MissingFeatureError, match="region_partition"):
        p.add(different_shape_across(edge, use, pls, board))


def test_all_adjacent_different_requires_features():
    p = Puzzle("test")
    board = square_grid(2, 4)

    D = polyomino("D", [(0, 0), (0, 1)], allow_rotate=True)
    pls = enumerate_placements(board, D)
    use = p.bool_var_map("use", pls)

    with pytest.raises(MissingFeatureError, match="region_partition"):
        p.add(all_adjacent_different_shape(use, pls, board))


def test_features_property():
    p = Puzzle("test")
    assert p.features == frozenset()

    board = square_grid(3, 3)
    p.int_var_grid("cv", board.cells, 1, 9)
    assert "cell_vars" in p.features

    p.bool_var_map("ev", board.edges)
    assert "edge_vars" in p.features

    p.add_feature("region_partition")
    assert "region_partition" in p.features


def test_error_message_format():
    p = Puzzle("test")
    board = square_grid(2, 4)

    D = polyomino("D", [(0, 0), (0, 1)], allow_rotate=True)
    pls = enumerate_placements(board, D)
    use = p.bool_var_map("use", pls)

    edge = _make_edge(Vertex(0, 2), Vertex(1, 2))
    try:
        p.add(same_shape_across(edge, use, pls, board))
        assert False, "Should have raised"
    except MissingFeatureError as e:
        msg = str(e)
        assert "ShapeAcrossConstraint cannot be used here" in msg
        assert "Missing features:" in msg
        assert "region_partition" in msg
        assert "shape_class" in msg
        assert "Hint:" in msg
