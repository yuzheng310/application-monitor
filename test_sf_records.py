import unittest
from records import parse_records

class SfRecordsTest(unittest.TestCase):
    def test_highlight_is_current_not_future_interview_labels(self):
        for status,group in [('网申','applied'),('复试','interview')]:
            raw='岗位记录\n职位：示例研发\n投递时间：2025-01-02\n当前状态：'+status+'\n网申\n初试\n复试\n终试\noffer\n待入职\n成功入职'
            r=parse_records('sf',raw)[0]
            self.assertEqual((r['title'],r['group'],r['applied_at']),('示例研发',group,'2025-01-02'))
            self.assertEqual([s['label'] for s in r['steps'] if s['state']=='current'],[status])
            self.assertFalse(any(s['state']=='done' for s in r['steps']))
            self.assertEqual(r['steps'][-1]['state'],'future')
