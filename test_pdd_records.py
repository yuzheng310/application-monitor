import unittest
from records import parse_records

class PddRecordsTest(unittest.TestCase):
    def test_shared_status_preserves_two_preferences(self):
        text='岗位记录\n职位：示例研发\n志愿：志愿一\n投递时间：2025-01-02\n当前状态：待处理\n岗位记录\n职位：示例测试\n志愿：志愿二\n投递时间：2025-01-02\n当前状态：待处理'
        rows=parse_records('pdd',text)
        self.assertEqual([r['title'] for r in rows],['示例研发','示例测试'])
        self.assertEqual([r['preference'] for r in rows],['志愿一','志愿二'])
        self.assertTrue(all(r['status']=='待处理' and not r['steps'] for r in rows))
