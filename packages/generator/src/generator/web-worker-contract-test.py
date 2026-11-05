"""Web worker transport must not turn malformed output into a verdict."""
from copy import deepcopy
import importlib
import json
from pathlib import Path
import subprocess

import pytest
from puzzle_defs import YajilinRecipe

with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(Path(__file__).resolve().parents[4] / 'examples'))
    catalog = importlib.import_module('web_catalog')
    server = importlib.import_module('web_server')
    worker = importlib.import_module('web_worker')


def shading_request():
    return {'format': catalog.PROFILE_FORMAT, 'family': 'shading', 'rows': 2, 'cols': 3,
            'rules': [{'id': 'count', 'parameters': {'count': 2}},
                      {'id': 'connected-white', 'parameters': {'nonempty': True}}],
            'clue_kinds': ['cell'], 'seed': 0, 'budget_seconds': 10}


def answer_request():
    return {'format': 'puzzle-box/web-answer-v1', 'request': shading_request(),
            'clues': [], 'answer': [0] * 6}


def fake_worker(monkeypatch, stdout):
    monkeypatch.setattr(server.subprocess, 'run',
                        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, stdout=stdout, stderr=''))


@pytest.mark.parametrize('value', [None, 0, 1, 'false', [], {}, 'true'])
def test_worker_check_requires_a_real_boolean(monkeypatch, value):
    fake_worker(monkeypatch, json.dumps({'status': 'ok', 'correct': value}))
    assert server.run_job(answer_request(), check=True) == {'status': 'unconfirmed'}


def test_definitive_booleans_and_inconclusive_check_remain_distinct(monkeypatch):
    for result in ({'status': 'ok', 'correct': True}, {'status': 'ok', 'correct': False},
                   {'status': 'unconfirmed'}):
        fake_worker(monkeypatch, json.dumps(result))
        assert server.run_job(answer_request(), check=True) == result
    fake_worker(monkeypatch, json.dumps({'status': 'unsatisfiable'}))
    assert server.run_job(answer_request(), check=True) == {'status': 'unconfirmed'}


@pytest.mark.parametrize('stdout', [
    '{"status":"ok","correct":true,"correct":false}',
    '{"status":"ok","correct":NaN}',
    '{"status":"unconfirmed","detail":1e999}',
    '[' * 2000 + '0' + ']' * 2000,
])
def test_invalid_or_ambiguous_worker_json_is_unconfirmed(monkeypatch, stdout):
    fake_worker(monkeypatch, stdout)
    assert server.run_job(answer_request(), check=True) == {'status': 'unconfirmed'}


@pytest.fixture(scope='module')
def shading_success():
    result = worker.generate_request(shading_request())
    assert result['status'] == 'ok'
    return json.loads(json.dumps(result))


def test_well_formed_serialized_success_is_accepted(monkeypatch, shading_success):
    data = shading_request()
    fake_worker(monkeypatch, json.dumps(shading_success))
    assert server.run_generation(data) == shading_success


@pytest.mark.parametrize('damage', ['missing-proof', 'unknown-unique', 'false-irreducible', 'integer-proof',
                                    'missing-evidence', 'missing-plan', 'wrong-plan', 'wrong-request',
                                    'missing-record', 'missing-solution', 'missing-clues',
                                    'missing-candidates', 'bad-candidates', 'unknown-method'])
def test_generation_rejects_unproven_or_mismatched_worker_success(monkeypatch, damage, shading_success):
    data = shading_request()
    result = deepcopy(shading_success)
    if damage == 'missing-proof': del result['evidence']['unique']
    elif damage == 'unknown-unique': result['evidence']['unique'] = None
    elif damage == 'false-irreducible': result['evidence']['irreducible'] = False
    elif damage == 'integer-proof': result['evidence']['unique'] = 1
    elif damage == 'missing-evidence': del result['evidence']
    elif damage == 'missing-plan': del result['plan']
    elif damage == 'wrong-plan': result['plan']['rows'] = 3
    elif damage == 'wrong-request': result['request']['seed'] = 1
    elif damage == 'missing-record': del result['record']
    elif damage == 'missing-solution': del result['record']['solution']
    elif damage == 'missing-clues': del result['clues']
    elif damage == 'missing-candidates': del result['evidence']['candidates']
    elif damage == 'bad-candidates': result['evidence']['candidates'] = True
    elif damage == 'unknown-method': result['evidence']['method'] = 'unknown'
    fake_worker(monkeypatch, json.dumps(result))
    assert server.run_generation(data) == {'status': 'unconfirmed'}


def test_finite_evidence_cannot_masquerade_as_shading_solver_proof(monkeypatch):
    data = shading_request()
    result = {'status': 'ok', 'request': deepcopy(data), 'plan': catalog.read_request(data).plan,
              'record': {'solution': [[0] * 3 for _ in range(2)]}, 'clues': [],
              'evidence': {'enumerated_boards': 64, 'completion_count': 1,
                           'unique': True, 'irreducible': True}}
    fake_worker(monkeypatch, json.dumps(result))
    assert server.run_generation(data) == {'status': 'unconfirmed'}


@pytest.mark.parametrize('status,count', [('unsatisfiable', 0), ('insufficient_hints', 1),
                                          ('search_exhausted', 64)])
def test_generation_non_success_statuses_are_not_conflated(monkeypatch, status, count):
    result = {'status': status, 'evidence': {'method': 'cp-sat', 'candidates': count,
                                             'unique': None, 'irreducible': None}}
    fake_worker(monkeypatch, json.dumps(result))
    assert server.run_generation(shading_request()) == result


def test_inconclusive_generation_remains_inconclusive(monkeypatch):
    result = {'status': 'unconfirmed'}
    fake_worker(monkeypatch, json.dumps(result))
    assert server.run_generation(shading_request()) == result


@pytest.mark.parametrize('family', ['shading', 'slitherlink', 'coupled'])
def test_real_worker_produces_accepted_artifact_for_each_family(family):
    if family == 'shading': data = shading_request()
    elif family == 'slitherlink':
        data = {'format': catalog.PROFILE_FORMAT, 'family': family, 'rows': 2, 'cols': 2,
                'rules': [{'id': 'single-loop', 'parameters': {}}],
                'clue_kinds': ['edge'], 'seed': 0, 'budget_seconds': 10}
    else:
        data = {'format': catalog.PROFILE_FORMAT, 'family': family, 'rows': 2, 'cols': 2,
                'rules': [{'id': r.identifier, 'parameters': {}} for r in YajilinRecipe.rule_ui],
                'clue_kinds': ['black', 'edge'], 'seed': 0, 'budget_seconds': 10}
    result = server.run_generation(data)
    assert result['status'] == 'ok', result
    assert result['evidence']['unique'] is True and result['evidence']['irreducible'] is True
    assert result['request'] == data
    assert result['plan'] == json.loads(json.dumps(catalog.read_request(data).plan))
    if family == 'shading':
        answer = [bit for row in result['record']['solution'] for bit in row]
    elif family == 'slitherlink':
        used = {tuple(edge) for edge in result['record']['solution']}
        answer = [int(tuple(edge) in used) for edge in result['edges']]
    else:
        solution = result['record']['solution']
        black = {tuple(cell) for cell in solution['black_cells']}
        used = {tuple(edge) for edge in solution['loop_edges']}
        answer = {'cells': [int(tuple(cell) in black) for cell in result['cells']],
                  'edges': [int(tuple(edge) in used) for edge in result['edges']]}
    check = {'format': 'puzzle-box/web-answer-v2' if family == 'coupled' else 'puzzle-box/web-answer-v1',
             'request': data, 'clues': result['clues'], 'answer': answer}
    assert server.run_job(check, check=True) == {'status': 'ok', 'correct': True}
    wrong = deepcopy(check)
    bits = wrong['answer']['cells'] if family == 'coupled' else wrong['answer']
    bits[0] ^= 1
    assert server.run_job(wrong, check=True) == {'status': 'ok', 'correct': False}


@pytest.mark.parametrize('field', ['request', 'plan'])
def test_returned_request_and_plan_distinguish_booleans_from_integers(monkeypatch, shading_success, field):
    result = deepcopy(shading_success)
    result[field]['rules'][1]['parameters']['nonempty'] = 1
    fake_worker(monkeypatch, json.dumps(result))
    assert server.run_generation(shading_request()) == {'status': 'unconfirmed'}


@pytest.mark.parametrize('status,count,unique,irreducible', [
    ('unsatisfiable', 1, None, None), ('unsatisfiable', 0, True, None),
    ('insufficient_hints', 0, None, None), ('search_exhausted', 1, None, None),
    ('search_exhausted', 65, None, None), ('ok', 65, True, True),
    ('unsatisfiable', True, None, None),
])
def test_contradictory_solver_evidence_is_unconfirmed(monkeypatch, status, count, unique, irreducible):
    result = {'status': status, 'evidence': {'method': 'cp-sat', 'candidates': count,
                                             'unique': unique, 'irreducible': irreducible}}
    fake_worker(monkeypatch, json.dumps(result))
    assert server.run_generation(shading_request()) == {'status': 'unconfirmed'}


def test_definitive_failure_with_a_success_artifact_is_unconfirmed(monkeypatch):
    result = {'status': 'unsatisfiable', 'record': {},
              'evidence': {'method': 'cp-sat', 'candidates': 0, 'unique': None, 'irreducible': None}}
    fake_worker(monkeypatch, json.dumps(result))
    assert server.run_generation(shading_request()) == {'status': 'unconfirmed'}


def family_request(family):
    if family == 'shading': return shading_request()
    if family == 'slitherlink':
        return {'format': catalog.PROFILE_FORMAT, 'family': family, 'rows': 2, 'cols': 2,
                'rules': [{'id': 'single-loop', 'parameters': {}}],
                'clue_kinds': ['edge'], 'seed': 0, 'budget_seconds': 10}
    return {'format': catalog.PROFILE_FORMAT, 'family': family, 'rows': 2, 'cols': 2,
            'rules': [{'id': r.identifier, 'parameters': {}} for r in YajilinRecipe.rule_ui],
            'clue_kinds': ['black', 'edge'], 'seed': 0, 'budget_seconds': 10}


@pytest.fixture(scope='module')
def samples():
    result = {}
    for family in ('shading', 'slitherlink', 'coupled'):
        data = family_request(family)
        output = worker.generate_request(data)
        assert output['status'] == 'ok'
        result[family] = json.loads(json.dumps(output))
    return result


@pytest.mark.parametrize('family', ['shading', 'slitherlink', 'coupled'])
@pytest.mark.parametrize('damage', ['null-solution', 'wrong-format', 'wrong-dimensions', 'wrong-seed',
                                    'wrong-hints', 'bad-clue', 'mismatched-clues', 'clue-contradicts-solution'])
def test_malformed_or_inconsistent_records_are_unconfirmed(monkeypatch, samples, family, damage):
    result = deepcopy(samples[family]); record = result['record']
    if damage == 'null-solution': record['solution'] = None
    elif damage == 'wrong-format': record['format'] = 'unknown'
    elif damage == 'wrong-dimensions': record['rows'] += 1
    elif damage == 'wrong-seed': record['seed'] += 1
    elif damage == 'wrong-hints': record['clue_kinds'] = []
    elif damage == 'bad-clue':
        result['clues'] = [{'type': 'not-a-hint'}]; record['clues'] = result['clues']
    elif damage == 'mismatched-clues': record['clues'] = [] if result['clues'] else ['bad']
    elif damage == 'clue-contradicts-solution':
        if family == 'shading':
            value = 1 - record['solution'][0][0]
            result['clues'] = [{'type': 'cell', 'row': 0, 'col': 0, 'value': value}]
            record['clues'] = [[0, 0, value]]
        elif family == 'slitherlink':
            edge = result['edges'][0]; used = int(edge not in record['solution'])
            result['clues'] = record['clues'] = [{'type': 'edge', 'edge': edge, 'used': used}]
        else:
            cell = [0, 0]; bit = int(cell not in record['solution']['black_cells'])
            result['clues'] = record['clues'] = [{'type': 'black', 'cell': cell, 'black': bit}]
    fake_worker(monkeypatch, json.dumps(result))
    assert server.run_generation(family_request(family)) == {'status': 'unconfirmed'}


@pytest.mark.parametrize('family', ['slitherlink', 'coupled'])
@pytest.mark.parametrize('damage', ['too-many-completions', 'wrong-enumeration', 'bad-edges', 'duplicate-edge', 'reversed-edge'])
def test_inconsistent_finite_evidence_and_solution_edges_are_unconfirmed(monkeypatch, samples, family, damage):
    result = deepcopy(samples[family])
    if damage == 'too-many-completions': result['evidence']['completion_count'] = result['evidence']['enumerated_boards'] + 1
    elif damage == 'wrong-enumeration': result['evidence']['enumerated_boards'] += 1
    elif damage == 'bad-edges': result['edges'][0] = [0, 0, 99, 99]
    else:
        solution = result['record']['solution']
        edges = solution if family == 'slitherlink' else solution['loop_edges']
        if damage == 'duplicate-edge': edges.append(edges[0])
        else: edges[0] = edges[0][2:] + edges[0][:2]
    fake_worker(monkeypatch, json.dumps(result))
    assert server.run_generation(family_request(family)) == {'status': 'unconfirmed'}


@pytest.mark.parametrize('status,completions', [('unsatisfiable', 1), ('insufficient_hints', 0)])
def test_contradictory_finite_failure_is_unconfirmed(monkeypatch, status, completions):
    result = {'status': status, 'evidence': {'enumerated_boards': 4096, 'completion_count': completions}}
    fake_worker(monkeypatch, json.dumps(result))
    assert server.run_generation(family_request('slitherlink')) == {'status': 'unconfirmed'}


@pytest.mark.parametrize('family', ['shading', 'slitherlink', 'coupled'])
def test_artifact_validation_never_builds_a_model_in_the_parent(monkeypatch, samples, family):
    from puzzle import Puzzle
    monkeypatch.setattr(Puzzle, '__init__', lambda *args, **kwargs: pytest.fail('unexpected model'))
    fake_worker(monkeypatch, json.dumps(samples[family]))
    assert server.run_generation(family_request(family))['status'] == 'ok'


def test_legacy_v1_shading_request_still_works_with_real_worker():
    data = shading_request()
    data.pop('family'); data['format'] = catalog.FORMAT
    result = server.run_generation(data)
    assert result['status'] == 'ok', result
    assert result['record']['format'] == 'puzzle-box/shading-v1'


@pytest.mark.parametrize('kind', ['shading-unsat', 'shading-insufficient', 'shading-exhausted',
                                  'loop-unsat', 'loop-insufficient', 'coupled-insufficient'])
def test_real_definitive_failure_evidence_is_preserved(kind):
    family = 'shading' if kind.startswith('shading') else 'coupled' if kind.startswith('coupled') else 'slitherlink'
    data = family_request(family)
    if kind == 'shading-unsat':
        data['rules'] = [{'id': 'count', 'parameters': {'count': 6}},
                         {'id': 'non-touching', 'parameters': {'diagonal': False}}]
    elif kind == 'shading-insufficient':
        data['rows'], data['cols'], data['clue_kinds'] = 2, 2, ['row-count']
        data['rules'] = [{'id': 'count', 'parameters': {'count': 1}}]
    elif kind == 'shading-exhausted':
        data.update(rows=3, cols=3, rules=[], clue_kinds=[])
    elif kind == 'coupled-insufficient':
        data.update(rows=3, cols=3, clue_kinds=[])
    elif kind == 'loop-unsat':
        data['rules'].append({'id': 'loop-length', 'parameters': {'length': 2}})
    else:
        data['clue_kinds'] = []
    result = server.run_generation(data)
    expected = ('unsatisfiable' if kind.endswith('unsat') else
                'search_exhausted' if kind.endswith('exhausted') else 'insufficient_hints')
    assert result['status'] == expected, result


def test_saved_rules_must_agree_with_the_original_request(monkeypatch, shading_success):
    result = deepcopy(shading_success)
    result['record']['rules'][1]['nonempty'] = False
    fake_worker(monkeypatch, json.dumps(result))
    assert server.run_generation(shading_request()) == {'status': 'unconfirmed'}
