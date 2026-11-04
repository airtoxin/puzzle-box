from itertools import product
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[4] / "examples" / "generate_shading.py"
SAMPLES = (SCRIPT.with_name("shading-sample.json"), SCRIPT.with_name("shading-mixed-sample.json"))


@pytest.fixture(scope="module")
def app():
    # run_path does not add the standalone script's sibling helpers to sys.path.
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(SCRIPT.parent))
        return runpy.run_path(str(SCRIPT))


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], check=False, capture_output=True,
                          text=True, timeout=45)


def _board(text: str) -> list[list[str]]:
    return [line.split("|", 1)[1].split() for line in text.splitlines() if "| " in line]


def _answer_text(values: list[list[int]]) -> str:
    return "/".join("".join("#" if value else "." for value in row) for row in values)


@pytest.mark.parametrize("path,expected", [
    (SAMPLES[0], [["?", "?", "?"], ["?", "?", "?"], [".", "?", "#"]]),
    (SAMPLES[1], [["?", "#", "?", "?"], ["?", "?", "?", "?"], ["?", "?", "?", "?"]]),
])
def test_show_renders_only_givens_and_reveals_solution_only_on_request(path, expected):
    before = path.read_bytes()
    record = json.loads(before)
    shown = _cli("show", str(path))
    assert shown.returncode == 0, shown.stderr
    assert _board(shown.stdout) == expected
    assert "Answer template: " + "/".join("".join(row) for row in expected) in shown.stdout
    assert "Exactly 3 cells are black." in shown.stdout
    assert "Black cells must not share an edge." in shown.stdout
    assert "Displayed row and column numbers start at 1." in shown.stdout
    revealed = _cli("show", str(path), "--solution")
    assert revealed.returncode == 0, revealed.stderr
    assert _board(revealed.stdout) == [["#" if v else "." for v in row] for row in record["solution"]]
    assert revealed.stdout.startswith("Solution:")
    assert "Answer template:" not in revealed.stdout
    assert path.read_bytes() == before


def test_zero_count_is_visible_and_different_from_a_missing_hint(app):
    record = {"format": "puzzle-box/shading-v2", "rows": 2, "cols": 3,
              "rules": [{"type": "count", "count": 3}], "clue_kinds": ["row-count"],
              "clues": [{"type": "row-count", "row": 0, "count": 0}],
              "solution": [[0, 0, 0], [1, 1, 1]]}
    shown = app["show"](record)
    assert "  1     0 |" in shown
    assert "  2     - |" in shown
    assert "      count  -  -  -" in shown
    assert _board(shown) == [["?", "?", "?"], ["?", "?", "?"]]


def test_two_digit_counts_and_indices_fit_the_text_grid(app):
    record = {"format": "puzzle-box/shading-v2", "rows": 1, "cols": 12, "rules": [],
              "clue_kinds": ["row-count"], "clues": [{"type": "row-count", "row": 0, "count": 12}],
              "solution": [[1] * 12]}
    shown = app["show"](record)
    assert "10 11 12" in shown
    assert "  1    12 |" in shown
    assert "No additional rules." in shown
    assert _board(shown) == [["?"] * 12]


def test_optional_rule_parameters_are_explained_to_the_player(app):
    record = {"format": "puzzle-box/shading-v1", "rows": 1, "cols": 1,
              "rules": [{"type": "non-touching", "diagonal": True},
                        {"type": "connected-white", "nonempty": False}, {"type": "no-white-2x2"}],
              "clues": [[0, 0, 1]], "solution": [[1]]}
    shown = app["show"](record)
    assert "an edge or a corner" in shown
    assert "zero white cells are allowed" in shown
    assert "Every 2x2 block contains at least one black cell." in shown
    normal = app["show"](json.loads(SAMPLES[0].read_text(encoding="utf-8")))
    assert "at least one must be white" in normal


@pytest.mark.parametrize("bits", product([0, 1], repeat=4))
def test_answer_check_matches_an_independent_complete_board_check(app, bits):
    record = {"format": "puzzle-box/shading-v1", "rows": 2, "cols": 2,
              "rules": [{"type": "count", "count": 2}, {"type": "non-touching", "diagonal": False}],
              "clues": [[0, 0, 1]], "solution": [[1, 0], [0, 1]]}
    expected = (sum(bits) == 2 and bits[0] == 1
                and all(not (bits[a] and bits[b]) for a, b in [(0, 1), (0, 2), (1, 3), (2, 3)]))
    assert app["check_answer"](record, _answer_text([list(bits[:2]), list(bits[2:])])) == expected


@pytest.mark.parametrize("path", SAMPLES)
def test_check_reports_correct_incorrect_and_incomplete_answers_without_spoilers(path):
    before = path.read_bytes()
    record = json.loads(before)
    correct = _cli("check", str(path), "--answer", _answer_text(record["solution"]))
    assert correct.returncode == 0
    assert correct.stdout.strip() == "Correct. All rules and clues are satisfied."
    record["solution"][0][0] ^= 1
    wrong = _cli("check", str(path), "--answer", _answer_text(record["solution"]))
    assert wrong.returncode == 1
    assert wrong.stdout.strip() == "Not correct. Check the rules and given clues."
    incomplete = "/".join("?" * record["cols"] for _ in range(record["rows"]))
    checked = _cli("check", str(path), "--answer", incomplete)
    assert checked.returncode == 2 and "Fill every cell" in checked.stderr
    assert not checked.stdout
    assert path.read_bytes() == before


@pytest.mark.parametrize("answer", ["", "..", "../..../..", "../../..", "##/0.", "??/??"])
def test_malformed_or_partial_answer_is_an_input_error(app, answer: str):
    with pytest.raises(ValueError):
        app["_parse_answer"](answer, 2, 2)


def test_spaces_in_answer_are_optional(app):
    assert app["_parse_answer"](" . # / # . ", 2, 2) == [[0, 1], [1, 0]]


@pytest.mark.parametrize("command", ["show", "check"])
@pytest.mark.parametrize("corruption", ["solution", "clues"])
def test_play_commands_refuse_unverified_artifacts(tmp_path: Path, command: str, corruption: str):
    record = json.loads(SAMPLES[0].read_text(encoding="utf-8"))
    if corruption == "solution":
        record["solution"][0][0] ^= 1
    else:
        record["clues"] = []
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    args = [command, str(path)]
    if command == "check":
        # Matching a corrupt stored answer must not be accepted as correct.
        args.extend(["--answer", _answer_text(record["solution"])])
    result = _cli(*args)
    assert result.returncode == 2
    assert not result.stdout
    assert "Stored" in result.stderr and "Traceback" not in result.stderr


def test_generate_display_and_answer_check_end_to_end(tmp_path: Path):
    path = tmp_path / "play.json"
    generated = _cli("generate", "--hints", "cell", "row-count", "column-count", "--seed", "17",
                     "--output", str(path), "--quiet")
    assert generated.returncode == 0, generated.stderr
    assert not generated.stdout
    record = json.loads(path.read_text(encoding="utf-8"))
    assert _cli("show", str(path)).returncode == 0
    assert _cli("check", str(path), "--answer", _answer_text(record["solution"])).returncode == 0


def test_quiet_generation_requires_an_output_file():
    generated = _cli("generate", "--quiet")
    assert generated.returncode == 2
    assert "Use --output with --quiet" in generated.stderr
    assert not generated.stdout
