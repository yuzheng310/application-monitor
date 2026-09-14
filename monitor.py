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
import shutil
import subprocess
import time
from datetime import datetime, timedelta
from urllib.parse import urlsplit
from datetime import timezone

ROOT = runtime.ROOT
DATA = runtime.DATA
TZ = timezone(timedelta(hours=8), "Asia/Shanghai")


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def normalize(text):
    return "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())


def cli(config, site, *args):
    command = runtime.opencli_command()
    command += ["--profile", config.get("profile") or runtime.browser_profile()]
    command += ["browser", "applications-" + site["id"], *args]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=50, **runtime.child_options())
    if result.returncode:
        # 原始错误可能含带令牌的 URL，不保存到结果中。
        raise RuntimeError("浏览器连接失败，请重新双击启动软件，确认内置浏览器保持打开")
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
      return {url: location.origin + location.pathname + location.hash,
        title: document.title,
        ready_found: body.includes(READY),
        auth_required: /获取验证码|短信验证码|扫码登录|安全验证|请完成验证/.test(body),
        count: nodes.length, text: nodes.map(e => e.innerText).join('\\n'), extra};
    })()""".replace("SELECTOR", selector).replace("PROGRESS", json.dumps(site.get("progress"))).replace("READY", json.dumps(site.get("ready_text") or ""))
    raw = cli(config, site, "eval", script)
    try:
        value = json.loads(raw)
    except ValueError:
        raise RuntimeError("OpenCLI 返回格式不符，未更新历史记录")
    if not isinstance(value, dict) or not isinstance(value.get("text"), str):
        raise RuntimeError("OpenCLI 未返回有效页面")
    return value


def same_route(expected_url, actual_url):
    expected, actual = urlsplit(expected_url), urlsplit(actual_url)
    return (expected.scheme == actual.scheme and expected.netloc == actual.netloc
            and actual.path.rstrip("/") == expected.path.rstrip("/")
            and actual.fragment.split("?")[0] == expected.fragment.split("?")[0])


def validate(page, site):
    if not same_route(site["url"], page["url"]):
        raise RuntimeError("页面发生跳转，可能需要重新登录")
    if page.get("auth_required") or re.search(r"获取验证码|短信验证码|扫码登录|安全验证|请完成验证", page.get("body", "")):
        raise RuntimeError("需要在内置浏览器中完成登录或验证")
    if not site.get("ready_text") or not page.get("ready_found", site["ready_text"] in page.get("body", "")):
        raise RuntimeError("未找到已配置的投递列表标识，页面尚未就绪或结构变化")
    if page.get("count") != 1:
        raise RuntimeError("投递区域不存在或不唯一，需要重新核实读取规则")
    text = normalize(page.get("text", ""))
    if not text or re.search(r"加载中|加载失败|网络异常|系统繁忙", text):
        raise RuntimeError("投递内容为空、未加载完成或网站报错")
    if site.get("content_pattern") and not re.search(site["content_pattern"], text):
        raise RuntimeError("投递区域尚未出现记录或明确的空列表提示")
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
                raise RuntimeError("记录页面发生跳转，需要登录或重新核实入口")
            if status["done"]:
                break
            if status["count"] == 1:
                cli(config, site, "click", step["selector"])
                # 等待下一轮验证，不重复点击可能切换开合状态的控件。
                for _ in range(12):
                    status = json.loads(cli(config, site, "eval", script))
                    if not same_route(site["url"], status["url"]):
                        raise RuntimeError("切换记录时页面发生跳转")
                    if status["done"]:
                        break
                    time.sleep(1)
                else:
                    raise RuntimeError("记录标签或历史列表未能展开")
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("未找到唯一的记录标签或展开按钮")
            time.sleep(1)


def check_site(config, site):
    if not site.get("selector") or not site.get("ready_text"):
        raise RuntimeError("待接入：需要在已登录页面核实投递区域与就绪标识")
    cli(config, site, "open", site["url"], "--window", "background")
    prepare_page(config, site)
    previous = None
    stable = 0
    deadline = time.monotonic() + 40
    last_error = "页面未稳定"
    while time.monotonic() < deadline:
        try:
            text = validate(read_page(config, site), site)
            stable = stable + 1 if text == previous else 1
            previous = text
            if stable >= 3:
                return text
        except RuntimeError as error:
            last_error = str(error)
            previous, stable = None, 0
        time.sleep(2)
    raise RuntimeError(last_error)


def run_once(config):
    state_path = DATA / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    stamp = datetime.now(TZ).isoformat(timespec="seconds")
    results = []
    progress = {"status": "running", "started_at": stamp, "pid": os.getpid(),
                "completed": 0, "total": len(config["sites"]), "current": None, "results": []}
    save(DATA / "progress.json", progress)
    for site in config["sites"]:
        progress["current"] = site["name"]
        save(DATA / "progress.json", progress)
        old = state.get(site["id"], {})
        checked_at = datetime.now(TZ).isoformat(timespec="seconds")
        result = {"id": site["id"], "company": site["name"], "checked_at": checked_at}
        try:
            text = check_site(config, site)
            prior = old.get("text")
            result["status"] = "首次记录" if prior is None else ("内容变化" if prior != text else "无变化")
            result["text"] = text
            if prior is not None and prior != text:
                result["diff"] = "\n".join(difflib.unified_diff(prior.splitlines(), text.splitlines(), fromfile="上次", tofile="本次", lineterm=""))
            state[site["id"]] = {"text": text, "last_success": checked_at}
        except (RuntimeError, subprocess.TimeoutExpired, ValueError) as error:
            result.update(status="检查失败", error="OpenCLI 超时" if isinstance(error, subprocess.TimeoutExpired) else str(error), last_success=old.get("last_success"))
        results.append(result)
        save(state_path, state)
        progress.update(completed=len(results), results=results)
        save(DATA / "progress.json", progress)
        print(site["name"] + "：" + result["status"] + (" — " + result["error"] if "error" in result else ""), flush=True)
    save(state_path, state)
    save(DATA / "latest.json", results)
    with (DATA / "history.jsonl").open("a", encoding="utf-8") as output:
        for result in results:
            output.write(json.dumps(result, ensure_ascii=False) + "\n")
    report = ["投递进度检查 · " + stamp, ""]
    report += [r["company"] + "：" + r["status"] for r in results]
    report += ["", "以下为各网站投递区域原文；流程步骤名称不代表已经完成。", ""]
    for result in results:
        report += [result["company"] + "：" + result["status"], result.get("error", result.get("diff", result.get("text", ""))), ""]
        if result.get("last_success"):
            report += ["上次成功检查：" + result["last_success"], ""]
    (DATA / "最新结果.txt").write_text("\n".join(report), encoding="utf-8")
    progress.update(status="complete", current=None, finished_at=datetime.now(TZ).isoformat(timespec="seconds"))
    save(DATA / "progress.json", progress)
    return not any(r["status"] == "检查失败" for r in results)


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
    parser.add_argument("--site", help="仅检查指定站点；名称见 sites.json 的 id")
    args = parser.parse_args()
    os.umask(0o077)
    runtime.initialize()
    DATA.mkdir(exist_ok=True, mode=0o700)
    config = json.loads(runtime.CONFIG.read_text(encoding="utf-8"))
    if args.site:
        config["sites"] = [s for s in config["sites"] if s["id"] == args.site]
        if not config["sites"]:
            parser.error("未知站点 id")
    with (DATA / "monitor.lock").open("a+") as lock:
        try:
            file_lock.acquire(lock)
        except BlockingIOError:
            parser.exit(1, "已有监控进程运行，请先停止它。\n")
        if args.command == "inspect":
            site = next((s for s in config["sites"] if s["id"] == args.site), None)
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
