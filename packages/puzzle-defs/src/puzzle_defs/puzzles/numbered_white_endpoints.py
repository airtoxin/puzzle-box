"""Validated composition of endpoint positions and straight visibility."""

from puzzle_defs.marker_layout import MarkerGrid, marker_grid
from puzzle_defs.number_layout import NumberGrid, number_grid
from puzzle_defs.puzzles.white_endpoint_markers import WhiteEndpointMarkers
from puzzle_defs.puzzles.white_visibility import WhiteVisibilityCounts


def numbered_white_endpoints(markers: MarkerGrid, lengths: NumberGrid) -> tuple[WhiteEndpointMarkers, WhiteVisibilityCounts]:
    """Return existing rules for circles and their optional straight lengths.

    A positive length belongs to a circle and includes that circle's cell.
    Zero means an unnumbered circle or no circle, as decided by markers.
    This helper checks classic placement; generic rule composition can still
    place independent visibility numbers elsewhere as a different hybrid.
    """
    circles = marker_grid(markers)
    counts = number_grid(lengths, rows=len(circles), cols=len(circles[0]))
    if any(n > 0 and circles[r][c] == 0 for r, row in enumerate(counts) for c, n in enumerate(row)):
        raise ValueError("Endpoint lengths may only be placed on marked circles")
    return WhiteEndpointMarkers(circles), WhiteVisibilityCounts(counts)
