import unittest
from records import parse_records

class MicrosoftRecordsTest(unittest.TestCase):
    def test_literal_status_and_english_dates(self):
        raw='岗位记录\n职位：Example Engineer\n投递时间：Applied on Jan 2, 2025\n当前状态：Submitted\n岗位记录\n职位：Example Scientist\n投递时间：Applied on February 3, 2025\n当前状态：Application Processing'
        rows=parse_records('microsoft',raw)
        self.assertEqual([r['title'] for r in rows],['Example Engineer','Example Scientist'])
        self.assertEqual([r['applied_at'] for r in rows],['2025-01-02','2025-02-03'])
        self.assertEqual([r['status'] for r in rows],['Submitted','Application Processing'])
        self.assertEqual([r['group'] for r in rows],['applied','other'])
        self.assertTrue(all(not r['steps'] for r in rows))

    def test_unknown_and_ended_statuses(self):
        for status,group in [('Not selected','ended'),('Withdrawn','ended'),('Unknown status','other')]:
            row=parse_records('microsoft','岗位记录\n职位：Example role\n投递时间：Applied on Feb 31, 2025\n当前状态：'+status)[0]
            self.assertEqual(row['group'],group)
            self.assertEqual(row['applied_at'],'')
