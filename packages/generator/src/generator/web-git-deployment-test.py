"""Repository Git-build entrypoint and public output; no platform credentials."""

import importlib
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
    static = importlib.import_module("prepare_web_static")
    prepare = importlib.import_module("prepare_vercel")


def test_static_output_is_exact_and_updates_in_place(tmp_path):
    output = tmp_path / "public"
    static.build(output)
    assert set(p.name for p in output.iterdir()) == set(static.ASSETS)
    for name in static.ASSETS:
        assert (output / name).read_bytes() == (ROOT / "apps/web" / name).read_bytes()
    (output / "app.js").write_text("old build", encoding="utf-8")
    static.build(output)
    assert (output / "app.js").read_bytes() == (ROOT / "apps/web/app.js").read_bytes()
    (output / "private.txt").write_text("leave alone", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected files"):
        static.build(output)
    assert (output / "private.txt").read_text(encoding="utf-8") == "leave alone"


def test_git_and_export_routes_headers_and_limits_match():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    exported = json.loads((ROOT / "deploy/vercel/vercel.json").read_text(encoding="utf-8"))
    assert config["rewrites"] == exported["rewrites"]
    assert config["headers"] == exported["headers"]
    assert config["functions"]["api/index.py"]["maxDuration"] == exported["functions"]["api/index.py"]["maxDuration"]
    assert config["outputDirectory"] == "build/vercel-public"
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    puzzle = tomllib.loads((ROOT / "packages/puzzle/pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["dependencies"] == puzzle["project"]["dependencies"]
    root_package = next(p for p in lock["package"] if p["name"] == "puzzle-box")
    assert {p["name"] for p in root_package["dependencies"]} == {"ortools"}


def test_git_entrypoint_uses_repository_sources_and_worker_dependency_path(tmp_path):
    # A fresh process with no editable source paths, containing only runtime
    # modules, the native entrypoint and the shared export bootstrap.
    root = tmp_path / "repo"
    for name, data in prepare.files().items():
        if name.startswith(("examples/", "packages/")):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    for name in ("api/index.py", "deploy/vercel/api/index.py"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / name).read_bytes())
    vendor = tmp_path / "platform-libs"
    vendor.mkdir()
    (vendor / "_git_build_probe.py").write_text("READY = True\n", encoding="utf-8")
    worker = root / "examples/web_worker.py"
    worker.write_text("import _git_build_probe\n" + worker.read_text(encoding="utf-8"), encoding="utf-8")
    script = """
import importlib.util, io, json, os, pathlib, sys
sys.path.insert(0, os.environ['PUZZLE_TEST_VENDOR'])
spec = importlib.util.spec_from_file_location('entry', 'api/index.py')
entry = importlib.util.module_from_spec(spec); spec.loader.exec_module(entry)
import puzzle
assert pathlib.Path(puzzle.__file__).is_relative_to(pathlib.Path.cwd())
def call(operation, data=None):
    raw = json.dumps(data).encode()
    reply = []
    body = b''.join(entry.app({'REQUEST_METHOD':'GET' if data is None else 'POST',
        'QUERY_STRING':'operation='+operation, 'HTTP_HOST':'demo.vercel.app',
        'HTTP_ORIGIN':'https://demo.vercel.app', 'CONTENT_TYPE':'application/json',
        'CONTENT_LENGTH':str(len(raw)), 'wsgi.input':io.BytesIO(raw)},
        lambda code, headers: reply.append(code)))
    assert reply == ['200 OK'], body
    return json.loads(body)
assert call('catalog')['format'] == 'puzzle-box/web-catalog-v1'
request = {'format':'puzzle-box/web-request-v2','family':'shading','rows':2,'cols':3,
    'rules':[{'id':'count','parameters':{'count':2}}],
    'clue_kinds':['cell'],'seed':0,'budget_seconds':10}
generated = call('generate', request)
assert generated['status'] == 'ok' and generated['evidence']['unique'] is True, generated
record = generated['record']
answer = {'format':'puzzle-box/web-answer-v1','request':request,'clues':generated['clues'],
    'answer':[v for row in record['solution'] for v in row]}
assert call('check', answer) == {'status':'ok','correct':True}
answer['answer'][0] ^= 1
assert call('check', answer) == {'status':'ok','correct':False}
print('generated and checked from repository entrypoint')
"""
    result = subprocess.run([sys.executable, "-c", script], cwd=root, capture_output=True, text=True,
                            env={**os.environ, "PYTHONPATH": "", "PUZZLE_TEST_VENDOR": str(vendor),
                                 "VERCEL_URL": "demo.vercel.app"}, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
