import unittest
from records import parse_records

class ShopeeRecordsTest(unittest.TestCase):
    def test_highlight_controls_current_stage_not_future_interviews(self):
        raw='第 1 志愿\n示例研发岗位\n备注:\n-\n2025-01-02 10:00\n1\n初筛\n2\n笔试阶段\n3\n初试\n4\n复试\n5\n加面\n6\nHR面试\n修改志愿顺序'
        for status,group in [('初筛','screening'),('笔试阶段','written'),('初试','interview'),('复试','interview'),('加面','interview'),('HR面试','interview')]:
            with self.subTest(status=status):
                r=parse_records('shopee',raw+'\n页面标记的当前阶段：\n示例研发岗位：'+status)[0]
                self.assertEqual((r['title'],r['group'],r['applied_at']),('示例研发岗位',group,'2025-01-02'))
                self.assertEqual([s['label'] for s in r['steps'] if s['state']=='current'],[status])
        r=parse_records('shopee',raw)[0]
        self.assertEqual(r['group'],'other')
        self.assertFalse(any(s['state']=='current' for s in r['steps']))

    def test_preferences_keep_separate_statuses(self):
        raw='第 1 志愿\n示例开发\n2025-01-02\n初筛\n初试\n第 2 志愿\n示例测试\n2025-01-03\n初筛\n初试\n页面标记的当前阶段：\n示例开发：初筛\n示例测试：初试'
        self.assertEqual([r['group'] for r in parse_records('shopee',raw)],['screening','interview'])
