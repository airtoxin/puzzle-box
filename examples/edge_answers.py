"""Text input for edges of a rectangular vertex grid (corners or cell centers)."""

from typing import Mapping

from puzzle import Edge, Vertex


def edge_rows(vertex_rows: int, vertex_cols: int) -> list[list[Edge]]:
    """Alternate horizontal and vertical rows in displayed top-to-bottom order."""
    result = []
    for r in range(vertex_rows):
        result.append([Edge(Vertex(r, c), Vertex(r, c + 1)) for c in range(vertex_cols - 1)])
        if r < vertex_rows - 1:
            result.append([Edge(Vertex(r, c), Vertex(r + 1, c)) for c in range(vertex_cols)])
    return result


def parse_edge_answer(text: str, vertex_rows: int, vertex_cols: int) -> set[Edge]:
    parts = ["".join(row.split()) for row in text.strip().split("/")]
    rows = edge_rows(vertex_rows, vertex_cols)
    if len(parts) != len(rows) or any(len(part) != len(edges) for part, edges in zip(parts, rows)):
        raise ValueError(f"Answer needs {2 * vertex_rows - 1} edge rows separated by '/', "
                         f"alternating {vertex_cols - 1} horizontal and {vertex_cols} vertical edges")
    if any(value not in "01" for part in parts for value in part):
        raise ValueError("Fill every edge with 1 (used) or 0 (unused); '?' is not a complete answer")
    return {edge for part, edges in zip(parts, rows) for value, edge in zip(part, edges) if value == "1"}


def edge_template(vertex_rows: int, vertex_cols: int, states: Mapping[Edge, int]) -> str:
    return "/".join("".join(str(states.get(e, "?")) for e in row)
                    for row in edge_rows(vertex_rows, vertex_cols))
