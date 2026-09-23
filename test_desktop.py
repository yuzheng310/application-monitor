import os
import plistlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from scripts.macos_app import create_app


class DesktopTests(unittest.TestCase):
    @unittest.skipIf(os.name == 'nt', 'POSIX Finder launcher')
    def test_app_resolves_adjacent_backend_when_folder_has_spaces(self):
        with tempfile.TemporaryDirectory(prefix='app folder ') as directory:
            folder = Path(directory)
            backend = folder / 'ApplicationMonitor'
            backend.write_text('#!/bin/sh\nprintf "desktop-started"\n')
            backend.chmod(0o755)
            app = create_app(folder / '投递进度助手.app')
            info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
            result = subprocess.run([str(app / 'Contents/MacOS' / info['CFBundleExecutable'])], cwd='/', check=True, capture_output=True, text=True)
            self.assertEqual(result.stdout, 'desktop-started')
            self.assertTrue((app / 'Contents/Resources/AppIcon.icns').is_file())
