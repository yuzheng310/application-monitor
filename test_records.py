import unittest
from records import parse_records

class RecordsTest(unittest.TestCase):
    def test_pipeline_and_action_labels_are_not_current_status(self):
        raw='AI Infra工程师\n2027届应届生\n千问工程技术\n2026-09-11\n100000000001\n新投递\n终止应聘\n面试\nOffer\n入职\n成功入职'
        r=parse_records('alibaba',raw)[0]
        self.assertEqual((r['title'],r['group']),('AI Infra工程师','applied'))
        raw='AI Infra研发工程师\n变更职位\n结束流程\n投递时间：2026-09-09\n面试\nOffer\n流程中\n页面标记的当前阶段：\nAI Infra研发工程师：简历筛选'
        self.assertEqual(parse_records('kuaishou',raw)[0]['group'],'screening')

    def test_dated_history_ignores_undated_future_steps(self):
        raw='【校招】算法工程师\n志愿一\n投递简历\n2026-09-08\n用人部门筛选\n2026-09-11\n面试\nOffer\n未开始\n【校招】开发工程师\n志愿二\n投递时间：2026-09-08'
        self.assertEqual([r['group'] for r in parse_records('xiaohongshu',raw)],['screening','waiting'])

    def test_multiple_jobs_have_independent_statuses(self):
        raw='推理工程师第 1 志愿\n官网投递\n北京校招\n投递简历\n2026-09-10\n笔试中\n2026-09-11\n算法工程师第 2 志愿\n官网投递\n北京校招\n投递简历\n2026-09-10'
        r=parse_records('xiaomi',raw)
        self.assertEqual([x['group'] for x in r],['written','applied'])
        self.assertEqual(r[0]['applied_at'],'2026-09-10')

    def test_unknown_text_is_not_fabricated_progress(self):
        self.assertEqual(parse_records('jd','未知页面\n面试\nOffer\n入职')[0]['group'],'other')

class TimelineTest(unittest.TestCase):
    def test_baidu_complete_funnel(self):
        raw='AI Infra工程师(J123)\n投递时间：2026-09-09\n投递简历\n已完成\n简历筛选\n简历筛选通过\n面试\n面试流程中\nOffer\n入职'
        r=parse_records('baidu',raw)[0]
        self.assertEqual([s['state'] for s in r['steps']],['done','done','current','future','future'])

    def test_assessment_completion_does_not_advance_main_application(self):
        raw='AI基础设施工程\n平台技术 2026-09-10 123456\n新投递\n简历投递\n简历评估\n笔试\n已完成\n测评\n已完成\n面试\nOffer\n入职\n页面标记的当前阶段：\n当前流程：1\n简历投递'
        r=parse_records('ant',raw)[0]
        self.assertEqual(r['steps'][0]['state'],'current')
        self.assertEqual([(s['label'],s['state']) for s in r['auxiliary']],[('笔试','done'),('测评','done')])

    def test_internship_and_department_screen(self):
        raw='第 1 志愿\n【转正实习】算法工程师(J123)\n当前进度：待部门简历筛选\n2026-04-24 10:00 投递\n测评已完成'
        r=parse_records('iflytek',raw)[0]
        self.assertTrue(r['internship'])
        self.assertEqual(r['screen_level'],'用人部门筛选')
        self.assertEqual(r['auxiliary'][0]['state'],'done')

    def test_unknown_previous_steps_are_not_marked_passed(self):
        raw='算法工程师\n投递\n测评\n笔试\nAI面试\n简历筛选\n简历筛选中\n面试\nOffer\n入职'
        r=parse_records('jd',raw)[0]
        self.assertEqual(r['steps'][3]['state'],'unknown')
        self.assertEqual(r['steps'][4]['state'],'current')

if __name__=='__main__': unittest.main()
