"""Create a Finder application launcher without adding runtime dependencies."""
import plistlib
import shlex
import shutil
from pathlib import Path


def create_app(destination, command=None):
    app = Path(destination)
    contents = app / 'Contents'
    macos = contents / 'MacOS'
    macos.mkdir(parents=True, exist_ok=True)
    # Release wrapper lives beside the portable executable and its dependencies.
    invocation = ('exec ' + shlex.join(command)) if command else 'cd -- "$(dirname -- "$0")/../../.." || exit 1\nexec ./ApplicationMonitor'
    executable = macos / 'ApplicationMonitor'
    executable.write_text('#!/bin/sh\n' + invocation + '\n', encoding='utf-8')
    executable.chmod(0o755)
    icon = Path(__file__).resolve().parents[1] / "docs/assets/AppIcon.icns"
    resources = contents / "Resources"
    resources.mkdir(exist_ok=True)
    shutil.copy2(icon, resources / icon.name)
    with (contents / 'Info.plist').open('wb') as output:
        plistlib.dump({'CFBundleName': '投递进度助手', 'CFBundleDisplayName': '投递进度助手',
                      'CFBundleIdentifier': 'io.github.application-monitor.desktop',
                      'CFBundleExecutable': 'ApplicationMonitor', 'CFBundlePackageType': 'APPL',
                      'CFBundleIconFile': 'AppIcon', 'CFBundleVersion': '1', 'CFBundleShortVersionString': '1.0',
                      'NSHighResolutionCapable': True}, output)
    return app
