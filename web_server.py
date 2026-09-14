#!/usr/bin/env python3
"""投递进度本地网页，只监听 127.0.0.1。"""
from records import parse_records, GROUPS
import argparse
import file_lock
import runtime
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = runtime.HOME
DATA = runtime.DATA
WEB = runtime.ASSETS / "web" / "dist"


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return default


def scanner_busy():
    with (DATA / "monitor.lock").open("a+") as lock:
        try:
            file_lock.acquire(lock)
        except BlockingIOError:
            return True
    return False


def safe_link(url):
    parts = urlsplit(url)
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if k == "dev"])
    fragment = parts.fragment
    if "?" in fragment:
        route, querystring = fragment.split("?", 1)
        kept = urlencode([(k, v) for k, v in parse_qsl(querystring) if k in ("tabKey", "type")])
        fragment = route + ("?" + kept if kept else "")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, fragment))


class Dashboard:
    def __init__(self):
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.worker = None

    def is_running(self):
        return (self.worker is not None and self.worker.poll() is None) or scanner_busy()

    def status(self):
        config = read_json(ROOT / "sites.json", {"sites": [], "times": []})
        latest = read_json(DATA / "latest.json", [])
        baseline = read_json(DATA / "state.json", {})
        progress = read_json(DATA / "progress.json", {})
        running = self.is_running()
        by_name = {r["company"]: r for r in latest}
        if progress.get("status") == "running" or running:
            by_name.update({r["company"]: r for r in progress.get("results", [])})
        sites = []
        for site in config["sites"]:
            result = dict(by_name.get(site["name"], {}))
            old = baseline.get(site["id"], {})
            result.update(id=site["id"], company=site["name"], url=safe_link(site["url"]))
            result.setdefault("status", "尚未查询")
            result["last_success"] = old.get("last_success")
            result["stale"] = result["status"] == "检查失败"
            if not result.get("text") and old.get("text"):
                result["text"] = old["text"]
            result["applications"] = parse_records(site["id"], result.get("text", ""))
            sites.append(result)
        interrupted = not running and progress.get("status") == "running"
        progress = {k: progress.get(k) for k in ("started_at", "finished_at", "current", "completed", "total")}
        if not running:
            progress["current"] = None
        return {"groups": GROUPS, "app": "application-monitor-public", "instance": runtime.browser_profile(), "sites": sites, "running": running, "progress": progress,
                "interrupted": interrupted, "times": config.get("times", []),
                "automation": read_json(DATA / "automation.json", {"enabled": False}),
                "csrf_token": self.token}

    def refresh(self):
        with self.lock:
            if self.is_running():
                return False
            with (DATA / "web-query.log").open("ab") as output:
                self.worker = subprocess.Popen(runtime.command("check"),
                    stdout=output, stderr=subprocess.STDOUT, **runtime.child_options(detached=True))
            return True


def handler_for(dashboard):
    class Handler(BaseHTTPRequestHandler):
        def allowed_host(self):
            expected = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            return self.headers.get("Host") in expected

        def reply(self, code, payload, content_type="application/json; charset=utf-8"):
            data = json.dumps(payload, ensure_ascii=False).encode() if isinstance(payload, (dict, list)) else payload
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self.allowed_host():
                self.reply(403, {"error": "仅允许从本机网页访问"})
                return
            path = urlsplit(self.path).path
            if path == "/api/status":
                self.reply(200, dashboard.status())
                return
            files = {"/": ("index.html", "text/html; charset=utf-8"),
                     "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                     "/style.css": ("style.css", "text/css; charset=utf-8")}
            if path not in files:
                self.reply(404, {"error": "页面不存在"})
                return
            name, mime = files[path]
            self.reply(200, (WEB / name).read_bytes(), mime)

        def do_POST(self):
            if not self.allowed_host():
                self.reply(403, {"error": "仅允许从本机网页访问"})
                return
            origin = self.headers.get("Origin")
            expected_origin = "http://" + self.headers.get("Host", "")
            if origin not in (None, expected_origin) or not secrets.compare_digest(self.headers.get("X-Query-Token", ""), dashboard.token):
                self.reply(403, {"error": "请从本地网页点击查询"})
                return
            if self.path != "/api/refresh":
                self.reply(404, {"error": "操作不存在"})
                return
            try:
                started = dashboard.refresh()
                self.reply(202 if started else 409, {"started": started, "message": "正在查询全部公司" if started else "已有查询正在进行"})
            except OSError:
                self.reply(500, {"error": "未能启动查询，请检查本地服务"})

        def log_message(self, format, *args):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18765)
    args = parser.parse_args()
    os.umask(0o077)
    runtime.initialize()
    DATA.mkdir(exist_ok=True, mode=0o700)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(Dashboard()))
    print(f"投递进度网页：http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
