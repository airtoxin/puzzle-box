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


def shading_request():
    return {'format': catalog.PROFILE_FORMAT, 'family': 'shading', 'rows': 2, 'cols': 3,
            'rules': [{'id': 'count', 'parameters': {'count': 2}}],
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


def test_well_formed_serialized_success_is_accepted(monkeypatch):
    data = shading_request()
    result = {'status': 'ok', 'request': deepcopy(data), 'plan': catalog.read_request(data).plan,
              'record': {'solution': [[0] * 3 for _ in range(2)]}, 'clues': [],
              'evidence': {'method': 'cp-sat', 'candidates': 1, 'unique': True, 'irreducible': True}}
    fake_worker(monkeypatch, json.dumps(result))
    assert server.run_generation(data) == json.loads(json.dumps(result))


@pytest.mark.parametrize('damage', ['missing-proof', 'unknown-unique', 'false-irreducible', 'integer-proof',
                                    'missing-evidence', 'missing-plan', 'wrong-plan', 'wrong-request',
                                    'missing-record', 'missing-solution', 'missing-clues',
                                    'missing-candidates', 'bad-candidates', 'unknown-method'])
def test_generation_rejects_unproven_or_mismatched_worker_success(monkeypatch, damage):
    data = shading_request()
    result = {'status': 'ok', 'request': deepcopy(data), 'plan': catalog.read_request(data).plan,
              'record': {'solution': [[0] * 3 for _ in range(2)]}, 'clues': [],
              'evidence': {'method': 'cp-sat', 'candidates': 1, 'unique': True, 'irreducible': True}}
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


@pytest.mark.parametrize('status', ['unsatisfiable', 'insufficient_hints', 'search_exhausted', 'unconfirmed'])
def test_generation_non_success_statuses_are_not_conflated(monkeypatch, status):
    result = {'status': status, 'evidence': {'unique': None}}
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
