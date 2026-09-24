import unittest
from records import parse_records
from monitor import same_route
from web_server import safe_link


class ShlabTests(unittest.TestCase):
    def test_highlighted_status_not_future_interviews(self):
        text='岗位记录\n职位：示例研发工程师\n投递时间：2026-09-24 10:00:00\n当前状态：简历初筛\n简历初筛\n笔试\n部门面试\nJob Talk\nHR面\nOffer沟通'
        row=parse_records('shlab',text)[0]
        self.assertEqual(row['group'],'screening')
        self.assertEqual(row['applied_at'],'2026-09-24')
        self.assertEqual([s['label'] for s in row['steps'] if s['state']=='current'],['简历初筛'])
        self.assertTrue(all(s['state']=='future' for s in row['steps'][1:]))
        for status in ('部门面试','Job Talk','HR面'):
            self.assertEqual(parse_records('shlab',text.replace('当前状态：简历初筛','当前状态：'+status))[0]['group'],'interview')

    def test_campus_mode_preserved_and_checked(self):
        url='https://www.shlab.org.cn/user/applications?mode=campus'
        self.assertEqual(safe_link(url+'&share_token=example'),url)
        self.assertTrue(same_route(url,url))
        self.assertFalse(same_route(url,url.replace('campus','social')))
        self.assertFalse(same_route(url,url.split('?')[0]))
