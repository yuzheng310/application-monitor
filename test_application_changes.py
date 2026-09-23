import unittest
from unittest.mock import patch
from application_changes import describe_changes


def row(title='示例岗位', status='简历筛选', department='', **extra):
    return dict(title=title,status=status,department=department,steps=[],**extra)


class ChangesTests(unittest.TestCase):
    def compare(self, before, after):
        with patch('application_changes.parse_records',side_effect=[before,after]):
            return describe_changes('example','before','after')

    def test_real_feishu_status_transition(self):
        before='示例岗位第 1 志愿\n官网投递\n北京校招\n投递简历\n2026-09-10'
        after=before+'\n面试中\n2026-09-23'
        change=describe_changes('agirobot',before,after)
        self.assertEqual(len(change),1)
        self.assertEqual(change[0]['message'],'状态：投递简历 → 面试中')

    def test_first_read_and_cosmetic_change_are_not_progress(self):
        self.assertEqual(describe_changes('agirobot',None,'text'),[])
        self.assertEqual(self.compare([row()],[row()]),[])

    def test_same_title_different_departments_do_not_cross_match(self):
        old=[row(department='甲部门'),row(department='乙部门')]
        new=[row(department='乙部门'),row(department='甲部门',status='面试中')]
        changes=self.compare(old,new)
        self.assertEqual(len(changes),1)
        self.assertEqual(changes[0]['context'],'甲部门')
        self.assertIn('简历筛选 → 面试中',changes[0]['message'])

    def test_ambiguous_duplicates_not_reported_as_rejection(self):
        changes=self.compare([row(),row()],[row(status='已结束'),row()])
        self.assertEqual([x['kind'] for x in changes],['uncertain'])

    def test_missing_is_not_rejection_and_internships_excluded(self):
        changes=self.compare([row()],[])
        self.assertEqual(changes[0]['kind'],'missing')
        self.assertIn('不代表被拒绝',changes[0]['message'])
        self.assertEqual(self.compare([],[row(internship=True)]),[])

    def test_changed_active_stage_with_same_status(self):
        a=row();b=row();a['steps']=[dict(label='一面',state='current')];b['steps']=[dict(label='二面',state='current')]
        self.assertEqual(self.compare([a],[b])[0]['message'],'当前阶段：一面 → 二面')
