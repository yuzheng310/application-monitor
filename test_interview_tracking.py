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

    def test_sync_is_idempotent_and_keeps_manual_rounds_and_status(self):
        with tempfile.TemporaryDirectory() as directory:
            store=InterviewTracking(directory)
            manual=store.access(dict(action='save',company='示例公司（Example）',role='工程师',status='waiting',rounds=[dict(date='2026-09-22',round='一面',notes='我的记录')],next_step='联系 HR'))[0]
            site=dict(id='example',company='示例公司',applications=[dict(title='工程师',group='interview')])
            first=store.sync_sites([site])
            self.assertEqual(len(first),1)
            self.assertEqual(first[0]['id'],manual['id'])
            for key in ('rounds','next_step','status','notes'):
                self.assertEqual(first[0][key],manual[key])
            self.assertEqual(store.sync_sites([site]),first)
            edited=dict(first[0],action='save',status='ended');edited.pop('source_key')
            store.access(edited)
            self.assertEqual(store.sync_sites([site])[0]['status'],'ended')

    def test_sync_adds_only_interviews_and_does_not_invent_rounds(self):
        with tempfile.TemporaryDirectory() as directory:
            store=InterviewTracking(directory)
            apps=[dict(title='正式岗位',group='interview'),dict(title='实习岗位',group='interview',internship=True),dict(title='筛选岗位',group='screening')]
            site=dict(id='example',company='示例公司',applications=apps)
            self.assertEqual(store.sync_sites([dict(site,stale=True)]),[])
            result=store.sync_sites([site])
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]['status'],'interviewing')
            self.assertEqual(result[0]['rounds'],[])
            self.assertEqual(result[0]['notes'],'')
            self.assertEqual(store.sync_sites([site]),result)

    def test_same_title_distinct_departments_are_kept_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            store=InterviewTracking(directory)
            site=dict(id='example',company='示例公司',applications=[dict(title='工程师',group='interview',department=department) for department in ('甲部门','乙部门')])
            result=store.sync_sites([site])
            self.assertEqual(len(result),2)
            self.assertEqual(store.sync_sites([site]),result)
