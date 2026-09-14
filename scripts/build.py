"""Build a self-contained native release. Network is used only at build time."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NODE_VERSION = "24.21.0"


def run(*args, **kwargs):
    subprocess.run(list(args), cwd=ROOT, check=True, **kwargs)


def main():
    system = {"Darwin": "darwin", "Windows": "win", "Linux": "linux"}[platform.system()]
    arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"
    label = {"darwin": "macos", "win": "windows", "linux": "linux"}[system] + "-" + arch
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
        "--name", "ApplicationMonitor", "launcher.py")
    bundle = ROOT / "dist/ApplicationMonitor"
    for name in ("web", "vendor"):
        shutil.copytree(ROOT / name, bundle / name, dirs_exist_ok=True)
    for name in ("sites.example.json", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, bundle / name)
    runtime = bundle / "runtime"
    runtime.mkdir(exist_ok=True)
    urllib.request.urlretrieve(f"https://raw.githubusercontent.com/python/cpython/v{platform.python_version()}/LICENSE", runtime / "PYTHON-LICENSE")
    import importlib.metadata
    dist = importlib.metadata.distribution("pyinstaller")
    for file in dist.files:
        if "COPYING" in str(file) and str(file).endswith("COPYING.txt"):
            shutil.copy2(dist.locate_file(file), runtime / "PYINSTALLER-LICENSE")
    for name in ("package.json", "package-lock.json"):
        shutil.copy2(ROOT / name, runtime / name)
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    run(npm, "ci", "--prefix", str(runtime), "--omit=dev", "--ignore-scripts", "--no-audit", "--no-fund")

    # Official Node binaries include their shared runtime dependencies.
    stem = f"node-v{NODE_VERSION}-{system}-{arch}"
    filename = stem + (".zip" if system == "win" else ".tar.gz")
    base = f"https://nodejs.org/dist/v{NODE_VERSION}/"
    cache = ROOT / "build/downloads"
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / filename
    urllib.request.urlretrieve(base + filename, archive)
    checksums = urllib.request.urlopen(base + "SHASUMS256.txt", timeout=60).read().decode()
    expected = next(line.split()[0] for line in checksums.splitlines() if line.split()[-1] == filename)
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected, "Node checksum mismatch"
    node_name = "node.exe" if system == "win" else "node"
    if system == "win":
        with zipfile.ZipFile(archive) as source:
            (runtime / node_name).write_bytes(source.read(stem + "/node.exe"))
            (runtime / "NODE-LICENSE").write_bytes(source.read(stem + "/LICENSE"))
    else:
        with tarfile.open(archive) as source:
            (runtime / node_name).write_bytes(source.extractfile(stem + "/bin/node").read())
            (runtime / "NODE-LICENSE").write_bytes(source.extractfile(stem + "/LICENSE").read())
        (runtime / node_name).chmod(0o755)

    run(sys.executable, "-m", "playwright", "install", "chromium", "--no-shell")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        executable = Path(p.chromium.executable_path)
        browser_root = next(parent for parent in executable.parents if parent.name.startswith("chromium-"))
        shutil.copytree(browser_root, runtime / "chromium", symlinks=True, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("INSTALLATION_COMPLETE", "DEPENDENCIES_VALIDATED"))
        relative = Path("chromium") / executable.relative_to(browser_root)
        (runtime / "browser.json").write_text(json.dumps({"executable": relative.as_posix()}), encoding="utf-8")
        # Chromium's built-in credits contain its third-party license notices.
        browser = p.chromium.launch(channel="chromium", headless=True)
        page = browser.new_page()
        page.goto("chrome://credits")
        (runtime / "CHROMIUM-CREDITS.html").write_text(page.content(), encoding="utf-8")
        page.goto("chrome://terms")
        (runtime / "BROWSER-TERMS.html").write_text(page.content(), encoding="utf-8")
        browser.close()

    versions = {"application": "1.0.0", "node": NODE_VERSION, "opencli": "1.8.6",
                "browser_bridge": "1.0.24", "playwright_build": "1.62.0", "platform": label,
                "python": platform.python_version(), "node_archive_sha256": expected}
    (bundle / "VERSIONS.json").write_text(json.dumps(versions, indent=2), encoding="utf-8")
    if system == "win":
        (bundle / "Start.cmd").write_bytes(b'@echo off\r\ncd /d "%~dp0"\r\n"%~dp0ApplicationMonitor.exe"\r\nif errorlevel 1 pause\r\n')
    else:
        start = bundle / ("Start.command" if system == "darwin" else "Start.sh")
        start.write_text('#!/bin/sh\ncd -- "$(dirname -- "$0")" || exit 1\nexec ./ApplicationMonitor "$@"\n', encoding="utf-8")
        start.chmod(0o755)
    executable = bundle / ("ApplicationMonitor.exe" if system == "win" else "ApplicationMonitor")
    env = dict(os.environ, APPLICATION_MONITOR_HOME=str(ROOT / "build/self-test"))
    run(str(executable), "--self-test", env=env)
    out = ROOT / "releases"
    out.mkdir(exist_ok=True)
    name = out / ("application-monitor-" + label)
    result = shutil.make_archive(str(name), "zip" if system == "win" else "gztar", bundle.parent, bundle.name)
    result = Path(result)
    result.with_name(result.name + ".sha256").write_text(hashlib.sha256(result.read_bytes()).hexdigest() + "  " + result.name + "\n")
    print("Release ready:", result)


if __name__ == "__main__":
    main()
