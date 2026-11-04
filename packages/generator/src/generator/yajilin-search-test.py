"""Retry policy tests: attempt limits, error boundaries and recorded seeds."""

import importlib.util
import json
from pathlib import Path
import sys

import pytest

from generator import InitialCluesNotUniqueError
from puzzle import Cell
from puzzle_defs import ArrowCountClue, ArrowSite, YajilinRecipe

SCRIPT = Path(__file__).resolve().parents[4] / "examples" / "generate_yajilin.py"


@pytest.fixture
def example(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("yajilin_search_example", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_retry_keeps_recipe_and_hint_types_and_stops_at_first_success(example, monkeypatch):
    recipe = YajilinRecipe(3, 4, (ArrowSite(Cell(1, 0), "right"),), ("arrow",))
    calls = []
    expected = [ArrowCountClue(Cell(1, 0), 1)]

    def fake_generate(actual, *, seed):
        assert actual is recipe
        calls.append(seed)
        if seed < 8:
            raise InitialCluesNotUniqueError("not unique")
        return expected

    monkeypatch.setattr(example, "generate", fake_generate)
    assert example.generate_with_attempts(recipe, 6, 8) == (expected, 8, 3)
    assert calls == [6, 7, 8]


def test_exhaustion_is_bounded_and_remains_a_value_error(example, monkeypatch):
    calls = []

    def failed(recipe, *, seed):
        calls.append(seed)
        raise InitialCluesNotUniqueError("no unique clues")

    monkeypatch.setattr(example, "generate", failed)
    with pytest.raises(InitialCluesNotUniqueError, match=r"3 attempt.*6\.\.8") as error:
        example.generate_with_attempts(YajilinRecipe(3, 4), 6, 3)
    assert isinstance(error.value, ValueError)
    assert calls == [6, 7, 8]


@pytest.mark.parametrize("error", [ValueError("invalid input"), RuntimeError("infeasible base"),
                                   TypeError("bad recipe")])
def test_other_failures_are_not_retried_or_relabelled(example, monkeypatch, error):
    calls = []

    def failed(recipe, *, seed):
        calls.append(seed)
        raise error

    monkeypatch.setattr(example, "generate", failed)
    with pytest.raises(type(error)) as observed:
        example.generate_with_attempts(YajilinRecipe(3, 4), 6, 32)
    assert observed.value is error and calls == [6]


@pytest.mark.parametrize("seed,attempts", [(0, 0), (0, 33), (0, True), (-1, 1),
                                         (True, 1), (2**31-1, 2), (0, 1.5)])
def test_invalid_search_bounds_fail_before_solving(example, monkeypatch, seed, attempts):
    def unexpected(*args, **kwargs):
        pytest.fail("Invalid bounds must not start generation")

    monkeypatch.setattr(example, "generate", unexpected)
    with pytest.raises(ValueError):
        example.generate_with_attempts(YajilinRecipe(3, 4), seed, attempts)


@pytest.mark.parametrize("seed,attempts", [(2**31-1, 1), (2**31-32, 32)])
def test_last_seed_boundary_is_accepted(example, monkeypatch, seed, attempts):
    monkeypatch.setattr(example, "generate", lambda recipe, *, seed: [])
    assert example.generate_with_attempts(YajilinRecipe(2, 2), seed, attempts) == ([], seed, 1)


@pytest.mark.parametrize("damage", ["seed", "used", "limit", "extra", "boolean"])
def test_generation_metadata_is_checked_without_replaying_history(example, damage):
    data = json.loads(SCRIPT.with_name("yajilin-sample.json").read_text(encoding="utf-8"))
    data["generation"] = {"initial_seed": 4, "attempt_limit": 3, "attempts_used": 3}
    assert data["seed"] == 6
    example.read_record(data)
    if damage == "seed":
        data["seed"] = 7
    elif damage == "used":
        data["generation"]["attempts_used"] = 4
    elif damage == "limit":
        data["generation"]["attempt_limit"] = 33
    elif damage == "extra":
        data["generation"]["unknown"] = 0
    else:
        data["generation"]["attempts_used"] = True
    with pytest.raises(ValueError):
        example.read_record(data)


def test_failed_search_does_not_overwrite_an_existing_output(example, monkeypatch, tmp_path):
    path = tmp_path / "keep.json"
    path.write_text("keep", encoding="utf-8")
    calls = []

    def failed(recipe, *, seed):
        calls.append(seed)
        raise InitialCluesNotUniqueError("not unique")

    monkeypatch.setattr(example, "generate", failed)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "generate", "--hints", "arrow", "--seed", "6",
                                     "--attempts", "3", "--output", str(path), "--quiet"])
    with pytest.raises(SystemExit) as error:
        example.main()
    assert error.value.code == 2 and calls == [6, 7, 8]
    assert path.read_text(encoding="utf-8") == "keep"
