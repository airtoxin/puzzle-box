"""Hosted WSGI boundary and curated deployment artifact; no platform credentials."""

import importlib
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[4]
with pytest.MonkeyPatch.context() as patch:
    patch.syspath_prepend(str(ROOT / "examples"))
    hosted = importlib.import_module("web_hosted")
    prepare = importlib.import_module("prepare_vercel")


def request():
    return {"format": "puzzle-box/web-request-v2", "family": "shading", "rows": 2, "cols": 3,
            "rules": [{"id": "count", "parameters": {"count": 2}}, {"id": "connected-white", "parameters": {"nonempty": True}}],
            "clue_kinds": ["cell", "row-count", "column-count"], "seed": 0, "budget_seconds": 10}


@pytest.fixture(autouse=True)
def hosts(monkeypatch):
    monkeypatch.setenv("VERCEL_URL", "demo-build.vercel.app")
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "demo.vercel.app")
    monkeypatch.delenv("VERCEL_BRANCH_URL", raising=False)


def call(operation="plan", data=None, **overrides):
    body = json.dumps(request() if data is None else data).encode()
    environ = {"REQUEST_METHOD": "POST", "QUERY_STRING": f"operation={operation}", "HTTP_HOST": "demo.vercel.app",
               "HTTP_ORIGIN": "https://demo.vercel.app", "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": str(len(body)),
               "wsgi.input": BytesIO(body), **overrides}
    response = []
    body = b"".join(hosted.app(environ, lambda code, headers: response.append((code, dict(headers)))))
    code, headers = response[0]
    assert headers["Cache-Control"] == "no-store" and int(headers["Content-Length"]) == len(body)
    return int(code[:3]), json.loads(body)


def test_catalog_advertises_hosted_budget_and_plan_matches_local_contract():
    code, data = call("catalog", REQUEST_METHOD="GET")
    assert code == 200 and data["limits"]["max_budget_seconds"] == 10
    assert data["hosting"]["concurrency_scope"] == "instance"
    assert call()[0] == 200
    assert call(data={**request(), "budget_seconds": 11})[0] == 400
    assert call(HTTP_HOST="demo-build.vercel.app", HTTP_ORIGIN="https://demo-build.vercel.app")[0] == 200


@pytest.mark.parametrize("override", [
    {"HTTP_HOST": "evil.example"}, {"HTTP_HOST": "demo.vercel.app,evil.example"},
    {"HTTP_ORIGIN": "https://evil.example"}, {"HTTP_ORIGIN": "null"}, {"HTTP_ORIGIN": "http://demo.vercel.app"},
    {"CONTENT_TYPE": "text/plain"}, {"CONTENT_LENGTH": ""}, {"CONTENT_LENGTH": "8193"},
    {"CONTENT_LENGTH": "-1"}, {"CONTENT_LENGTH": "2,2"}, {"HTTP_TRANSFER_ENCODING": "chunked"},
    {"wsgi.input": BytesIO(b"{")}, {"QUERY_STRING": "operation=plan&operation=generate"},
    {"QUERY_STRING": "operation=plan&extra=1"}, {"QUERY_STRING": "operation=" + "x"*300},
    {"REQUEST_METHOD": "GET"},
])
def test_invalid_requests_never_start_computation(monkeypatch, override):
    monkeypatch.setattr(hosted, "run_job", lambda *a, **k: pytest.fail("Worker must not run"))
    assert call("generate", **override)[0] in (400,403,404,405)


def test_missing_platform_host_and_duplicate_json_are_rejected(monkeypatch):
    body = b'{"format":"one","format":"two"}'
    assert call(**{"wsgi.input": BytesIO(body), "CONTENT_LENGTH": str(len(body))})[0] == 400
    monkeypatch.delenv("VERCEL_URL"); monkeypatch.delenv("VERCEL_PROJECT_PRODUCTION_URL")
    assert call()[0] == 403


def test_per_instance_lock_is_shared_by_generate_and_check_and_released_on_timeout(monkeypatch):
    monkeypatch.setattr(hosted, "run_job", lambda *a, **k: {"status": "timeout", "budget_seconds": 10})
    hosted.JOB_LOCK.acquire()
    try: assert call("generate") == (409, {"status": "busy"})
    finally: hosted.JOB_LOCK.release()
    assert call("generate")[1]["status"] == "timeout" and not hosted.JOB_LOCK.locked()


@pytest.mark.parametrize("rule_group", ["basic", "rooms", "component-shapes", "room-runs", "numbers", "run-length", "room-symmetry", "component-size", "tetromino-contact", "white-visibility", "component-border", "island-areas", "neighbor-counts", "cell-path", "component-sum", "room-forest", "corner-connected", "white-area-clues", "white-endpoints", "numbered-endpoints", "black-runs", "room-fill-levels", "room-neighbors", "room-components", "component-area-clues"])
def test_curated_export_contains_no_worktree_metadata_tests_or_developer_environment(tmp_path, rule_group):
    output = tmp_path / "artifact"
    payload = prepare.export(output)
    assert set(name for name in payload if name.startswith("public/")) == {"public/index.html", "public/app.js", "public/style.css"}
    assert not any(".git/" in name or ".venv/" in name or name.endswith("-test.py") or ".env" in name for name in payload)
    versions = {p["name"]: p["version"] for p in tomllib.loads((ROOT/"uv.lock").read_text())["package"]}
    for line in payload["requirements.txt"].decode().splitlines():
        if line.startswith("#"): continue
        name, version = line.split("=="); assert versions[name] == version
    with pytest.raises(FileExistsError): prepare.export(output)
    assert (output/"api/index.py").read_bytes() == payload["api/index.py"]
    # Simulate a platform-provided dependency directory added only to the parent
    # interpreter. The child must inherit it, as it does on Vercel's runtime.
    vendor = tmp_path / "platform-libs"; vendor.mkdir()
    (vendor/"_deployment_dependency_probe.py").write_text("READY = True\n")
    worker_path = output / "examples/web_worker.py"
    worker_path.write_text("import _deployment_dependency_probe\n" + worker_path.read_text(encoding="utf-8"), encoding="utf-8")
    # Fresh process: imports the artifact, not the developer's editable workspace.
    script = """
import importlib.util, io, json, os, pathlib, sys
sys.path.insert(0, os.environ['PUZZLE_TEST_VENDOR'])
spec = importlib.util.spec_from_file_location('entry', 'api/index.py')
entry = importlib.util.module_from_spec(spec); spec.loader.exec_module(entry)
import puzzle
assert pathlib.Path(puzzle.__file__).is_relative_to(pathlib.Path.cwd())
data = json.loads(os.environ['PUZZLE_TEST_REQUEST'])
raw = json.dumps(data).encode()
reply = []
body = b''.join(entry.app({'REQUEST_METHOD':'POST','QUERY_STRING':'operation=generate',
    'HTTP_HOST':'demo.vercel.app','HTTP_ORIGIN':'https://demo.vercel.app',
    'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw)},
    lambda code, headers: reply.append(code)))
assert reply == ['200 OK'] and json.loads(body)['status'] == 'ok', body
print('artifact generation passed')
"""
    data = request()
    if rule_group == "rooms":
        data["rules"] = [{"id": "room-black-count", "parameters": {"rooms": [[0,0,0], [1,1,1]], "count": 2}},
                         {"id": "black-dominoes", "parameters": {}}]
    elif rule_group == "component-shapes":
        data["rules"] = [{"id": "count", "parameters": {"count": 2}},
                         {"id": "rectangular-components", "parameters": {"black": True}},
                         {"id": "nonrectangular-components", "parameters": {"black": False}}]
    elif rule_group == "room-runs":
        data["rules"] = [{"id": "count", "parameters": {"count": 2}},
                         {"id": "no-white-across-three-rooms", "parameters": {"rooms": [[0,1,2],[0,1,2]]}}]
    elif rule_group == "numbers":
        data["rules"] = [{"id": "distinct-white-numbers", "parameters": {"numbers": [[1,1,2],[2,3,2]]}},
                         {"id": "non-touching", "parameters": {"diagonal": False}},
                         {"id": "connected-white", "parameters": {"nonempty": True}}]
    elif rule_group in ("run-length","room-symmetry"):
        data["rows"], data["cols"] = 1,6
        data["rules"] = [{"id": "room-black-count", "parameters": {"rooms": [[0,0,0,0,0,0]], "count": 2}},
                         {"id": "connected-black", "parameters": {"nonempty": True}},
                         {"id": "run-length-limit", "parameters": {"max_length": 3}}]
        if rule_group == "room-symmetry":
            data["rules"].append({"id": "room-rotational-symmetry", "parameters": {"rooms": [[0,0,0,0,0,0]]}})
    elif rule_group == "component-size":
        data["rows"],data["cols"] = 3,3
        data["rules"] = [{"id": "count", "parameters": {"count": 6}},
                         {"id": "connected-white", "parameters": {"nonempty": True}},
                         {"id": "color-component-size", "parameters": {"size": 3, "black": True}}]
    elif rule_group == "tetromino-contact":
        data["rows"],data["cols"] = 3,3
        rooms=[[0,0,1],[0,0,1],[1,1,1]]
        data["rules"] = [{"id": "room-black-count", "parameters": {"rooms": rooms, "count": 4}},
                         {"id": "room-connected-black", "parameters": {"rooms": rooms, "nonempty": True}},
                         {"id": "no-touching-equal-tetrominoes", "parameters": {"rooms": rooms}}]
    elif rule_group == "white-visibility":
        data["rules"] = [{"id": "white-visibility-counts", "parameters": {"counts": [[0,3,2],[0,0,0]]}},
                         {"id": "non-touching", "parameters": {"diagonal": False}},
                         {"id": "connected-white", "parameters": {"nonempty": True}}]
    elif rule_group == "component-border":
        data["rows"],data["cols"] = 3,3
        data["rules"] = [{"id": "white-visibility-counts", "parameters": {"counts": [[5,3,5],[0,0,0],[0,0,0]]}},
                         {"id": "connected-white", "parameters": {"nonempty": True}},
                         {"id": "components-touch-border", "parameters": {"black": True}}]
    elif rule_group == "island-areas":
        data["rules"] = [{"id": "white-island-areas", "parameters": {"areas": [[1,0,0],[0,0,2]]}},
                         {"id": "connected-black", "parameters": {"nonempty": False}},
                         {"id": "no-black-2x2", "parameters": {}}]
    elif rule_group == "neighbor-counts":
        data["rules"] = [{"id": "adjacent-black-counts", "parameters": {"neighbor_counts": [[0,None,1],[None,1,None]], "diagonal": True}}]
    elif rule_group == "cell-path":
        data["rules"] = [{"id": "connected-black", "parameters": {"nonempty": True}},
                         {"id": "color-degree-range", "parameters": {"minimum": 1, "maximum": 2, "black": True}},
                         {"id": "color-endpoint-count", "parameters": {"count": 2, "black": True}}]
    elif rule_group == "black-runs":
        data["rows"],data["cols"] = 3,3
        data["rules"] = [{"id": "adjacent-black-runs", "parameters": {"run_clues": [[None,[1,2],None],[None,[6],None],[None,None,None]]}},
                         {"id": "connected-black", "parameters": {"nonempty": True}},
                         {"id": "no-black-2x2", "parameters": {}}]
    elif rule_group == "numbered-endpoints":
        data["rules"] = [{"id": "white-endpoint-markers", "parameters": {"markers": [[1,0,0],[0,0,1]]}},
                         {"id": "white-visibility-counts", "parameters": {"counts": [[3,0,0],[0,0,2]]}},
                         {"id": "connected-white", "parameters": {"nonempty": True}}]
    elif rule_group == "white-endpoints":
        data["rules"] = [{"id": "white-endpoint-markers", "parameters": {"markers": [[1,0,0],[0,0,1]]}},
                         {"id": "connected-white", "parameters": {"nonempty": True}},
                         {"id": "no-white-2x2", "parameters": {}}]
    elif rule_group == "white-area-clues":
        data["rules"] = [{"id": "white-area-clues", "parameters": {"areas": [[1,0,0],[0,0,0]]}},
                         {"id": "rectangular-components", "parameters": {"black": False}},
                         {"id": "corner-connected-color", "parameters": {"black": False, "nonempty": True}},
                         {"id": "count", "parameters": {"count": 3}}]
    elif rule_group == "corner-connected":
        data["rules"] = [{"id": "corner-connected-color", "parameters": {"black": False, "nonempty": True}},
                         {"id": "rectangular-components", "parameters": {"black": False}},
                         {"id": "count", "parameters": {"count": 3}}]
    elif rule_group == "room-forest":
        data["rules"] = [{"id": "uniform-rooms", "parameters": {"rooms": [[0,0,1],[0,1,1]]}},
                         {"id": "acyclic-color", "parameters": {"black": False}},
                         {"id": "connected-white", "parameters": {"nonempty": True}}]
    elif rule_group == "component-area-clues":
        data["rules"] = [{"id":"component-area-clues","parameters":{"component_areas":[[1,0,0],[0,0,4]]}},
                         {"id":"rectangular-components","parameters":{"black":True}},
                         {"id":"nonrectangular-components","parameters":{"black":False}}]
        data["clue_kinds"] = ["cell"]
    elif rule_group == "room-components":
        rooms = [[0,0,1],[0,1,1],[1,1,1]]
        data["rows"],data["cols"] = 3,3
        data["rules"] = [{"id":"room-component-count","parameters":{"rooms":rooms,"count":2,"black":True}},
                         {"id":"equal-room-component-sizes","parameters":{"rooms":rooms,"black":True}},
                         {"id":"connected-black","parameters":{"nonempty":True}},
                         {"id":"no-black-2x2","parameters":{}}]
        data["clue_kinds"] = ["cell"]
    elif rule_group == "room-neighbors":
        rooms = [[0,0,0],[1,1,1]]
        data["rules"] = [{"id":"room-connected-black","parameters":{"rooms":rooms,"nonempty":True}}] + [
            {"id":name,"parameters":{"rooms":rooms,"black":True}}
            for name in ("no-color-across-rooms","adjacent-room-counts-differ")]
        data["clue_kinds"] = ["cell"]
    elif rule_group == "room-fill-levels":
        data["rows"], data["cols"] = 3,3
        data["rules"] = [{"id":"room-fill-levels","parameters":{"rooms":[[0,1,0],[0,1,0],[0,0,0]],"black":True}}]
        data["clue_kinds"] = ["row-count","column-count"]
    elif rule_group == "component-sum":
        data["rules"] = [{"id": "adjacent-black-component-sum", "parameters": {"component_counts": [[5,None,None],[None,None,None]]}}]
    result = subprocess.run([sys.executable, "-c", script], cwd=output, capture_output=True, text=True,
                            env={**os.environ, "PYTHONPATH": "", "PUZZLE_TEST_REQUEST": json.dumps(data),
                                 "PUZZLE_TEST_VENDOR": str(vendor)}, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
