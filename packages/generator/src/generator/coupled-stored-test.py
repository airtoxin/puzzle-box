from copy import deepcopy
from functools import lru_cache
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from puzzle import Cell, Edge, Vertex
from puzzle_defs import ArrowSite, YajilinAnswer, YajilinRecipe

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    diagnostic = importlib.import_module("diagnose_coupled_rules")
    records = importlib.import_module("coupled_records")
    oracle = importlib.import_module("coupled_oracle")
    experiment = importlib.import_module("explore_coupled")
    cli = importlib.import_module("generate_yajilin")
SAMPLE = EXAMPLES / "coupled-stored-sample.json"


def sample():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def record(recipe, mask, answer, clues):
    return {"format": records.FORMAT, "rows": recipe.rows, "cols": recipe.cols, "rule_mask": mask,
            "arrow_sites": [{"cell": list(s.cell), "direction": s.direction} for s in recipe.arrow_sites],
            "clue_kinds": list(recipe.clue_kinds), "solution": experiment.answer_record(answer),
            "clues": [cli.clue_record(c) for c in clues]}


def answer(data):
    return YajilinAnswer(frozenset(Cell(*c) for c in data["black_cells"]),
                        frozenset(Edge(Vertex(a, b), Vertex(c, d)) for a, b, c, d in data["loop_edges"]))


@lru_cache(maxsize=None)
def report():
    return diagnostic.diagnose(sample(), verify_models=True)


def test_reduced_hint_changes_rule_necessity_and_witnesses_satisfy_the_same_hints():
    result = report()
    assert result["models_verified"] and result["model_queries_verified"] > 0
    assert result["original_answer_count"] == 1
    assert result["answer_projection"] == ["black_cells", "loop_edges"]
    assert result["stored_clues_irreducible"]
    assert len(result["full_candidate_clues"]) == 18
    assert [r["answers_with_stored_clues"] for r in result["removals"]] == [123, 3]
    assert [r["answers_with_full_candidate_clues"] for r in result["removals"]] == [1, 1]
    recipe, _, clues, original = records.read_puzzle(sample())
    for removal in result["removals"]:
        alternative = answer(removal["stored_clue_alternative"])
        assert alternative != original
        assert set(clues) <= set(oracle.full_clues(recipe, alternative, recipe.clue_kinds))
        assert oracle.accepts(recipe, removal["remaining_rule_mask"], alternative)
        assert not oracle.accepts(recipe, 3, alternative)
        assert removal["needed_with_stored_but_not_full_clues"]
        assert removal["full_clue_alternative"] is None


@pytest.mark.parametrize("mask", range(8))
def test_all_rule_masks_with_full_stored_hints_match_the_dsl(mask):
    recipe = YajilinRecipe(2, 4)
    original = next(a for a in oracle.universe(recipe) if oracle.accepts(recipe, 7, a))
    data = record(recipe, mask, original, oracle.full_clues(recipe, original, recipe.clue_kinds))
    result = diagnostic.diagnose(data, verify_models=True)
    assert result["original_answer_count"] == 1
    assert len(result["removals"]) == mask.bit_count()
    assert all(r["answers_with_stored_clues"] == r["answers_with_full_candidate_clues"] == 1
               for r in result["removals"])


@pytest.mark.parametrize("direction", ["up", "down", "left", "right"])
def test_all_arrow_directions_and_existing_yajilin_records(direction):
    recipe = YajilinRecipe(2, 4, (ArrowSite(Cell(0, 0), direction),))
    original = next(a for a in oracle.universe(recipe) if oracle.accepts(recipe, 7, a))
    data = record(recipe, 7, original, oracle.full_clues(recipe, original, recipe.clue_kinds))
    data["format"] = cli.FORMAT
    del data["rule_mask"]
    data.update(seed=8, generation={"initial_seed": 6, "attempt_limit": 3, "attempts_used": 3})
    result = diagnostic.diagnose(data, verify_models=True)
    assert result["rule_mask"] == 7 and result["source_format"] == cli.FORMAT
    assert result["models_verified"]


def test_zero_clues_and_both_components_of_the_saved_answer():
    data = sample()
    data["rule_mask"], data["clues"] = 7, []
    result = diagnostic.diagnose(data, verify_models=True)
    assert result["stored_clues_irreducible"] and result["removable_clue_indices"] == []
    assert [r["answers_with_stored_clues"] for r in result["removals"]] == [246, 6, 2]
    data["solution"]["loop_edges"] = []
    with pytest.raises(ValueError, match="do not match"):
        diagnostic.diagnose(data)
    data = sample()
    data["solution"]["black_cells"] = [[0, 0]]
    with pytest.raises(ValueError, match="do not match"):
        diagnostic.diagnose(data)


def test_black_only_projection_is_not_unique_and_contradictory_clues_are_infeasible():
    data = sample()
    data["clues"] = [{"type": "black", "cell": [r, c], "black": 0} for r in range(2) for c in range(4)]
    with pytest.raises(ValueError, match="2 joint answers"):
        diagnostic.diagnose(data, verify_models=True)
    data = sample()
    data["clues"].append({"type": "edge", "edge": [0, 2, 1, 2], "used": 1})
    with pytest.raises(ValueError, match="0 joint answers"):
        diagnostic.diagnose(data, verify_models=True)


@pytest.mark.parametrize("rows,cols", [(2, 2), (2, 3), (3, 2), (4, 2)])
def test_other_supported_board_shapes_match_the_dsl(rows, cols):
    recipe = YajilinRecipe(rows, cols)
    original = next(a for a in oracle.universe(recipe) if oracle.accepts(recipe, 7, a))
    data = record(recipe, 7, original, oracle.full_clues(recipe, original, recipe.clue_kinds))
    result = diagnostic.diagnose(data, verify_models=True)
    assert result["original_answer_count"] == 1 and result["models_verified"]


def test_full_candidates_keep_the_selected_hint_policy():
    data = sample()
    data["clue_kinds"] = ["edge"]
    result = diagnostic.diagnose(data, verify_models=True)
    assert len(result["full_candidate_clues"]) == 10
    assert all(c["type"] == "edge" for c in result["full_candidate_clues"])
    coupling = result["removals"][0]
    assert coupling["answers_with_stored_clues"] == 123
    assert coupling["answers_with_full_candidate_clues"] == 41
    assert coupling["necessary_with_full_candidate_clues"]
    assert not coupling["needed_with_stored_but_not_full_clues"]


def test_duplicate_clues_are_separate_occurrences_and_input_is_unchanged():
    data = sample()
    data["clues"] *= 2
    before = deepcopy(data)
    result = diagnostic.diagnose(data, verify_models=True)
    assert result["removable_clue_indices"] == [1, 2]
    assert not result["stored_clues_irreducible"]
    assert data == before
    data["clues"] = []
    with pytest.raises(ValueError, match="2 joint answers"):
        diagnostic.diagnose(data)


def test_model_timeout_and_disagreement_never_report_verified(monkeypatch):
    with pytest.raises(RuntimeError, match="did not finish"):
        diagnostic.diagnose(sample(), verify_models=True, time_limit=0)
    monkeypatch.setattr(diagnostic, "model_answers", lambda *args, **kwargs: (set(), 0))
    with pytest.raises(RuntimeError, match="differ"):
        diagnostic.diagnose(sample(), verify_models=True)


@pytest.mark.parametrize("field,value", [
    ("rows", True), ("rows", 1), ("rows", 3), ("cols", 10**20), ("cols", 4.0),
    ("rule_mask", True), ("rule_mask", -1), ("rule_mask", 8),
    ("format", "puzzle-box/coupled-exploration-v1"), ("unknown", 1),
    ("arrow_sites", {}), ("arrow_sites", [{"cell": [0, 0], "direction": "up"}] * 9),
    ("clue_kinds", "edge"), ("clue_kinds", ["edge", "edge"]), ("clue_kinds", [{}]),
    ("clue_kinds", ["black"]), ("clues", {}), ("clues", [0] * 33),
    ("clues", [{"type": "black", "cell": [2, 0], "black": 1}]),
    ("clues", [{"type": "arrow", "cell": [0, 0], "count": 0}]),
    ("clues", [{"type": "edge", "edge": [0, 0, 1, 1], "used": 0}]),
    ("solution", []), ("seed", True), ("environment", []),
    ("generation", {"initial_seed": 0, "attempt_limit": 1, "attempts_used": 1}),
])
def test_invalid_records_are_rejected(field, value):
    data = sample()
    data[field] = value
    with pytest.raises((ValueError, TypeError)):
        diagnostic.diagnose(data)


def test_missing_fields_yajilin_override_and_invalid_answer_coordinates():
    data = sample()
    del data["rule_mask"]
    with pytest.raises(ValueError, match="fields"):
        diagnostic.diagnose(data)
    data = sample()
    data["format"] = cli.FORMAT
    with pytest.raises(ValueError, match="fields"):
        diagnostic.diagnose(data)
    for key, values in [("black_cells", [[0, 0], [0, 0]]), ("black_cells", [[-1, 0]]),
                        ("loop_edges", [[0, 3, 0, 4]])]:
        data = sample()
        data["solution"][key] = values
        with pytest.raises(ValueError):
            diagnostic.diagnose(data)


@pytest.mark.parametrize("raw", ['{"format":1,"format":2}', '{"x":NaN}', '{"x":Infinity}',
                                 '[' * 20000 + ']' * 20000, ' ' * 65537, '\ufffd'],
                         ids=['duplicate', 'nan', 'infinity', 'deep', 'oversized', 'invalid'])
def test_strict_bounded_file_loading(tmp_path, raw):
    path = tmp_path / "input.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError):
        records.load_puzzle(path)


def test_cli_is_reproducible_and_reports_ascii_witnesses(tmp_path):
    args = [sys.executable, str(EXAMPLES / "diagnose_coupled_rules.py"), str(SAMPLE)]
    outputs = [subprocess.check_output(args + ["--json"], env={**os.environ, "PYTHONHASHSEED": seed})
               for seed in ("1", "999")]
    assert outputs[0] == outputs[1]
    data = json.loads(outputs[0])
    assert data["models_verified"] is False
    saved = tmp_path / "report.json"
    text = subprocess.check_output(args + ["--verify-models", "--output", str(saved)], text=True)
    assert "coupling | 1 | 123" in text and "non_touching | 1 | 3" in text
    assert "SAME stored clues" in text and "---" in text and "Model/oracle comparison: verified" in text
    assert json.loads(saved.read_text())["models_verified"] is True


def test_cli_preserves_input_and_existing_output_on_error(tmp_path):
    source, output = tmp_path / "puzzle.json", tmp_path / "report.json"
    source.write_text(SAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    before = source.read_bytes()
    args = [sys.executable, str(EXAMPLES / "diagnose_coupled_rules.py"), str(source)]
    result = subprocess.run(args + ["--output", str(source)], capture_output=True, text=True)
    assert result.returncode == 2 and "different files" in result.stderr
    assert source.read_bytes() == before
    output.write_text("keep", encoding="utf-8")
    source.write_text('{}', encoding="utf-8")
    result = subprocess.run(args + ["--output", str(output)], capture_output=True, text=True)
    assert result.returncode == 2 and output.read_text() == "keep"


def test_existing_generator_output_can_be_diagnosed_without_conversion(tmp_path):
    saved = tmp_path / "small-yajilin.json"
    subprocess.run([sys.executable, str(EXAMPLES / "generate_yajilin.py"), "generate", "--rows", "2",
                    "--cols", "4", "--arrow", "0", "0", "right", "--seed", "6",
                    "--output", str(saved), "--quiet"], check=True, capture_output=True)
    before = saved.read_bytes()
    output = subprocess.check_output([sys.executable, str(EXAMPLES / "diagnose_coupled_rules.py"),
                                      str(saved), "--verify-models", "--json"])
    result = json.loads(output)
    assert result["source_format"] == cli.FORMAT and result["rule_mask"] == 7
    assert result["original_answer_count"] == 1 and result["models_verified"]
    assert saved.read_bytes() == before


def test_hardlink_output_cannot_overwrite_input(tmp_path):
    source, alias = tmp_path / "puzzle.json", tmp_path / "alias.json"
    source.write_text(SAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    try:
        os.link(source, alias)
    except OSError:
        pytest.skip("Hardlink creation unavailable in this environment")
    with pytest.raises(ValueError, match="different files"):
        records.check_output(source, alias)
