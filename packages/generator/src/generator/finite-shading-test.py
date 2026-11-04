"""Exercise the exploration-to-generation gap with an independent DSL pool."""

from collections import defaultdict
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from generator import InitialCluesNotUniqueError
from puzzle import at_least_one, unique
from puzzle_defs import BlackCount, ConnectedWhite, NonTouchingBlack, NoWhite2x2, RowCountClue, ShadingRecipe, ShadingPuzzle

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    finite = importlib.import_module("finite_shading")


def _cli(script, *args, hash_seed="0"):
    return subprocess.run([sys.executable, str(EXAMPLES / script), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8", timeout=60,
                          env={**os.environ, "PYTHONHASHSEED": hash_seed})


def _dsl_groups(recipe):
    puzzle = recipe.create_empty()
    variables = [puzzle.black[c] for c in puzzle.board.cells]
    groups = defaultdict(list)
    seen = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits not in seen
        seen.add(bits)
        groups[tuple(recipe.extract_clues(solution, puzzle))].append(bits)
        puzzle.add(at_least_one(v != solution.value(v) for v in variables))
        assert len(seen) <= 2**(recipe.rows * recipe.cols)
    return groups


@pytest.mark.parametrize("rules", [(), (BlackCount(2),), (NonTouchingBlack(),),
    (ConnectedWhite(False),), (NoWhite2x2(),), (BlackCount(2), NonTouchingBlack())])
@pytest.mark.parametrize("kinds", [(), ("cell",), ("row-count",), ("row-count", "column-count")])
def test_eligible_pool_matches_all_projected_dsl_answers(rules, kinds):
    recipe = ShadingRecipe(2, 2, rules, kinds)
    expected = sorted(group[0] for group in _dsl_groups(recipe).values() if len(group) == 1)
    if expected:
        assert finite.identifiable_completions(recipe) == expected
    else:
        with pytest.raises(InitialCluesNotUniqueError, match="changing the seed cannot help"):
            finite.identifiable_completions(recipe)


def test_selected_recipe_has_two_identifiable_answers_out_of_ten_and_preserves_only_row_hints():
    recipe = ShadingRecipe(2, 3, (BlackCount(3), ConnectedWhite()), ("row-count",))
    groups = _dsl_groups(recipe)
    assert sum(len(g) for g in groups.values()) == 10
    eligible = {g[0] for g in groups.values() if len(g) == 1}
    assert eligible == {(0, 0, 0, 1, 1, 1), (1, 1, 1, 0, 0, 0)}
    observed = set()
    for seed in range(8):
        clues = finite.generate_finite(recipe, seed=seed)
        assert len(clues) == 1 and isinstance(clues[0], RowCountClue)
        puzzle = recipe.build_from_clues(clues)
        puzzle.add(unique())
        solution = puzzle.solve(seed=seed)
        assert solution is not None
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits in eligible
        observed.add(bits)
        # Independently evaluate the remaining hints against ALL DSL answers.
        matches = [b for signature, group in groups.items() if set(clues) <= set(signature) for b in group]
        assert matches == [bits]
        empty = recipe.create_empty()
        empty.add(unique())
        assert empty.solve() is None  # The only remaining hint is necessary.
    assert observed == eligible


@pytest.mark.parametrize("recipe,message", [
    (ShadingRecipe(2, 2, (BlackCount(0), BlackCount(1))), "No completion satisfies"),
    (ShadingRecipe(2, 2, (BlackCount(2), NonTouchingBlack()), ("row-count", "column-count")),
     "No completion is identifiable"),
    (ShadingRecipe(2, 5, ()), "at most 9 cells"),
    (ShadingRecipe(1, 1, (BlackCount(0),) * 9), "8 rule occurrences"),
])
def test_unsupported_or_impossible_recipes_fail_before_reduction(recipe, message, monkeypatch):
    monkeypatch.setattr(finite, "reduce_clues", lambda *a, **k: pytest.fail("Must not reduce this recipe"))
    with pytest.raises(ValueError, match=message):
        finite.generate_finite(recipe)


@pytest.mark.parametrize("seed", [-1, 2**31, True, 1.0])
def test_invalid_seed_fails_before_enumeration(seed, monkeypatch):
    monkeypatch.setattr(finite, "identifiable_completions", lambda *a: pytest.fail("Must not enumerate"))
    with pytest.raises(ValueError, match="Seed"):
        finite.generate_finite(ShadingRecipe(1, 1, ()), seed=seed)


def test_custom_rule_subclasses_are_not_silently_enumerated():
    class CustomCount(BlackCount):
        pass

    with pytest.raises(ValueError, match="exact built-in"):
        finite.generate_finite(ShadingRecipe(1, 1, (CustomCount(0),)))


@pytest.mark.parametrize("damage", ["no-solution", "wrong-answer", "wrong-hints"])
def test_oracle_model_disagreement_never_reaches_reduction(monkeypatch, damage):
    recipe = ShadingRecipe(1, 1, (BlackCount(1),))
    monkeypatch.setattr(finite, "reduce_clues", lambda *a, **k: pytest.fail("Disagreement must stop generation"))
    if damage == "no-solution":
        monkeypatch.setattr(ShadingPuzzle, "solve", lambda *a, **k: None)
    elif damage == "wrong-answer":
        monkeypatch.setattr(ShadingPuzzle, "result", lambda *a, **k: [[0]])
    else:
        monkeypatch.setattr(ShadingRecipe, "extract_clues", lambda *a: [])
    with pytest.raises(RuntimeError, match="disagree"):
        finite.generate_finite(recipe)


def test_exploration_export_to_generation_play_verification_and_diagnosis(tmp_path):
    recipe, puzzle = tmp_path / "chosen.json", tmp_path / "puzzle.json"
    chosen = _cli("explore_shading.py", "--rows", 2, "--cols", 3, "--black-counts", 3,
                  "--candidates", "count", "connected-white", "--hints", "row-count",
                  "--explain", 1, 2, "--export-recipe", recipe)
    assert chosen.returncode == 0, chosen.stderr
    before = recipe.read_bytes()
    result = _cli("generate_shading.py", "generate", "--recipe", recipe, "--selection", "finite",
                  "--seed", 0, "--output", puzzle, "--quiet")
    assert result.returncode == 0 and result.stdout == "", result.stderr
    data = json.loads(puzzle.read_text())
    assert data["clue_kinds"] == ["row-count"] and len(data["clues"]) == 1
    assert data["environment"]["completion_selection"] == finite.SELECTION
    assert data["seed"] == 0 and recipe.read_bytes() == before
    shown = _cli("generate_shading.py", "show", puzzle)
    assert shown.returncode == 0 and "Answer template: ???/???" in shown.stdout
    verified = _cli("generate_shading.py", "verify", puzzle)
    assert verified.returncode == 0 and json.loads(verified.stdout)["irreducible"]
    answer = "/".join("".join("#" if v else "." for v in row) for row in data["solution"])
    assert _cli("generate_shading.py", "check", puzzle, "--answer", answer).returncode == 0
    assert _cli("generate_shading.py", "check", puzzle, "--answer", ".../...").returncode == 1
    diagnosed = _cli("diagnose_shading_rules.py", puzzle, "--json")
    assert diagnosed.returncode == 0, diagnosed.stderr
    report = json.loads(diagnosed.stdout)
    assert report["original_answer_count"] == 1 and report["stored_clues_irreducible"]


def test_finite_generation_is_reproducible_and_explicit_solver_selection_preserves_default_output():
    args = ("generate", "--rows", 2, "--cols", 3, "--rules", "count", "connected-white",
            "--black-count", 3, "--hints", "row-count", "--seed", 7, "--selection", "finite")
    first, second = _cli("generate_shading.py", *args), _cli("generate_shading.py", *args, hash_seed="999")
    assert first.returncode == second.returncode == 0, (first.stderr, second.stderr)
    assert first.stdout == second.stdout
    ordinary = ("generate", "--rows", 2, "--cols", 2, "--rules", "count", "--black-count", 1, "--seed", 0)
    default = _cli("generate_shading.py", *ordinary)
    explicit = _cli("generate_shading.py", *ordinary, "--selection", "solver")
    assert default.returncode == explicit.returncode == 0
    assert default.stdout == explicit.stdout and "completion_selection" not in json.loads(default.stdout)["environment"]


@pytest.mark.parametrize("options,message", [
    (["--rows", 2, "--cols", 2, "--rules", "count", "non-touching", "--black-count", 2,
      "--hints", "row-count", "column-count"], "changing the seed cannot help"),
    (["--rows", 2, "--cols", 5], "at most 9 cells"),
    (["--seed", -1], "Seed"),
])
def test_cli_failure_preserves_output_and_gives_a_specific_reason(tmp_path, options, message):
    output = tmp_path / "keep.json"
    output.write_text("keep", encoding="utf-8")
    result = _cli("generate_shading.py", "generate", "--selection", "finite", *options, "--output", output)
    assert result.returncode == 2 and message in result.stderr and "Traceback" not in result.stderr
    assert output.read_text() == "keep"


def test_zero_hint_unique_recipe_works_with_the_largest_seed():
    clues = finite.generate_finite(ShadingRecipe(1, 1, (BlackCount(0),), ()), seed=2**31-1)
    assert clues == []


def test_largest_finite_board_and_rule_count_are_supported():
    recipe = ShadingRecipe(3, 3, (BlackCount(0),) * 8)
    assert finite.identifiable_completions(recipe) == [(0,) * 9]
    assert finite.generate_finite(recipe) == []
