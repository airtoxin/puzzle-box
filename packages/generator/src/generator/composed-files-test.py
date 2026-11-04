"""Data-only component round trips, independent answers and file boundaries."""

from copy import deepcopy
import importlib
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from generator import with_constraints
from puzzle import at_least_one
from puzzle_defs import BlackCount, ConnectedWhite, ShadingRecipe

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    codec = importlib.import_module("composed_shading_recipe")
    demo = importlib.import_module("generate_composed_shading")
    legacy = importlib.import_module("generate_shading")


def _record():
    return json.loads((EXAMPLES / "composed-shading-recipe-sample.json").read_text(encoding="utf-8"))


def _connected(bits, color, rows=2, cols=3):
    cells = {i for i, value in enumerate(bits) if value == color}
    if not cells:
        return True
    seen, todo = set(), [min(cells)]
    while todo:
        i = todo.pop()
        if i not in seen:
            seen.add(i)
            r, c = divmod(i, cols)
            todo.extend(j for j in cells - seen if abs(j//cols-r) + abs(j%cols-c) == 1)
    return seen == cells


def _answers(recipe):
    puzzle = recipe.create_empty()
    cells = puzzle.board.cells
    result = set()
    while (solution := puzzle.solve()) is not None:
        bits = tuple(solution.value(puzzle.black[c]) for c in cells)
        assert bits not in result  # Internal connected witnesses are not answers.
        result.add(bits)
        puzzle.add(at_least_one(puzzle.black[c] != bit for c, bit in zip(cells, bits)))
    return result


def test_two_component_round_trip_matches_all_64_boards_and_changes_base():
    recipe = with_constraints(ShadingRecipe(2, 3, (ConnectedWhite(),), ("cell", "row-count", "column-count")),
                              codec.CellCount("black", 2), codec.ConnectedCells("black"))
    data = codec.recipe_record(recipe)
    assert data == _record()
    restored = codec.read_recipe(json.loads(json.dumps(data)))
    assert codec.recipe_record(restored) == data
    oracle = {bits for bits in product((0, 1), repeat=6)
              if sum(bits) == 2 and _connected(bits, 1) and _connected(bits, 0)}
    assert len(oracle) == 6
    assert _answers(restored) == _answers(recipe) == oracle
    base = {bits for bits in product((0, 1), repeat=6) if 0 in bits and _connected(bits, 0)}
    assert oracle < base


def test_white_component_semantics_match_existing_builtins():
    recipe = with_constraints(ShadingRecipe(2, 2, ()), codec.CellCount("white", 2), codec.ConnectedCells("white"))
    restored = codec.read_recipe(codec.recipe_record(recipe))
    direct = ShadingRecipe(2, 2, (BlackCount(2), ConnectedWhite()))
    expected = {bits for bits in product((0, 1), repeat=4) if sum(bits) == 2 and _connected(bits, 0, 2, 2)}
    assert len(expected) == 4
    assert _answers(restored) == _answers(direct) == expected


@pytest.mark.parametrize("color", ["black", "white"])
def test_empty_selected_color_has_explicit_semantics(color):
    recipe = with_constraints(ShadingRecipe(1, 1, ()), codec.CellCount(color, 0),
                              codec.ConnectedCells(color, False))
    assert len(_answers(codec.read_recipe(codec.recipe_record(recipe)))) == 1
    strict = with_constraints(recipe.base, codec.CellCount(color, 0), codec.ConnectedCells(color, True))
    assert _answers(codec.read_recipe(codec.recipe_record(strict))) == set()


@pytest.mark.parametrize("seed", [0, 1])
def test_generated_saved_problem_is_independently_unique_and_irreducible(seed):
    record = demo.generate_record(_record(), seed=seed)
    assert demo.verify(json.loads(json.dumps(record)))["valid"]
    answers = {bits for bits in product((0, 1), repeat=6)
               if sum(bits) == 2 and _connected(bits, 1) and _connected(bits, 0)}

    def matches(hints):
        def satisfied(bits, clue):
            if clue["type"] == "cell":
                return bits[clue["row"]*3+clue["col"]] == clue["value"]
            if clue["type"] == "row-count":
                return sum(bits[clue["row"]*3:clue["row"]*3+3]) == clue["count"]
            return sum(bits[clue["col"]::3]) == clue["count"]
        return [bits for bits in answers if all(satisfied(bits, c) for c in hints)]

    clues = record["clues"]
    assert matches(clues) == [tuple(v for row in record["solution"] for v in row)]
    assert all(len(matches(clues[:i]+clues[i+1:])) > 1 for i in range(len(clues)))
    # Dropping the wrapper when saving would lose the defining conditions.
    lost = deepcopy(record)
    lost["recipe"]["components"] = []
    with pytest.raises(ValueError, match="not uniquely"):
        demo.verify(lost)
    wrong = deepcopy(record)
    wrong["solution"][0][0] ^= 1
    with pytest.raises(ValueError, match="does not match"):
        demo.verify(wrong)
    with pytest.raises(ValueError, match="Unsupported puzzle format"):
        legacy.verify(record)


def test_order_duplicates_and_empty_components_are_preserved():
    record = _record()
    record["components"] += [deepcopy(record["components"][0])]
    assert codec.recipe_record(codec.read_recipe(record)) == record
    record["components"] = []
    assert codec.recipe_record(codec.read_recipe(record)) == record


@pytest.mark.parametrize("component", [
    None, [], {}, {"id": "cell-count/v2", "color": "black", "count": 2},
    {"id": "cell-count/v1", "color": "black", "count": True},
    {"id": "cell-count/v1", "color": "black", "count": 2.0},
    {"id": "cell-count/v1", "color": "black", "count": -1},
    {"id": "cell-count/v1", "color": "black", "count": 7},
    {"id": "cell-count/v1", "color": [], "count": 2},
    {"id": "cell-count/v1", "color": "edges", "count": 2},
    {"id": "connected-cells/v1", "color": "white", "nonempty": 1},
    {"id": "connected-cells/v1", "color": "white"},
    {"id": "connected-cells/v1", "color": "black", "nonempty": True, "module": "payload"},
    {"id": "__import__('os').system('payload')"},
    {"id": "external", "module": "payload", "callable": "execute"},
])
def test_unknown_or_invalid_components_are_rejected(component):
    record = _record()
    record["components"] = [component]
    with pytest.raises(ValueError):
        codec.read_recipe(record)


@pytest.mark.parametrize("field,value", [
    ("format", "puzzle-box/composed-shading-recipe-v2"), ("components", {}),
    ("components", "connected-cells/v1"), ("components", [{}] * 9),
    ("base", {}), ("base", {"format": "puzzle-box/slitherlink-v1"}),
])
def test_invalid_recipe_schema(field, value):
    record = _record()
    record[field] = value
    with pytest.raises(ValueError):
        codec.read_recipe(record)


def test_file_and_board_bounds(tmp_path):
    record = _record()
    record["base"]["rows"] = 4
    with pytest.raises(ValueError, match="9 cells"):
        codec.read_recipe(record)
    record = _record()
    record["base"]["rows"] = 3
    record["components"] *= 4
    assert len(codec.read_recipe(record).builders) == 8
    raw = json.dumps(record).encode()
    file = tmp_path / "recipe.json"
    file.write_bytes(raw + b" " * (65536-len(raw)))
    assert len(codec.load_recipe(file).builders) == 8
    file.write_bytes(file.read_bytes() + b" ")
    with pytest.raises(ValueError, match="65536"):
        codec.load_recipe(file)


@pytest.mark.parametrize("data", [None, [], {}, {**_record(), "module": "payload"},
                                  {k: v for k, v in _record().items() if k != "components"}])
def test_recipe_root_must_match_exactly(data):
    with pytest.raises(ValueError):
        codec.read_recipe(data)


def test_float_overflow_count_is_rejected(tmp_path):
    raw = json.dumps(_record()).replace('"count": 2', '"count": 1e400')
    file = tmp_path / "overflow.json"
    file.write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError):
        codec.load_recipe(file)


@pytest.mark.parametrize("raw", [
    b'{"format":"x","format":"y"}', b'{"base":{"rows":1,"rows":2}}',
    b'{"count":NaN}', b'{"count":Infinity}', b'\xff', b'{',
    b'[' * 20000 + b']' * 20000,
], ids=["duplicate-root", "duplicate-nested", "nan", "infinity", "encoding", "syntax", "deep"])
def test_invalid_json_is_a_value_error(tmp_path, raw):
    file = tmp_path / "bad.json"
    file.write_bytes(raw)
    with pytest.raises(ValueError):
        codec.load_recipe(file)


def test_export_refuses_unknown_code_and_semantic_subclasses_without_calling_them():
    def unknown(puzzle):
        pytest.fail("Serialization must never execute an unknown builder")
    class ChangedCount(codec.CellCount):
        pass
    class ChangedBase(ShadingRecipe):
        pass
    class ChangedRule(ConnectedWhite):
        pass
    base = ShadingRecipe(1, 1, ())
    for recipe in [with_constraints(base, unknown), with_constraints(base, ChangedCount("black", 0)),
                   with_constraints(ChangedBase(1, 1, ())), with_constraints(with_constraints(base)),
                   with_constraints(ShadingRecipe(1, 1, (ChangedRule(),)))]:
        with pytest.raises(ValueError):
            codec.recipe_record(recipe)


@pytest.fixture(scope="module")
def artifact():
    return demo.generate_record(_record())


@pytest.mark.parametrize("field,value", [
    ("format", "puzzle-box/composed-shading-v2"), ("seed", True), ("seed", -1),
    ("seed", 2**31), ("clues", {}), ("clues", [None]), ("clues", [{}] * 12),
    ("solution", {}), ("solution", [[True, 0, 0], [0, 0, 1]]),
    ("solution", [[0, 1], [0, 0]]),
    ("clues", [{"type": "cell", "row": 99, "col": 0, "value": 0}]),
])
def test_invalid_saved_problem(artifact, field, value):
    record = deepcopy(artifact)
    record[field] = value
    with pytest.raises(ValueError):
        demo.verify(record)


def test_empty_clues_are_an_array_and_valid_when_components_fix_the_answer():
    recipe = with_constraints(ShadingRecipe(1, 1, (), ()), codec.CellCount("black", 0),
                              codec.ConnectedCells("white"))
    record = demo.generate_record(codec.recipe_record(recipe))
    assert record["clues"] == [] and record["solution"] == [[0]]
    assert demo.verify(record)["clue_count"] == 0
    for bad in [None, [], {**record, "valid": True}, {k: v for k, v in record.items() if k != "recipe"}]:
        with pytest.raises(ValueError):
            demo.verify(bad)


def _cli(*args, hash_seed="0"):
    return subprocess.run([sys.executable, str(EXAMPLES / "generate_composed_shading.py"), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8", timeout=30,
                          env={**os.environ, "PYTHONHASHSEED": hash_seed})


def test_cli_generate_reload_reproduce_and_preserve_files(tmp_path):
    recipe = EXAMPLES / "composed-shading-recipe-sample.json"
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    for output, hash_seed in [(first, "0"), (second, "71")]:
        result = _cli("generate", "--recipe", recipe, "--seed", 0, "--output", output, hash_seed=hash_seed)
        assert result.returncode == 0, result.stderr
    assert first.read_bytes() == second.read_bytes()
    result = _cli("verify", first)
    assert result.returncode == 0 and json.loads(result.stdout)["unique"], result.stderr
    before = first.read_bytes()
    result = _cli("generate", "--recipe", recipe, "--output", first)
    assert result.returncode == 2 and first.read_bytes() == before
    result = _cli("generate", "--recipe", first, "--output", first)
    assert result.returncode == 2 and first.read_bytes() == before
    bad = tmp_path / "bad.json"
    bad.write_text('{"format":"external","module":"payload"}')
    output = tmp_path / "never-created.json"
    result = _cli("generate", "--recipe", bad, "--output", output)
    assert result.returncode == 2 and "Traceback" not in result.stderr and not output.exists()


@pytest.mark.parametrize("mode", ["contradictory", "ambiguous"])
def test_generation_failure_never_creates_output(tmp_path, mode):
    record = _record()
    record["base"]["rules"] = []
    record["base"]["clue_kinds"] = []
    record["components"] = [{"id": "cell-count/v1", "color": "black", "count": 2}]
    if mode == "contradictory":
        record["components"].append({"id": "cell-count/v1", "color": "black", "count": 0})
    recipe, output = tmp_path / "recipe.json", tmp_path / "puzzle.json"
    recipe.write_text(json.dumps(record), encoding="utf-8")
    result = _cli("generate", "--recipe", recipe, "--output", output)
    assert result.returncode == 2 and "Traceback" not in result.stderr and not output.exists()
    assert ("Initial clues" if mode == "ambiguous" else "Failed to generate") in result.stderr
