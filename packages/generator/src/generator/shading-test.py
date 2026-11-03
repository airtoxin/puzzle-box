from itertools import combinations, product
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from generator import generate
from puzzle import Cell, unique
from puzzle_defs import BlackCount, ConnectedWhite, NonTouchingBlack, NoWhite2x2, ShadingRecipe
from puzzle_defs.puzzles.shading import Clue, ShadingRule


def _answers(recipe: ShadingRecipe, clues: list[Clue]) -> list[tuple[int, ...]]:
    """Enumerate raw bit grids and check graph/window rules without the DSL."""
    rows, cols = recipe.rows, recipe.cols
    coordinates = list(product(range(rows), range(cols)))
    answers = []
    for bits in product([0, 1], repeat=rows * cols):
        black = {c for c, value in zip(coordinates, bits) if value}
        white = set(coordinates) - black
        if any(bits[cell.row * cols + cell.col] != value for cell, value in clues):
            continue
        valid = True
        for rule in recipe.rules:
            if isinstance(rule, BlackCount):
                valid &= len(black) == rule.count
            elif isinstance(rule, NonTouchingBlack):
                for (r1, c1), (r2, c2) in combinations(black, 2):
                    distance = max(abs(r1 - r2), abs(c1 - c2)) if rule.diagonal else abs(r1 - r2) + abs(c1 - c2)
                    valid &= distance != 1
            elif isinstance(rule, ConnectedWhite):
                seen = set()
                todo = [next(iter(white))] if white else []
                while todo:
                    r, c = todo.pop()
                    if (r, c) in seen:
                        continue
                    seen.add((r, c))
                    todo.extend(n for n in [(r-1, c), (r+1, c), (r, c-1), (r, c+1)]
                                if n in white and n not in seen)
                valid &= seen == white and (bool(white) or not rule.nonempty)
            elif isinstance(rule, NoWhite2x2):
                valid &= all(any((r+dr, c+dc) in black for dr in (0, 1) for dc in (0, 1))
                             for r in range(rows-1) for c in range(cols-1))
            else:
                raise AssertionError("Oracle has no semantics for this rule")
        if valid:
            answers.append(bits)
    return answers


RULE_COMBINATIONS: list[tuple[ShadingRule, ...]] = [
    (BlackCount(2), NonTouchingBlack()),
    (BlackCount(2), ConnectedWhite()),
    (NonTouchingBlack(), ConnectedWhite()),
    (BlackCount(2), NonTouchingBlack(), ConnectedWhite()),
    (BlackCount(2), NonTouchingBlack(), NoWhite2x2()),
    (BlackCount(2), NonTouchingBlack(), ConnectedWhite(), NoWhite2x2()),
    (BlackCount(3), NonTouchingBlack(), ConnectedWhite(), NoWhite2x2()),
    (BlackCount(2), NonTouchingBlack(diagonal=True), ConnectedWhite()),
]


@pytest.mark.parametrize("rules", RULE_COMBINATIONS)
@pytest.mark.parametrize("seed", [7, 17])
def test_composed_generation_is_unique_and_irreducible(rules, seed: int):
    recipe = ShadingRecipe(3, 3, rules)
    clues = generate(recipe, seed=seed)
    answers = _answers(recipe, clues)
    assert len(answers) == 1
    for idx in range(len(clues)):
        assert len(_answers(recipe, clues[:idx] + clues[idx+1:])) > 1
    rebuilt = recipe.build_from_clues(clues)
    rebuilt.add(unique())
    solution = rebuilt.solve()
    assert solution is not None
    assert tuple(v for row in rebuilt.result(solution) for v in row) == answers[0]


@pytest.mark.parametrize("rule", [BlackCount(2), NonTouchingBlack(), NonTouchingBlack(True),
                                 ConnectedWhite(), ConnectedWhite(False), NoWhite2x2()])
def test_rule_acceptance_matches_all_two_by_two_boards(rule: ShadingRule):
    recipe = ShadingRecipe(2, 2, (rule,))
    accepted = set(_answers(recipe, []))
    for bits in product([0, 1], repeat=4):
        clues = [(Cell(idx // 2, idx % 2), bit) for idx, bit in enumerate(bits)]
        p = recipe.build_from_clues(clues)
        assert (p.solve() is not None) == (bits in accepted)


def test_contradictory_rule_combination_fails_instead_of_producing_a_puzzle():
    recipe = ShadingRecipe(2, 2, (BlackCount(4), ConnectedWhite()))
    with pytest.raises(RuntimeError, match="Failed to generate"):
        generate(recipe, seed=17)


def test_already_unique_recipe_can_generate_zero_clues():
    assert generate(ShadingRecipe(2, 2, (BlackCount(0), ConnectedWhite())), seed=17) == []


@pytest.mark.parametrize("rows,cols", [(0, 2), (2, -1)])
def test_invalid_dimensions_are_rejected(rows: int, cols: int):
    with pytest.raises(ValueError, match="positive"):
        ShadingRecipe(rows, cols, ())


@pytest.mark.parametrize("clue", [(Cell(2, 0), 0), (Cell(0, 0), 2)])
def test_invalid_clues_are_rejected(clue: Clue):
    with pytest.raises(ValueError):
        ShadingRecipe(2, 2, ()).build_from_clues([clue])


SCRIPT = Path(__file__).resolve().parents[4] / "examples" / "generate_shading.py"
SAMPLE = SCRIPT.with_name("shading-sample.json")


def _cli(*args: str, hash_seed: str = "1") -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONHASHSEED=hash_seed)
    return subprocess.run([sys.executable, str(SCRIPT), *args], env=env, check=False,
                          capture_output=True, text=True, timeout=45)


def test_cli_generation_is_repeatable_and_saved_record_verifies(tmp_path: Path):
    output = tmp_path / "puzzle.json"
    args = ("generate", "--seed", "17", "--output", str(output))
    first = _cli(*args, hash_seed="1")
    second = _cli(*args, hash_seed="999")
    assert first.returncode == second.returncode == 0, (first.stderr, second.stderr)
    assert first.stdout == second.stdout == output.read_text(encoding="utf-8")
    checked = _cli("verify", str(output))
    assert checked.returncode == 0, checked.stderr
    assert json.loads(checked.stdout) == {
        "valid": True, "unique": True, "irreducible": True,
        "clue_count": len(json.loads(first.stdout)["clues"]),
    }
    data = json.loads(output.read_text(encoding="utf-8"))
    data["solution"][0][0] = 1 - data["solution"][0][0]
    output.write_text(json.dumps(data), encoding="utf-8")
    invalid = _cli("verify", str(output))
    assert invalid.returncode != 0
    assert "does not match" in invalid.stderr


def test_cli_rejects_unknown_rules_and_oversized_boards():
    assert _cli("generate", "--rules", "unknown").returncode != 0
    too_large = _cli("generate", "--rows", "6", "--cols", "6")
    assert too_large.returncode != 0 and "at most 25" in too_large.stderr


def test_published_sample_verifies_and_each_rule_matters():
    checked = _cli("verify", str(SAMPLE))
    assert checked.returncode == 0, checked.stderr
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    recipe = ShadingRecipe(3, 3, (BlackCount(3), NonTouchingBlack(), ConnectedWhite(), NoWhite2x2()))
    clues = [(Cell(r, c), v) for r, c, v in data["clues"]]
    answers = _answers(recipe, clues)
    assert answers == [tuple(v for row in data["solution"] for v in row)]
    for idx in range(len(clues)):
        assert len(_answers(recipe, clues[:idx] + clues[idx+1:])) > 1
    # This example actually needs all four rules, rather than merely listing them.
    for idx in range(len(recipe.rules)):
        weaker = ShadingRecipe(3, 3, recipe.rules[:idx] + recipe.rules[idx+1:])
        assert len(_answers(weaker, clues)) > 1
