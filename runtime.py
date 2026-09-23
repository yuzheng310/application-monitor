"""Paths, bundled tools and operating-system integration for the portable app."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

FROZEN = getattr(sys, "frozen", False)
ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
ASSETS = ROOT
VERSION = json.loads((ROOT / ('VERSIONS.json' if FROZEN else 'package.json')).read_text(encoding='utf-8')).get('application' if FROZEN else 'version', 'unknown')


def user_directory():
    override = os.environ.get("APPLICATION_MONITOR_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ApplicationMonitor"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/ApplicationMonitor"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "application-monitor"


HOME = user_directory()
DATA = HOME / "data"
CONFIG = HOME / "sites.json"


def initialize():
    HOME.mkdir(parents=True, exist_ok=True, mode=0o700)
    DATA.mkdir(exist_ok=True, mode=0o700)
    if not CONFIG.exists():
        # Exclusive creation avoids overwriting a user's configuration.
        try:
            with CONFIG.open("x", encoding="utf-8") as stream:
                stream.write((ASSETS / "sites.example.json").read_text(encoding="utf-8"))
        except FileExistsError:
            pass


def command(mode, *args):
    return ([sys.executable, mode] if FROZEN else [sys.executable, str(ROOT / "launcher.py"), mode]) + list(args)


def child_options(detached=False):
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW
        if detached:
            flags |= subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        return {"creationflags": flags}
    return {"start_new_session": detached}


def opencli_command():
    node = ASSETS / "runtime" / ("node.exe" if os.name == "nt" else "node")
    entry = ASSETS / "runtime/node_modules/@jackwener/opencli/dist/src/main.js"
    if node.is_file() and entry.is_file():
        return [str(node), str(entry)]
    if not FROZEN and shutil.which("opencli"):
        return [shutil.which("opencli")]
    raise RuntimeError("发布包不完整：缺少内置 OpenCLI，请重新下载完整压缩包。")


def browser_executable():
    manifest = ASSETS / "runtime/browser.json"
    if not manifest.is_file():
        raise RuntimeError("缺少内置浏览器，请下载 Release 完整包，或先运行构建脚本。")
    return ASSETS / "runtime" / json.loads(manifest.read_text(encoding="utf-8"))["executable"]


def browser_profile():
    path = HOME / "browser-id.txt"
    if not path.exists():
        try:
            with path.open("x", encoding="ascii") as output:
                output.write("application-monitor-" + uuid.uuid4().hex)
        except FileExistsError:
            pass
    return path.read_text(encoding="ascii").strip()


def prepare_extension():
    target = HOME / "browser-bridge"
    source = ASSETS / "vendor/browser-bridge"
    shutil.copytree(source, target, dirs_exist_ok=True)
    script = target / "dist/background.js"
    text = script.read_text(encoding="utf-8")
    marker = "async function getCurrentContextId() {"
    if text.count(marker) != 1:
        raise RuntimeError("内置扩展版本不兼容。")
    # Explicit routing prevents using another connected browser's login state.
    script.write_text(text.replace(marker, marker + "\n  return " + json.dumps(browser_profile()) + ";"), encoding="utf-8")
    return target


def open_browser(url, desktop=True):
    extension = prepare_extension()
    browser = browser_executable()
    args = [str(browser), "--user-data-dir=" + str(HOME / "browser"),
            "--no-first-run", "--no-default-browser-check",
            "--disable-extensions-except=" + str(extension), "--load-extension=" + str(extension),
            *(["--app=" + url, "--window-size=1280,900"] if desktop else [url])]
    with (DATA / "browser.log").open("ab") as log:
        return subprocess.Popen(args, stdout=log, stderr=log, **child_options(detached=True))
