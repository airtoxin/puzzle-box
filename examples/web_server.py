"""Local-only declarative puzzle Web app; not a production/public HTTP server."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from typing import Any, cast

from json_records import _constant, _finite_float, _object
from web_catalog import catalog, read_request
from web_answers import read_check
from web_assets import ASSET_TYPES

ROOT = Path(__file__).resolve().parents[1]
MAX_BODY = 32768
ASSETS = {"/": ("index.html", ASSET_TYPES["index.html"]),
          **{f"/{name}": (name, mime) for name, mime in ASSET_TYPES.items() if name != "index.html"}}


def run_generation(data: Any) -> dict[str, Any]:
    return run_job(data)


def run_job(data: Any, *, check: bool = False) -> dict[str, Any]:
    request = read_check(data) if check else read_request(data)
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "examples/web_worker.py"), *( ["--check"] if check else [])], input=json.dumps(data),
            capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=request.budget,
            env=dict(os.environ, PYTHONHASHSEED="0", PYTHONIOENCODING="utf-8"),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode != 0:
            return {"status": "unconfirmed"}
        response = json.loads(result.stdout)
        if type(response) is not dict or response.get("status") not in (
                "ok", "unsatisfiable", "insufficient_hints", "search_exhausted", "unconfirmed"):
            return {"status": "unconfirmed"}
        return response
    except subprocess.TimeoutExpired:
        # run() kills and reaps the worker. OS startup/cleanup may exceed the
        # budget; this is not a CPU, memory, or arbitrary-code sandbox.
        return {"status": "timeout", "budget_seconds": request.budget}
    except (OSError, ValueError):
        return {"status": "unconfirmed"}


class LocalServer(ThreadingHTTPServer):
    # Keep bounded generation requests alive through Ctrl+C/server_close so
    # subprocess.run can enforce its timeout and reap the worker.
    daemon_threads = False

    def __init__(self, port: int):
        self.generation_lock = threading.Lock()
        super().__init__(("127.0.0.1", port), Handler)
        self.authority = f"127.0.0.1:{self.server_port}"
        self.origin = f"http://{self.authority}"


class Handler(BaseHTTPRequestHandler):
    @property
    def application(self) -> LocalServer:
        return cast(LocalServer, self.server)

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(3)

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Do not log client-controlled paths or payloads.

    def respond(self, status: int, data: bytes, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; "
                         "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def json_response(self, status: int, data: Any) -> None:
        self.respond(status, json.dumps(data, ensure_ascii=True, allow_nan=False).encode("utf-8"))

    def valid_host(self) -> bool:
        if self.headers.get_all("Host") != [self.application.authority]:
            self.json_response(403, {"status": "forbidden"})
            return False
        return True

    def do_GET(self) -> None:
        if not self.valid_host():
            return
        if self.path == "/api/catalog":
            self.json_response(200, catalog())
        elif self.path in ASSETS:
            name, mime = ASSETS[self.path]
            self.respond(200, (ROOT / "apps/web" / name).read_bytes(), mime)
        else:
            self.json_response(404, {"status": "not_found"})

    def read_body(self) -> bytes:
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not lengths[0].isdigit() or "Transfer-Encoding" in self.headers:
            raise ValueError("A single Content-Length is required")
        length = int(lengths[0])
        if length <= 0:
            raise ValueError("Request must have a nonempty body")
        # Consume a bounded, framed request before a rejection closes the socket:
        # closing with incoming body data can erase the response via a TCP reset.
        # Read at most one extra byte even if a hostile length declares gigabytes.
        raw = self.rfile.read(min(length, MAX_BODY + 1))
        if length > MAX_BODY:
            raise ValueError(f"Request must be at most {MAX_BODY} bytes")
        if len(raw) != length:
            raise ValueError("Incomplete request")
        return raw

    def do_POST(self) -> None:
        try:
            raw = self.read_body()
        except (ValueError, TimeoutError) as exc:
            self.json_response(400, {"status": "invalid", "message": str(exc)})
            return
        except OSError:
            return  # The client disconnected; no work or JSON parsing occurred.
        if not self.valid_host():
            return
        if (self.headers.get_all("Origin") != [self.application.origin]
                or self.headers.get_content_type() != "application/json"):
            self.json_response(403, {"status": "forbidden"})
            return
        if self.path not in ("/api/plan", "/api/generate", "/api/check"):
            self.json_response(404, {"status": "not_found"})
            return
        try:
            data = json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                              parse_constant=_constant, parse_float=_finite_float)
            request = read_check(data) if self.path == "/api/check" else read_request(data)
        except (ValueError, RecursionError, TimeoutError) as exc:
            self.json_response(400, {"status": "invalid", "message": str(exc)})
            return
        if self.path == "/api/plan":
            self.json_response(200, {"status": "ok", "plan": request.plan})
        elif not self.application.generation_lock.acquire(blocking=False):
            self.json_response(409, {"status": "busy"})
        else:
            try:
                self.json_response(200, run_job(data, check=True) if self.path == "/api/check" else run_generation(data))
            finally:
                self.application.generation_lock.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("port must be in 0..65535")
    with LocalServer(args.port) as server:
        print(f"Puzzle Box: {server.origin} (local only; Ctrl+C to stop)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
