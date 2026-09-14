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
from check_errors import CheckError, details
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
        try:
            config = json.loads((ROOT / 'sites.json').read_text(encoding='utf-8'))
            if not isinstance(config, dict) or not isinstance(config.get('sites'), list):
                raise ValueError()
            for site in config['sites']:
                if not isinstance(site, dict) or not all(isinstance(site.get(k), str) for k in ('id', 'name', 'url')):
                    raise ValueError()
        except (OSError, ValueError):
            raise CheckError('CONFIG_ERROR')
        latest = read_json(DATA / "latest.json", [])
        baseline = read_json(DATA / "state.json", {})
        progress = read_json(DATA / "progress.json", {})
        running = self.is_running()
        by_name = {r["company"]: r for r in latest}
        if progress.get("status") == "running" or running:
            by_name.update({r["company"]: r for r in progress.get("results", [])})
        sites = []
        active_ids = {x['id'] for x in progress.get('active', [])} if running else set()
        pending_ids = set(progress.get('pending', [])) if running else set()
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
            result['query_state'] = 'running' if site['id'] in active_ids else 'pending' if site['id'] in pending_ids else 'idle'
            sites.append(result)
        interrupted = not running and progress.get("status") == "running"
        batch_error = {k: progress.get(k) for k in ('error', 'error_code', 'suggestion')} if progress.get('status') == 'failed' else None
        progress = {k: progress.get(k) for k in ("started_at", "finished_at", "current", "completed", "total", "active", "pending", "concurrency", "elapsed_seconds")}
        if not running:
            progress["current"] = None
        return {"groups": GROUPS, "app": "application-monitor-public", "version": runtime.VERSION, "instance": runtime.browser_profile(), "sites": sites, "running": running, "progress": progress,
                "interrupted": interrupted, "batch_error": batch_error, "concurrency": config.get('concurrency', 4), "times": config.get("times", []),
                "automation": read_json(DATA / "automation.json", {"enabled": False}),
                "csrf_token": self.token}

    def refresh(self, site_ids=None, workers=None):
        with self.lock:
            if self.is_running():
                return False
            args = []
            if site_ids is not None:
                known = {x['id'] for x in self.status()['sites']}
                if not site_ids or any(x not in known for x in site_ids):
                    raise ValueError('请选择有效的公司后重试。')
                for site_id in dict.fromkeys(site_ids):
                    args += ['--site', site_id]
            if workers is not None:
                args += ['--workers', str(workers)]
            # Show pending companies immediately instead of a previous run's progress.
            selected = [s for s in self.status()['sites'] if site_ids is None or s['id'] in site_ids]
            from monitor import save
            save(DATA / 'progress.json', {'status': 'running', 'completed': 0, 'total': len(selected),
                 'active': [], 'pending': [s['id'] for s in selected], 'results': [], 'concurrency': workers or 4})
            with (DATA / "web-query.log").open("ab") as output:
                self.worker = subprocess.Popen(runtime.command("check", *args),
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
                try:
                    self.reply(200, dashboard.status())
                except CheckError as error:
                    self.reply(500, details(error))
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
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 <= length <= 4096:
                    raise ValueError('请求过大，请刷新网页后重试。')
                body = json.loads(self.rfile.read(length)) if length else {}
                if not isinstance(body, dict) or set(body) - {'site_ids', 'workers'}:
                    raise ValueError('查询参数无效。')
                site_ids, workers = body.get('site_ids'), body.get('workers')
                if 'site_ids' in body and (not isinstance(site_ids, list) or not site_ids or len(site_ids) > 100 or any(not isinstance(x, str) for x in site_ids)):
                    raise ValueError('请选择有效的公司。')
                if 'workers' in body and (type(workers) is not int or not 1 <= workers <= 8):
                    raise ValueError('并发数应为 1 到 8 之间的整数。')
                started = dashboard.refresh(site_ids, workers) if body else dashboard.refresh()
                self.reply(202 if started else 409, {"started": started, "message": "已开始查询" if started else "已有查询正在进行，请等待完成。"})
            except (ValueError, UnicodeError):
                self.reply(400, {'error': '查询参数无效，请刷新网页后重新选择公司和并发数。'})
            except CheckError as error:
                self.reply(400, details(error))
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
