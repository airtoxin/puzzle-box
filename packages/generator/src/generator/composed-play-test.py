"""Play uses the complete composed semantics, never a stripped base record."""

from copy import deepcopy
from dataclasses import dataclass
import importlib
from itertools import product
import json
from pathlib import Path
import subprocess
import sys

import pytest

from generator import with_constraints
from puzzle_defs import BlackCount, ShadingRecipe

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    app = importlib.import_module("generate_composed_shading")
    codec = importlib.import_module("composed_shading_recipe")
    registry_api = importlib.import_module("component_registry")
    custom = importlib.import_module("custom_row_band")


def _recipe(name):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def _custom_record():
    return {"format": app.FORMAT, "recipe": _recipe("custom-row-band-recipe.json"), "seed": 0,
            "clues": [{"type": "cell", "row": 0, "col": 0, "value": 1},
                      {"type": "column-count", "col": 2, "count": 1}],
            "solution": [[1, 0, 0], [0, 0, 1]]}


def _answer(bits):
    return "/".join("".join("#" if v else "." for v in bits[r:r+3]) for r in (0, 3))


def _board(text):
    return [line.split("|", 1)[1].split() for line in text.splitlines() if "| " in line]


def _cli(script, *args):
    return subprocess.run([sys.executable, str(EXAMPLES / script), *map(str, args)],
                          capture_output=True, text=True, timeout=30)


def test_builtin_play_shows_count_givens_and_every_rule_without_answer():
    data = app.generate_record(_recipe("composed-shading-recipe-sample.json"), seed=0)
    before = deepcopy(data)
    shown = app.show(data)
    expected = [["?"] * 3 for _ in range(2)]
    for clue in data["clues"]:
        if clue["type"] == "cell":
            expected[clue["row"]][clue["col"]] = "#" if clue["value"] else "."
    assert _board(shown) == expected
    assert "Exactly 2 cells are black." in shown
    assert "All white cells connect through edges; at least one must be white." in shown
    assert "All black cells connect through edges; at least one must be black." in shown
    assert "Answer template:" in shown
    revealed = app.show(data, reveal=True)
    assert _board(revealed) == [["#" if v else "." for v in row] for row in data["solution"]]
    assert revealed.startswith("Solution:") and "Answer template:" not in revealed
    assert data == before


def test_zero_row_count_is_shown_as_a_clue():
    # Fixed, uniquely solvable record: relying on a seed to generate this clue
    # ties the display test to solver/model search order.
    data = {"format": app.FORMAT, "recipe": _recipe("composed-shading-recipe-sample.json"), "seed": 0,
            "clues": [{"type": "row-count", "row": 0, "count": 0},
                      {"type": "column-count", "col": 0, "count": 1}],
            "solution": [[0, 0, 0], [1, 1, 0]]}
    assert app.verify(data) == {"valid": True, "unique": True, "irreducible": True, "clue_count": 2}
    assert "  1     0 |" in app.show(data)


def test_custom_play_keeps_component_identity_and_all_parameter_values():
    data = _custom_record()
    before = deepcopy(data)
    shown = app.show(data, registry=custom.COMPONENTS)
    assert _board(shown) == [["#", "?", "?"], ["?", "?", "?"]]
    assert "Answer template: #??/???" in shown
    assert "example/row-black-band/v1" in shown
    assert '"minimum": 0' in shown and '"maximum": 1' in shown
    assert "Each row contains between 0 and 1 black cells (inclusive)." in shown
    assert data == before


def test_checks_match_independent_64_board_oracle_and_retain_the_custom_rule():
    data = _custom_record()
    def valid(bits):
        whites = {i for i, v in enumerate(bits) if not v}
        seen, todo = set(), list(whites)[:1]
        while todo:
            i = todo.pop()
            if i not in seen:
                seen.add(i)
                todo.extend(j for j in whites-seen if abs(i//3-j//3)+abs(i%3-j%3) == 1)
        return (sum(bits) == 2 and seen == whites and bool(whites) and
                sum(bits[:3]) <= 1 and sum(bits[3:]) <= 1 and bits[0] == 1 and bits[2]+bits[5] == 1)
    expected = [bits for bits in product((0, 1), repeat=6) if valid(bits)]
    assert expected == [(1, 0, 0, 0, 0, 1)]
    for bits in product((0, 1), repeat=6):
        assert app.check_answer(data, _answer(bits), registry=custom.COMPONENTS) == valid(bits)
    # This board satisfies the base, cell count and clues but violates RowBlackBand.
    assert not app.check_answer(data, "#.#/...", registry=custom.COMPONENTS)
    stripped = deepcopy(data)
    stripped["recipe"]["components"].pop()
    with pytest.raises(ValueError, match="not uniquely"):
        app.show(stripped, registry=custom.COMPONENTS)


@pytest.mark.parametrize("operation", ["show", "reveal", "check"])
@pytest.mark.parametrize("corruption", ["answer", "clues", "component"])
def test_play_refuses_corrupt_certificates_even_if_the_candidate_matches_them(operation, corruption):
    data = _custom_record()
    if corruption == "answer":
        data["solution"] = [[1, 0, 1], [0, 0, 0]]
    elif corruption == "clues":
        data["clues"] = []
    else:
        data["recipe"]["components"][1]["maximum"] = 0
    before = deepcopy(data)
    with pytest.raises(ValueError, match="Stored"):
        if operation == "check":
            app.check_answer(data, _answer(sum(data["solution"], [])), registry=custom.COMPONENTS)
        else:
            app.show(data, reveal=operation == "reveal", registry=custom.COMPONENTS)
    assert data == before


@pytest.mark.parametrize("answer", ["", "#../..", "#../..#/.#.", "#??/???", "100/001"])
def test_malformed_or_partial_answers_are_input_errors(answer):
    with pytest.raises(ValueError, match="Answer must|Fill every cell"):
        app.check_answer(_custom_record(), answer, registry=custom.COMPONENTS)


@pytest.mark.parametrize("script,recipe", [("generate_composed_shading.py", "composed-shading-recipe-sample.json"),
                                          ("custom_row_band.py", "custom-row-band-recipe.json")])
def test_generate_show_reveal_and_answer_cli_without_spoilers_or_file_changes(tmp_path, script, recipe):
    output = tmp_path / "puzzle.json"
    made = _cli(script, "generate", "--recipe", EXAMPLES / recipe, "--seed", 0, "--output", output)
    assert made.returncode == 0, made.stderr
    before = output.read_bytes()
    data = json.loads(before)
    answer = _answer(sum(data["solution"], []))
    shown = _cli(script, "show", output)
    assert shown.returncode == 0 and "Answer template:" in shown.stdout, shown.stderr
    revealed = _cli(script, "show", output, "--solution")
    assert revealed.returncode == 0 and revealed.stdout.startswith("Solution:"), revealed.stderr
    good = _cli(script, "check", output, "--answer", answer)
    assert good.returncode == 0 and good.stdout.strip() == "Correct. All rules and clues are satisfied."
    bad = _cli(script, "check", output, "--answer", "###/###")
    assert bad.returncode == 1 and bad.stdout.strip() == "Not correct. Check the rules and given clues."
    partial = _cli(script, "check", output, "--answer", "???/???")
    assert partial.returncode == 2 and not partial.stdout and "Traceback" not in partial.stderr
    assert output.read_bytes() == before


@pytest.mark.parametrize("command", ["show", "check"])
def test_default_cli_never_imports_custom_components(tmp_path, command):
    output = tmp_path / "custom.json"
    output.write_text(json.dumps(_custom_record()), encoding="utf-8")
    args = [command, str(output)] + (["--answer", "#../..#"] if command == "check" else [])
    run = _cli("generate_composed_shading.py", *args)
    assert run.returncode == 2 and not run.stdout and "Unknown component" in run.stderr


def test_custom_parameter_control_characters_are_escaped_in_rule_display():
    @dataclass(frozen=True)
    class Label:
        text: str
        def __call__(self, puzzle):
            return []
    value = "note\n\x1b[2J"
    registry = codec.BUILTIN_COMPONENTS.with_component("example/label/v1", Label,
                                                      text=registry_api.ChoiceParam((value,)))
    recipe = with_constraints(ShadingRecipe(1, 1, (BlackCount(0),)), Label(value))
    data = app.generate_record(codec.recipe_record(recipe, registry=registry), registry=registry)
    shown = app.show(data, registry=registry)
    assert "\x1b" not in shown and value not in shown
    assert json.dumps(value) in shown
