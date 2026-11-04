class Symbolic:
    """Internal base for DSL objects that cannot be evaluated by Python."""

    def __bool__(self) -> bool:
        raise TypeError(
            "Puzzle DSL objects have no Python truth value; do not use if/and/or/not "
            "or chained comparisons. Add constraints separately, and use "
            "Solution.value() to read solved variables."
        )
