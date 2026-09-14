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
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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
            from playwright.sync_api import sync_playwright, expect
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
                    # End-to-end speed and retry regression, using only local fixtures.
                    login_required = [True]
                    class Fixture(BaseHTTPRequestHandler):
                        def do_GET(self):
                            text = '短信验证码' if self.path == '/login-fixture' and login_required[0] else '投递记录 岗位 ' + self.path
                            body = ('<html><meta charset="utf-8"><div id="records">'+text+'</div></html>').encode()
                            self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8')
                            self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
                        def log_message(self, *args): pass
                    fixtures = ThreadingHTTPServer(('127.0.0.1',0), Fixture)
                    threading.Thread(target=fixtures.serve_forever,daemon=True).start()
                    try:
                        sites = [{'id':'test'+str(i),'name':'测试公司'+str(i),'url':f'http://127.0.0.1:{fixtures.server_port}/fixture-{i}',
                                  'selector':'#records','ready_text':'投递记录','content_pattern':'岗位'} for i in range(4)]
                        config = {'sites': sites, 'times': [], 'concurrency': 4}
                        runtime.CONFIG.write_text(json.dumps(config),encoding='utf-8')
                        start = time.monotonic()
                        subprocess.run([str(binary),'check','--workers','1'],check=True,timeout=180)
                        serial = time.monotonic()-start
                        page.reload();page.wait_for_selector('.site-retry')
                        start = time.monotonic()
                        page.click('#refresh')
                        page.locator('.query-badge').nth(1).wait_for()
                        expect(page.locator('#refresh')).to_be_enabled(timeout=180000)
                        parallel = time.monotonic()-start
                        assert parallel < serial, (serial, parallel)
                        print(f'REAL BROWSER: 4 sites serial={serial:.2f}s parallel={parallel:.2f}s speedup={serial/parallel:.2f}x')
                        sites.append({'id':'login','name':'登录测试','url':f'http://127.0.0.1:{fixtures.server_port}/login-fixture',
                                      'selector':'#records','ready_text':'投递记录'})
                        runtime.CONFIG.write_text(json.dumps(config),encoding='utf-8')
                        page.reload();page.wait_for_selector('[data-site-id="login"]')
                        page.click('[data-site-id="login"]')
                        page.wait_for_selector('#company-login .error',timeout=60000)
                        assert 'LOGIN_REQUIRED' in page.locator('#company-login .error').inner_text()
                        assert '验证码' in page.locator('#company-login .error').inner_text()
                        page.screenshot(path=str(ROOT/'build/errors.png'),full_page=True)
                        login_required[0] = False
                        expect(page.locator('#retryFailed')).to_be_enabled()
                        page.click('#retryFailed')
                        page.locator('.query-badge').first.wait_for()
                        expect(page.locator('#refresh')).to_be_enabled(timeout=60000)
                        with urllib.request.urlopen(base+'api/status') as response: final = json.load(response)
                        assert len(final['sites']) == 5 and not any(x['stale'] for x in final['sites']), [(x['id'], x['status'], x.get('error_code')) for x in final['sites']]
                        assert final['progress']['total'] == 1
                        # A failed request message must survive polling, and controls remain usable.
                        page.route('**/api/refresh', lambda route: route.fulfill(status=500,content_type='application/json',body='{"error":"模拟启动失败"}'))
                        page.click('#refresh');page.wait_for_selector('#requestError:not([hidden])')
                        assert '模拟启动失败' in page.locator('#requestError').inner_text()
                        page.wait_for_timeout(2200)
                        assert page.locator('#requestError').is_visible()
                        assert page.locator('#refresh').is_enabled()
                    finally:
                        fixtures.shutdown();fixtures.server_close()

                finally:
                    browser.close()
            print('PASS: release startup, reuse, HTTP, empty state, browser, extension, OpenCLI read')
        finally:
            server.terminate()
            server.wait(timeout=20)


if __name__ == '__main__':
    main()
