"""Exercise a real release server, bundled browser, extension and OpenCLI offline."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    bundle = ROOT / 'dist/ApplicationMonitor'
    binary = bundle / ('ApplicationMonitor.exe' if os.name == 'nt' else 'ApplicationMonitor')
    with tempfile.TemporaryDirectory(prefix='application-monitor-smoke-') as directory:
        os.environ['APPLICATION_MONITOR_HOME'] = directory
        import runtime
        runtime.ASSETS = bundle
        runtime.initialize()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port}/'
        server = subprocess.Popen([str(binary), 'serve', '--port', str(port)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(base+'api/status', timeout=1) as response:
                        status = json.load(response)
                    break
                except OSError:
                    if server.poll() is not None:
                        raise RuntimeError(server.stdout.read().decode(errors='replace'))
                    time.sleep(.2)
            else:
                raise RuntimeError('Packaged server did not start')
            assert status['app'] == 'application-monitor-public'
            assert len(status['sites']) == 18
            assert not any(site['applications'] for site in status['sites'])
            # Repeated launcher invocation must reuse the same server.
            subprocess.run([str(binary), '--no-browser', '--port', str(port)], check=True, timeout=30)
            from playwright.sync_api import sync_playwright
            extension = runtime.prepare_extension()
            with sync_playwright() as p:
                browser = p.chromium.launch_persistent_context(str(Path(directory)/'browser'),
                    executable_path=str(runtime.browser_executable()), channel='chromium', headless=True,
                    args=['--disable-extensions-except='+str(extension), '--load-extension='+str(extension)])
                try:
                    page = browser.new_page()
                    page.goto(base)
                    page.wait_for_selector('.company-block')
                    assert page.locator('.company-block').count() == 18
                    assert page.locator('.job').count() == 0
                    page.screenshot(path=str(ROOT/'build/dashboard.png'), full_page=True)
                    cli = runtime.opencli_command()+['--profile', runtime.browser_profile(), 'browser', 'release-smoke']
                    for _ in range(6):
                        result = subprocess.run(cli+['open', base], capture_output=True, text=True, encoding="utf-8", timeout=60)
                        if result.returncode == 0:
                            break
                        time.sleep(2)
                    assert result.returncode == 0, result.stderr
                    result = subprocess.run(cli+['eval', 'JSON.stringify({title:document.title,companies:document.querySelectorAll(".company-block").length})'],
                                            capture_output=True, text=True, encoding="utf-8", check=True, timeout=60)
                    assert '18' in result.stdout and '投递进度助手' in result.stdout, result.stdout
                finally:
                    browser.close()
            print('PASS: release startup, reuse, HTTP, empty state, browser, extension, OpenCLI read')
        finally:
            server.terminate()
            server.wait(timeout=20)


if __name__ == '__main__':
    main()
