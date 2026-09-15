import unittest
from unittest.mock import patch
import monitor

class ReadRecoveryTests(unittest.TestCase):
    site={'id':'example','url':'https://example.com/records','selector':'#records','ready_text':'投递记录'}

    def test_unready_page_recovers_in_a_new_owned_session(self):
        for code in ('SITE_CHANGED','PAGE_LOADING','TIMEOUT','NETWORK_ERROR'):
            with self.subTest(code=code), patch.object(monitor,'cli') as cli, patch.object(monitor,'read_stable_site',side_effect=[monitor.CheckError(code),'记录']) as read:
                self.assertEqual(monitor.check_site({},self.site),'记录')
                self.assertEqual(read.call_count,2)
                opens=[c for c in cli.call_args_list if c.args[2]=='open']
                closes=[c for c in cli.call_args_list if c.args[2]=='close']
                self.assertEqual(len(opens),2)
                self.assertNotEqual(opens[0].args[0]['_session_suffix'],opens[1].args[0]['_session_suffix'])
                self.assertEqual([c.args[0]['_session_suffix'] for c in opens],[c.args[0]['_session_suffix'] for c in closes])

    def test_persistent_failure_is_bounded(self):
        with patch.object(monitor,'cli'), patch.object(monitor,'read_stable_site',side_effect=monitor.CheckError('SITE_CHANGED')) as read:
            with self.assertRaises(monitor.CheckError):monitor.check_site({},self.site)
            self.assertEqual(read.call_count,2)

    def test_login_or_config_does_not_retry(self):
        for code in ('LOGIN_REQUIRED','CONFIG_ERROR','PAGE_REDIRECT'):
            with self.subTest(code=code),patch.object(monitor,'cli'),patch.object(monitor,'read_stable_site',side_effect=monitor.CheckError(code)) as read:
                with self.assertRaises(monitor.CheckError):monitor.check_site({},self.site)
                self.assertEqual(read.call_count,1)
