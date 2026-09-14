import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import file_lock
import runtime
from records import parse_records


class RuntimeTests(unittest.TestCase):
    def test_lock_excludes_another_process_and_releases_on_close(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scan.lock'
            child = 'import file_lock,sys; f=open(sys.argv[1],"a+"); file_lock.acquire(f)'
            with path.open('a+') as lock:
                file_lock.acquire(lock)
                result = subprocess.run([sys.executable, '-c', child, str(path)], capture_output=True)
                self.assertNotEqual(result.returncode, 0)
            result = subprocess.run([sys.executable, '-c', child, str(path)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_first_run_preserves_config_and_has_no_fake_applications(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            with patch.object(runtime, 'HOME', home), patch.object(runtime, 'DATA', home/'data'), patch.object(runtime, 'CONFIG', home/'sites.json'):
                runtime.initialize()
                self.assertEqual(len(json.loads(runtime.CONFIG.read_text(encoding='utf-8'))['sites']), 18)
                runtime.CONFIG.write_text('{"sites": []}', encoding='utf-8')
                runtime.initialize()
                self.assertEqual(json.loads(runtime.CONFIG.read_text(encoding='utf-8'))['sites'], [])
                first = runtime.browser_profile()
                self.assertEqual(first, runtime.browser_profile())
                self.assertEqual(parse_records('baidu', ''), [])

    def test_extension_routes_only_to_its_private_browser(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime, 'HOME', Path(directory)):
            destination = runtime.prepare_extension()
            script = (destination/'dist/background.js').read_text(encoding='utf-8')
            self.assertIn('return ' + json.dumps(runtime.browser_profile()) + ';', script)
            original = (runtime.ASSETS/'vendor/browser-bridge/dist/background.js').read_text(encoding='utf-8')
            self.assertNotIn(runtime.browser_profile(), original)
