#!/usr/bin/env python3
"""通过 OpenCLI 复用 Chrome 登录态；只读监控选定的投递记录区域。"""
import argparse
import difflib
import file_lock
import runtime
import json
import os
from pathlib import Path
import re
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from check_errors import CheckError, cli_error, details
import subprocess
import uuid
import threading
import time
from datetime import datetime, timedelta
from urllib.parse import urlsplit
from datetime import timezone

BROWSER_TURN = threading.RLock()

ROOT = runtime.ROOT
DATA = runtime.DATA
TZ = timezone(timedelta(hours=8), "Asia/Shanghai")


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def normalize(text):
    return "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())


def cli(config, site, *args, timeout=50):
    try:
        command = runtime.opencli_command()
    except RuntimeError:
        raise CheckError('DEPENDENCY_MISSING')
    profile = config.get("profile") or runtime.browser_profile()
    if profile:
        command += ["--profile", profile]
    command += ["browser", "applications-" + site["id"] + config.get("_session_suffix", "")]
    options = dict(capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                   env=dict(os.environ, OPENCLI_WINDOW="background"), **runtime.child_options())
    # OpenCLI shares a background window. Hidden tabs may never render their
    # application list. Keep activation and the read/click in one browser turn;
    # network loading and polling waits still overlap across company workers.
    with BROWSER_TURN:
        if config.get("_page") and args and args[0] in ("eval", "click", "state"):
            selected = subprocess.run(command + ["tab", "select", config["_page"]], **options)
            if selected.returncode:
                raise cli_error(selected.stderr or selected.stdout)
            time.sleep(0.15)  # Allow visibility handlers and animation frames to run.
        result = subprocess.run(command + list(args), **options)
    if result.returncode:
        # 原始错误可能含带令牌的 URL，不保存到结果中。
        raise cli_error(result.stderr or result.stdout)
    return result.stdout.strip()


def read_page(config, site):
    selector = json.dumps(site.get("selector") or "body")
    script = """(() => {
      const nodes = [...document.querySelectorAll(SELECTOR)]
        .filter(e => e.getClientRects().length);
      const visible = e => e.getClientRects().length > 0;
      const body = document.body.innerText;
      const progress = PROGRESS;
      const extra = progress ? [...document.querySelectorAll(progress.row)]
        .filter(visible).flatMap(row => {
          const title = progress.title ? row.querySelector(progress.title)?.innerText : '当前流程';
          return [...row.querySelectorAll(progress.current)].filter(visible)
            .map(e => (title || '当前流程') + '：' + e.innerText.trim());
        }) : [];
      const table = TABLE_RECORDS;
      let text = nodes.map(e => e.innerText).join('\\n');
      if (table) {
        text = nodes.flatMap(container => [...container.querySelectorAll(table.row)]).filter(visible).flatMap(row => {
          const date = row.querySelector(table.date)?.innerText.trim() || '';
          const detail = row.nextElementSibling;
          const status = detail?.querySelector(table.status)?.innerText.replace(/^当前状态[：:]\\s*/, '').trim() || '';
          if (!status) return [];
          return table.titles.flatMap(column => {
            const title = row.querySelector(column.selector)?.innerText.trim();
            if (!title || ['-', '—', '暂无', '未填写'].includes(title)) return [];
            return ['岗位记录\\n职位：'+title+'\\n志愿：'+column.preference+'\\n投递时间：'+date+'\\n当前状态：'+status];
          });
        }).join('\\n');
      }
      return {url: location.origin + location.pathname + location.hash,
        title: document.title,
        ready_found: body.includes(READY),
        auth_required: /获取验证码|短信验证码|扫码登录|安全验证|请完成验证/.test(body),
        count: nodes.length, text, extra};
    })()""".replace("TABLE_RECORDS", json.dumps(site.get("table_records"))).replace("SELECTOR", selector).replace("PROGRESS", json.dumps(site.get("progress"))).replace("READY", json.dumps(site.get("ready_text") or ""))
    raw = cli(config, site, "eval", script)
    try:
        value = json.loads(raw)
    except ValueError:
        raise CheckError('INVALID_RESPONSE')
    if not isinstance(value, dict) or not isinstance(value.get("text"), str):
        raise CheckError('INVALID_RESPONSE')
    return value


def same_route(expected_url, actual_url):
    expected, actual = urlsplit(expected_url), urlsplit(actual_url)
    return (expected.scheme == actual.scheme and expected.netloc == actual.netloc
            and actual.path.rstrip("/") == expected.path.rstrip("/")
            and actual.fragment.split("?")[0] == expected.fragment.split("?")[0])


def validate(page, site):
    if not same_route(site["url"], page["url"]):
        if re.search(r"(?:/|#)(?:login|signin|sign-in|auth)(?:[/?#]|$)", page.get("url", ""), re.I):
            raise CheckError('LOGIN_REQUIRED')
        raise CheckError('PAGE_REDIRECT')
    if page.get("auth_required") or re.search(r"获取验证码|短信验证码|扫码登录|安全验证|请完成验证", page.get("body", "")):
        raise CheckError('LOGIN_REQUIRED')
    if not site.get("ready_text") or not page.get("ready_found", site["ready_text"] in page.get("body", "")):
        raise CheckError('SITE_CHANGED', wait_for_page=True)
    if page.get("count") != 1:
        raise CheckError('SITE_CHANGED', wait_for_page=True)
    text = normalize(page.get("text", ""))
    if not text or re.search(r"加载中|加载失败|网络异常|系统繁忙", text):
        raise CheckError('PAGE_LOADING', wait_for_page=True)
    if site.get("content_pattern") and not re.search(site["content_pattern"], text):
        raise CheckError('SITE_CHANGED', wait_for_page=True)
    if page.get("extra"):
        text += "\n\n页面标记的当前阶段：\n" + normalize("\n".join(page["extra"]))
    return text


def prepare_page(config, site):
    """仅执行已核实的读取操作：切换记录标签、展开历史记录。"""
    for step in site.get("read_steps", []):
        deadline = time.monotonic() + 25
        while True:
            script = """(() => {
              const visible = e => e.getClientRects().length > 0;
              return {url: location.origin + location.pathname + location.hash,
                done: [...document.querySelectorAll(DONE)].some(visible),
                count: [...document.querySelectorAll(TARGET)].filter(visible).length};
            })()""".replace("DONE", json.dumps(step["done_selector"])).replace("TARGET", json.dumps(step["selector"]))
            status = json.loads(cli(config, site, "eval", script))
            if not same_route(site["url"], status["url"]):
                raise CheckError('PAGE_REDIRECT')
            if status["done"]:
                break
            if status["count"] == 1:
                cli(config, site, "click", step["selector"])
                # 等待下一轮验证，不重复点击可能切换开合状态的控件。
                for _ in range(12):
                    status = json.loads(cli(config, site, "eval", script))
                    if not same_route(site["url"], status["url"]):
                        raise CheckError('PAGE_REDIRECT')
                    if status["done"]:
                        break
                    time.sleep(1)
                else:
                    raise CheckError('SITE_CHANGED')
                break
            if time.monotonic() >= deadline:
                raise CheckError('SITE_CHANGED')
            time.sleep(1)


def check_site(config, site):
    if not site.get("selector") or not site.get("ready_text"):
        raise CheckError('CONFIG_ERROR')
    # A loaded but stalled page can fail validation despite valid site rules.
    # Reopen once in a fresh owned session; never reuse or close user tabs.
    for attempt in range(2):
        session = dict(config, _session_suffix="-" + uuid.uuid4().hex[:12])
        try:
            opened = cli(session, site, "open", site["url"], "--window", "background")
            if isinstance(opened, str):
                try:
                    page = json.loads(opened)["page"]
                    if not isinstance(page, str) or not page:
                        raise ValueError()
                    session["_page"] = page
                except (ValueError, KeyError, TypeError):
                    raise CheckError('INVALID_RESPONSE')
            return read_stable_site(session, site)
        except CheckError as error:
            if attempt or error.code not in {'SITE_CHANGED', 'PAGE_LOADING', 'TIMEOUT', 'NETWORK_ERROR'}:
                raise
        except subprocess.TimeoutExpired:
            if attempt:
                raise
        finally:
            try:
                cli(session, site, "close", timeout=5)
            except Exception:
                pass  # Cleanup failure must not discard a successful record.


def read_stable_site(config, site):
    prepare_page(config, site)
    previous = None
    stable = 0
    deadline = time.monotonic() + 40
    last_error = CheckError('PAGE_LOADING')
    while time.monotonic() < deadline:
        try:
            text = validate(read_page(config, site), site)
            stable = stable + 1 if text == previous else 1
            previous = text
            if stable >= 3:
                return text
        except CheckError as error:
            if not error.wait_for_page:
                raise
            last_error = error
            previous, stable = None, 0
        time.sleep(2)
    raise last_error


def concurrency_limit(config):
    value = config.get("concurrency", 4)
    if type(value) is not int or not 1 <= value <= 8:
        raise CheckError('CONFIG_ERROR')
    return value


def check_result(config, site, old):
    started = time.monotonic()
    result = {"id": site["id"], "company": site["name"],
              "checked_at": datetime.now(TZ).isoformat(timespec="seconds")}
    try:
        text = check_site(config, site)
        prior = old.get("text")
        result.update(status="首次记录" if prior is None else "内容变化" if prior != text else "无变化", text=text)
        if prior is not None and prior != text:
            result["diff"] = "\n".join(difflib.unified_diff(prior.splitlines(), text.splitlines(), fromfile="上次", tofile="本次", lineterm=""))
    except Exception as error:
        # One malformed site/response must not cancel the other companies.
        result.update(status="检查失败", last_success=old.get("last_success"), **details(error))
    result["elapsed_seconds"] = round(time.monotonic() - started, 2)
    return result


def run_once(config):
    workers = concurrency_limit(config)
    sites = config["sites"]
    ids = [site['id'] for site in sites]
    if len(ids) != len(set(ids)):
        raise CheckError('CONFIG_ERROR')
    state_path = DATA / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    started = time.monotonic()
    stamp = datetime.now(TZ).isoformat(timespec="seconds")
    results = []
    progress = {"status": "running", "started_at": stamp, "pid": os.getpid(),
                "completed": 0, "total": len(sites), "current": None, "active": [],
                "pending": ids[:], "concurrency": workers, "results": []}
    def publish():
        progress.update(completed=len(results), results=list(results),
                        elapsed_seconds=round(time.monotonic() - started, 2))
        progress["current"] = "、".join(x['company'] for x in progress['active']) or None
        save(DATA / "progress.json", progress)
    publish()
    # Only the coordinator writes files; workers return independent site results.
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="application") as executor:
        pending = iter(sites)
        futures = {}
        def submit_next():
            site = next(pending, None)
            if site is None:
                return
            futures[executor.submit(check_result, config, site, dict(state.get(site['id'], {})))] = site
            progress['pending'].remove(site['id'])
            progress['active'].append({'id': site['id'], 'company': site['name']})
        for _ in range(min(workers, len(sites))):
            submit_next()
        publish()
        while futures:
            completed, _ = wait(futures, return_when=FIRST_COMPLETED)
            for future in completed:
                site = futures.pop(future)
                result = future.result()
                if result['status'] != '检查失败':
                    state[site['id']] = {'text': result['text'], 'last_success': result['checked_at']}
                results.append(result)
                progress['active'] = [x for x in progress['active'] if x['id'] != site['id']]
                save(state_path, state)
                # Preserve each completed result, even if a later query is interrupted.
                with (DATA / "history.jsonl").open("a", encoding="utf-8") as output:
                    output.write(json.dumps(result, ensure_ascii=False) + "\n")
                print(site['name'] + '：' + result['status'] + (' — ' + result['error'] if 'error' in result else ''), flush=True)
                submit_next()
            publish()
    # A targeted retry replaces only that company's last result.
    latest_path = DATA / 'latest.json'
    previous = json.loads(latest_path.read_text(encoding='utf-8')) if latest_path.exists() else []
    by_id = {x.get('id', x['company']): x for x in previous}
    by_id.update({x['id']: x for x in results})
    save(latest_path, list(by_id.values()))
    report = ['投递进度检查 · ' + stamp, '']
    for result in by_id.values():
        report += [result['company'] + '：' + result['status'], result.get('error', result.get('diff', result.get('text', ''))), result.get('suggestion', ''), '']
    (DATA / '最新结果.txt').write_text('\n'.join(report), encoding='utf-8')
    progress.update(status='complete', active=[], pending=[], finished_at=datetime.now(TZ).isoformat(timespec='seconds'))
    publish()
    return not any(r['status'] == '检查失败' for r in results)


def next_run(now, times):
    candidates = []
    for offset in (0, 1):
        for value in times:
            hour, minute = map(int, value.split(":"))
            target = (now + timedelta(days=offset)).replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target > now:
                candidates.append(target)
    return min(candidates)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check", "watch", "inspect"])
    parser.add_argument("--site", action="append", help="仅检查指定站点，可重复指定")
    parser.add_argument("--workers", type=int, choices=range(1, 9), help="并发数，默认 4")
    args = parser.parse_args()
    os.umask(0o077)
    runtime.initialize()
    DATA.mkdir(exist_ok=True, mode=0o700)
    try:
        config = json.loads(runtime.CONFIG.read_text(encoding="utf-8"))
        if not isinstance(config, dict) or not isinstance(config.get('sites'), list):
            raise ValueError()
        for site in config['sites']:
            if not isinstance(site, dict) or not all(isinstance(site.get(k), str) for k in ('id','name','url')):
                raise ValueError()
        concurrency_limit(config)
    except (OSError, ValueError, TypeError):
        raise CheckError('CONFIG_ERROR')
    if args.workers is not None:
        config["concurrency"] = args.workers
    if args.site:
        if set(args.site) - {s["id"] for s in config["sites"]}:
            parser.error("未知站点 id")
        config["sites"] = [s for s in config["sites"] if s["id"] in args.site]
        if not config["sites"]:
            parser.error("未知站点 id")
    with (DATA / "monitor.lock").open("a+") as lock:
        try:
            file_lock.acquire(lock)
        except BlockingIOError:
            parser.exit(1, "已有监控进程运行，请先停止它。\n")
        if args.command == "inspect":
            site = next((s for s in config["sites"] if args.site and s["id"] == args.site[0]), None)
            if not site:
                parser.error("inspect 需要有效的 --site")
            cli(config, site, "open", site["url"], "--window", "background")
            print(cli(config, site, "state"))
            return
        if args.command == "check":
            raise SystemExit(0 if run_once(config) else 1)
        if not any(s.get("selector") and s.get("ready_text") for s in config["sites"]):
            parser.exit(1, "尚未完成任何页面适配，暂不启动定时检查。\n")
        run_once(config)
        while True:
            target = next_run(datetime.now(TZ), config["times"])
            print("下次检查：" + target.isoformat(), flush=True)
            while datetime.now(TZ) < target:
                time.sleep(min(30, max(0.1, (target - datetime.now(TZ)).total_seconds())))
            # 睡眠后恢复只补查一次，不连续重放错过的时间点。
            run_once(config)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已停止监控")
