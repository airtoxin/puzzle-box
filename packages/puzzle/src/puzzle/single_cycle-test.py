"""Focused tests for the single_cycle constraint.

Tests use direct edge on/off constraints (not Slitherlink clues)
to precisely control which configurations are accepted or rejected.
"""

from puzzle import Puzzle, one_of, single_cycle, square_grid, sum_expr
from puzzle.grid import Edge, Vertex, _make_edge


def _edges_of_loop(vertices: list[tuple[int, int]]) -> set[Edge]:
    """Given a list of (row, col) forming a loop, return the edge set."""
    edges = set()
    for i in range(len(vertices)):
        a = Vertex(*vertices[i])
        b = Vertex(*vertices[(i + 1) % len(vertices)])
        edges.add(_make_edge(a, b))
    return edges


def _setup_with_forced_edges(
    rows: int, cols: int, on_edges: set[Edge]
) -> tuple:
    """Create a puzzle with single_cycle + degree constraints,
    forcing specific edges on/off."""
    p = Puzzle("test")
    board = square_grid(rows, cols)
    edge_on = p.bool_var_map("edge_on", board.edges)

    for v in board.vertices:
        deg = sum_expr(edge_on[e] for e in board.edges_incident(v))
        p.add(one_of(deg == 0, deg == 2))

    p.add(single_cycle(edge_on, board))

    # Force edges
    for e in board.edges:
        if e in on_edges:
            p.add(edge_on[e] == 1)
        else:
            p.add(edge_on[e] == 0)

    return p, board, edge_on


def test_single_loop_accepted():
    """A single rectangular loop should be accepted.

    (0,0)─(0,1)
      │       │
    (1,0)─(1,1)
    """
    loop = _edges_of_loop([(0, 0), (0, 1), (1, 1), (1, 0)])
    p, board, edge_on = _setup_with_forced_edges(2, 2, loop)
    assert p.solve() is not None


def test_two_disjoint_loops_rejected():
    """Two separate loops must be rejected by single_cycle.

    On a 4x2 grid:
    Loop 1: (0,0)-(0,1)-(1,1)-(1,0) (top-left cell)
    Loop 2: (2,0)-(2,1)-(3,1)-(3,0) (bottom-left cell)
    """
    loop1 = _edges_of_loop([(0, 0), (0, 1), (1, 1), (1, 0)])
    loop2 = _edges_of_loop([(2, 0), (2, 1), (3, 1), (3, 0)])
    on_edges = loop1 | loop2
    p, board, edge_on = _setup_with_forced_edges(4, 2, on_edges)
    assert p.solve() is None


def test_two_disjoint_loops_rejected_horizontal():
    """Two separate loops side by side must be rejected.

    On a 2x4 grid:
    Loop 1: (0,0)-(0,1)-(1,1)-(1,0)
    Loop 2: (0,2)-(0,3)-(1,3)-(1,2)
    """
    loop1 = _edges_of_loop([(0, 0), (0, 1), (1, 1), (1, 0)])
    loop2 = _edges_of_loop([(0, 2), (0, 3), (1, 3), (1, 2)])
    on_edges = loop1 | loop2
    p, board, edge_on = _setup_with_forced_edges(2, 4, on_edges)
    assert p.solve() is None


def test_large_single_loop_accepted():
    """An L-shaped single loop on a 3x3 grid should be accepted.

    (0,0)─(0,1)─(0,2)─(0,3)
      │                   │
    (1,0)  (1,1)─(1,2)─(1,3)
      │       │
    (2,0)─(2,1)
    """
    loop = _edges_of_loop([
        (0, 0), (0, 1), (0, 2), (0, 3),
        (1, 3), (1, 2), (1, 1),
        (2, 1), (2, 0),
        (1, 0),
    ])
    p, board, edge_on = _setup_with_forced_edges(3, 3, loop)
    assert p.solve() is not None


def test_outer_boundary_loop_accepted():
    """The full outer boundary of a 3x3 grid is a valid single cycle."""
    loop = _edges_of_loop([
        (0, 0), (0, 1), (0, 2), (0, 3),
        (1, 3), (2, 3), (3, 3),
        (3, 2), (3, 1), (3, 0),
        (2, 0), (1, 0),
    ])
    p, board, edge_on = _setup_with_forced_edges(3, 3, loop)
    assert p.solve() is not None


def test_all_edges_off_accepted():
    """No edges at all — trivially a single (empty) cycle."""
    p, board, edge_on = _setup_with_forced_edges(2, 2, set())
    assert p.solve() is not None


def test_single_edge_rejected():
    """A single edge is not a cycle — degree constraint violation."""
    e = _make_edge(Vertex(0, 0), Vertex(0, 1))
    p, board, edge_on = _setup_with_forced_edges(2, 2, {e})
    assert p.solve() is None


def test_open_path_rejected():
    """An open path (not closed) is rejected — vertices have odd degree.

    (0,0)─(0,1)─(0,2)  (not a loop: endpoints have degree 1)
    """
    e1 = _make_edge(Vertex(0, 0), Vertex(0, 1))
    e2 = _make_edge(Vertex(0, 1), Vertex(0, 2))
    p, board, edge_on = _setup_with_forced_edges(2, 2, {e1, e2})
    assert p.solve() is None


def test_minimal_loop_3_vertices_impossible():
    """On a grid, a triangle (3-vertex cycle) is impossible
    because grid edges only connect adjacent vertices."""
    # Try a "triangle" by forcing 3 edges that don't form a cycle
    e1 = _make_edge(Vertex(0, 0), Vertex(0, 1))
    e2 = _make_edge(Vertex(0, 1), Vertex(1, 1))
    e3 = _make_edge(Vertex(0, 0), Vertex(1, 0))
    # These 3 edges form a path, not a loop (missing (1,0)-(1,1))
    p, board, edge_on = _setup_with_forced_edges(2, 2, {e1, e2, e3})
    assert p.solve() is None


def test_without_single_cycle_allows_two_loops():
    """Verify that without single_cycle, two disjoint loops ARE feasible.

    This confirms single_cycle is actually doing its job.
    """
    loop1 = _edges_of_loop([(0, 0), (0, 1), (1, 1), (1, 0)])
    loop2 = _edges_of_loop([(2, 0), (2, 1), (3, 1), (3, 0)])
    on_edges = loop1 | loop2

    p = Puzzle("no_single_cycle")
    board = square_grid(4, 2)
    edge_on = p.bool_var_map("edge_on", board.edges)

    for v in board.vertices:
        deg = sum_expr(edge_on[e] for e in board.edges_incident(v))
        p.add(one_of(deg == 0, deg == 2))

    # NO single_cycle constraint

    for e in board.edges:
        if e in on_edges:
            p.add(edge_on[e] == 1)
        else:
            p.add(edge_on[e] == 0)

    assert p.solve() is not None, "Two loops should be feasible without single_cycle"


def test_touching_loops_rejected():
    """Two loops sharing a vertex but no edge — still two separate cycles.

    On a 2x3 grid:
    Loop 1: (0,0)-(0,1)-(1,1)-(1,0)
    Loop 2: (1,1)-(1,2)-(2,2)-(2,1)
    Vertex (1,1) has degree 4, which is rejected by degree constraints.
    """
    loop1 = _edges_of_loop([(0, 0), (0, 1), (1, 1), (1, 0)])
    loop2 = _edges_of_loop([(1, 1), (1, 2), (2, 2), (2, 1)])
    on_edges = loop1 | loop2
    p, board, edge_on = _setup_with_forced_edges(2, 3, on_edges)
    assert p.solve() is None


def test_larger_grid_two_loops_rejected():
    """Two small loops on a 5x5 grid — far apart.

    Loop 1: top-left corner
    Loop 2: bottom-right corner
    """
    loop1 = _edges_of_loop([(0, 0), (0, 1), (1, 1), (1, 0)])
    loop2 = _edges_of_loop([(4, 4), (4, 5), (5, 5), (5, 4)])
    on_edges = loop1 | loop2
    p, board, edge_on = _setup_with_forced_edges(5, 5, on_edges)
    assert p.solve() is None


def test_single_cycle_free_solve():
    """Let the solver find a valid single cycle on a 3x3 grid,
    with only the constraint that exactly 8 edges are on."""
    p = Puzzle("free")
    board = square_grid(3, 3)
    edge_on = p.bool_var_map("edge_on", board.edges)

    for v in board.vertices:
        deg = sum_expr(edge_on[e] for e in board.edges_incident(v))
        p.add(one_of(deg == 0, deg == 2))

    p.add(single_cycle(edge_on, board))

    # Require exactly 8 edges on (e.g., a 2x2 rectangle somewhere)
    p.add(sum_expr(edge_on[e] for e in board.edges) == 8)

    solution = p.solve()
    assert solution is not None

    # Verify it's a valid cycle
    on_edges = [e for e in board.edges if solution.value(edge_on[e])]
    assert len(on_edges) == 8

    # Verify connectivity: BFS from any on-vertex
    from collections import deque

    adj: dict = {}
    for e in on_edges:
        adj.setdefault(e.v1, []).append(e.v2)
        adj.setdefault(e.v2, []).append(e.v1)

    start = next(iter(adj))
    visited = set()
    queue = deque([start])
    while queue:
        v = queue.popleft()
        if v in visited:
            continue
        visited.add(v)
        for u in adj[v]:
            if u not in visited:
                queue.append(u)

    assert visited == set(adj.keys()), "Edges do not form a single connected cycle"
