from functools import lru_cache
from itertools import product
import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

from generator import reduce_clues
from puzzle import Cell, Edge, Vertex
from puzzle_defs import EdgeStateClue, YajilinRecipe


SCRIPT = Path(__file__).resolve().parents[4] / "examples" / "generate_yajilin.py"
SAMPLE = SCRIPT.with_name("yajilin-sample.json")


@pytest.fixture(scope="module")
def app():
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(SCRIPT.parent))
        return runpy.run_path(str(SCRIPT))


def _cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], text=True, capture_output=True, timeout=45)


def _edges(rows, cols):
    return ([(r, c, r, c + 1) for r in range(rows) for c in range(cols - 1)]
            + [(r, c, r + 1, c) for r in range(rows - 1) for c in range(cols)])


def _cycle(edges):
    adjacent = {}
    for e in edges:
        a, b = e[:2], e[2:]
        adjacent.setdefault(a, set()).add(b)
        adjacent.setdefault(b, set()).add(a)
    if not adjacent or any(len(ns) != 2 for ns in adjacent.values()):
        return False
    seen, todo = set(), [next(iter(adjacent))]
    while todo:
        vertex = todo.pop()
        if vertex not in seen:
            seen.add(vertex)
            todo.extend(adjacent[vertex])
    return seen == set(adjacent)


@lru_cache(maxsize=None)
def _cycles(rows, cols):
    candidates = _edges(rows, cols)
    loops = []
    for bits in product((0, 1), repeat=len(candidates)):
        chosen = frozenset(e for e, bit in zip(candidates, bits) if bit)
        if _cycle(chosen):
            loops.append(chosen)
    return loops


def _satisfies(record, black, edges):
    blocked = {tuple(s["cell"]) for s in record["arrow_sites"]}
    ordinary = {(r, c) for r in range(record["rows"]) for c in range(record["cols"])} - blocked
    visited = {v for e in edges for v in (e[:2], e[2:])}
    if not _cycle(edges) or visited & blocked or black != ordinary - visited:
        return False
    if any(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1 for a in black for b in black):
        return False
    directions = {tuple(s["cell"]): s["direction"] for s in record["arrow_sites"]}
    for clue in record["clues"]:
        if clue["type"] == "edge":
            if int(tuple(clue["edge"]) in edges) != clue["used"]:
                return False
        elif clue["type"] == "black":
            if int(tuple(clue["cell"]) in black) != clue["black"]:
                return False
        else:
            r, c = clue["cell"]
            d = directions[r, c]
            count = sum((d == "right" and a == r and b > c) or (d == "left" and a == r and b < c)
                        or (d == "down" and b == c and a > r) or (d == "up" and b == c and a < r)
                        for a, b in black)
            if count != clue["count"]:
                return False
    return True


def _texts(record, black, edges):
    rows, cols = record["rows"], record["cols"]
    sites = {tuple(s["cell"]) for s in record["arrow_sites"]}
    cells = "/".join("".join("@" if (r, c) in sites else "#" if (r, c) in black else "."
                            for c in range(cols)) for r in range(rows))
    parts = []
    for r in range(rows):
        parts.append("".join(str(int((r, c, r, c + 1) in edges)) for c in range(cols - 1)))
        if r < rows - 1:
            parts.append("".join(str(int((r, c, r + 1, c) in edges)) for c in range(cols)))
    return cells, "/".join(parts)


def _record(rows, cols, black, edges, clues=(), kinds=("arrow", "black", "edge")):
    return {"format": "puzzle-box/yajilin-v1", "rows": rows, "cols": cols, "arrow_sites": [],
            "clue_kinds": list(kinds), "clues": list(clues),
            "solution": {"black_cells": [list(c) for c in sorted(black)],
                         "loop_edges": [list(e) for e in sorted(edges)]}}


def test_sample_joint_inputs_agree_with_independent_geometry_and_clues(app):
    record = json.loads(SAMPLE.read_text(encoding="utf-8"))
    blocked = {tuple(s["cell"]) for s in record["arrow_sites"]}
    ordinary = {(r, c) for r in range(3) for c in range(4)} - blocked
    loops = _cycles(3, 4)
    assert len(loops) == 40
    successes = 0
    for edges in loops:
        black = ordinary - {v for e in edges for v in (e[:2], e[2:])}
        expected = _satisfies(record, black, edges)
        assert app["check_answer"](record, *_texts(record, black, edges)) == expected
        successes += expected
    assert successes == 1
    black = {tuple(c) for c in record["solution"]["black_cells"]}
    edges = {tuple(e) for e in record["solution"]["loop_edges"]}
    # Changing just one half must fail, including a line into a fixed arrow.
    for cell in ordinary:
        assert not app["check_answer"](record, *_texts(record, black ^ {cell}, edges))
    for edge in _edges(3, 4):
        assert not app["check_answer"](record, *_texts(record, black, edges ^ {edge}))


@pytest.mark.parametrize("black_bits", product((0, 1), repeat=4))
def test_all_256_two_by_two_joint_inputs_use_both_answer_components(app, black_bits):
    record = _record(2, 2, set(), set(_edges(2, 2)))
    black = {(i // 2, i % 2) for i, bit in enumerate(black_bits) if bit}
    for edge_bits in product((0, 1), repeat=4):
        edges = {e for e, bit in zip(_edges(2, 2), edge_bits) if bit}
        assert app["check_answer"](record, *_texts(record, black, edges)) == (not black and all(edge_bits))


def test_equal_black_cells_do_not_hide_different_loops_or_ambiguous_records(app):
    all_cells = {(r, c) for r in range(3) for c in range(4)}
    loops = [loop for loop in _cycles(3, 4) if {v for e in loop for v in (e[:2], e[2:])} == all_cells]
    assert len(loops) == 2
    target, alternative = loops
    recipe = YajilinRecipe(3, 4, clue_kinds=("edge",))
    clues = reduce_clues(recipe, [EdgeStateClue(Edge(Vertex(a, b), Vertex(c, d)), int((a, b, c, d) in target))
                                 for a, b, c, d in _edges(3, 4)], seed=0)
    record = _record(3, 4, set(), target, [app["clue_record"](c) for c in clues], ("edge",))
    assert app["check_answer"](record, *_texts(record, set(), target))
    assert not app["check_answer"](record, *_texts(record, set(), alternative))
    ambiguous = _record(3, 4, set(), target,
                        [{"type": "black", "cell": list(c), "black": 0} for c in sorted(all_cells)], ("black",))
    with pytest.raises(ValueError, match="uniquely solvable"):
        app["check_answer"](ambiguous, *_texts(ambiguous, set(), target))


def test_templates_show_only_givens_and_fixed_arrow_structure(app):
    record = json.loads(SAMPLE.read_text(encoding="utf-8"))
    shown = app["show"](record)
    assert "Cells template: ????/@???/????" in shown
    assert "Edges template: ???/0???/0??/0??1/???" in shown
    assert "# = black; . = on loop (white); [?] = unknown cell." in shown
    assert "template:" not in app["show"](record, reveal=True)
    # These two black/white givens are necessary and determine the joint answer.
    edges = {(0, 0, 0, 1), (0, 0, 1, 0), (0, 1, 0, 2), (0, 2, 0, 3), (0, 3, 1, 3),
             (1, 0, 2, 0), (1, 2, 1, 3), (1, 2, 2, 2), (2, 0, 2, 1), (2, 1, 2, 2)}
    record = _record(3, 4, {(1, 1), (2, 3)}, edges,
                     [{"type": "black", "cell": [1, 1], "black": 1},
                      {"type": "black", "cell": [0, 3], "black": 0}], ("black",))
    shown = app["show"](record)
    assert "Cells template: ???./?#??/????" in shown
    assert "Edges template: ???/????/???/????/???" in shown


@pytest.mark.parametrize("cells", ["", ".../@.../....", "????/@???/????", "#..#/..../#...",
                                   "#..#/#.../#...", "#..#/@..@/#...", "#..#/>.../#..."])
def test_incomplete_missized_or_moved_arrow_cells_are_input_errors(app, cells):
    record = json.loads(SAMPLE.read_text(encoding="utf-8"))
    with pytest.raises(ValueError):
        app["check_answer"](record, cells, "010/0110/001/0101/011")


@pytest.mark.parametrize("edges", ["", "???/0???/0??/0??1/???", "010/011/001/010/011",
                                   "0000/00000/0000/00000/0000/00000/0000", "01x/0110/001/0101/011"])
def test_edge_input_is_complete_and_uses_cell_centers_not_corners(app, edges):
    with pytest.raises(ValueError):
        app["check_answer"](json.loads(SAMPLE.read_text(encoding="utf-8")), "#..#/@.../#...", edges)


def test_spaces_in_both_halves_are_accepted(app):
    assert app["check_answer"](json.loads(SAMPLE.read_text(encoding="utf-8")),
                               " # . . # / @ . . . / # . . . ", " 0 1 0 / 0 1 1 0 / 0 0 1 / 0 1 0 1 / 0 1 1 ")


@pytest.mark.parametrize("damage", ["black", "edges", "ambiguous", "redundant", "experimental-format"])
def test_check_refuses_bad_saved_artifacts_even_when_input_matches_them(tmp_path, damage):
    record = json.loads(SAMPLE.read_text(encoding="utf-8"))
    if damage in ("black", "edges"):
        record["solution"]["black_cells" if damage == "black" else "loop_edges"] = []
    elif damage == "ambiguous":
        record["clues"] = []
    elif damage == "redundant":
        record["clues"].append(record["clues"][0])
    else:
        record["format"] = "puzzle-box/coupled-puzzle-v1"
    path = tmp_path / "corrupt.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    before = path.read_bytes()
    cells, edges = _texts(record, {tuple(c) for c in record["solution"]["black_cells"]},
                          {tuple(e) for e in record["solution"]["loop_edges"]})
    result = _cli("check", str(path), "--cells", cells, "--edges", edges)
    assert result.returncode == 2 and not result.stdout and "Traceback" not in result.stderr
    assert path.read_bytes() == before


@pytest.mark.parametrize("kinds", [("arrow", "edge"), ("arrow",), ("edge",)])
def test_generate_show_and_check_both_halves_end_to_end(tmp_path, kinds):
    path = tmp_path / "play.json"
    generated = _cli("generate", "--hints", *kinds, "--seed", "6", "--attempts", "3", "--output", str(path), "--quiet")
    assert generated.returncode == 0 and not generated.stdout, generated.stderr
    before = path.read_bytes()
    record = json.loads(before)
    cells, edges = _texts(record, {tuple(c) for c in record["solution"]["black_cells"]},
                          {tuple(e) for e in record["solution"]["loop_edges"]})
    shown = _cli("show", str(path))
    assert shown.returncode == 0 and "Cells template: ????/@???/????" in shown.stdout
    if kinds == ("edge",):
        assert ">?" in shown.stdout  # Removing its number never removes the arrow obstacle.
    correct = _cli("check", str(path), "--cells", cells, "--edges", edges)
    assert correct.returncode == 0 and correct.stdout.strip() == "Correct. All rules and clues are satisfied."
    wrong_cells = ("." if cells[0] == "#" else "#") + cells[1:]
    wrong = _cli("check", str(path), "--cells", wrong_cells, "--edges", edges)
    assert wrong.returncode == 1 and wrong.stdout.strip() == "Not correct. Check the rules and given clues."
    for args in [("--cells", cells), ("--edges", edges), ("--cells", "????/@???/????", "--edges", edges)]:
        incomplete = _cli("check", str(path), *args)
        assert incomplete.returncode == 2 and not incomplete.stdout
    assert _cli("verify", str(path)).returncode == 0
    assert path.read_bytes() == before
