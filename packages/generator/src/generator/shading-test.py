from itertools import combinations, product
from collections.abc import Sequence
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from generator import generate, reduce_clues
from puzzle import Cell, unique
from puzzle_defs import (
    BlackCount, ConnectedWhite, NonTouchingBlack, NoWhite2x2,
    ColumnCountClue, RowCountClue, ShadingRecipe,
)
from puzzle_defs.puzzles.shading import CLUE_KINDS, Clue, ClueKind, ShadingRule


def _answers(recipe: ShadingRecipe, clues: Sequence[Clue]) -> list[tuple[int, ...]]:
    """Enumerate raw bit grids and check graph/window rules without the DSL."""
    rows, cols = recipe.rows, recipe.cols
    coordinates = list(product(range(rows), range(cols)))
    answers = []
    for bits in product([0, 1], repeat=rows * cols):
        black = {c for c, value in zip(coordinates, bits) if value}
        white = set(coordinates) - black
        if not all(_matches_clue(bits, rows, cols, clue) for clue in clues):
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


def _matches_clue(bits: tuple[int, ...], rows: int, cols: int, clue: Clue) -> bool:
    if isinstance(clue, RowCountClue):
        return sum(bits[clue.row * cols + c] for c in range(cols)) == clue.count
    if isinstance(clue, ColumnCountClue):
        return sum(bits[r * cols + clue.col] for r in range(rows)) == clue.count
    cell, value = clue
    return bits[cell.row * cols + cell.col] == value


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
    assert json.loads(first.stdout)["format"] == "puzzle-box/shading-v1"
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


MIXED_KINDS: list[tuple[ClueKind, ...]] = [
    CLUE_KINDS, ("cell", "row-count"), ("cell", "column-count"),
]


@pytest.mark.parametrize("kinds", MIXED_KINDS)
@pytest.mark.parametrize("rules", [
    (BlackCount(3), NonTouchingBlack()),
    (BlackCount(3), NonTouchingBlack(), ConnectedWhite(), NoWhite2x2()),
    (ConnectedWhite(), NoWhite2x2()),
])
@pytest.mark.parametrize("seed", [7, 17])
def test_mixed_clue_generation_matches_exhaustive_oracle(kinds, rules, seed: int):
    recipe = ShadingRecipe(3, 3, rules, kinds)
    clues = generate(recipe, seed=seed)
    answers = _answers(recipe, clues)
    assert len(answers) == 1
    for idx in range(len(clues)):
        assert len(_answers(recipe, clues[:idx] + clues[idx+1:])) > 1
    p = recipe.build_from_clues(clues)
    p.add(unique())
    s = p.solve()
    assert s is not None
    assert tuple(v for row in p.result(s) for v in row) == answers[0]


def test_ambiguous_counts_keep_necessary_cell_clues():
    recipe = ShadingRecipe(3, 3, (BlackCount(3), NonTouchingBlack()), CLUE_KINDS)
    bits = (0, 0, 1, 0, 1, 0, 1, 0, 0)
    source = recipe.build_from_clues([(Cell(i // 3, i % 3), v) for i, v in enumerate(bits)])
    solution = source.solve()
    assert solution is not None
    candidates = recipe.extract_clues(solution, source)
    counts: list[Clue] = [c for c in candidates if not isinstance(c, tuple)]
    assert len(_answers(recipe, counts)) == 6
    with pytest.raises(ValueError, match="Initial clues must define a uniquely solvable"):
        reduce_clues(recipe, counts, seed=1)
    clues = reduce_clues(recipe, candidates, seed=1)
    assert any(isinstance(c, tuple) for c in clues)
    assert any(isinstance(c, RowCountClue) for c in clues)
    assert any(isinstance(c, ColumnCountClue) for c in clues)
    assert _answers(recipe, clues) == [bits]
    for idx in range(len(clues)):
        assert len(_answers(recipe, clues[:idx] + clues[idx+1:])) > 1


def test_counts_only_can_succeed_when_the_rules_determine_the_answer():
    recipe = ShadingRecipe(3, 3, (BlackCount(3), NonTouchingBlack(), ConnectedWhite(), NoWhite2x2()),
                           ("row-count", "column-count"))
    clues = generate(recipe, seed=17)
    assert all(isinstance(c, (RowCountClue, ColumnCountClue)) for c in clues)
    assert len(_answers(recipe, clues)) == 1
    for idx in range(len(clues)):
        assert len(_answers(recipe, clues[:idx] + clues[idx+1:])) > 1


@pytest.mark.parametrize("axis,index", [("row", 0), ("row", 1), ("column", 0), ("column", 1), ("column", 2)])
def test_line_counts_match_every_two_by_three_board(axis: str, index: int):
    recipe = ShadingRecipe(2, 3, ())
    factory = RowCountClue if axis == "row" else ColumnCountClue
    length = 3 if axis == "row" else 2
    for bits in product([0, 1], repeat=6):
        cells: list[Clue] = [(Cell(i // 3, i % 3), v) for i, v in enumerate(bits)]
        for count in range(length + 1):
            clue = factory(index, count)
            p = recipe.build_from_clues([*cells, clue])
            assert (p.solve() is not None) == _matches_clue(bits, 2, 3, clue)


@pytest.mark.parametrize("clue", [RowCountClue(2, 0), ColumnCountClue(3, 0),
                                 RowCountClue(0, 4), ColumnCountClue(0, 3)])
def test_line_clues_cannot_exceed_dimensions(clue: Clue):
    with pytest.raises(ValueError, match="dimensions"):
        ShadingRecipe(2, 3, ()).build_from_clues([clue])


@pytest.mark.parametrize("factory", [RowCountClue, ColumnCountClue])
@pytest.mark.parametrize("index,count", [(-1, 0), (0, -1), (True, 1), (0, 1.5)])
def test_line_clue_fields_are_nonnegative_integers(factory, index, count):
    with pytest.raises(ValueError, match="nonnegative integer"):
        factory(index, count)


def test_cli_mixed_generation_repeats_and_count_only_generation_verifies(tmp_path: Path):
    output = tmp_path / "mixed.json"
    args = ("generate", "--rules", "count", "non-touching", "--black-count", "3",
            "--hints", "cell", "row-count", "column-count", "--seed", "17", "--output", str(output))
    first, second = _cli(*args, hash_seed="1"), _cli(*args, hash_seed="999")
    assert first.returncode == second.returncode == 0, (first.stderr, second.stderr)
    assert first.stdout == second.stdout == output.read_text(encoding="utf-8")
    data = json.loads(first.stdout)
    assert data["format"] == "puzzle-box/shading-v2"
    assert data["clue_kinds"] == list(CLUE_KINDS)
    assert _cli("verify", str(output)).returncode == 0
    counts = _cli("generate", "--hints", "row-count", "column-count", "--output", str(output))
    assert counts.returncode == 0, counts.stderr
    assert _cli("verify", str(output)).returncode == 0


@pytest.mark.parametrize("clue", [
    {"type": "diagonal-count", "count": 1},
    {"type": "row-count", "row": 0, "count": 1.5},
    {"type": "column-count", "col": 99, "count": 0},
    {"type": "row-count", "row": 0, "count": 99},
    {"type": "row-count", "row": 0, "count": 1, "extra": 0},
])
def test_cli_rejects_invalid_mixed_clues(tmp_path: Path, clue):
    data = json.loads(SAMPLE.with_name("shading-mixed-sample.json").read_text(encoding="utf-8"))
    data["clues"] = [clue]
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    checked = _cli("verify", str(path))
    assert checked.returncode != 0
    assert "Traceback" not in checked.stderr


def test_mixed_sample_verifies_and_needs_every_clue_kind():
    path = SAMPLE.with_name("shading-mixed-sample.json")
    checked = _cli("verify", str(path))
    assert checked.returncode == 0, checked.stderr
    data = json.loads(path.read_text(encoding="utf-8"))
    clues: list[Clue] = []
    for clue in data["clues"]:
        if clue["type"] == "cell":
            clues.append((Cell(clue["row"], clue["col"]), clue["value"]))
        elif clue["type"] == "row-count":
            clues.append(RowCountClue(clue["row"], clue["count"]))
        else:
            assert clue["type"] == "column-count"
            clues.append(ColumnCountClue(clue["col"], clue["count"]))
    assert {type(clue) for clue in clues} == {tuple, RowCountClue, ColumnCountClue}
    recipe = ShadingRecipe(data["rows"], data["cols"], (BlackCount(3), NonTouchingBlack()), CLUE_KINDS)
    assert _answers(recipe, clues) == [tuple(v for row in data["solution"] for v in row)]
    for idx in range(len(clues)):
        assert len(_answers(recipe, clues[:idx] + clues[idx+1:])) > 1


def test_cli_does_not_save_ambiguous_count_only_generation(tmp_path: Path):
    output = tmp_path / "ambiguous.json"
    result = _cli("generate", "--rules", "count", "non-touching", "--hints", "column-count",
                  "--seed", "17", "--output", str(output))
    assert result.returncode != 0
    assert "include cell in --hints" in result.stderr
    assert not output.exists()


def test_count_only_cli_preserves_invalid_rule_diagnostic():
    result = _cli("generate", "--black-count", "99", "--hints", "row-count")
    assert result.returncode != 0
    assert "Black count cannot exceed the board area" in result.stderr


@pytest.mark.parametrize("kinds", [("cell", "cell"), ("unknown",)])
def test_unknown_or_duplicate_clue_kinds_are_rejected(kinds):
    with pytest.raises(ValueError, match="Clue kinds"):
        ShadingRecipe(2, 3, (), kinds)
