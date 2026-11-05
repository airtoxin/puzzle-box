"""Validate bounded Web worker output without constructing a solver model."""
import json
from typing import Any

from puzzle import Cell
from puzzle_defs import ShadingRecipe, SlitherlinkRecipe, YajilinRecipe
from generator.search import DEFAULT_MAX_CANDIDATES
from analyze_shading import full_clues as shading_full_clues
from generate_shading import _read_record as read_shading_record, clue_record as shading_clue_record
from generate_slitherlink import read_record as read_loop_record, clue_record as loop_clue_record, edge_record
from generate_yajilin import read_record as read_coupled_record, clue_record as coupled_clue_record
from shading_recipe import rule_record
from web_answers import read_clues
from web_catalog import Request
from web_loop import edges_for, full_clues as loop_full_clues
from web_coupled import full_clues as coupled_full_clues


def same_json(left: Any, right: Any) -> bool:
    """Compare JSON types exactly while treating Python tuples as JSON arrays."""
    return json.dumps(left, sort_keys=True, separators=(',', ':'), allow_nan=False) == json.dumps(
        right, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _evidence_ok(status: str, evidence: Any, recipe: Any) -> bool:
    if type(evidence) is not dict:
        return False
    if isinstance(recipe, ShadingRecipe):
        if evidence.get('method') != 'cp-sat': return False
        count = evidence.get('candidates')
        if type(count) is not int or not 0 <= count <= min(DEFAULT_MAX_CANDIDATES, 2**(recipe.rows*recipe.cols)):
            return False
        if status == 'ok':
            return count > 0 and evidence.get('unique') is True and evidence.get('irreducible') is True
        if evidence.get('unique') is not None or evidence.get('irreducible') is not None:
            return False
        if status == 'unsatisfiable': return count == 0
        if status == 'insufficient_hints': return count > 0
        if status == 'search_exhausted': return count == DEFAULT_MAX_CANDIDATES
        return False
    if 'method' in evidence: return False
    edge_count = (2*recipe.rows*recipe.cols - recipe.rows - recipe.cols if isinstance(recipe, YajilinRecipe)
                  else 2*recipe.rows*recipe.cols + recipe.rows + recipe.cols)
    boards, completions = evidence.get('enumerated_boards'), evidence.get('completion_count')
    if (type(boards) is not int or boards != 2**edge_count
            or type(completions) is not int or not 0 <= completions <= boards):
        return False
    if status == 'ok':
        return completions > 0 and evidence.get('unique') is True and evidence.get('irreducible') is True
    if evidence.get('unique') is not None or evidence.get('irreducible') is not None: return False
    if status == 'unsatisfiable': return completions == 0
    if status == 'insufficient_hints': return completions > 0
    return False


def _record_ok(response: dict[str, Any], request: Request) -> bool:
    recipe, record = request.recipe, response.get('record')
    if type(record) is not dict or type(response.get('clues')) is not list:
        return False
    # Bound both lists before invoking any record reader.
    rows, cols = recipe.rows, recipe.cols
    edge_count = (2*rows*cols-rows-cols if isinstance(recipe, YajilinRecipe)
                  else 2*rows*cols+rows+cols if isinstance(recipe, SlitherlinkRecipe) else 0)
    count = rows*cols + edge_count if isinstance(recipe, YajilinRecipe) else edge_count or rows*cols
    clues = read_clues(recipe, response['clues'], count)
    if type(record.get('clues')) is not list or len(record['clues']) != len(clues): return False
    if (not same_json(record.get('seed'), request.seed) or not same_json(record.get('rows'), rows)
            or not same_json(record.get('cols'), cols)):
        return False
    environment = record.get('environment')
    if (type(environment) is not dict or set(environment) != {'python', 'ortools', 'seeded_search_workers'}
            or type(environment['python']) is not str or not environment['python']
            or type(environment['ortools']) is not str or not environment['ortools']
            or type(environment['seeded_search_workers']) is not int or environment['seeded_search_workers'] != 1):
        return False
    if isinstance(recipe, ShadingRecipe):
        answer = record.get('solution')
        if (type(answer) is not list or len(answer) != rows or any(
                type(row) is not list or len(row) != cols or any(type(v) is not int or v not in (0, 1) for v in row)
                for row in answer)):
            return False
        if not same_json(record.get('rules'), [rule_record(rule) for rule in recipe.rules]): return False
        legacy = recipe.clue_kinds == ('cell',)
        if record.get('format') != ('puzzle-box/shading-v1' if legacy else 'puzzle-box/shading-v2'):
            return False
        if not legacy and not same_json(record.get('clue_kinds'), list(recipe.clue_kinds)): return False
        parsed_recipe, stored_clues, answer = read_shading_record(record)
        expected_web = [shading_clue_record(clue) for clue in clues]
        expected_stored = [shading_clue_record(clue, legacy=legacy) for clue in clues]
        possible = shading_full_clues(recipe, tuple(v for row in answer for v in row))
    elif isinstance(recipe, SlitherlinkRecipe):
        solution = record.get('solution')
        if type(solution) is not list or len(solution) > edge_count: return False
        if set(record) != {'format', 'rows', 'cols', 'loop_length', 'clue_kinds', 'clues', 'seed', 'solution', 'environment'}:
            return False
        if not same_json(record.get('clue_kinds'), list(recipe.clue_kinds)): return False
        parsed_recipe, stored_clues, answer = read_loop_record(record)
        edges = edges_for(rows, cols)
        if not same_json(response.get('edges'), [edge_record(e) for e in edges]): return False
        if not same_json(solution, [edge_record(e) for e in edges if e in answer]): return False
        if not same_json(record.get('loop_length'), recipe.loop_length): return False
        expected_web = expected_stored = [loop_clue_record(clue) for clue in clues]
        possible = loop_full_clues(recipe, frozenset(answer))
    else:
        solution = record.get('solution')
        if (type(solution) is not dict or set(solution) != {'black_cells', 'loop_edges'}
                or type(solution['black_cells']) is not list or len(solution['black_cells']) > rows*cols
                or type(solution['loop_edges']) is not list or len(solution['loop_edges']) > edge_count):
            return False
        if set(record) != {'format', 'rows', 'cols', 'arrow_sites', 'clue_kinds', 'clues', 'seed', 'solution', 'environment'}:
            return False
        if (not same_json(record.get('clue_kinds'), list(recipe.clue_kinds))
                or not same_json(record.get('arrow_sites'), [])):
            return False
        parsed_recipe, stored_clues, answer = read_coupled_record(record)
        cells = [Cell(r, c) for r in range(rows) for c in range(cols)]
        edges = edges_for(rows-1, cols-1)
        if not same_json(response.get('cells'), [list(c) for c in cells]): return False
        if not same_json(response.get('edges'), [edge_record(e) for e in edges]): return False
        if not same_json(solution['black_cells'], [list(c) for c in cells if c in answer.black_cells]): return False
        if not same_json(solution['loop_edges'], [edge_record(e) for e in edges if e in answer.loop_edges]): return False
        expected_web = expected_stored = [coupled_clue_record(clue) for clue in clues]
        possible = coupled_full_clues(recipe, answer, cells, edges)
    return (parsed_recipe == recipe and stored_clues == clues
            and same_json(response['clues'], expected_web) and same_json(record['clues'], expected_stored)
            and set(clues) <= set(possible))


def worker_response(response: Any, request: Request, data: Any, *, check: bool, restore: bool = False) -> dict[str, Any]:
    """Admit coherent transport outcomes, without re-solving mathematical claims."""
    unknown = {'status': 'unconfirmed'}
    try:
        if type(response) is not dict: return unknown
        status = response.get('status')
        if restore:
            if status in ('unconfirmed', 'invalid_puzzle'): return {'status': status}
            if (status != 'ok' or not same_json(response.get('plan'), request.plan)
                    or not same_json(response.get('request'), data['request'])
                    or not same_json(response.get('clues'), data['clues'])
                    or not _record_ok(response, request)):
                return unknown
            return response
        if check:
            if status == 'unconfirmed': return response
            return response if status == 'ok' and type(response.get('correct')) is bool else unknown
        if status == 'unconfirmed': return response
        if status not in ('ok', 'unsatisfiable', 'insufficient_hints', 'search_exhausted'): return unknown
        if not _evidence_ok(status, response.get('evidence'), request.recipe): return unknown
        if status != 'ok':
            if any(key in response for key in ('record', 'clues', 'plan', 'request', 'cells', 'edges')):
                return unknown
            return response
        if (not same_json(response.get('plan'), request.plan) or not same_json(response.get('request'), data)
                or not _record_ok(response, request)):
            return unknown
        return response
    except (ValueError, TypeError, KeyError, IndexError, RecursionError):
        return unknown
