"""Default orthogonal and opt-in eight-neighbor connectivity."""

from itertools import product

import pytest

from puzzle import Cell, ConnectedConstraint, Puzzle, SquareGrid, at_least_one, connected, unique


def closure_reference(cells,selected,diagonal):
    # Transitive closure of an explicit distance matrix, independently of
    # parent/order witnesses and the finite checker used by shading recipes.
    active = [c for c in cells if c in selected]
    reachable = {(a,b) for a in active for b in active
                 if a == b or (max(abs(a.row-b.row),abs(a.col-b.col)) if diagonal
                               else abs(a.row-b.row)+abs(a.col-b.col)) == 1}
    for middle in active:
        reachable |= {(a,b) for a in active for b in active if (a,middle) in reachable and (middle,b) in reachable}
    return all((a,b) in reachable for a in active for b in active)


@pytest.mark.parametrize("diagonal", [False,True])
def test_all_two_by_three_assignments_match_transitive_closure(diagonal):
    cells=SquareGrid(2,3).cells
    p=Puzzle("connectivity")
    active=p.int_var_map("active",cells,0,1)
    p.add(connected(cells,lambda c: active[c],diagonal=diagonal))
    expected={bits for bits in product((0,1),repeat=len(cells))
              if closure_reference(cells,{c for c,b in zip(cells,bits) if b},diagonal)}
    actual=set()
    while (solution:=p.solve(seed=0)) is not None:
        bits=tuple(solution.value(active[c]) for c in cells)
        assert bits not in actual
        actual.add(bits)
        p.add(at_least_one(active[c] != solution.value(active[c]) for c in cells))
    assert actual == expected


def test_default_and_direct_legacy_constructor_still_require_edge_connections():
    cells=[Cell(0,0),Cell(1,1)]
    for constructor in [lambda v: connected(cells,lambda c:v[c]),
                        lambda v: ConnectedConstraint(cells,{c:v[c] for c in cells})]:
        p=Puzzle("legacy")
        v=p.int_var_map("v",cells,1,1)
        constraint=constructor(v)
        assert constraint.diagonal is False
        p.add(constraint)
        assert p.solve() is None
    p=Puzzle("corners")
    v=p.int_var_map("v",cells,1,1)
    p.add(connected(cells,lambda c:v[c],diagonal=True))
    p.add(unique())
    assert p.solve() is not None  # Internal connection witnesses never count.


@pytest.mark.parametrize("cells,expected", [([],True),([Cell(0,0)],True),
    ([Cell(0,0),Cell(1,1),Cell(0,2)],True),([Cell(0,0),Cell(2,2)],False)])
def test_only_supplied_cells_can_connect_and_empty_is_allowed(cells,expected):
    p=Puzzle("subset")
    v=p.int_var_map("v",cells,1,1)
    p.add(connected(cells,lambda c:v[c],diagonal=True))
    assert (p.solve() is not None) == expected


@pytest.mark.parametrize("bad", [0,1,None,"true"])
def test_boolean_option_is_strict_on_factory_and_direct_constraint(bad):
    with pytest.raises(ValueError,match="boolean"):
        connected([],lambda c:pytest.fail("Empty input has no predicate calls"),diagonal=bad)
    with pytest.raises(ValueError,match="boolean"): ConnectedConstraint([],{},bad)
