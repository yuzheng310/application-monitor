import tempfile
import unittest
from pathlib import Path
from interview_tracking import InterviewTracking


class TrackingTests(unittest.TestCase):
    def test_history_preserved_and_invalid_edit_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store=InterviewTracking(directory)
            body=dict(action='save',company='示例公司',role='示例岗位',rounds=[dict(date='2026-09-22',round='一面',notes='')])
            row=store.access(body)[0]
            row['rounds'].append(dict(date='2026-09-25',round='二面',notes='已完成，等待反馈'))
            store.access(dict(row,action='save'))
            self.assertEqual(len(InterviewTracking(directory).access()[0]['rounds']),2)
            before=(Path(directory)/'interview-tracking.json').read_bytes()
            row['rounds'][0]['date']='2026-02-30'
            with self.assertRaises(ValueError):store.access(dict(row,action='save'))
            self.assertEqual((Path(directory)/'interview-tracking.json').read_bytes(),before)
            self.assertEqual(store.access(dict(action='delete',id=row['id'])),[])

    def test_corrupt_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'interview-tracking.json';path.write_text('{}')
            with self.assertRaises(ValueError):InterviewTracking(directory).access(dict(action='save',company='示例'))
            self.assertEqual(path.read_text(),'{}')
