"""Build a persistent native macOS window around the local dashboard."""
import plistlib
import shutil
import subprocess
from pathlib import Path


def create_app(destination, command=None, url=None, browser_command=None):
    app = Path(destination)
    contents = app / 'Contents'
    macos = contents / 'MacOS'
    macos.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    subprocess.run(['xcrun', 'swiftc', '-O', str(root / 'scripts/DesktopHost.swift'),
                    '-o', str(macos / 'ApplicationMonitor'), '-framework', 'Cocoa', '-framework', 'WebKit'], check=True)
    resources = contents / 'Resources'
    resources.mkdir(exist_ok=True)
    shutil.copy2(root / 'docs/assets/AppIcon.icns', resources / 'AppIcon.icns')
    info = {'CFBundleName': '投递进度助手', 'CFBundleDisplayName': '投递进度助手',
            'CFBundleIdentifier': 'io.github.application-monitor.desktop',
            'CFBundleExecutable': 'ApplicationMonitor', 'CFBundlePackageType': 'APPL',
            'CFBundleIconFile': 'AppIcon', 'CFBundleVersion': '2', 'CFBundleShortVersionString': '1.0.1',
            'NSHighResolutionCapable': True,
            'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True}}
    if command: info['MonitorBackend'] = command
    if url: info['MonitorURL'] = url
    if browser_command: info['MonitorBrowser'] = browser_command
    with (contents / 'Info.plist').open('wb') as output:
        plistlib.dump(info, output)
    return app
