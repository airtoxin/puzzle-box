"""Compare reusable fragments with independent finite boards and saved/Web flows."""

from dataclasses import fields
import importlib
from itertools import product
import json
from pathlib import Path
import subprocess
import sys

import pytest

from puzzle import at_least_one
from puzzle_defs import (BalancedLines, BlackCount, BlackDominoes, ConnectedBlack,
                         DistinctLines, NoBlack2x2, NoThreeConsecutive,
                         NonTouchingBlack, ShadingRecipe)

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    oracle = importlib.import_module("analyze_shading")
    codec = importlib.import_module("shading_recipe")
    finite = importlib.import_module("finite_shading")
    saved = importlib.import_module("generate_shading")
    deduction = importlib.import_module("explain_shading")
    api = importlib.import_module("web_catalog")
    worker = importlib.import_module("web_worker")

FRAGMENTS = (ConnectedBlack(), ConnectedBlack(False), NoBlack2x2(), BlackDominoes(),
             NoThreeConsecutive(), BalancedLines(), DistinctLines())


def solver_answers(recipe):
    puzzle = recipe.create_empty()
    variables = [puzzle.black[c] for c in puzzle.board.cells]
    answers = set()
    while (solution := puzzle.solve(seed=0)) is not None:
        bits = tuple(v for row in puzzle.result(solution) for v in row)
        assert bits not in answers
        answers.add(bits)
        puzzle.add(at_least_one(v != solution.value(v) for v in variables))
    return answers


@pytest.mark.parametrize("rule", FRAGMENTS)
@pytest.mark.parametrize("rows,cols", [(1, 1), (1, 3), (3, 1), (2, 2), (2, 3)])
def test_all_visible_dsl_answers_equal_independent_finite_checker(rule, rows, cols):
    expected = {bits for bits in product((0, 1), repeat=rows*cols)
                if oracle.accepts(rule, bits, rows, cols)}
    assert solver_answers(ShadingRecipe(rows, cols, (rule,))) == expected


@pytest.mark.parametrize("rule,board,expected", [
    (ConnectedBlack(), ("..", ".."), False),
    (ConnectedBlack(False), ("..", ".."), True),
    (ConnectedBlack(), ("#.", ".#"), False),
    (NoBlack2x2(), ("##", "##"), False),
    (NoBlack2x2(), ("###",), True),
    (BlackDominoes(), ("...", "..."), True),
    (BlackDominoes(), ("##.", "..#", "..#"), True),  # diagonal contact is allowed
    (BlackDominoes(), ("##", "#."), False),
    (BlackDominoes(), ("##", "##"), False),
    (BlackDominoes(), ("#.", ".#"), False),
    (NoThreeConsecutive(), ("...", "###"), False),
    (NoThreeConsecutive(), (".#", ".#", ".#"), False),
    (NoThreeConsecutive(), ("#..", ".#.", "..#"), True),
    (BalancedLines(), ("#.", ".#"), True),
    (BalancedLines(), ("#.", "#.", ".."), False),
    (DistinctLines(), ("#.", ".#"), True),  # rows may equal columns
    (DistinctLines(), ("#.", "#."), False),
    (DistinctLines(), ("##", ".."), False),
])
def test_named_rule_boundary_examples(rule, board, expected):
    bits = tuple(int(c == "#") for row in board for c in row)
    assert oracle.accepts(rule, bits, len(board), len(board[0])) is expected


@pytest.mark.parametrize("rule", FRAGMENTS)
def test_exact_codecs_and_ui_parameters_round_trip_without_accepting_subclasses(rule):
    record = codec.rule_record(rule)
    assert codec.read_rule(record) == rule
    assert {p.name for p in rule.ui.parameters} == {f.name for f in fields(rule)}
    assert rule.ui.requirements.topology == "rectangular-cells"
    with pytest.raises(ValueError, match="invalid"):
        codec.read_rule({**record, "module": "untrusted.py"})
    subclass = type("ExtendedRule", (type(rule),), {})
    with pytest.raises(ValueError, match="exact built-in"):
        codec.rule_record(subclass())


@pytest.mark.parametrize("invalid", [0, 1, "true", None])
def test_connectivity_nonempty_requires_a_real_boolean(invalid):
    with pytest.raises(ValueError, match="boolean"):
        codec.read_rule({"type": "connected-black", "nonempty": invalid})


def test_conflicting_and_redundant_combinations_have_exact_finite_meaning():
    sea = (BlackCount(4), ConnectedBlack())
    assert len(solver_answers(ShadingRecipe(2, 3, sea))) == 10
    assert len(solver_answers(ShadingRecipe(2, 3, (*sea, NoBlack2x2())))) == 8
    # Positive dominoes cannot coexist with orthogonal non-contact.
    report = oracle.analyze(ShadingRecipe(2, 3, (BlackCount(2), BlackDominoes(), NonTouchingBlack())))
    assert report["completion_count"] == 0 and report["minimal_conflicts"] == [[1, 2, 3]]
    assert ShadingRecipe(2, 3, (BalancedLines(),)).create_empty().solve() is None
    # Dominoes already forbid black 2x2; connected dominoes are exactly one pair.
    base = solver_answers(ShadingRecipe(2, 3, (BlackDominoes(),)))
    assert base == solver_answers(ShadingRecipe(2, 3, (BlackDominoes(), NoBlack2x2())))
    paired = ShadingRecipe(2, 3, (BlackDominoes(), ConnectedBlack()))
    assert all(sum(bits) == 2 for bits in solver_answers(paired))
    # Balance fixes all marginal counts; these clues cannot break the two diagonals.
    report = oracle.analyze(ShadingRecipe(2, 2, (BalancedLines(), DistinctLines(), NoThreeConsecutive()),
                                         ("row-count", "column-count")))
    assert report["completion_count"] == 2 and report["hint_policy"] == "none_identifiable"


def test_all_three_binary_fragments_act_on_four_by_four_without_expanding_demo_limits():
    rules = (BalancedLines(), NoThreeConsecutive(), DistinctLines())
    expected = {bits for bits in product((0, 1), repeat=16)
                if all(oracle.accepts(rule, bits, 4, 4) for rule in rules)}
    assert expected and expected == solver_answers(ShadingRecipe(4, 4, rules))
    with pytest.raises(ValueError, match="at most 9"):
        oracle.finite_space(ShadingRecipe(4, 4, rules))


@pytest.mark.parametrize("rows,cols", [(2, 4), (4, 2)])
def test_eight_cell_balance_is_feasible_until_distinct_lines_are_added(rows, cols):
    recipe = ShadingRecipe(rows, cols, (BalancedLines(), NoThreeConsecutive()))
    expected = {bits for bits in product((0, 1), repeat=8)
                if all(oracle.accepts(rule, bits, rows, cols) for rule in recipe.rules)}
    assert len(expected) == 6 and solver_answers(recipe) == expected
    assert ShadingRecipe(rows, cols, (*recipe.rules, DistinctLines())).create_empty().solve() is None


RECIPES = [
    ShadingRecipe(2, 3, (BlackCount(4), ConnectedBlack(), NoBlack2x2())),
    ShadingRecipe(3, 3, (BlackCount(4), BlackDominoes())),
    ShadingRecipe(2, 2, (BalancedLines(), NoThreeConsecutive(), DistinctLines())),
]


@pytest.mark.parametrize("recipe", RECIPES)
def test_generation_serialization_display_and_deductions_keep_every_rule(recipe):
    recipe = codec.read_recipe(codec.recipe_record(recipe))
    clues = finite.generate_finite(recipe, seed=0)
    assert clues == finite.generate_finite(recipe, seed=0)
    data = saved.puzzle_record(recipe, clues, seed=0, selection="finite")
    assert saved.verify(data)["unique"] and saved.verify(data)["irreducible"]
    text = saved.show(data)
    assert all(saved._rule_text(rule) in text for rule in recipe.rules)
    bits = tuple(v for row in data["solution"] for v in row)
    assert all(oracle.accepts(rule, bits, recipe.rows, recipe.cols) for rule in recipe.rules)
    trace = deduction.explain_puzzle(data)
    unsupported = [i for i, rule in enumerate(recipe.rules, 1) if type(rule) is not BlackCount]
    assert trace["rules_without_deductions"] == unsupported
    assert all(v is None or v == data["solution"][r][c]
               for r, row in enumerate(trace["cells"]) for c, v in enumerate(row))
    if type(recipe.rules[0]) is BalancedLines:
        assert trace["status"] == "stalled" and not trace["steps"]


def request(recipe):
    return {"format": api.PROFILE_FORMAT, "family": "shading", "rows": recipe.rows, "cols": recipe.cols,
            "rules": [{"id": (record := codec.rule_record(rule))["type"],
                       "parameters": {k: v for k, v in record.items() if k != "type"}} for rule in recipe.rules],
            "clue_kinds": list(recipe.clue_kinds), "seed": 0, "budget_seconds": 10}


@pytest.mark.parametrize("recipe", RECIPES)
def test_web_generation_uses_the_shared_cell_plan_and_validates_the_final_puzzle(recipe):
    result = worker.generate_request(request(recipe))
    assert result["status"] == "ok"
    assert list(result["plan"]["requirements"]["channels"]) == [
        {"name": "answer", "kind": "binary-cells"}, {"name": "givens", "kind": "cell-givens"}]
    assert saved.verify(result["record"])["valid"]


def test_web_reports_conflicts_and_hint_insufficiency_without_widening_limits():
    assert worker.generate_request(request(ShadingRecipe(2, 3, (BalancedLines(),))))["status"] == "unsatisfiable"
    recipe = ShadingRecipe(2, 2, (BalancedLines(),), ("row-count", "column-count"))
    assert worker.generate_request(request(recipe))["status"] == "insufficient_hints"
    for family in ("slitherlink", "coupled"):
        with pytest.raises(ValueError): api.read_request({**request(RECIPES[0]), "family": family})
    nine = tuple(codec.rule_choices().values())[:9]
    with pytest.raises(ValueError, match="at most 8"):
        api.read_request(request(ShadingRecipe(2, 3, nine)))
    assert api.read_request(request(ShadingRecipe(4, 4, (BalancedLines(),)))).recipe.rows == 4


@pytest.mark.parametrize("script,args", [
    ("analyze_shading.py", ["--rules", "balanced-lines", "distinct-lines", "no-three-consecutive", "--json"]),
    ("explore_shading.py", ["--candidates", "black-dominoes", "connected-black", "no-black-2x2", "--json"]),
])
def test_cli_choices_preserve_new_rule_ids(script, args):
    proc = subprocess.run([sys.executable, str(EXAMPLES / script), *args], capture_output=True,
                          text=True, encoding="utf-8", timeout=30)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data
    assert all(name in proc.stdout for name in args[1:-1])


def test_original_cli_defaults_are_not_expanded_to_every_catalog_rule():
    assert codec.DEFAULT_RULES == ("count", "non-touching", "connected-white", "no-white-2x2")
    assert len(codec.RULES) == len(set(codec.RULES))
    assert set(codec.DEFAULT_RULES) < set(codec.RULES)


@pytest.mark.parametrize("filename,recipe", zip(
    ("shading-sea-recipe.json", "shading-domino-recipe.json", "shading-binary-recipe.json"), RECIPES))
def test_documented_recipe_files_match_the_verified_examples(filename, recipe):
    assert codec.load_recipe(EXAMPLES / filename) == recipe
