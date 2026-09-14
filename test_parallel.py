import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import monitor


class ParallelTests(unittest.TestCase):
    def test_each_check_uses_fresh_owned_session_and_releases_it(self):
        site = {'id':'one','url':'https://example.com/','selector':'#records','ready_text':'投递记录'}
        with patch.object(monitor, 'cli') as cli, patch.object(monitor, 'read_stable_site', return_value='新记录'):
            self.assertEqual(monitor.check_site({}, site), '新记录')
            self.assertEqual(monitor.check_site({}, site), '新记录')
        opens = [c for c in cli.call_args_list if c.args[2]=='open']
        closes = [c for c in cli.call_args_list if c.args[2]=='close']
        self.assertNotEqual(opens[0].args[0]['_session_suffix'], opens[1].args[0]['_session_suffix'])
        self.assertEqual([c.args[0]['_session_suffix'] for c in opens], [c.args[0]['_session_suffix'] for c in closes])

    def test_login_named_application_route_is_not_misclassified(self):
        site = {'url': 'https://example.com/login#/myDeliver', 'ready_text': '网申投递'}
        page = {'url': site['url'], 'ready_found': True, 'count': 1, 'text': '投递详情'}
        self.assertEqual(monitor.validate(page, site), '投递详情')

    def test_targeted_retry_preserves_other_latest_results(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(monitor, 'DATA', Path(folder)):
            sites = [{'id': str(i), 'name': '公司'+str(i)} for i in range(3)]
            def mixed(config, site):
                if site['id'] == '1':
                    raise monitor.CheckError('LOGIN_REQUIRED')
                return '记录'+site['id']
            with patch.object(monitor, 'check_site', side_effect=mixed):
                self.assertFalse(monitor.run_once({'sites': sites}))
            with patch.object(monitor, 'check_site', return_value='恢复的记录'):
                self.assertTrue(monitor.run_once({'sites': [sites[1]]}))
            latest = json.loads((Path(folder)/'latest.json').read_text(encoding='utf-8'))
            self.assertEqual(len(latest), 3)
            self.assertFalse(any(s['status']=='检查失败' for s in latest))
            state = json.loads((Path(folder)/'state.json').read_text(encoding='utf-8'))
            self.assertEqual(state['0']['text'], '记录0')

    def test_login_failure_does_not_wait_for_page_timeout(self):
        site = {'id':'login','url':'https://example.com/records','selector':'#records','ready_text':'投递记录'}
        with patch.object(monitor, 'cli'), patch.object(monitor, 'read_page', return_value={'url':'https://example.com/login'}) as read, patch.object(monitor.time, 'sleep') as sleep:
            with self.assertRaises(monitor.CheckError) as error:
                monitor.check_site({}, site)
            self.assertEqual(error.exception.code, 'LOGIN_REQUIRED')
            self.assertEqual(read.call_count, 1)
            sleep.assert_not_called()

    def test_one_unexpected_site_error_does_not_cancel_others(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(monitor, 'DATA', Path(folder)):
            def mixed(config, site):
                if site['id']=='bad': raise KeyError('PRIVATE_VALUE')
                return '正常记录'
            with patch.object(monitor, 'check_site', side_effect=mixed):
                self.assertFalse(monitor.run_once({'sites':[{'id':'bad','name':'异常公司'},{'id':'ok','name':'正常公司'}]}))
            raw = (Path(folder)/'latest.json').read_text(encoding='utf-8')
            self.assertNotIn('PRIVATE_VALUE', raw)
            self.assertEqual(len(json.loads(raw)), 2)
            self.assertEqual(json.loads((Path(folder)/'progress.json').read_text(encoding='utf-8'))['status'], 'complete')

    def test_queries_overlap_with_a_bound_and_preserve_every_result(self):
        active = peak = 0
        guard = threading.Lock()
        def check(config, site):
            nonlocal active, peak
            with guard:
                active += 1
                peak = max(peak, active)
            time.sleep(.06)
            with guard:
                active -= 1
            return '岗位 ' + site['id']
        sites = [{'id': str(i), 'name': '公司' + str(i)} for i in range(6)]
        with tempfile.TemporaryDirectory() as folder, patch.object(monitor, 'DATA', Path(folder)), patch.object(monitor, 'check_site', side_effect=check):
            before = time.monotonic()
            self.assertTrue(monitor.run_once({'sites': sites, 'concurrency': 3}))
            print('Six simulated sites: %.3fs, peak concurrency=%d' % (time.monotonic()-before, peak))
            self.assertGreater(peak, 1, 'Queries are still serial')
            self.assertLessEqual(peak, 3)
            self.assertEqual(len(json.loads((Path(folder)/'state.json').read_text(encoding='utf-8'))), 6)
            self.assertEqual(len((Path(folder)/'history.jsonl').read_text(encoding='utf-8').splitlines()), 6)

    def test_network_failure_has_actionable_safe_details(self):
        failed = subprocess.CompletedProcess([], 1, '', 'net::ERR_NAME_NOT_RESOLVED https://example.com/?token=PRIVATE_VALUE')
        with tempfile.TemporaryDirectory() as folder, patch.object(monitor, 'DATA', Path(folder)), patch.object(monitor.runtime, 'opencli_command', return_value=['node', 'cli']), patch.object(monitor.runtime, 'browser_profile', return_value='test'), patch.object(monitor.subprocess, 'run', return_value=failed):
            monitor.run_once({'sites': [{'id': 'one', 'name': '公司', 'url': 'https://example.com', 'selector':'#records','ready_text':'投递记录'}]})
            text = (Path(folder)/'latest.json').read_text(encoding='utf-8')
            result = json.loads(text)[0]
            self.assertEqual(result.get('error_code'), 'NETWORK_ERROR')
            self.assertTrue(result.get('suggestion'))
            self.assertNotIn('PRIVATE_VALUE', text)


if __name__ == '__main__':
    unittest.main()
