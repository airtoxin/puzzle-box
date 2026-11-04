"""The local Web boundary, declarative plans, and finite generation outcomes."""

from copy import deepcopy
from dataclasses import fields
import http.client
import importlib
import json
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from puzzle_defs import BlackCount, ConnectedWhite, NoWhite2x2, NonTouchingBlack
from puzzle_defs.ui import UiChannel, UiRequirements, merge_requirements

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(EXAMPLES))
    api = importlib.import_module("web_catalog")
    worker = importlib.import_module("web_worker")
    server_api = importlib.import_module("web_server")
    saved = importlib.import_module("generate_shading")


def request():
    return {"format": api.FORMAT, "rows": 2, "cols": 3,
            "rules": [{"id": "count", "parameters": {"count": 2}},
                      {"id": "connected-white", "parameters": {"nonempty": True}}],
            "clue_kinds": ["cell", "row-count", "column-count"], "seed": 0, "budget_seconds": 10}


def test_existing_rules_declare_their_controls_without_changing_dataclass_parameters():
    assert {p.name for p in BlackCount.ui.parameters} == {f.name for f in fields(BlackCount)} == {"count"}
    assert NonTouchingBlack.ui.parameters[0].kind == ConnectedWhite.ui.parameters[0].kind == "boolean"
    assert not NoWhite2x2.ui.parameters and not fields(NoWhite2x2)
    assert {item["identifier"] for item in api.catalog()["rules"]} == set(api.CATALOG)


def test_plan_merges_shared_cells_and_only_selected_hint_channels():
    data = request()
    full = api.read_request(data).plan
    assert {c["name"] for c in full["requirements"]["channels"]} == set(api.RENDERERS)
    data["clue_kinds"] = ["row-count"]
    reduced = api.read_request(data).plan["requirements"]
    assert {c["name"] for c in reduced["channels"]} == {"answer", "row-counts"}
    data["rules"].reverse()
    assert api.read_request(data).plan["requirements"] == reduced


@pytest.mark.parametrize("requirements,match", [
    ([UiRequirements(), UiRequirements("vertices")], "Incompatible"),
    ([UiRequirements(channels=(UiChannel("answer", "numbers"),)), UiRequirements()], "Conflicting"),
    ([UiRequirements(channels=(UiChannel("edges", "loop"),))], "Unsupported UI"),
    ([UiRequirements("vertices")], "Unsupported board"),
    ([UiRequirements(max_cells=0)], "positive"),
])
def test_incompatible_or_unimplemented_requirements_are_not_silently_dropped(requirements, match):
    with pytest.raises(ValueError, match=match):
        merge_requirements(requirements, supported=api.RENDERERS)


def test_combined_board_limits_use_the_strictest_requirement():
    result = merge_requirements([UiRequirements(max_cells=6), UiRequirements()], supported=api.RENDERERS)
    assert result.max_cells == 6


@pytest.mark.parametrize("field,value", [("rows", True), ("cols", 0), ("seed", 1.0), ("seed", -1),
    ("budget_seconds", 0), ("budget_seconds", 31), ("budget_seconds", True), ("rules", {}),
    ("rules", [{"id": "payload/import", "parameters": {}}]), ("clue_kinds", {}),
    ("clue_kinds", ["cell", "cell"]), ("clue_kinds", ["edge"]), ("format", "future-version"),
    ("module", "payload"), ("requirements", {"max_cells": 999})])
def test_untrusted_request_cannot_extend_the_schema_or_run_custom_code(field, value):
    with pytest.raises(ValueError):
        api.read_request({**request(), field: value})


def test_parameter_types_bounds_unknown_fields_duplicates_and_area_are_checked():
    for params in ({"count": True}, {"count": 7}, {"count": 2, "module": "payload"}, {}):
        data = request(); data["rules"][0]["parameters"] = params
        with pytest.raises(ValueError): api.read_request(data)
    data = request(); data["rules"] *= 2
    with pytest.raises(ValueError, match="duplicate"): api.read_request(data)
    with pytest.raises(ValueError, match="9 cells"): api.read_request({**request(), "rows": 4})


def test_two_rule_generation_is_reproducible_and_accepted_by_existing_saved_reader():
    data = request(); before = deepcopy(data)
    first = worker.generate_request(data)
    second = worker.generate_request(data)
    assert first == second and data == before and first["status"] == "ok"
    assert saved.verify(first["record"]) == {"valid": True, "unique": True, "irreducible": True,
                                           "clue_count": len(first["clues"])}
    assert first["evidence"]["enumerated_boards"] == 64
    assert first["evidence"]["unique"] and first["evidence"]["irreducible"]
    assert saved.check_answer(first["record"], "/".join("".join("#" if v else "." for v in row)
                                                      for row in first["record"]["solution"]))


def test_impossible_and_insufficient_hint_results_have_finite_evidence():
    data = request(); data["rules"] = [{"id": "count", "parameters": {"count": 6}},
                                      {"id": "non-touching", "parameters": {"diagonal": False}}]
    result = worker.generate_request(data)
    assert result == {"status": "unsatisfiable", "evidence": {"enumerated_boards": 64, "completion_count": 0}}
    data.update(rows=2, cols=2, rules=[{"id": "count", "parameters": {"count": 1}}], clue_kinds=["row-count"])
    result = worker.generate_request(data)
    assert result == {"status": "insufficient_hints", "evidence": {"enumerated_boards": 16, "completion_count": 4}}


@pytest.mark.parametrize("mode", ["timeout", "exit", "malformed"])
def test_worker_failure_does_not_claim_infeasibility_or_uniqueness(monkeypatch, mode):
    def run(*args, **kwargs):
        assert kwargs["timeout"] == 10 and kwargs.get("shell", False) is False
        assert args[0][1] == str(EXAMPLES / "web_worker.py")
        if mode == "timeout": raise subprocess.TimeoutExpired(args[0], 10)
        return subprocess.CompletedProcess(args[0], 1 if mode == "exit" else 0, stdout="invalid", stderr="private")
    monkeypatch.setattr(server_api.subprocess, "run", run)
    assert server_api.run_generation(request())["status"] == ("timeout" if mode == "timeout" else "unconfirmed")


def test_actual_worker_process_returns_a_verified_problem():
    result = server_api.run_generation(request())
    assert result["status"] == "ok", result
    assert saved.verify(result["record"])["valid"]


def test_actual_timeout_kills_and_reaps_the_worker(monkeypatch):
    # The HTTP API never accepts an executable. Replace only the test's trusted
    # worker launch with a slow process, then inspect the real process object.
    original, started = subprocess.Popen, []
    def slow_worker(command, **kwargs):
        process = original([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
        started.append(process)
        return process
    monkeypatch.setattr(server_api.subprocess, "Popen", slow_worker)
    assert server_api.run_generation({**request(), "budget_seconds": 1}) == {"status": "timeout", "budget_seconds": 1}
    assert len(started) == 1 and started[0].poll() is not None


@pytest.fixture
def local_server():
    server = server_api.LocalServer(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    yield server
    server.shutdown(); server.server_close(); thread.join(timeout=3)


def send(server, path, body=None, *, origin=None, host=None, content_type="application/json"):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    headers = {"Host": host or server.authority, "Content-Type": content_type}
    if origin is not None: headers["Origin"] = origin
    connection.request("GET" if body is None else "POST", path, body=body, headers=headers)
    response = connection.getresponse(); result = response.status, dict(response.getheaders()), response.read()
    connection.close(); return result


def test_server_close_waits_for_the_active_worker_to_be_reaped(monkeypatch):
    original, processes, responses = subprocess.Popen, [], []
    started, closed = threading.Event(), threading.Event()
    def slow_worker(command, **kwargs):
        process = original([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
        processes.append(process); started.set()
        return process
    monkeypatch.setattr(server_api.subprocess, "Popen", slow_worker)
    server = server_api.LocalServer(0)
    serving = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01))
    serving.start()
    client = threading.Thread(target=lambda: responses.append(send(
        server, "/api/generate", json.dumps({**request(), "budget_seconds": 2}), origin=server.origin)))
    def close():
        server.server_close(); closed.set()
    closing = threading.Thread(target=close)
    client.start()
    try:
        assert started.wait(3)
        server.shutdown(); serving.join(timeout=3)
        # The context manager used after Ctrl+C calls this same close path.
        closing.start()
        assert not closed.wait(0.05), "server closed before its active worker was reaped"
        assert closed.wait(6)
        client.join(timeout=3)
        assert processes[0].poll() is not None
        assert responses[0][0] == 200
        assert json.loads(responses[0][2]) == {"status": "timeout", "budget_seconds": 2}
    finally:
        server.shutdown(); server.server_close()
        client.join(timeout=6); serving.join(timeout=3)
        if closing.ident is not None: closing.join(timeout=6)


def test_http_catalog_static_allowlist_and_real_plan(local_server):
    status, headers, body = send(local_server, "/")
    assert status == 200 and b"app.js" in body and "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert send(local_server, "/api/catalog")[0] == 200
    assert send(local_server, "/../uv.lock")[0] == 404
    assert send(local_server, "/", host="attacker.example")[0] == 403
    status, _, raw = send(local_server, "/api/plan", json.dumps(request()), origin=local_server.origin)
    assert status == 200 and json.loads(raw)["plan"]["rows"] == 2


@pytest.mark.parametrize("origin,content_type", [(None, "application/json"), ("null", "application/json"),
    ("https://attacker.example", "application/json"), ("same", "text/plain")])
def test_http_rejects_cross_origin_or_simple_form_requests(local_server, origin, content_type):
    origin = local_server.origin if origin == "same" else origin
    assert send(local_server, "/api/generate", json.dumps(request()), origin=origin, content_type=content_type)[0] == 403


@pytest.mark.parametrize("body", ['{"seed":0,"seed":1}', '{"x":NaN}', "["*1100, "x"*8193, b"\xff"],
                         ids=["duplicate", "nonfinite", "deep", "oversize", "encoding"])
def test_http_rejects_ambiguous_oversize_or_invalid_json(local_server, body):
    assert send(local_server, "/api/generate", body, origin=local_server.origin)[0] == 400


def test_busy_response_and_generation_error_do_not_leak_or_hold_the_lock(local_server, monkeypatch):
    with local_server.generation_lock:
        status, _, body = send(local_server, "/api/generate", json.dumps(request()), origin=local_server.origin)
        assert status == 409 and json.loads(body) == {"status": "busy"}
    monkeypatch.setattr(server_api, "run_generation", lambda data: {"status": "timeout", "budget_seconds": 10})
    status, _, body = send(local_server, "/api/generate", json.dumps(request()), origin=local_server.origin)
    assert status == 200 and json.loads(body)["status"] == "timeout"
    assert local_server.generation_lock.acquire(blocking=False)
    local_server.generation_lock.release()


def test_http_answer_validation_is_origin_protected_bounded_and_uses_a_real_worker(local_server):
    result = worker.generate_request(request())
    data = {"format": "puzzle-box/web-answer-v1", "request": request(), "clues": result["clues"],
            "answer": [v for row in result["record"]["solution"] for v in row]}
    assert send(local_server, "/api/check", json.dumps(data))[0] == 403
    with local_server.generation_lock:
        assert send(local_server, "/api/check", json.dumps(data), origin=local_server.origin)[0] == 409
    status, _, body = send(local_server, "/api/check", json.dumps(data), origin=local_server.origin)
    assert status == 200 and json.loads(body) == {"status": "ok", "correct": True}
    data["answer"] = [0]*6
    status, _, body = send(local_server, "/api/check", json.dumps(data), origin=local_server.origin)
    assert status == 200 and json.loads(body) == {"status": "ok", "correct": False}
    data["answer"] = [True]*6
    assert send(local_server, "/api/check", json.dumps(data), origin=local_server.origin)[0] == 400
