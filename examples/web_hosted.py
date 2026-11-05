"""Bounded WSGI entry for the hosted demo; the local HTTP server stays local."""

from http import HTTPStatus
import json
import os
import threading
from urllib.parse import parse_qs

from json_records import _constant, _finite_float, _object
from web_answers import read_check
from web_catalog import catalog, read_request
from web_server import MAX_BODY, run_job

MAX_BUDGET = 10
JOB_LOCK = threading.Lock()  # Per Python instance, not a deployment-wide quota.


def app(environ, start_response):
    def respond(code, value):
        body = json.dumps(value, ensure_ascii=True, allow_nan=False).encode("utf-8")
        start_response(f"{code} {HTTPStatus(code).phrase}", [
            ("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
            ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"),
        ])
        return [body]

    # These hosts come from Vercel's deployment environment, never request headers.
    hosts = {os.environ.get(name) for name in ("VERCEL_URL", "VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_BRANCH_URL")}
    hosts.discard(None); hosts.discard("")
    host = environ.get("HTTP_HOST", "")
    if not hosts or host not in hosts:
        return respond(403, {"status": "forbidden"})
    raw_query = environ.get("QUERY_STRING", "")
    if len(raw_query) > 256: return respond(404, {"status": "not_found"})
    query = parse_qs(raw_query, keep_blank_values=True)
    if set(query) != {"operation"} or len(query["operation"]) != 1:
        return respond(404, {"status": "not_found"})
    operation = query["operation"][0]
    method = environ.get("REQUEST_METHOD")
    if operation == "catalog" and method == "GET":
        data = catalog()
        data["limits"]["max_budget_seconds"] = MAX_BUDGET
        data["hosting"] = {"label": "WEB DEMO", "budget_seconds": MAX_BUDGET,
                           "concurrency_scope": "instance", "persistent_jobs": False}
        return respond(200, data)
    if operation not in ("plan", "generate", "check"):
        return respond(404, {"status": "not_found"})
    if method != "POST": return respond(405, {"status": "method_not_allowed"})
    if (environ.get("HTTP_ORIGIN") != f"https://{host}"
            or environ.get("CONTENT_TYPE", "").split(";", 1)[0].strip().lower() != "application/json"):
        return respond(403, {"status": "forbidden"})
    try:
        length = environ.get("CONTENT_LENGTH", "")
        if (not length.isascii() or not length.isdigit() or len(length) > 5
                or not 0 < int(length) <= MAX_BODY or environ.get("HTTP_TRANSFER_ENCODING")):
            raise ValueError(f"A body of 1..{MAX_BODY} bytes and a single Content-Length is required")
        raw = environ["wsgi.input"].read(int(length))
        if len(raw) != int(length): raise ValueError("Incomplete request body")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                          parse_constant=_constant, parse_float=_finite_float)
        request = read_check(data) if operation == "check" else read_request(data)
        if request.budget > MAX_BUDGET: raise ValueError("Hosted computation budget must be 1..10 seconds")
    except (ValueError, RecursionError):
        # Do not echo arbitrary input or environment values to clients or logs.
        return respond(400, {"status": "invalid", "message": "Invalid request, unsupported recipe, or budget outside 1..10 seconds"})
    if operation == "plan": return respond(200, {"status": "ok", "plan": request.plan})
    if not JOB_LOCK.acquire(blocking=False): return respond(409, {"status": "busy"})
    try:
        return respond(200, run_job(data, check=operation == "check"))
    finally:
        JOB_LOCK.release()
