import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
import monitor


class MonitorTests(unittest.TestCase):
    def test_fragment_routes_reject_login_and_resume(self):
        expected = "https://example.com/app/#/candidate/applications?source=share"
        self.assertTrue(monitor.same_route(expected, "https://example.com/app/#/candidate/applications"))
        for actual in ["https://example.com/app/#/login", "https://example.com/app/#/candidate/resume",
                       "https://other.example/app/#/candidate/applications"]:
            self.assertFalse(monitor.same_route(expected, actual))

    def test_progress_only_change_is_captured(self):
        site = {"url": "https://example.com/app", "ready_text": "投递记录"}
        page = {"url": site["url"], "ready_found": True, "count": 1,
                "text": "岗位 A\n简历筛选\n面试\nOffer", "extra": ["岗位 A：简历筛选"]}
        first = monitor.validate(page, site)
        page["extra"] = ["岗位 A：面试"]
        self.assertNotEqual(first, monitor.validate(page, site))
        page["auth_required"] = True
        with self.assertRaises(RuntimeError):
            monitor.validate(page, site)

    def test_record_tab_clicked_once_and_verified(self):
        site = {"url": "https://example.com/", "read_steps": [{"selector": "#records", "done_selector": "#records-panel.active"}]}
        replies = ['{"url":"https://example.com/", "done":false, "count":1}',
                   '{}', '{"url":"https://example.com/", "done":true, "count":1}']
        with patch.object(monitor, "cli", side_effect=replies) as cli:
            monitor.prepare_page({}, site)
        actions = [call.args[2] for call in cli.call_args_list]
        self.assertEqual(actions, ["eval", "click", "eval"])
        with patch.object(monitor, "cli", return_value='{"url":"https://example.com/login", "done":false, "count":1}') as cli:
            with self.assertRaises(RuntimeError):
                monitor.prepare_page({}, site)
            self.assertEqual(cli.call_count, 1)

    def test_schedule_and_midnight(self):
        for now, expected in [("2026-09-13T09:00:00", "2026-09-13T12:30:00+08:00"),
                              ("2026-09-13T20:00:00", "2026-09-14T09:00:00+08:00")]:
            actual = monitor.next_run(datetime.fromisoformat(now).replace(tzinfo=monitor.TZ), ["09:00", "12:30", "19:00"])
            self.assertEqual(actual.isoformat(), expected)

    def test_login_and_loading_not_status(self):
        site = {"url": "https://example.com/application", "ready_text": "应聘记录"}
        page = {"url": site["url"], "body": "应聘记录", "count": 1, "text": "岗位 A\n投递简历"}
        self.assertEqual(monitor.validate(page, site), page["text"])
        for change in [{"url": "https://example.com/login"}, {"body": "应聘记录 获取验证码"},
                       {"text": "加载中"}, {"count": 0}, {"count": 2}, {"text": ""}]:
            with self.assertRaises(RuntimeError):
                monitor.validate(dict(page, **change), site)

    def test_failure_preserves_baseline_and_recovery_diff(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(monitor, "DATA", Path(directory)):
            config = {"sites": [{"id": "one", "name": "公司"}]}
            with patch.object(monitor, "check_site", return_value="岗位\n投递简历"):
                self.assertTrue(monitor.run_once(config))
            baseline = (Path(directory) / "state.json").read_text()
            with patch.object(monitor, "check_site", side_effect=RuntimeError("登录失效")):
                self.assertFalse(monitor.run_once(config))
            self.assertEqual((Path(directory) / "state.json").read_text(), baseline)
            with patch.object(monitor, "check_site", return_value="岗位\n面试"):
                self.assertTrue(monitor.run_once(config))
            result = (Path(directory) / "最新结果.txt").read_text()
            self.assertIn("-投递简历", result)
            self.assertIn("+面试", result)


if __name__ == "__main__":
    unittest.main()
