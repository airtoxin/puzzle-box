from functools import lru_cache
from itertools import product
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from generator import generate, reduce_clues
from puzzle import Cell, Edge, Vertex, at_least_one, unique
from puzzle_defs import (ArrowCountClue, ArrowSite, BlackCellClue, EdgeStateClue,
                         YajilinAnswer, YajilinPuzzle, YajilinRecipe)
from puzzle_defs.puzzles.yajilin_recipe import YAJILIN_CLUE_KINDS, YajilinClue
from puzzle_defs.puzzles.yajilin import Grid


def _edges(rows: int, cols: int) -> list[Edge]:
    # Cell centers: deliberately independent of the DSL grid helpers.
    return ([Edge(Vertex(r, c), Vertex(r, c+1)) for r in range(rows) for c in range(cols-1)]
            + [Edge(Vertex(r, c), Vertex(r+1, c)) for r in range(rows-1) for c in range(cols)])


@lru_cache(maxsize=None)
def _cycles(rows: int, cols: int) -> tuple[frozenset[Edge], ...]:
    edges = _edges(rows, cols)
    loops = []
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
            vertex = todo.pop()
            if vertex not in seen:
                seen.add(vertex)
                todo.extend(neighbors[vertex])
        if seen == set(neighbors):
            loops.append(selected)
    return tuple(loops)


def _count(answer: YajilinAnswer, site: ArrowSite) -> int:
    r, c = site.cell
    # Check direction geometrically, without calling recipe.ray().
    return sum((site.direction == "up" and b.col == c and b.row < r)
               or (site.direction == "down" and b.col == c and b.row > r)
               or (site.direction == "left" and b.row == r and b.col < c)
               or (site.direction == "right" and b.row == r and b.col > c)
               for b in answer.black_cells)


def _answers(recipe: YajilinRecipe, clues: list[YajilinClue]) -> set[YajilinAnswer]:
    blocked = {s.cell for s in recipe.arrow_sites}
    cells = {Cell(r, c) for r in range(recipe.rows) for c in range(recipe.cols)}
    sites = {s.cell: s for s in recipe.arrow_sites}
    answers = set()
    for loop in _cycles(recipe.rows, recipe.cols):
        visited = {Cell(*v) for e in loop for v in e}
        if visited & blocked:
            continue
        black = cells - blocked - visited
        if any(Cell(*a) in black and Cell(*b) in black for a, b in _edges(recipe.rows, recipe.cols)):
            continue
        answer = YajilinAnswer(frozenset(black), loop)
        if all(_count(answer, sites[c.cell]) == c.count if isinstance(c, ArrowCountClue)
               else int(c.cell in black) == c.black if isinstance(c, BlackCellClue)
               else int(c.edge in loop) == c.used for c in clues):
            answers.add(answer)
    return answers


def _solver_answers(recipe: YajilinRecipe, clues: list[YajilinClue]) -> set[YajilinAnswer]:
    puzzle = recipe.build_from_clues(clues)
    variables = ([puzzle.is_black[c] for c in puzzle.board.cells if c not in puzzle.clue_cells]
                 + [puzzle.edge_on[e] for e in puzzle.loop_board.edges])
    answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        answer = recipe.answer(solution, puzzle)
        assert answer not in answers
        answers.add(answer)
        puzzle.add(at_least_one(v != solution.value(v) for v in variables))
        assert len(answers) <= 40
    return answers


@pytest.mark.parametrize("sites", [(), (ArrowSite(Cell(0, 0), "right"),),
    (ArrowSite(Cell(1, 0), "right"),), (ArrowSite(Cell(1, 1), "up"),),
    (ArrowSite(Cell(0, 0), "down"), ArrowSite(Cell(0, 3), "left"))])
def test_model_matches_all_131072_edge_subsets(sites):
    recipe = YajilinRecipe(3, 4, sites)
    assert len(_cycles(3, 4)) == 40
    assert _solver_answers(recipe, []) == _answers(recipe, [])


@pytest.mark.parametrize("sites", [(), (ArrowSite(Cell(1, 0), "right"),)])
@pytest.mark.parametrize("kinds", [YAJILIN_CLUE_KINDS, ("arrow", "edge"), ("edge",)])
@pytest.mark.parametrize("seed", [6, 17])
def test_generated_clues_are_unique_and_irreducible_against_oracle(sites, kinds, seed):
    recipe = YajilinRecipe(3, 4, sites, kinds)
    clues = generate(recipe, seed=seed)
    expected = _answers(recipe, clues)
    assert len(expected) == 1
    for i in range(len(clues)):
        assert len(_answers(recipe, clues[:i]+clues[i+1:])) > 1
    puzzle = recipe.build_from_clues(clues)
    puzzle.bool_var_map("unobserved_witness", [0])
    puzzle.add(unique())
    solution = puzzle.solve()
    assert solution is not None and recipe.answer(solution, puzzle) in expected


def test_black_cells_alone_can_hide_two_different_loops():
    recipe = YajilinRecipe(3, 4, clue_kinds=("black",))
    clues: list[YajilinClue] = [BlackCellClue(Cell(r, c), 0) for r in range(3) for c in range(4)]
    answers = _answers(recipe, clues)
    assert len(answers) == 2 and all(not a.black_cells for a in answers)
    assert _solver_answers(recipe, clues) == answers
    puzzle = recipe.build_from_clues(clues)
    puzzle.add(unique())
    assert puzzle.solve() is None
    # Demonstrate the incorrect answer projection explicitly.
    puzzle.set_solution_vars(puzzle.is_black[c] for c in puzzle.board.cells)
    assert puzzle.solve() is not None
    with pytest.raises(ValueError, match="uniquely solvable"):
        reduce_clues(recipe, clues, seed=0)
    mixed = YajilinRecipe(3, 4)
    answer = next(iter(answers))
    full = clues + [EdgeStateClue(e, int(e in answer.loop_edges)) for e in _edges(3, 4)]
    reduced = reduce_clues(mixed, full, seed=0)
    assert any(isinstance(c, EdgeStateClue) for c in reduced)
    assert _answers(mixed, reduced) == {answer}


def test_removing_arrow_count_keeps_cell_roles_and_only_relaxes_constraints():
    site = ArrowSite(Cell(1, 0), "right")
    recipe = YajilinRecipe(3, 4, (site,))
    before = recipe.build_from_clues([ArrowCountClue(site.cell, 0)])
    after = recipe.create_empty()
    assert before.clue_cells == after.clue_cells == {site.cell}
    assert site.cell not in before.is_black and site.cell not in after.is_black
    assert len(_answers(recipe, [])) == 3
    assert len(_answers(recipe, [ArrowCountClue(site.cell, 0)])) == 2
    assert _solver_answers(recipe, [ArrowCountClue(site.cell, 0)]) < _solver_answers(recipe, [])
    old_grid: Grid = [[None] * 4 for _ in range(3)]
    old_grid[1][0] = ("right", 0)
    legacy = YajilinPuzzle(old_grid)
    solution = legacy.solve()
    assert solution is not None
    result = legacy.result(solution)
    assert result is not None and result[1][0] == "clue"
    assert recipe.answer(solution, legacy) in _answers(recipe, [ArrowCountClue(site.cell, 0)])


@pytest.mark.parametrize("direction", ["up", "down", "left", "right"])
def test_arrow_counts_in_every_direction_match_oracle(direction: str):
    site = ArrowSite(Cell(1, 1), direction)
    recipe = YajilinRecipe(3, 4, (site,))
    for count in range(len(recipe.ray(site))+1):
        clues: list[YajilinClue] = [ArrowCountClue(site.cell, count)]
        assert _solver_answers(recipe, clues) == _answers(recipe, clues)


def test_rays_skip_other_sites_and_empty_ray_zero_is_valid():
    a, b = ArrowSite(Cell(0, 0), "right"), ArrowSite(Cell(0, 2), "down")
    recipe = YajilinRecipe(3, 4, (a, b))
    assert recipe.ray(a) == (Cell(0, 1), Cell(0, 3))
    outward = ArrowSite(Cell(1, 0), "left")
    recipe = YajilinRecipe(3, 4, (outward,))
    assert _solver_answers(recipe, [ArrowCountClue(outward.cell, 0)]) == _answers(recipe, [])
    with pytest.raises(ValueError, match="ray"):
        recipe.build_from_clues([ArrowCountClue(outward.cell, 1)])


def test_coupling_rejects_loop_on_black_and_edges_into_reserved_cells():
    recipe = YajilinRecipe(3, 4, (ArrowSite(Cell(1, 0), "right"),))
    e = Edge(Vertex(0, 1), Vertex(0, 2))
    assert recipe.build_from_clues([BlackCellClue(Cell(0, 1), 1), EdgeStateClue(e, 1)]).solve() is None
    blocked_edge = Edge(Vertex(0, 0), Vertex(1, 0))
    assert recipe.build_from_clues([EdgeStateClue(blocked_edge, 1)]).solve() is None
    assert recipe.build_from_clues([BlackCellClue(Cell(2, 1), 1), BlackCellClue(Cell(2, 2), 1)]).solve() is None
    assert recipe.build_from_clues([EdgeStateClue(e, 0) for e in _edges(3, 4)]).solve() is None


def test_incompatible_layout_fails_without_moving_arrow_sites():
    recipe = YajilinRecipe(2, 2, (ArrowSite(Cell(0, 0), "right"),))
    assert _answers(recipe, []) == set()
    with pytest.raises(RuntimeError, match="Failed to generate"):
        generate(recipe, seed=6)


@pytest.mark.parametrize("rows,cols", [(0, 3), (1, 3), (3, True), (2.5, 3)])
def test_invalid_dimensions(rows, cols):
    with pytest.raises(ValueError):
        YajilinRecipe(rows, cols)


@pytest.mark.parametrize("cell,direction", [(Cell(-1, 0), "up"), (Cell(True, 0), "up"),
                                            (Cell(0, 0), "north"), (Cell(0, 0), [])])
def test_invalid_arrow_sites(cell, direction):
    with pytest.raises(ValueError):
        ArrowSite(cell, direction)


@pytest.mark.parametrize("kind,value", [("arrow", -1), ("arrow", True), ("black", 2), ("black", True)])
def test_invalid_clue_values(kind, value):
    with pytest.raises(ValueError):
        (ArrowCountClue if kind == "arrow" else BlackCellClue)(Cell(0, 0), value)


@pytest.mark.parametrize("clue", [ArrowCountClue(Cell(0, 0), 0), ArrowCountClue(Cell(1, 0), 4),
    BlackCellClue(Cell(1, 0), 1), BlackCellClue(Cell(3, 0), 1),
    EdgeStateClue(Edge(Vertex(0, 3), Vertex(0, 4)), 1), (Cell(0, 0), 1)])
def test_invalid_or_foreign_clues(clue):
    with pytest.raises(ValueError):
        YajilinRecipe(3, 4, (ArrowSite(Cell(1, 0), "right"),)).build_from_clues([clue])


def test_duplicate_contradictions_stay_unsatisfiable_and_recipe_validation():
    site = ArrowSite(Cell(1, 0), "right")
    recipe = YajilinRecipe(3, 4, (site,))
    for clues in ([ArrowCountClue(site.cell, 0), ArrowCountClue(site.cell, 1)],
                  [BlackCellClue(Cell(2, 3), 0), BlackCellClue(Cell(2, 3), 1)]):
        assert recipe.build_from_clues(clues).solve() is None
    for sites in [(site, site), (ArrowSite(Cell(3, 0), "right"),)]:
        with pytest.raises(ValueError):
            YajilinRecipe(3, 4, sites)
    for kinds in [("arrow", "arrow"), ("cell-count",)]:
        with pytest.raises(ValueError):
            YajilinRecipe(3, 4, clue_kinds=kinds)
    with pytest.raises(ValueError):
        recipe.ray(ArrowSite(Cell(0, 0), "right"))


@pytest.mark.parametrize("reserved", [[Cell(-1, 0)], [Cell(3, 0)], [Cell(True, 0)], [(0, 0)]])
def test_low_level_reserved_cells_are_validated(reserved):
    with pytest.raises(ValueError, match="Reserved"):
        YajilinPuzzle([[None]*4 for _ in range(3)], reserved_clue_cells=reserved)


def test_extraction_rejects_wrong_topology_and_solution_owner():
    recipe = YajilinRecipe(3, 4)
    source = recipe.create_empty()
    solution = source.solve()
    assert solution is not None
    for other in [YajilinRecipe(3, 3), YajilinRecipe(3, 4, (ArrowSite(Cell(0, 0), "right"),))]:
        with pytest.raises(ValueError, match="dimensions and reserved"):
            other.extract_clues(solution, source)
    with pytest.raises(ValueError):
        recipe.extract_clues(solution, recipe.create_empty())


SCRIPT = Path(__file__).resolve().parents[4] / "examples" / "generate_yajilin.py"
SAMPLE = SCRIPT.with_name("yajilin-sample.json")


def _cli(*args: str, hash_seed: str = "1") -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], check=False, text=True,
                          capture_output=True, timeout=45, env=dict(os.environ, PYTHONHASHSEED=hash_seed))


def _sample() -> tuple[YajilinRecipe, list[YajilinClue], YajilinAnswer]:
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    sites = tuple(ArrowSite(Cell(*s["cell"]), s["direction"]) for s in data["arrow_sites"])
    recipe = YajilinRecipe(data["rows"], data["cols"], sites, tuple(data["clue_kinds"]))
    clues: list[YajilinClue] = []
    for c in data["clues"]:
        if c["type"] == "arrow":
            clues.append(ArrowCountClue(Cell(*c["cell"]), c["count"]))
        else:
            a, b, d, e = c["edge"]
            clues.append(EdgeStateClue(Edge(Vertex(a, b), Vertex(d, e)), c["used"]))
    expected = data["solution"]
    answer = YajilinAnswer(frozenset(Cell(*c) for c in expected["black_cells"]),
        frozenset(Edge(Vertex(a, b), Vertex(c, d)) for a, b, c, d in expected["loop_edges"]))
    return recipe, clues, answer


def test_saved_sample_needs_both_arrow_and_edge_clues():
    recipe, clues, answer = _sample()
    assert {type(c) for c in clues} == {ArrowCountClue, EdgeStateClue}
    assert len(answer.black_cells) == 3 and len(answer.loop_edges) == 8
    assert _answers(recipe, clues) == {answer}
    for i in range(len(clues)):
        assert len(_answers(recipe, clues[:i]+clues[i+1:])) == 2
    checked = _cli("verify", str(SAMPLE))
    assert checked.returncode == 0, checked.stderr


@pytest.mark.parametrize("kinds", [("arrow", "edge"), YAJILIN_CLUE_KINDS])
def test_cli_repeatability_show_and_verify(tmp_path: Path, kinds):
    path = tmp_path / "coupled.json"
    args = ("generate", "--seed", "6", "--output", str(path), "--hints", *kinds)
    first, second = _cli(*args), _cli(*args, hash_seed="999")
    assert first.returncode == second.returncode == 0, (first.stderr, second.stderr)
    assert first.stdout == second.stdout == path.read_text(encoding="utf-8")
    original = path.read_bytes()
    assert _cli("verify", str(path)).returncode == 0
    question, answer = _cli("show", str(path)), _cli("show", str(path), "--solution")
    assert question.returncode == answer.returncode == 0
    assert "Coupled puzzle:" in question.stdout and "Solution:" not in question.stdout
    if kinds == ("arrow", "edge"):
        assert " # " not in question.stdout.split("# = black")[0]
        assert ">0" in question.stdout and "|" in question.stdout.split("# = black")[0]
    assert "Solution:" in answer.stdout and " # " in answer.stdout
    assert path.read_bytes() == original


def test_hidden_count_leaves_a_visible_blocked_arrow(tmp_path: Path):
    path = tmp_path / "no-count.json"
    made = _cli("generate", "--seed", "0", "--hints", "edge", "--output", str(path), "--quiet")
    assert made.returncode == 0, made.stderr
    shown = _cli("show", str(path))
    assert shown.returncode == 0 and ">?" in shown.stdout


@pytest.mark.parametrize("damage", ["black-answer", "edge-answer", "duplicate-answer", "missing-half",
    "unknown-clue", "foreign-format", "clue-on-arrow", "corner-edge", "invalid-direction"])
def test_cli_rejects_corrupted_coupled_records(tmp_path: Path, damage: str):
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    if damage == "black-answer":
        data["solution"]["black_cells"] = []
    elif damage == "edge-answer":
        data["solution"]["loop_edges"] = []
    elif damage == "duplicate-answer":
        data["solution"]["loop_edges"].append(data["solution"]["loop_edges"][0])
    elif damage == "missing-half":
        del data["solution"]["loop_edges"]
    elif damage == "unknown-clue":
        data["clues"][0]["type"] = "cell-count"
    elif damage == "foreign-format":
        data["format"] = "puzzle-box/slitherlink-v1"
    elif damage == "clue-on-arrow":
        data["clue_kinds"].append("black")
        data["clues"][0] = {"type": "black", "cell": [1, 0], "black": 1}
    elif damage == "corner-edge":
        data["solution"]["loop_edges"][0] = [0, 3, 0, 4]
    else:
        data["arrow_sites"][0]["direction"] = []
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    checked = _cli("verify", str(path))
    assert checked.returncode == 2 and "Traceback" not in checked.stderr


def test_cli_limits_quiet_and_incompatible_layout(tmp_path: Path):
    path = tmp_path / "quiet.json"
    made = _cli("generate", "--output", str(path), "--quiet")
    assert made.returncode == 0 and not made.stdout
    for args in [("--quiet",), ("--rows", "4", "--cols", "4"), ("--seed", "-1"),
                 ("--rows", "2", "--cols", "2"), ("--arrow", "x", "0", "right")]:
        result = _cli("generate", *args)
        assert result.returncode == 2 and "Traceback" not in result.stderr


def test_bounded_arrow_only_search_is_repeatable_and_independently_unique(tmp_path: Path):
    path = tmp_path / "arrow-only.json"
    args = ("generate", "--hints", "arrow", "--seed", "6", "--attempts", "3", "--output", str(path))
    first, second = _cli(*args), _cli(*args, hash_seed="999")
    assert first.returncode == second.returncode == 0, (first.stderr, second.stderr)
    assert first.stdout == second.stdout
    data = json.loads(first.stdout)
    assert data["clue_kinds"] == ["arrow"]
    assert data["arrow_sites"] == [{"cell": [1, 0], "direction": "right"}]
    history = data["generation"]
    assert history["initial_seed"] == 6 and history["attempt_limit"] == 3
    assert data["seed"] == 6 + history["attempts_used"] - 1
    clues: list[YajilinClue] = [ArrowCountClue(Cell(*c["cell"]), c["count"]) for c in data["clues"]]
    assert all(c["type"] == "arrow" for c in data["clues"])
    recipe = YajilinRecipe(3, 4, (ArrowSite(Cell(1, 0), "right"),), ("arrow",))
    assert len(_answers(recipe, clues)) == 1
    for i in range(len(clues)):
        assert len(_answers(recipe, clues[:i]+clues[i+1:])) > 1
    assert _cli("verify", str(path)).returncode == 0
    replay = _cli("generate", "--hints", "arrow", "--seed", str(data["seed"]))
    assert replay.returncode == 0
    direct = json.loads(replay.stdout)
    assert "generation" not in direct
    assert direct == {k: v for k, v in data.items() if k != "generation"}
