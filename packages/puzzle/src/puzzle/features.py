"""Feature definitions and validation for puzzle constraints."""

FEATURE_DESCRIPTIONS: dict[str, str] = {
    "cell_vars": "cell variables are defined",
    "edge_vars": "edge/boolean variables are defined",
    "region_partition": "cells are partitioned into non-overlapping regions",
    "shape_class": "each region has a named shape type",
}

FEATURE_HINTS: dict[str, str] = {
    "cell_vars": "Define cell variables with int_var_grid() or int_var_map().",
    "edge_vars": "Define edge variables with bool_var_map().",
    "region_partition": "Define a region partition via placement-based exact cover.",
    "shape_class": "Use polyomino placements with named piece types.",
}

# Maps constraint class name -> required features
CONSTRAINT_REQUIRES: dict[str, frozenset[str]] = {
    "AllDifferentConstraint": frozenset({"cell_vars"}),
    "BoolExpr": frozenset(),
    "LinearConstraint": frozenset(),
    "UniqueConstraint": frozenset(),
    "OneOfConstraint": frozenset(),
    "SingleCycleConstraint": frozenset({"edge_vars"}),
    "ConnectedConstraint": frozenset({"cell_vars"}),
    "ShapeAcrossConstraint": frozenset({"region_partition", "shape_class"}),
}


class MissingFeatureError(Exception):
    """Raised when a constraint requires features not available on the puzzle."""

    def __init__(self, constraint_name: str, missing: frozenset[str] | set[str]) -> None:
        lines = [f"{constraint_name} cannot be used here.", "", "Missing features:"]
        for f in sorted(missing):
            desc = FEATURE_DESCRIPTIONS.get(f, f)
            lines.append(f"  - {f}: {desc}")
        lines.append("")
        lines.append("Hint:")
        for f in sorted(missing):
            hint = FEATURE_HINTS.get(f, f"Provide the '{f}' feature.")
            lines.append(f"  {hint}")
        super().__init__("\n".join(lines))
        self.constraint_name = constraint_name
        self.missing = missing
