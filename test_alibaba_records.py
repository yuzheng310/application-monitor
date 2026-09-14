"""Synthetic examples of Alibaba's two different application table layouts."""
import unittest
from records import parse_records

ACTIVE = '''进行中的流程
示例事业群
职位
所属部门
申请日期
申请编号
当前状态
操作
示例开发岗位
示例校招批次
示例研发部门
2025-01-02
900000001
新投递
终止应聘
简历投递
评估
面试
Offer
入职
成功入职
'''
FINISHED = '''已完成的流程
职位
所属部门
申请日期
申请编号
示例算法岗位
示例算法部门
2025-01-01
900000002
简历投递
评估
面试
Offer
入职
成功入职
'''

class AlibabaRecordsTest(unittest.TestCase):
    def test_finished_table_has_no_recruitment_batch_or_status_column(self):
        records = parse_records('alibaba', ACTIVE + FINISHED)
        self.assertEqual([r['title'] for r in records], ['示例开发岗位', '示例算法岗位'])
        self.assertEqual([r['group'] for r in records], ['applied', 'ended'])
        self.assertEqual(records[1]['department'], '示例算法部门')
        self.assertEqual(records[1]['applied_at'], '2025-01-01')
        self.assertFalse(any(s['state'] == 'current' for s in records[1]['steps']))
        self.assertEqual(records[0]['status'], '新投递')

    def test_collapsed_finished_rows_without_pipeline_or_trailing_status(self):
        raw = FINISHED.split('简历投递')[0] + '另一示例岗位\n另一示例部门\n2025-01-03\n900000003'
        records = parse_records('alibaba', raw)
        self.assertEqual([r['title'] for r in records], ['示例算法岗位', '另一示例岗位'])
        self.assertTrue(all(r['group'] == 'ended' for r in records))
        self.assertFalse(any(s['state'] == 'current' for r in records for s in r['steps']))

if __name__ == '__main__':
    unittest.main()
