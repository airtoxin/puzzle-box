from collections.abc import Iterable
from itertools import product

import pytest

from generator import InitialCluesNotUniqueError, generate, reduce_clues, with_constraints
from puzzle import Cell, Constraint, non_touching, sum_expr, unique
from puzzle_defs import BlackCount, ShadingPuzzle, ShadingRecipe, SudokuPuzzle
from puzzle_defs.puzzles.shading import Clue


@pytest.mark.parametrize("value", [False, True, None])
@pytest.mark.parametrize("with_clues", [False, True])
def test_non_constraints_are_rejected_instead_of_silently_ignored(value, with_clues):
    recipe = with_constraints(ShadingRecipe(1, 1, (BlackCount(1),)), lambda p: [value])
    with pytest.raises(TypeError, match="DSL constraint"):
        if with_clues:
            recipe.build_from_clues([(Cell(0, 0), 1)])
        else:
            recipe.create_empty()


@pytest.mark.parametrize("with_clues", [False, True])
def test_uniqueness_query_is_not_accepted_as_a_base_rule(with_clues):
    recipe = with_constraints(ShadingRecipe(1, 1, ()), lambda p: [unique()])
    with pytest.raises(ValueError, match="unique"):
        if with_clues:
            recipe.build_from_clues([(Cell(0, 0), 1)])
        else:
            recipe.create_empty()


@pytest.mark.parametrize("target", [0, 1])
def test_constant_dsl_conditions_keep_their_mathematical_meaning(target):
    # A DSL constant condition is valid, unlike a stray Python bool.
    recipe = with_constraints(ShadingRecipe(1, 1, ()), lambda p: [sum_expr([]) == target])
    assert (recipe.create_empty().solve() is not None) == (target == 0)


def test_a_constraint_object_cannot_be_used_as_a_builder():
    with pytest.raises(ValueError, match="callable"):
        with_constraints(ShadingRecipe(1, 1, ()), unique())  # type: ignore[arg-type]


def test_class_recipe_accepts_generator_builders_and_keeps_extraction_and_clues():
    def fix_corner(p: SudokuPuzzle) -> Iterable[Constraint]:
        yield p.cell_value[Cell(0, 0)] == 1

    recipe = with_constraints(SudokuPuzzle, fix_corner)
    source = recipe.create_empty()
    solution = source.solve(seed=0)
    assert solution is not None
    answer = source.result(solution)
    assert answer[0][0] == 1
    assert all(sorted(row) == list(range(1, 10)) for row in answer)
    assert all(sorted(answer[r][c] for r in range(9)) == list(range(1, 10)) for c in range(9))
    assert all(sorted(answer[r+dr][c+dc] for dr in range(3) for dc in range(3)) == list(range(1, 10))
               for r in range(0, 9, 3) for c in range(0, 9, 3))

    clues = recipe.extract_clues(solution, source)
    assert clues == SudokuPuzzle.extract_clues(solution, source)
    assert len(clues) == 81
    restored = recipe.build_from_clues([clue for clue in clues if clue[0] != Cell(0, 0)])
    restored.add(unique())
    restored_solution = restored.solve()
    assert restored_solution is not None and restored.result(restored_solution) == answer
    conflicting = [(Cell(0, 0), 2)]
    assert recipe.build_from_clues(conflicting).solve() is None
    assert SudokuPuzzle.build_from_clues(conflicting).solve() is not None


def test_empty_composition_preserves_generation_and_duplicate_clue_semantics():
    base = ShadingRecipe(1, 2, (BlackCount(1),))
    recipe = with_constraints(base)
    assert generate(recipe, seed=7) == generate(base, seed=7)
    clues: list[Clue] = [(Cell(0, 0), 1), (Cell(0, 0), 1)]
    original = clues.copy()
    assert reduce_clues(recipe, clues, seed=7) == [clues[0]]
    assert clues == original


def test_fixed_additional_rule_does_not_hide_insufficient_initial_hints():
    def count(p: ShadingPuzzle) -> Iterable[Constraint]:
        return [sum_expr(p.black[c] for c in p.board.cells) == 1]

    # A row count cannot distinguish the independent bit boards (0,1) and (1,0).
    base = ShadingRecipe(1, 2, (), clue_kinds=("row-count",))
    assert [bits for bits in product((0, 1), repeat=2) if sum(bits) == 1] == [(0, 1), (1, 0)]
    with pytest.raises(InitialCluesNotUniqueError):
        generate(with_constraints(base, count), seed=0)


@pytest.mark.parametrize("reverse,repeat", [(False, False), (True, False), (False, True)])
def test_constraint_conjunction_order_and_repetition_match_all_bit_boards(reverse, repeat):
    def count(p: ShadingPuzzle) -> Iterable[Constraint]:
        return [sum_expr(p.black[c] for c in p.board.cells) == 2]

    def separated(p: ShadingPuzzle) -> Iterable[Constraint]:
        return [non_touching(p.black, p.board.adjacent_cell_pairs())]

    builders = [count, separated]
    if reverse:
        builders.reverse()
    if repeat:
        builders += builders
    recipe = with_constraints(ShadingRecipe(2, 2, ()), *builders)
    for bits in product((0, 1), repeat=4):
        expected = sum(bits) == 2 and not any(bits[a] and bits[b] for a, b in ((0, 1), (0, 2), (1, 3), (2, 3)))
        clues = [(Cell(i//2, i%2), bit) for i, bit in enumerate(bits)]
        assert (recipe.build_from_clues(clues).solve() is not None) == expected
