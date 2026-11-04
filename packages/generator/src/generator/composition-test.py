import importlib
from itertools import combinations, product
import json
from pathlib import Path
import subprocess
import sys

import pytest

from generator import generate, with_constraints
from puzzle import Cell, Edge, Vertex, at_least_one, non_touching, sum_expr, unique
from puzzle_defs import BlackCount, BlackCellClue, EdgeStateClue, NonTouchingBlack, ShadingRecipe, SlitherlinkRecipe, YajilinRecipe

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    demo = importlib.import_module("compose_recipe_constraints")


def _edges(rows, cols):
    # Independent rectangular vertex geometry, not SquareGrid.
    return tuple([Edge(Vertex(r, c), Vertex(r, c+1)) for r in range(rows) for c in range(cols-1)]
                 + [Edge(Vertex(r, c), Vertex(r+1, c)) for r in range(rows-1) for c in range(cols)])


def _cycle(loop):
    neighbors = {}
    for a, b in loop:
        neighbors.setdefault(a, set()).add(b)
        neighbors.setdefault(b, set()).add(a)
    if not neighbors or any(len(ns) != 2 for ns in neighbors.values()):
        return False
    seen, todo = set(), [next(iter(neighbors))]
    while todo:
        v = todo.pop()
        if v not in seen:
            seen.add(v)
            todo.extend(neighbors[v] - seen)
    return seen == set(neighbors)


def _loops(rows, cols, length):
    return {frozenset(es) for es in combinations(_edges(rows, cols), length) if _cycle(es)}


def _model_answers(puzzle, variables, read):
    answers = set()
    while (solution := puzzle.solve()) is not None:
        answer = read(solution, puzzle)
        assert answer not in answers, "Auxiliary assignments must not be counted as different answers"
        answers.add(answer)
        puzzle.add(at_least_one(v != solution.value(v) for v in variables))
    return answers


def _loop_answers(recipe):
    p = recipe.create_empty()
    return _model_answers(p, [p.edge_on[e] for e in p.board.edges], lambda s, q: frozenset(q.result(s)))


def test_same_count_component_has_real_effect_in_corner_and_center_edge_recipes():
    loop_base = SlitherlinkRecipe(1, 2)
    loop = with_constraints(loop_base, demo.selected_count(demo.corner_edges, 6))
    expected = _loops(2, 3, 6)
    assert len(expected) == 1
    assert _loop_answers(loop) == expected == _loop_answers(SlitherlinkRecipe(1, 2, loop_length=6))
    assert len(_loop_answers(loop_base)) == 3  # The wrapper did not mutate its base.

    coupled_base = YajilinRecipe(3, 4)
    coupled = with_constraints(coupled_base, demo.selected_count(demo.center_edges, 12))
    p = coupled.create_empty()
    variables = [p.is_black[c] for c in p.board.cells] + [p.edge_on[e] for e in p.loop_board.edges]
    actual = _model_answers(p, variables, lambda s, q: coupled_base.answer(s, q))
    # A length-12 simple cycle on these 12 vertices uses every cell, so coupling
    # forces no black cells. Enumerate all 6,188 edge subsets of that size.
    expected_coupled = _loops(3, 4, 12)
    assert len(expected_coupled) == 2
    assert {a.loop_edges for a in actual} == expected_coupled
    assert all(not a.black_cells for a in actual)

    # A concrete valid base answer of length 10 is excluded by the new component.
    walk = [(1, 1), (0, 1), (0, 2), (1, 2), (1, 3), (2, 3), (2, 2), (2, 1), (2, 0), (1, 0)]
    shorter = frozenset(Edge(min(Vertex(*a), Vertex(*b)), max(Vertex(*a), Vertex(*b)))
                        for a, b in zip(walk, walk[1:] + walk[:1]))
    assert _cycle(shorter) and len(shorter) == 10
    full = [EdgeStateClue(e, int(e in shorter)) for e in _edges(3, 4)]
    assert coupled_base.build_from_clues(full).solve() is not None
    assert coupled.build_from_clues(full).solve() is None


@pytest.mark.parametrize("seed", [0, 1])
def test_shading_generation_and_reduction_preserve_added_rules(seed):
    base = ShadingRecipe(2, 2, (NonTouchingBlack(),))
    recipe = with_constraints(base, demo.selected_count(demo.black_cells, 2))
    clues = generate(recipe, seed=seed)
    answers = [bits for bits in product((0, 1), repeat=4) if sum(bits) == 2
               and not any(bits[a] and bits[b] for a, b in ((0, 1), (0, 2), (1, 3), (2, 3)))]
    matches = lambda hints: [bits for bits in answers if all(bits[c.row*2+c.col] == v for c, v in hints)]
    assert len(matches(clues)) == 1
    assert all(len(matches(clues[:i]+clues[i+1:])) > 1 for i in range(len(clues)))
    puzzle = recipe.build_from_clues(clues)
    puzzle.add(unique())
    solution = puzzle.solve()
    assert solution is not None
    assert tuple(v for row in puzzle.result(solution) for v in row) == matches(clues)[0]


@pytest.mark.parametrize("seed", [0, 1])
def test_loop_generation_reapplies_rules_even_after_all_clues_are_removed(seed):
    recipe = with_constraints(SlitherlinkRecipe(1, 2), demo.selected_count(demo.corner_edges, 6))
    clues = generate(recipe, seed=seed)
    assert clues == []  # Without the added rule, the same clue set has 3 answers.
    puzzle = recipe.build_from_clues(clues)
    puzzle.add(unique())
    solution = puzzle.solve()
    assert solution is not None and frozenset(puzzle.result(solution)) in _loops(2, 3, 6)


@pytest.mark.parametrize("seed", [0, 1])
def test_coupled_generation_has_unique_irreducible_joint_answer(seed):
    base = YajilinRecipe(3, 4)
    recipe = with_constraints(base, demo.selected_count(demo.center_edges, 12))
    clues = generate(recipe, seed=seed)
    answers = _loops(3, 4, 12)

    def matches(hints):
        return [loop for loop in answers if all(
            clue.black == 0 if isinstance(clue, BlackCellClue)
            else isinstance(clue, EdgeStateClue) and clue.used == int(clue.edge in loop)
            for clue in hints)]

    assert len(matches(clues)) == 1
    assert all(len(matches(clues[:i]+clues[i+1:])) > 1 for i in range(len(clues)))
    puzzle = recipe.build_from_clues(clues)
    puzzle.add(unique())
    solution = puzzle.solve()
    assert solution is not None
    answer = base.answer(solution, puzzle)
    assert not answer.black_cells and answer.loop_edges == matches(clues)[0]


def test_nested_builders_use_fresh_puzzles_and_keep_order():
    seen = []

    def count(p):
        seen.append(("count", p))
        return [sum_expr(p.black[c] for c in p.board.cells) == 2]

    def separated(p):
        seen.append(("separated", p))
        return [non_touching(p.black, p.board.adjacent_cell_pairs())]

    base = ShadingRecipe(2, 2, ())
    recipe = with_constraints(with_constraints(base, count), separated)
    first, second = recipe.create_empty(), recipe.build_from_clues([])
    assert first is not second
    assert seen == [("count", first), ("separated", first), ("count", second), ("separated", second)]
    assert first.solve() is not None and second.solve() is not None


def test_foreign_model_bindings_are_rejected():
    base = ShadingRecipe(1, 1, ())
    foreign = base.create_empty()
    recipe = with_constraints(base, lambda p: [foreign.black[Cell(0, 0)] == 1])
    with pytest.raises(ValueError, match="same Puzzle"):
        recipe.create_empty()


def test_extra_witness_does_not_replace_the_bases_explicit_projection():
    def witness(p):
        p.bool_var_map("internal_witness", ["free"])
        return []

    recipe = with_constraints(ShadingRecipe(1, 1, (BlackCount(1),)), witness)
    assert generate(recipe, seed=0) == []
    p = recipe.build_from_clues([])
    p.add(unique())
    solution = p.solve()
    assert solution is not None and p.result(solution) == [[1]]


def test_incompatible_components_fail_without_changing_the_base():
    base = ShadingRecipe(1, 1, (BlackCount(1),))
    recipe = with_constraints(base, demo.selected_count(demo.black_cells, 0))
    assert recipe.create_empty().solve() is None
    with pytest.raises(RuntimeError, match="Failed to generate"):
        generate(recipe, seed=0)
    assert base.create_empty().solve() is not None


def test_example_reports_all_three_recipe_types_without_claiming_a_puzzle_format():
    result = subprocess.run([sys.executable, str(EXAMPLES / "compose_recipe_constraints.py")],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["format"] == "puzzle-box/constraint-composition-demo-v1"
    assert len(report["results"]) == 3
    assert all(r["unique"] and r["irreducible"] for r in report["results"])
