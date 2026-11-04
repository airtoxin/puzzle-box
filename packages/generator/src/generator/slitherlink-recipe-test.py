from functools import lru_cache
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from generator import generate, reduce_clues
from puzzle import Cell, Edge, Vertex, unique
from puzzle_defs import CellEdgeCountClue, EdgeStateClue, SlitherlinkPuzzle, SlitherlinkRecipe
from puzzle_defs.puzzles.slitherlink_recipe import LOOP_CLUE_KINDS, LoopClue


def _edges(rows: int, cols: int) -> list[Edge]:
    return ([Edge(Vertex(r, c), Vertex(r, c + 1)) for r in range(rows + 1) for c in range(cols)]
            + [Edge(Vertex(r, c), Vertex(r + 1, c)) for r in range(rows) for c in range(cols + 1)])


@lru_cache(maxsize=None)
def _cycles(rows: int, cols: int) -> tuple[frozenset[Edge], ...]:
    """Enumerate raw edge subsets, then test degree and graph reachability."""
    edges = _edges(rows, cols)
    answers = []
    for bits in product([0, 1], repeat=len(edges)):
        selected = frozenset(e for e, bit in zip(edges, bits) if bit)
        neighbors: dict[Vertex, list[Vertex]] = {}
        for a, b in selected:
            neighbors.setdefault(a, []).append(b)
            neighbors.setdefault(b, []).append(a)
        if not neighbors or any(len(ns) != 2 for ns in neighbors.values()):
            continue
        seen: set[Vertex] = set()
        todo = [next(iter(neighbors))]
        while todo:
            v = todo.pop()
            if v not in seen:
                seen.add(v)
                todo.extend(neighbors[v])
        if seen == set(neighbors):
            answers.append(selected)
    return tuple(answers)


def _count(loop: frozenset[Edge], cell: Cell) -> int:
    r, c = cell
    corners = {Vertex(r, c), Vertex(r, c + 1), Vertex(r + 1, c), Vertex(r + 1, c + 1)}
    return sum(a in corners and b in corners for a, b in loop)


def _answers(recipe: SlitherlinkRecipe, clues: list[LoopClue]) -> list[frozenset[Edge]]:
    return [loop for loop in _cycles(recipe.rows, recipe.cols)
            if (recipe.loop_length is None or len(loop) == recipe.loop_length)
            and all(_count(loop, c.cell) == c.count if isinstance(c, CellEdgeCountClue)
                    else int(c.edge in loop) == c.used for c in clues)]


@pytest.mark.parametrize("length", [None, 4, 6, 8])
@pytest.mark.parametrize("kinds", [LOOP_CLUE_KINDS, ("edge",)])
@pytest.mark.parametrize("seed", [7, 17])
def test_generation_matches_all_4096_two_by_two_edge_subsets(length, kinds, seed: int):
    recipe = SlitherlinkRecipe(2, 2, length, kinds)
    clues = generate(recipe, seed=seed)
    answers = _answers(recipe, clues)
    assert len(_cycles(2, 2)) == 13
    assert len(answers) == 1
    for i in range(len(clues)):
        assert len(_answers(recipe, clues[:i] + clues[i+1:])) > 1
    p = recipe.build_from_clues(clues)
    p.add(unique())
    s = p.solve()
    assert s is not None and p.result(s) == answers[0]


def test_full_cell_counts_and_equal_length_can_still_have_two_loops():
    recipe = SlitherlinkRecipe(2, 2, 8)
    counts: list[LoopClue] = [CellEdgeCountClue(Cell(i // 2, i % 2), n)
                              for i, n in enumerate([3, 2, 2, 3])]
    loops = _answers(recipe, counts)
    assert len(loops) == 2
    with pytest.raises(ValueError, match="uniquely solvable"):
        reduce_clues(recipe, counts, seed=0)
    fixed = recipe.build_from_clues([EdgeStateClue(e, int(e in loops[0])) for e in _edges(2, 2)])
    solution = fixed.solve()
    assert solution is not None
    candidates = recipe.extract_clues(solution, fixed)
    clues = reduce_clues(recipe, candidates, seed=0)
    assert any(isinstance(c, EdgeStateClue) for c in clues)
    assert _answers(recipe, clues) == [loops[0]]
    for i in range(len(clues)):
        assert len(_answers(recipe, clues[:i] + clues[i+1:])) > 1


def test_count_only_contract_for_every_small_loop():
    recipe = SlitherlinkRecipe(2, 2, clue_kinds=("cell-count",))
    for loop in _cycles(2, 2):
        p = recipe.build_from_clues([EdgeStateClue(e, int(e in loop)) for e in _edges(2, 2)])
        solution = p.solve()
        assert solution is not None
        clues = recipe.extract_clues(solution, p)
        assert all(isinstance(c, CellEdgeCountClue) for c in clues)
        answers = _answers(recipe, clues)
        if len(answers) == 1:
            assert _answers(recipe, reduce_clues(recipe, clues, seed=7)) == [loop]
        else:
            with pytest.raises(ValueError, match="uniquely solvable"):
                reduce_clues(recipe, clues, seed=7)


def test_only_visible_edges_count_as_a_solution():
    recipe = SlitherlinkRecipe(1, 1)
    p = recipe.create_empty()
    p.bool_var_map("unobserved_witness", [0])
    p.add(unique())
    s = p.solve()
    assert s is not None and p.result(s) == set(_edges(1, 1))
    assert generate(recipe, seed=7) == []
    # Preserve the original empty-loop behavior outside this nonempty recipe.
    assert SlitherlinkPuzzle([[0]]).solve() is not None
    assert recipe.build_from_clues([CellEdgeCountClue(Cell(0, 0), 0)]).solve() is None


def test_disconnected_loops_are_rejected():
    edges = _edges(2, 3)
    corners = [{Vertex(r, c), Vertex(r + 1, c), Vertex(r, c + 1), Vertex(r + 1, c + 1)}
               for r, c in [(0, 0), (1, 2)]]
    selected = {e for e in edges if any(e.v1 in cs and e.v2 in cs for cs in corners)}
    assert len(selected) == 8
    recipe = SlitherlinkRecipe(2, 3, 8)
    assert recipe.build_from_clues([EdgeStateClue(e, int(e in selected)) for e in edges]).solve() is None


@pytest.mark.parametrize("length", [0, 3, 5])
def test_incompatible_lengths_fail_generation(length: int):
    with pytest.raises(RuntimeError, match="Failed to generate"):
        generate(SlitherlinkRecipe(2, 2, length), seed=17)


@pytest.mark.parametrize("rows,cols,length", [(0, 2, None), (2, False, None), (2, 2, -1),
                                             (2, 2, 13), (2, 2, True)])
def test_invalid_recipe_parameters_are_rejected(rows, cols, length):
    with pytest.raises(ValueError):
        SlitherlinkRecipe(rows, cols, length)


@pytest.mark.parametrize("count", [-1, 5, True, 1.5])
def test_invalid_cell_counts_are_rejected(count):
    with pytest.raises(ValueError):
        CellEdgeCountClue(Cell(0, 0), count)


@pytest.mark.parametrize("a,b,used", [(Vertex(0, 0), Vertex(0, 0), 1),
    (Vertex(0, 0), Vertex(1, 1), 1), (Vertex(-1, 0), Vertex(0, 0), 1),
    (Vertex(0, 0), Vertex(0, 1), 2), (Vertex(0, 0), Vertex(0, 1), True)])
def test_invalid_edge_states_are_rejected(a, b, used):
    with pytest.raises(ValueError):
        EdgeStateClue(Edge(a, b), used)


@pytest.mark.parametrize("clue", [CellEdgeCountClue(Cell(2, 0), 0),
                                 EdgeStateClue(Edge(Vertex(0, 2), Vertex(0, 3)), 1),
                                 (Cell(0, 0), 1)])
def test_out_of_board_or_untyped_cell_clues_are_rejected(clue):
    with pytest.raises(ValueError):
        SlitherlinkRecipe(2, 2).build_from_clues([clue])


def test_reversed_edges_normalize_and_conflicting_duplicates_stay_inconsistent():
    edge = Edge(Vertex(0, 0), Vertex(0, 1))
    assert EdgeStateClue(Edge(edge.v2, edge.v1), 1).edge == edge
    recipe = SlitherlinkRecipe(2, 2)
    assert recipe.build_from_clues([EdgeStateClue(edge, 1), EdgeStateClue(edge, 0)]).solve() is None
    assert recipe.build_from_clues([CellEdgeCountClue(Cell(0, 0), 1),
                                    CellEdgeCountClue(Cell(0, 0), 2)]).solve() is None


SCRIPT = Path(__file__).resolve().parents[4] / "examples" / "generate_slitherlink.py"
SAMPLE = SCRIPT.with_name("slitherlink-sample.json")


def _cli(*args: str, hash_seed: str = "1") -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], check=False, text=True,
                          capture_output=True, timeout=45, env=dict(os.environ, PYTHONHASHSEED=hash_seed))


def test_cli_roundtrip_is_repeatable_and_corrupted_answers_are_rejected(tmp_path: Path):
    path = tmp_path / "loop.json"
    args = ("generate", "--loop-length", "8", "--seed", "0", "--output", str(path))
    first, second = _cli(*args), _cli(*args, hash_seed="999")
    assert first.returncode == second.returncode == 0, (first.stderr, second.stderr)
    assert first.stdout == second.stdout == path.read_text(encoding="utf-8")
    checked = _cli("verify", str(path))
    assert checked.returncode == 0, checked.stderr
    assert json.loads(checked.stdout)["unique"] is True
    shown = _cli("show", str(path))
    assert shown.returncode == 0 and "Loop puzzle:" in shown.stdout
    revealed = _cli("show", str(path), "--solution")
    assert revealed.returncode == 0 and "Solution:" in revealed.stdout
    data = json.loads(path.read_text(encoding="utf-8"))
    data["solution"] = []
    path.write_text(json.dumps(data), encoding="utf-8")
    assert _cli("verify", str(path)).returncode == 2


def test_published_sample_needs_its_clues_and_length_rule():
    checked = _cli("verify", str(SAMPLE))
    assert checked.returncode == 0, checked.stderr
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    clues: list[LoopClue] = []
    for c in data["clues"]:
        if c["type"] == "cell-count":
            clues.append(CellEdgeCountClue(Cell(c["row"], c["col"]), c["count"]))
        else:
            a, b, c1, d = c["edge"]
            clues.append(EdgeStateClue(Edge(Vertex(a, b), Vertex(c1, d)), c["used"]))
    assert {type(c) for c in clues} == {CellEdgeCountClue, EdgeStateClue}
    recipe = SlitherlinkRecipe(data["rows"], data["cols"], data["loop_length"])
    answers = _answers(recipe, clues)
    assert len(answers) == 1
    expected = {Edge(Vertex(a, b), Vertex(c, d)) for a, b, c, d in data["solution"]}
    assert answers[0] == expected
    for i in range(len(clues)):
        assert len(_answers(recipe, clues[:i] + clues[i+1:])) > 1
    assert len(_answers(SlitherlinkRecipe(recipe.rows, recipe.cols), clues)) == 2


def test_cli_limits_and_shading_format_are_explicit(tmp_path: Path):
    assert _cli("generate", "--rows", "4", "--cols", "4").returncode == 2
    assert _cli("generate", "--quiet").returncode == 2
    path = tmp_path / "loop.json"
    made = _cli("generate", "--loop-length", "8", "--output", str(path), "--quiet")
    assert made.returncode == 0 and not made.stdout
    other = SCRIPT.with_name("shading-sample.json")
    assert _cli("verify", str(other)).returncode == 2


@pytest.mark.parametrize("kinds", [("cell-count", "cell-count"), ("row-count",)])
def test_unknown_or_duplicate_candidate_kinds_are_rejected(kinds):
    with pytest.raises(ValueError, match="Clue kinds"):
        SlitherlinkRecipe(2, 2, clue_kinds=kinds)


@pytest.mark.parametrize("cell", [Cell(-1, 0), Cell(True, 0)])
def test_invalid_cell_coordinates_are_rejected(cell):
    with pytest.raises(ValueError, match="coordinates"):
        CellEdgeCountClue(cell, 1)


def test_extraction_requires_matching_dimensions():
    source = SlitherlinkRecipe(1, 1).create_empty()
    solution = source.solve()
    assert solution is not None
    with pytest.raises(ValueError, match="dimensions"):
        SlitherlinkRecipe(2, 2).extract_clues(solution, source)


@pytest.mark.parametrize("damage", ["duplicate-solution-edge", "diagonal-clue", "unknown-clue"])
def test_cli_rejects_malformed_loop_records(tmp_path: Path, damage: str):
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    if damage == "duplicate-solution-edge":
        data["solution"].append(data["solution"][0])
    elif damage == "diagonal-clue":
        data["clues"] = [{"type": "edge", "edge": [0, 0, 1, 1], "used": 1}]
    else:
        data["clues"] = [{"type": "row-count", "row": 0, "count": 1}]
    path = tmp_path / "bad-loop.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    checked = _cli("verify", str(path))
    assert checked.returncode == 2
    assert "Traceback" not in checked.stderr
