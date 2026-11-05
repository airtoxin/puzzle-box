"""Connected-subset clauses versus two component partitions and local floods."""

from dataclasses import replace
import importlib
from itertools import product
from pathlib import Path

import pytest

from puzzle import Cell, unique
from puzzle_defs import BlackCount, ConnectedBlack, CornerConnectedColor, CornerLinkedComponents, ShadingRecipe

EXAMPLES=Path(__file__).resolve().parents[4]/"examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    oracle=importlib.import_module("analyze_shading")
    codec=importlib.import_module("shading_recipe")
    saved=importlib.import_module("generate_shading")
    deductions=importlib.import_module("explain_shading")
    api=importlib.import_module("web_catalog")
    worker=importlib.import_module("web_worker")
    checks=importlib.import_module("web_answers")


def reference(bits,rows,cols,black):
    selected=[i for i,v in enumerate(bits) if bool(v)==black]
    def partition(diagonal):
        parents={i:i for i in selected}
        def root(i):
            while parents[i]!=i:i=parents[i]
            return i
        for i in selected:
            for j in selected:
                dr,dc=abs(i//cols-j//cols),abs(i%cols-j%cols)
                if (max(dr,dc)==1 if diagonal else dr+dc==1):parents[root(i)]=root(j)
        return {i:root(i) for i in selected}
    orthogonal,diagonal=partition(False),partition(True)
    chains={}
    for i in selected:chains.setdefault(diagonal[i],set()).add(orthogonal[i])
    # A selected eight-component is valid exactly when it contains at least
    # two distinct four-components. Empty selections satisfy this vacuously.
    return all(len(blocks)>=2 for blocks in chains.values())


@pytest.mark.parametrize("rows,cols",[(1,1),(1,4),(2,2),(2,3),(3,2)])
@pytest.mark.parametrize("black",[True,False])
def test_every_small_board_matches_the_dsl_and_two_independent_component_checks(rows,cols,black):
    rule=CornerLinkedComponents(black)
    for bits in product((0,1),repeat=rows*cols):
        expected=reference(bits,rows,cols,black)
        assert oracle.accepts(rule,bits,rows,cols)==expected
        # Fixed assignments bound solver work even for nearly unrestricted sets.
        assert (fixed(rows,cols,bits,rule).solve() is not None)==expected


def fixed(rows,cols,bits,*rules):
    return ShadingRecipe(rows,cols,rules).build_from_clues(
        [(Cell(r,c),bits[r*cols+c]) for r in range(rows) for c in range(cols)])


def test_three_by_three_reference_checkers_agree_on_all_512_boards():
    for black in (True,False):
        rule=CornerLinkedComponents(black)
        for bits in product((0,1),repeat=9):
            assert oracle.accepts(rule,bits,3,3)==reference(bits,3,3,black)


def test_internal_corners_single_components_and_empty_color_have_distinct_meanings():
    rule=CornerLinkedComponents()
    assert fixed(2,2,(1,1,1,0),CornerConnectedColor()).solve() is not None
    assert fixed(2,2,(1,1,1,0),rule).solve() is None  # diagonal contact is INTERNAL
    assert fixed(2,2,(1,0,0,1),rule).solve() is not None  # equal singleton shapes allowed
    assert fixed(2,3,(1,0,0,1,0,1),rule).solve() is None  # domino and isolated singleton
    for value in (0,1):
        p=fixed(2,3,(value,)*6,CornerLinkedComponents(bool(value)))
        assert p.solve() is None  # nonempty single component
        q=fixed(2,3,(value,)*6,CornerLinkedComponents(not bool(value)))
        q.add(unique());assert q.solve() is not None  # empty selected color


@pytest.mark.parametrize("black",[True,False])
def test_two_disconnected_corner_chains_are_allowed_in_a_ten_cell_core_board(black):
    chosen=(1,0,0,0,1,0,1,0,1,0)
    bits=chosen if black else tuple(1-v for v in chosen)
    rule=CornerLinkedComponents(black)
    assert reference(bits,2,5,black) and oracle.accepts(rule,bits,2,5)
    p=fixed(2,5,bits,rule);assert p.solution_vars is not None and len(p.solution_vars)==10
    p.add(unique());assert p.solve() is not None
    assert fixed(2,5,bits,CornerConnectedColor(black)).solve() is None


@pytest.mark.parametrize("bad",[0,1,None,"black"])
def test_color_input_is_strict_and_codecs_are_exact(bad):
    with pytest.raises(ValueError):CornerLinkedComponents(bad)
    with pytest.raises(ValueError):codec.read_rule({"type":"corner-linked-components","black":bad})


def test_round_trip_and_resource_bound_are_checked_before_enumeration(monkeypatch):
    for rule in (CornerLinkedComponents(),CornerLinkedComponents(False)):
        assert codec.read_rule(codec.rule_record(rule))==rule
        with pytest.raises(ValueError):codec.read_rule({**codec.rule_record(rule),"extra":0})
        with pytest.raises(ValueError):codec.read_rule({"type":"corner-linked-components"})
        with pytest.raises(ValueError,match="exact built-in"):codec.rule_record(type("Changed",(CornerLinkedComponents,),{})())
    ten=ShadingRecipe(2,5,(CornerLinkedComponents(),BlackCount(0)))
    assert codec.read_recipe(codec.recipe_record(ten))==ten
    record=saved.puzzle_record(ten,[],seed=0)
    assert saved.verify(record)["unique"] and "corner" in saved.show(record)
    large=replace(ten,cols=6)
    with pytest.raises(ValueError,match="at most 10"):codec.recipe_record(large)
    with pytest.raises(ValueError,match="at most 10"):saved.show({**record,"cols":6,"solution":[[0]*6,[0]*6]})
    module=importlib.import_module("puzzle_defs.puzzles.corner_linked_components")
    monkeypatch.setattr(module,"_connected_subsets",lambda *a:pytest.fail("Must reject before enumeration"))
    with pytest.raises(ValueError,match="at most 10"):large.create_empty()


def request(recipe):
    return {"format":api.PROFILE_FORMAT,"family":"shading","rows":recipe.rows,"cols":recipe.cols,
            "rules":[{"id":(r:=codec.rule_record(rule))["type"],"parameters":{k:v for k,v in r.items() if k!="type"}} for rule in recipe.rules],
            "clue_kinds":list(recipe.clue_kinds),"seed":0,"budget_seconds":10}


def test_corner_chain_example_composes_with_component_and_cell_counts():
    recipe=codec.load_recipe(EXAMPLES/"shading-corner-chain-recipe.json")
    expected={(0,0,1,1,1,0),(0,1,1,1,0,0),(1,0,0,0,1,1),(1,1,0,0,0,1)}
    assert oracle.analyze(recipe)["completion_count"]==4
    assert {b for b in product((0,1),repeat=6) if reference(b,2,3,True) and sum(b)==3
            and oracle.accepts(recipe.rules[1],b,2,3)}==expected
    result=worker.generate_request(request(recipe))
    assert result["status"]=="ok" and len(result["clues"])==2
    assert tuple(v for row in result["record"]["solution"] for v in row) in expected
    assert saved.verify(result["record"])["unique"]
    assert "touches a different component" in saved.show(result["record"])
    assert deductions.explain_puzzle(result["record"])["rules_without_deductions"]==[1,2]
    answer=[v for row in result["record"]["solution"] for v in row]
    assert checks.check_answer({"format":checks.FORMAT,"request":result["request"],"clues":result["clues"],"answer":answer})=={"status":"ok","correct":True}
    assert worker.generate_request(request(replace(recipe,rules=(*recipe.rules,ConnectedBlack()))))["status"]=="unsatisfiable"
    with pytest.raises(ValueError):api.read_request(request(ShadingRecipe(2,5,(CornerLinkedComponents(),))))
    for family in ("slitherlink","coupled"):
        with pytest.raises(ValueError):api.read_request({**request(recipe),"family":family})
