import json
import unittest
from records import parse_records
from application_changes import describe_changes


def text(steps=None, title='示例工程师'):
    base=f'{title}\n变更职位\n结束流程\n投递时间：2026-09-09\n投递简历\n简历筛选\n面试\nOffer\n流程中\n页面标记的当前阶段：\n{title}：简历筛选'
    if steps is not None:base+='\n悬浮筛选详情：'+json.dumps([dict(index=0,title=title,steps=steps)],ensure_ascii=False)
    return base


class KuaishouHoverTests(unittest.TestCase):
    def test_department_screening_and_completed_hr(self):
        steps=[dict(label='HR初筛',state='done'),dict(label='用人部门筛选',state='current')]
        record=parse_records('kuaishou',text(steps))[0]
        self.assertEqual(record['status'],'用人部门筛选')
        self.assertEqual(record['group'],'screening')
        self.assertEqual(record['screen_level'],'用人部门筛选')
        states={s['label']:s['state'] for s in record['steps']}
        self.assertEqual(states['HR初筛'],'done');self.assertEqual(states['用人部门筛选'],'current')
        self.assertEqual(states['面试'],'future')

    def test_unknown_icons_do_not_invent_stage(self):
        steps=[dict(label='HR初筛',state='unknown'),dict(label='用人部门筛选',state='unknown')]
        self.assertEqual(parse_records('kuaishou',text(steps))[0]['status'],'简历筛选')

    def test_tooltip_for_another_role_is_not_reused(self):
        raw=text([dict(label='用人部门筛选',state='current')]).replace('"title": "示例工程师"','"title": "另一个岗位"')
        self.assertEqual(parse_records('kuaishou',raw)[0]['status'],'简历筛选')

    def test_changes_distinguish_new_detail_from_real_progress(self):
        hr=text([dict(label='HR初筛',state='current'),dict(label='用人部门筛选',state='unknown')])
        department=text([dict(label='HR初筛',state='done'),dict(label='用人部门筛选',state='current')])
        self.assertEqual(describe_changes('kuaishou',text(),department)[0]['kind'],'details')
        self.assertEqual(describe_changes('kuaishou',hr,department)[0]['message'],'状态：HR初筛 → 用人部门筛选')
