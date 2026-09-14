import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer
import web_server


class DashboardTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(web_server.runtime, 'browser_profile', return_value='test-instance')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_failed_query_keeps_stale_success_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);data=root/'data';data.mkdir()
            (root/'sites.json').write_text(json.dumps({'sites':[{'id':'one','name':'公司','url':'https://example.com/?share_token=secret'}]}))
            (data/'state.json').write_text(json.dumps({'one':{'text':'原记录','last_success':'2026-09-13T09:00:00+08:00'}}))
            (data/'latest.json').write_text(json.dumps([{'company':'公司','status':'检查失败','error':'需要登录'}]))
            with patch.object(web_server,'ROOT',root),patch.object(web_server,'DATA',data):
                status=web_server.Dashboard().status()
            site=status['sites'][0]
            self.assertEqual(site['text'],'原记录')
            self.assertTrue(site['stale'])
            self.assertNotIn('secret',site['url'])

    def test_partial_progress_overlays_only_completed_companies(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);data=root/'data';data.mkdir()
            (root/'sites.json').write_text(json.dumps({'sites':[{'id':'one','name':'公司','url':'https://example.com/'}]}))
            (data/'latest.json').write_text(json.dumps([{'company':'公司','status':'无变化','text':'旧记录'}]))
            (data/'progress.json').write_text(json.dumps({'status':'running','results':[{'company':'公司','status':'内容变化','text':'新记录'}]}))
            with patch.object(web_server,'ROOT',root),patch.object(web_server,'DATA',data):
                dashboard=web_server.Dashboard()
                with patch.object(dashboard,'is_running',return_value=True):
                    status=dashboard.status()
            self.assertEqual(status['sites'][0]['text'],'新记录')
            self.assertTrue(status['running'])

    def test_http_boundaries_and_duplicate_refresh(self):
        dashboard=web_server.Dashboard()
        with patch.object(dashboard,'status',return_value={'sites':[],'csrf_token':dashboard.token}),patch.object(dashboard,'refresh',side_effect=[True,False]) as refresh:
            server=ThreadingHTTPServer(('127.0.0.1',0),web_server.handler_for(dashboard))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base='http://127.0.0.1:'+str(server.server_port)
            try:
                with urlopen(base+'/api/status') as response:self.assertEqual(response.status,200)
                for path in ['/sites.json','/data/state.json','/../sites.json']:
                    with self.assertRaises(HTTPError) as error:urlopen(base+path)
                    self.assertEqual(error.exception.code,404)
                for headers in [{},{'X-Query-Token':dashboard.token,'Origin':'https://example.com'},{'Host':'example.com'}]:
                    with self.assertRaises(HTTPError) as error:urlopen(Request(base+'/api/refresh',method='POST',headers=headers))
                    self.assertEqual(error.exception.code,403)
                self.assertEqual(refresh.call_count,0)
                request=Request(base+'/api/refresh',method='POST',headers={'X-Query-Token':dashboard.token,'Origin':base})
                with urlopen(request) as response:self.assertEqual(response.status,202)
                with self.assertRaises(HTTPError) as error:urlopen(request)
                self.assertEqual(error.exception.code,409)
            finally:
                server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
