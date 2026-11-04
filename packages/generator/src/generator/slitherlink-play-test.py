from itertools import product
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

from puzzle import Edge, Vertex


SCRIPT = Path(__file__).resolve().parents[4] / "examples" / "generate_slitherlink.py"
SAMPLE = SCRIPT.with_name("slitherlink-sample.json")
# Explicit displayed order, independent of the application/grid implementation.
EDGE_ROWS = [
    [(0, 0, 0, 1), (0, 1, 0, 2)],
    [(0, 0, 1, 0), (0, 1, 1, 1), (0, 2, 1, 2)],
    [(1, 0, 1, 1), (1, 1, 1, 2)],
    [(1, 0, 2, 0), (1, 1, 2, 1), (1, 2, 2, 2)],
    [(2, 0, 2, 1), (2, 1, 2, 2)],
]


@pytest.fixture(scope="module")
def app():
    return runpy.run_path(str(SCRIPT))


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], check=False,
                          capture_output=True, text=True, timeout=45)


def _text(edges: set[tuple[int, ...]]) -> str:
    return "/".join("".join(str(int(e in edges)) for e in row) for row in EDGE_ROWS)


def _cycle(edges: set[tuple[int, ...]]) -> bool:
    neighbors: dict[tuple[int, ...], set[tuple[int, ...]]] = {}
    for edge in edges:
        a, b = edge[:2], edge[2:]
        neighbors.setdefault(a, set()).add(b)
        neighbors.setdefault(b, set()).add(a)
    if not neighbors or any(len(ns) != 2 for ns in neighbors.values()):
        return False
    seen = set()
    todo = [next(iter(neighbors))]
    while todo:
        vertex = todo.pop()
        if vertex not in seen:
            seen.add(vertex)
            todo.extend(neighbors[vertex])
    return seen == set(neighbors)


def _satisfies(edges: set[tuple[int, ...]], record: dict) -> bool:
    if not _cycle(edges) or record["loop_length"] is not None and len(edges) != record["loop_length"]:
        return False
    for clue in record["clues"]:
        if clue["type"] == "edge":
            if int(tuple(clue["edge"]) in edges) != clue["used"]:
                return False
        else:
            r, c = clue["row"], clue["col"]
            corners = {(r, c), (r, c + 1), (r + 1, c), (r + 1, c + 1)}
            if sum(e[:2] in corners and e[2:] in corners for e in edges) != clue["count"]:
                return False
    return True


def test_all_small_edge_inputs_map_to_the_displayed_coordinates(app):
    coordinates = [e for row in EDGE_ROWS for e in row]
    for bits in product((0, 1), repeat=12):
        edges = {e for e, bit in zip(coordinates, bits) if bit}
        parsed = app["_parse_answer"](_text(edges), 2, 2)
        expected = {Edge(Vertex(*e[:2]), Vertex(*e[2:])) for e in edges}
        assert parsed == expected


def test_answer_check_agrees_with_independent_loop_and_clue_checks(app):
    record = json.loads(SAMPLE.read_text(encoding="utf-8"))
    coordinates = [e for row in EDGE_ROWS for e in row]
    loops = [{e for e, bit in zip(coordinates, bits) if bit} for bits in product((0, 1), repeat=12)]
    loops = [edges for edges in loops if _cycle(edges)]
    assert len(loops) == 13
    stored = {tuple(e) for e in record["solution"]}
    candidates = loops + [set(), set(coordinates)] + [stored ^ {e} for e in coordinates]
    assert sum(_satisfies(edges, record) for edges in loops) == 1
    for edges in candidates:
        assert app["check_answer"](record, _text(edges)) == _satisfies(edges, record)


@pytest.mark.parametrize("bits", product((0, 1), repeat=4))
def test_zero_clue_puzzle_accepts_only_the_complete_nonempty_loop(app, bits):
    record = {"format": "puzzle-box/slitherlink-v1", "rows": 1, "cols": 1,
              "loop_length": None, "clue_kinds": ["cell-count", "edge"], "clues": [],
              "solution": [[0, 0, 0, 1], [0, 0, 1, 0], [0, 1, 1, 1], [1, 0, 1, 1]]}
    text = f"{bits[0]}/{bits[1]}{bits[2]}/{bits[3]}"
    assert app["check_answer"](record, text) == all(bits)


@pytest.mark.parametrize("rows,cols,text,expected", [
    (1, 3, "101/0101/010", [(0, 0, 0, 1), (0, 2, 0, 3), (0, 1, 1, 1), (0, 3, 1, 3), (1, 1, 1, 2)]),
    (3, 1, "1/10/0/01/1/10/0", [(0, 0, 0, 1), (0, 0, 1, 0), (1, 1, 2, 1), (2, 0, 2, 1), (2, 0, 3, 0)]),
])
def test_rectangular_boards_keep_horizontal_and_vertical_rows_distinct(app, rows, cols, text, expected):
    assert app["_parse_answer"](text, rows, cols) == {Edge(Vertex(a, b), Vertex(c, d)) for a, b, c, d in expected}


@pytest.mark.parametrize("text", ["", "11/111/11", "111/11/111/11/111", "11/11/11/111/11",
                                    "??/???/??/???/??", "1x/111/11/111/11", "11/111/11/111/１２"])
def test_incomplete_or_malformed_answer_is_an_input_error(app, text):
    with pytest.raises(ValueError):
        app["_parse_answer"](text, 2, 2)


def test_answer_can_include_spaces_for_readability(app):
    assert app["_parse_answer"](" 0 1 / 0 1 1 / 1 0 / 1 0 1 / 1 1 ", 2, 2) == app["_parse_answer"]("01/011/10/101/11", 2, 2)


def test_show_template_contains_only_explicit_edge_givens(app):
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    assert "Answer template: ??/???/??/??1/??" in app["show"](sample)
    assert "Answer template:" not in app["show"](sample, reveal=True)
    # A zero-valued edge clue is distinct from both an unknown edge and a cell number.
    record = {"format": "puzzle-box/slitherlink-v1", "rows": 1, "cols": 2,
              "loop_length": 4, "clue_kinds": ["edge"],
              "clues": [{"type": "edge", "edge": [0, 1, 0, 2], "used": 0}],
              "solution": [[0, 0, 0, 1], [0, 0, 1, 0], [0, 1, 1, 1], [1, 0, 1, 1]]}
    assert "Answer template: ?0/???/??" in app["show"](record)


@pytest.mark.parametrize("damage", ["solution", "ambiguous", "contradictory", "redundant"])
def test_check_does_not_trust_corrupted_or_nonunique_saved_answers(tmp_path, damage):
    record = json.loads(SAMPLE.read_text(encoding="utf-8"))
    if damage == "solution":
        record["solution"] = []
    elif damage == "ambiguous":
        record["clues"] = []
    elif damage == "contradictory":
        record["clues"][0]["count"] = 4
    else:
        record["clues"].append(record["clues"][0])
    path = tmp_path / "corrupt.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    before = path.read_bytes()
    checked = _cli("check", str(path), "--answer", _text({tuple(e) for e in record["solution"]}))
    assert checked.returncode == 2 and "Stored" in checked.stderr
    assert not checked.stdout and "Traceback" not in checked.stderr
    assert path.read_bytes() == before


def test_generated_puzzle_can_be_shown_and_checked_without_spoilers_or_file_changes(tmp_path):
    path = tmp_path / "loop.json"
    made = _cli("generate", "--loop-length", "8", "--seed", "2", "--output", str(path), "--quiet")
    assert made.returncode == 0 and not made.stdout, made.stderr
    before = path.read_bytes()
    record = json.loads(before)
    shown = _cli("show", str(path))
    assert shown.returncode == 0 and "Answer template: ??/???/??/??1/??" in shown.stdout
    correct = _cli("check", str(path), "--answer", _text({tuple(e) for e in record["solution"]}))
    assert correct.returncode == 0 and correct.stdout.strip() == "Correct. All rules and clues are satisfied."
    wrong = _cli("check", str(path), "--answer", "00/000/00/000/00")
    assert wrong.returncode == 1 and wrong.stdout.strip() == "Not correct. Check the rules and given clues."
    partial = _cli("check", str(path), "--answer", "??/???/??/??1/??")
    assert partial.returncode == 2 and "Fill every edge" in partial.stderr and not partial.stdout
    verified = _cli("verify", str(path))
    assert verified.returncode == 0 and json.loads(verified.stdout)["unique"]
    assert path.read_bytes() == before
