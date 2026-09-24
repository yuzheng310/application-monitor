import sys
import plistlib
from pathlib import Path
import subprocess
import tempfile
import unittest
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from scripts.macos_app import create_app


class DesktopTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'darwin', 'Native macOS window')
    def test_native_app_stays_running_after_backend_is_ready(self):
        loaded = threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/": loaded.set()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json' if self.path=='/api/status' else 'text/html')
                self.end_headers()
                self.wfile.write(b'{"app":"application-monitor"}' if self.path=='/api/status' else b'<h1>Desktop test</h1>')
            def log_message(self, *args): pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix='app folder ') as directory:
                app=create_app(Path(directory)/'Test.app',url=f'http://127.0.0.1:{server.server_port}/')
                info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
                process=subprocess.Popen([str(app/'Contents/MacOS'/info['CFBundleExecutable'])],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                try:
                    self.assertTrue(loaded.wait(timeout=10), "Native window must load the dashboard HTML")
                    time.sleep(3)
                    self.assertIsNone(process.poll(),'Desktop host must own its window instead of exiting after delegating to Chrome')
                    self.assertTrue((app/'Contents/Resources/AppIcon.icns').is_file())
                finally:
                    if process.poll() is None:process.terminate()
                    process.wait(timeout=10)
        finally:
            server.shutdown();server.server_close()
