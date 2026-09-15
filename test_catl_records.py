import unittest
from records import parse_records

class CatlRecordsTest(unittest.TestCase):
    def test_preferences_and_literal_status_without_invented_stage(self):
        raw='第 1 志愿\n示例研发岗位\n修改申请\n状态:\n简历已处理，请耐心等待\n项目:\n示例校招\n2025-01-02 10:00\n职位部门名称：示例一部\n第 2 志愿\n示例测试岗位\n修改申请\n状态:\n简历已处理，请耐心等待\n2025-01-03 11:00\n职位部门名称：示例二部'
        rows=parse_records('catl',raw)
        self.assertEqual([r['title'] for r in rows],['示例研发岗位','示例测试岗位'])
        self.assertEqual([r['preference'] for r in rows],['第 1 志愿','第 2 志愿'])
        self.assertEqual([r['applied_at'] for r in rows],['2025-01-02','2025-01-03'])
        self.assertEqual([r['department'] for r in rows],['示例一部','示例二部'])
        for row in rows:
            self.assertEqual(row['status'],'简历已处理，请耐心等待')
            self.assertEqual(row['group'],'other')
            self.assertFalse(any(s['state'] in ('done','current') for s in row['steps']))
