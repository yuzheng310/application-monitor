import unittest
from records import parse_records


class ShopeeCurrentTests(unittest.TestCase):
    def test_new_cards_have_independent_statuses_and_dates(self):
        raw='岗位记录\n职位：示例研发工程师\n志愿：\n投递时间：2026-09-22\n当前状态：初筛\n地点：北京市\n岗位记录\n职位：示例算法工程师\n志愿：\n投递时间：2026-09-11\n当前状态：暂不匹配\n地点：上海市'
        rows=parse_records('shopee',raw)
        self.assertEqual([r['group'] for r in rows],['screening','ended'])
        self.assertEqual([r['applied_at'] for r in rows],['2026-09-22','2026-09-11'])
        self.assertEqual([r['location'] for r in rows],['北京市','上海市'])
        self.assertEqual(rows[0]['steps'],[dict(label='初筛',date='',state='current')])
        self.assertNotIn('HR',rows[0]['screen_level'])

    def test_legacy_records_still_parse(self):
        raw='第 1 志愿\n示例工程师\n投递时间：2026-09-09\n页面标记的当前阶段：\n示例工程师：初试'
        self.assertEqual(parse_records('shopee',raw)[0]['group'],'interview')
