#!/usr/bin/env python3
"""Double-click entry point; child processes use the same frozen executable."""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import runtime


class OlderVersion(RuntimeError):
    pass


def available(url):
    try:
        with urllib.request.urlopen(url + "api/status", timeout=2) as response:
            value = json.load(response)
        if value.get("app") != "application-monitor-public":
            raise RuntimeError("网页端口被其他软件占用，请通过 --port 指定其他端口。")
        if value.get("instance") != runtime.browser_profile():
            raise RuntimeError("网页端口被另一个数据目录占用，请使用不同端口。")
        if value.get('version') != runtime.VERSION:
            raise OlderVersion('此端口运行的是其他版本。')
        return True
    except urllib.error.HTTPError as error:
        raise RuntimeError("网页端口被其他服务占用。") from error
    except urllib.error.URLError:
        return False


def main():
    # Frozen Windows programs ignore PYTHONUTF8; redirected logs otherwise use
    # the machine's legacy code page and fail on the first Chinese message.
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    os.umask(0o077)
    runtime.initialize()
    if len(sys.argv) > 1 and sys.argv[1] in ("serve", "check", "watch", "inspect"):
        mode = sys.argv.pop(1)
        if mode == "serve":
            import web_server
            web_server.main()
        else:
            import monitor
            sys.argv.insert(1, mode)
            try:
                monitor.main()
            except Exception as error:
                from check_errors import details
                monitor.save(runtime.DATA / 'progress.json', {'status': 'failed', **details(error)})
                raise
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18765)
    parser.add_argument("--browser-tab", action="store_true", help="使用普通浏览器标签页打开看板")
    parser.add_argument("--no-browser", action="store_true", help="仅启动网页服务")
    parser.add_argument("--self-test", action="store_true", help="验证内置运行环境，无需网络")
    args = parser.parse_args()
    if args.self_test:
        version = subprocess.run(runtime.opencli_command() + ["--version"], check=True,
                                 capture_output=True, text=True, timeout=30, **runtime.child_options())
        assert runtime.browser_executable().is_file(), "缺少 Chromium"
        assert (runtime.prepare_extension() / "manifest.json").is_file()
        import monitor
        print(json.dumps({"ok": True, "opencli": version.stdout.strip(), "timezone": str(monitor.TZ)}))
        return
    for candidate in range(args.port, min(args.port + 20, 65536)):
        url = f"http://127.0.0.1:{candidate}/"
        try:
            running = available(url)
            args.port = candidate
            break
        except OlderVersion:
            continue
    else:
        raise RuntimeError('已有多个旧版本运行，请通过 --port 指定空闲端口。')
    if not running:
        with (runtime.DATA / "web-server.log").open("ab") as log:
            worker = subprocess.Popen(runtime.command("serve", "--port", str(args.port)),
                                      stdout=log, stderr=log, **runtime.child_options(detached=True))
        for _ in range(60):
            if available(url):
                break
            if worker.poll() is not None:
                raise RuntimeError("网页未能启动，请查看用户数据目录内 data/web-server.log。")
            time.sleep(0.25)
        else:
            raise RuntimeError("网页启动超时，请查看 data/web-server.log。")
    if not args.no_browser:
        runtime.open_browser(url, desktop=not args.browser_tab)
    print("投递进度：" + url)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as error:
        print("启动失败：" + str(error), file=sys.stderr)
        if len(sys.argv) == 1:
            try:
                input("按回车关闭窗口…")
            except EOFError:
                pass
        raise SystemExit(1)
