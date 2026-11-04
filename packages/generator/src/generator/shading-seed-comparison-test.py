"""Compare reduced-clue rule roles and exercise safe recipe-to-puzzle export."""

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from puzzle import at_least_one
from puzzle_defs import BlackCount, ConnectedWhite, NonTouchingBlack, ShadingRecipe

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    comparison = importlib.import_module("compare_shading_seeds")
    codec = importlib.import_module("shading_recipe")
    display = importlib.import_module("generate_shading")


def _cli(script, *args, hash_seed="0"):
    return subprocess.run([sys.executable, str(EXAMPLES / script), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8", timeout=90,
                          env={**os.environ, "PYTHONHASHSEED": hash_seed})


def _dsl_answers(recipe, clues):
    puzzle = recipe.build_from_clues(clues)
    variables = [puzzle.black[c] for c in puzzle.board.cells]
    answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(v != solution.value(v) for v in variables))
        assert len(answers) <= 2**(recipe.rows * recipe.cols)
    return answers


@pytest.mark.parametrize("name,counts", [("diagonal-cells", (2, 2)), ("row-counts", (10, 2)),
                                         ("three-rules", (18, 18))])
def test_examples_compare_actual_reduced_puzzles_against_projected_dsl(name, counts):
    recipe = codec.load_recipe(EXAMPLES / "recipes" / f"shading-{name}.json")
    report = comparison.compare(recipe, [0, 1])
    assert (report["analysis"]["completion_count"], report["analysis"]["identifiable_completions"]) == counts
    for attempt in report["attempts"]:
        restored, clues, answer = display._read_record(attempt["puzzle"])
        bits = tuple(v for row in answer for v in row)
        assert restored == recipe
        assert _dsl_answers(recipe, clues) == {bits}
        for index in range(len(clues)):
            assert len(_dsl_answers(recipe, clues[:index] + clues[index+1:])) > 1
        for index, removal in enumerate(attempt["diagnostic"]["removals"]):
            relaxed = ShadingRecipe(recipe.rows, recipe.cols, recipe.rules[:index] + recipe.rules[index+1:], recipe.clue_kinds)
            for label, raw in (("stored", attempt["diagnostic"]["stored_clues"]),
                               ("full_candidate", attempt["diagnostic"]["full_candidate_clues"])):
                answers = _dsl_answers(relaxed, [display.read_clue(c) for c in raw])
                assert len(answers) == removal[f"answers_with_{label}_clues"]
                witness = removal["stored_clue_alternative" if label == "stored" else "full_clue_alternative"]
                if witness is not None:
                    alternative = tuple(v for row in witness for v in row)
                    assert alternative in answers - {bits}
        assert set(attempt["necessary_rule_indices"]) | set(attempt["redundant_rule_indices"]) == set(range(1, len(recipe.rules)+1))
    if name == "three-rules":
        assert report["attempts"][0]["necessary_rule_indices"] == []
        assert report["attempts"][1]["necessary_rule_indices"] == [1, 2, 3]
        assert all(not r["necessary_with_full_candidate_clues"] for a in report["attempts"] for r in a["diagnostic"]["removals"])


@pytest.mark.parametrize("connected,policy,count", [(False, "none_identifiable", 2), (True, "no_completion", 0)])
def test_infeasible_and_ambiguous_recipes_skip_generation(connected, policy, count, monkeypatch):
    rules = (BlackCount(2), NonTouchingBlack()) + ((ConnectedWhite(),) if connected else ())
    monkeypatch.setattr(comparison, "generate_finite", lambda *a, **k: pytest.fail("No seed can help"))
    report = comparison.compare(ShadingRecipe(2, 2, rules, ("row-count", "column-count")), [0, 1])
    assert report["analysis"]["hint_policy"] == policy
    assert report["analysis"]["completion_count"] == count
    assert report["attempts"] == [] and report["distinct_answers"] == 0
    assert "No generation attempted" in comparison.explain(report)
    assert report["analysis"]["minimal_conflicts"] == ([[1, 2, 3]] if connected else [])


@pytest.mark.parametrize("seeds", [[], list(range(9)), [1, 1], [True], [1.0], [-1], [2**31]])
def test_seed_budget_is_validated_before_any_analysis(seeds, monkeypatch):
    monkeypatch.setattr(comparison, "analyze", lambda *a, **k: pytest.fail("Invalid seeds must stop first"))
    with pytest.raises(ValueError, match="1..8 distinct"):
        comparison.compare(ShadingRecipe(1, 1, ()), seeds)


def test_finite_board_limit_and_empty_rules():
    with pytest.raises(ValueError, match="9 cells"):
        comparison.compare(ShadingRecipe(2, 5, ()), [0])
    report = comparison.compare(ShadingRecipe(1, 1, ()), [0])
    assert report["attempts"][0]["necessary_rule_indices"] == []
    assert report["attempts"][0]["redundant_rule_indices"] == []


def test_cli_export_matches_normal_generation_and_can_be_played(tmp_path):
    source = EXAMPLES / "recipes" / "shading-three-rules.json"
    output, regular = tmp_path / "selected.json", tmp_path / "normal.json"
    compared = _cli("compare_shading_seeds.py", source, "--seeds", 0, 1, "--export-seed", 1, "--export-puzzle", output)
    assert compared.returncode == 0, compared.stderr
    assert "0 | 1 | 4 | - / 1+2+3" in compared.stdout
    assert "1 | 2 | 3 | 1+2+3 / -" in compared.stdout
    assert "solution" not in compared.stdout and "witness" not in compared.stdout.split("--json")[0]
    generated = _cli("generate_shading.py", "generate", "--recipe", source, "--selection", "finite", "--seed", 1, "--output", regular, "--quiet")
    assert generated.returncode == 0, generated.stderr
    assert json.loads(output.read_text()) == json.loads(regular.read_text())
    before = output.read_bytes()
    record = json.loads(before)
    answer = "/".join("".join("#" if v else "." for v in row) for row in record["solution"])
    for command, options in (("show", ()), ("verify", ()), ("check", ("--answer", answer))):
        result = _cli("generate_shading.py", command, output, *options)
        assert result.returncode == 0, result.stderr
    assert output.read_bytes() == before
    again = _cli("compare_shading_seeds.py", source, "--seeds", 0, 1, "--json", hash_seed="17")
    assert again.returncode == 0, again.stderr
    assert json.loads(again.stdout)["attempts"][1]["puzzle"] == record


@pytest.mark.parametrize("case", ["same-input", "existing-output", "missing-seed", "unlisted-seed", "invalid-recipe", "impossible", "duplicate-seeds"])
def test_cli_errors_protect_existing_files(tmp_path, case):
    source, output = tmp_path / "source.json", tmp_path / "output.json"
    record = json.loads((EXAMPLES / "recipes" / "shading-diagonal-cells.json").read_text())
    if case == "invalid-recipe":
        record["extra"] = True
    if case == "impossible":
        record["clue_kinds"] = ["row-count", "column-count"]
    source.write_text(json.dumps(record))
    if case == "existing-output":
        output.write_bytes(b"keep this file")
    if case == "same-input":
        output = source
    before = {p: p.read_bytes() for p in (source, output) if p.exists()}
    args = ["--seeds", "0", "0"] if case == "duplicate-seeds" else ["--seeds", "0"]
    if case != "missing-seed":
        args += ["--export-seed", "1" if case == "unlisted-seed" else "0"]
    result = _cli("compare_shading_seeds.py", source, *args, "--export-puzzle", output)
    assert result.returncode == 2
    for path, raw in before.items():
        assert path.read_bytes() == raw
    if output not in before:
        assert not output.exists()


def test_legacy_cell_format_and_maximum_seed():
    report = comparison.compare(ShadingRecipe(1, 1, (BlackCount(1),)), [2**31 - 1])
    record = report["attempts"][0]["puzzle"]
    assert record["format"] == display.FORMAT
    assert "clue_kinds" not in record
    assert report["attempts"][0]["clue_count"] == 0
    assert display.verify(record)["unique"] is True


def test_disagreement_aborts_instead_of_reporting_success(monkeypatch):
    monkeypatch.setattr(comparison, "diagnose", lambda record: {"stored_clues_irreducible": False})
    with pytest.raises(RuntimeError, match="disagree"):
        comparison.compare(ShadingRecipe(1, 1, (BlackCount(1),)), [0])


def test_eight_seeds_do_not_imply_eight_distinct_answers():
    report = comparison.compare(ShadingRecipe(1, 1, (BlackCount(1),)), list(range(8)))
    assert len(report["attempts"]) == 8 and report["distinct_answers"] == 1
    assert {a["answer_id"] for a in report["attempts"]} == {1}


def test_export_refuses_a_file_created_after_preflight(tmp_path, monkeypatch):
    source, output = tmp_path / "recipe.json", tmp_path / "selected.json"
    recipe = ShadingRecipe(1, 1, (BlackCount(1),))
    source.write_text(json.dumps(codec.recipe_record(recipe)))
    report = comparison.compare(recipe, [0])
    def arrive_during_comparison(*args):
        output.write_bytes(b"created by someone else")
        return report
    monkeypatch.setattr(comparison, "compare", arrive_during_comparison)
    monkeypatch.setattr(sys, "argv", ["compare_shading_seeds.py", str(source), "--seeds", "0",
                                     "--export-seed", "0", "--export-puzzle", str(output)])
    with pytest.raises(SystemExit) as exc:
        comparison.main()
    assert exc.value.code == 2
    assert output.read_bytes() == b"created by someone else"
