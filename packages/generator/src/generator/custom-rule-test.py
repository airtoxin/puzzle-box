import importlib
from itertools import product
import json
from pathlib import Path
import subprocess
import sys

import pytest

from generator import generate
from puzzle import Cell, sum_expr, unique
from puzzle_defs import NonTouchingBlack, ShadingRecipe

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    demo = importlib.import_module("custom_shading_rule")


def _valid(bits):
    return (1 <= sum(bits) <= 2
            and all(not (bits[a] and bits[b]) for a, b in [(0, 1), (0, 2), (1, 3), (2, 3)]))


def test_custom_rule_combination_matches_all_six_valid_boards_independently():
    recipe = demo.make_recipe()
    expected = [bits for bits in product((0, 1), repeat=4) if _valid(bits)]
    assert len(expected) == 6
    for bits in product((0, 1), repeat=4):
        clues = [(Cell(i // 2, i % 2), bit) for i, bit in enumerate(bits)]
        assert (recipe.build_from_clues(clues).solve() is not None) == (bits in expected)


def test_accidentally_chaining_custom_rule_bounds_fails_instead_of_accepting_all_white():
    class BrokenRange:
        def apply(self, puzzle, board, black):
            total = sum_expr(black[c] for c in board.cells)
            puzzle.add(1 <= total <= 2)
    recipe = ShadingRecipe(2, 2, (NonTouchingBlack(), BrokenRange()))
    with pytest.raises(TypeError, match="Python truth value"):
        generate(recipe, seed=0)


def test_custom_rule_generation_is_unique_and_irreducible_against_raw_boards():
    recipe = demo.make_recipe()
    clues = generate(recipe, seed=0)
    def matches(hints):
        return [bits for bits in product((0, 1), repeat=4) if _valid(bits)
                and all(bits[c.row * 2 + c.col] == value for c, value in hints)]
    assert len(matches(clues)) == 1
    assert all(len(matches(clues[:i] + clues[i+1:])) > 1 for i in range(len(clues)))
    puzzle = recipe.build_from_clues(clues)
    puzzle.add(unique())
    answer = puzzle.solve()
    assert answer is not None
    assert tuple(v for row in puzzle.result(answer) for v in row) == matches(clues)[0]


def test_example_report_contains_the_actual_disambiguating_clues():
    result = subprocess.run([sys.executable, str(EXAMPLES / "custom_shading_rule.py")],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    matches = [bits for bits in product((0, 1), repeat=4) if _valid(bits)
               and all(bits[c[0]*2+c[1]] == value for c, value in report["clues"])]
    assert matches == [tuple(v for row in report["answer"] for v in row)]
