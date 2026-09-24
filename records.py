"""Clean application records using explicit status fields, never future pipeline labels."""
import re

GROUPS = [('interview','面试中'),('written','笔试 / 测评'),('screening','简历筛选'),('applied','已投递'),('waiting','待开启'),('other','其他 / 待确认'),('ended','已结束')]
DATE = r'20\d{2}[-/]\d{2}[-/]\d{2}'

def category(status):
    if re.search('结束|终止|不匹配|不通过|淘汰', status): return 'ended'
    if re.search('待开启|未开始', status): return 'waiting'
    if re.search('面试', status): return 'interview'
    if re.search('笔试|测评', status): return 'written'
    if re.search('筛选|初筛|评估|评审', status): return 'screening'
    if status in ('投递简历','简历投递','新投递','已投递','投递成功'): return 'applied'
    return 'other'

def parse_records(site_id, text):
    if not text.strip():
        return []
    main, _, current = text.partition('页面标记的当前阶段：')
    lines = [s.strip() for s in main.splitlines() if s.strip()]
    records = []
    def add(title, status, block='', location='', department='', preference='', note=''):
        date = re.search(DATE, block)
        title = re.sub(r'\*\d+推荐$', '', title)
        title = re.sub(r'\((?:J|MJ)\d+\)$', '', title).strip()
        records.append(dict(title=title, status=status or '待确认', group=category(status),
            applied_at=date.group().replace('/','-') if date else '', location=location,
            department=department, preference=preference, note=note,
            internship='实习' in title, **progress_details(site_id, title, status, block, current)))
    def segments(indices):
        return [(lines[i], lines[i:(indices[n+1] if n+1<len(indices) else len(lines))]) for n,i in enumerate(indices)]
    def field(block, label):
        m = re.search(label+r'[:：]\s*([^\n]+)', '\n'.join(block))
        return m.group(1) if m else ''
    def dated(block):
        return [(block[i-1], x) for i,x in enumerate(block) if i and re.fullmatch(DATE,x)]
    if site_id in ('minimax','poizon','kuro','sensetime','xiaomi','xiaopeng','momenta','agirobot','bambulab'):
        for title,b in segments([i-1 for i,x in enumerate(lines) if i and x=='官网投递']):
            pref = re.search(r'第\s*\d+\s*志愿',title)
            stages=dated(b)
            loc=re.split(r'校招|技术类|项目：', b[2])[0] if len(b)>2 else ''
            add(re.sub(r'第\s*\d+\s*志愿','',title), stages[-1][0] if stages else '', '\n'.join(b),loc,preference=pref.group() if pref else '')
    elif site_id=='baidu':
        for title,b in segments([i for i,x in enumerate(lines) if re.search(r'\(J\d+\)$',x)]):
            status=next((x for x in b if '流程已结束' in x), '') or next((x for x in b if re.search(r'流程结束|面试流程中|筛选中|筛选通过|Offer已发放|已入职',x)), '')
            # Prefer the explicit active interview over the preceding completed screen.
            if '面试流程中' in b and '流程结束' not in status: status='面试流程中'
            add(title,status,'\n'.join(b),next((x for x in b[1:] if x.endswith('市')),''))
    elif site_id=='kuaishou':
        for title,b in segments([i-1 for i,x in enumerate(lines) if i and x=='变更职位']):
            m=re.search(re.escape(title)+r'：([^\n]+)',current)
            add(title,'已结束' if '已结束' in b else m.group(1) if m else '流程中','\n'.join(b),field(b,'意向地点'))
    elif site_id=='shlab':
        labels=('简历初筛','笔试','简历评估(校招)','评估通过','部门面试','Job Talk','HR面','意向书','Offer沟通','三方','待入职','已入职')
        for _,b in segments([i for i,x in enumerate(lines) if x=='岗位记录']):
            title=field(b,'职位')
            if not title: continue
            status=field(b,'当前状态')
            add(title,status,'\n'.join(b))
            record=records[-1]
            if status in ('Job Talk','HR面'): record['group']='interview'
            stages=list(dict.fromkeys(x for x in b if x in labels))
            active=stages.index(status) if status in stages else None
            record['steps']=[dict(label=label,date='',state='current' if i==active else
                'future' if active is not None and i>active else 'unknown') for i,label in enumerate(stages)]
            record['pipeline_note']='仅按官网高亮节点标识当前阶段'
    elif site_id=='sf':
        labels=('网申','初试','复试','终试','offer','Offer','待入职','成功入职')
        for _,b in segments([i for i,x in enumerate(lines) if x=='岗位记录']):
            title=field(b,'职位')
            if not title: continue
            status=field(b,'当前状态')
            add(title,status,'\n'.join(b))
            record=records[-1]
            record['group']={'网申':'applied','初试':'interview','复试':'interview','终试':'interview',
                             '成功入职':'ended'}.get(status,'other')
            stages=list(dict.fromkeys('Offer' if x=='offer' else x for x in b if x in labels))
            active=stages.index('Offer' if status=='offer' else status) if ('Offer' if status=='offer' else status) in stages else None
            record['steps']=[dict(label=label,date='',state='current' if i==active else
                'future' if active is not None and i>active else 'unknown') for i,label in enumerate(stages)]
            record['pipeline_complete']='成功入职' in stages
            record['pipeline_note']='仅高亮阶段代表当前进度，之前阶段的完成情况未单独公开'
    elif site_id=='microsoft':
        months={name:n for n,name in enumerate(('jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'),1)}
        for _,b in segments([i for i,x in enumerate(lines) if x=='岗位记录']):
            title=field(b,'职位')
            if not title: continue
            status=field(b,'当前状态')
            add(title,status,'\n'.join(b),note='保留官网英文状态；仅显示当前申请列表，处理中不代表进入面试')
            record=records[-1]
            record['group']={'submitted':'applied','application processing':'other',
                'not selected':'ended','withdrawn':'ended','inactive':'ended'}.get(status.lower(),'other')
            record['steps']=[]
            match=re.search(r'([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})',field(b,'投递时间'))
            if match and match[1][:3].lower() in months:
                from datetime import date
                try:record['applied_at']=date(int(match[3]),months[match[1][:3].lower()],int(match[2])).isoformat()
                except ValueError:pass
    elif site_id=='pdd':
        for _,b in segments([i for i,x in enumerate(lines) if x=='岗位记录']):
            title=field(b,'职位')
            if not title: continue
            add(title,field(b,'当前状态'),'\n'.join(b),preference=field(b,'志愿'),
                note='官网按校招项目显示共同状态，未细分每个志愿的流程阶段')
            records[-1]['steps']=[]
    elif site_id=='catl':
        for pref,b in segments([i for i,x in enumerate(lines) if re.fullmatch(r'第\s*\d+\s*志愿',x)]):
            if len(b)<2: continue
            add(b[1],field(b,'状态'),'\n'.join(b),department=field(b,'职位部门名称'),
                preference=pref,note='官网仅展示状态文字，未公开具体流程阶段')
            records[-1]['steps']=[]
    elif site_id=='shopee':
        for pref,b in segments([i for i,x in enumerate(lines) if re.fullmatch(r'第\s*\d+\s*志愿',x)]):
            if len(b)<2: continue
            title=b[1]
            match=re.search(re.escape(title)+r'：([^\n]+)',current)
            status=match.group(1).strip() if match else ''
            add(title,status,'\n'.join(b),preference=pref)
            if status in ('初试','复试','加面'):
                records[-1]['group']='interview'
    elif site_id=='didi':
        for title,b in segments([i-1 for i,x in enumerate(lines) if i and x in ('修改申请','查看详情')]):
            add(title,field(b,'状态'),'\n'.join(b),department=field(b,'职位一级部门名称'))
    elif site_id=='meituan':
        for title,b in segments([i for i,x in enumerate(lines) if re.match('志愿[一二三四五六七八九十]+：',x)]):
            idx=next((i for i,x in enumerate(b) if x.startswith('投递时间')),None)
            add(re.sub(r'^志愿[^：]+：','',title),b[idx+1] if idx is not None and idx+1<len(b) else '', '\n'.join(b),field(b,'意向工作地'),field(b,'意向部门'),title.split('：')[0])
    elif site_id=='jd' and lines:
        add(lines[0],next((x for x in lines if re.fullmatch(r'.+(?:中|已结束|不通过)',x)),''), main)
    elif site_id=='ant':
        for i,x in enumerate(lines):
            m=re.fullmatch(r'(.+?) ('+DATE+r') \d+',x)
            if m and i and i+1<len(lines): add(lines[i-1],lines[i+1],'\n'.join(lines[i:i+next((n for n,y in enumerate(lines[i+1:],1) if re.fullmatch(r'.+ '+DATE+r' \d+',y)),len(lines)-i)]),department=m.group(1),note='笔试、测评已完成' if lines[i+1]=='新投递' and '笔试\n已完成' in main and '测评\n已完成' in main else '')
    elif site_id=='alibaba':
        # Completed applications omit both the recruitment batch and status
        # columns. Their section heading is the evidence that they have ended.
        finished=False
        rows=[]
        headers={'职位','所属部门','申请日期','申请编号','当前状态','操作'}
        for i,x in enumerate(lines):
            if x=='已完成的流程': finished=True
            elif x=='进行中的流程': finished=False
            if not re.fullmatch(DATE,x) or i+1>=len(lines) or not lines[i+1].isdigit():
                continue
            start=i-(2 if finished else 3)
            if start<0 or lines[start] in headers:
                continue
            status='已结束' if finished else lines[i+2] if i+2<len(lines) else ''
            rows.append((start,i,status,finished))
        for n,(start,i,status,finished) in enumerate(rows):
            end=rows[n+1][0] if n+1<len(rows) else len(lines)
            end=next((j for j in range(i+2,end) if lines[j] in ('职位','已完成的流程','进行中的流程')),end)
            add(lines[start],status,'\n'.join(lines[i:end]),department=lines[i-1],
                note='官网归入已完成的流程，未显示具体结束原因' if finished else '')
    elif site_id=='xiaohongshu':
        starts=[i for i,x in enumerate(lines) if x.startswith('【') and i+1<len(lines) and lines[i+1].startswith('志愿')]
        for (title,b),idx in zip(segments(starts),starts):
            bucket=next((x for x in reversed(lines[:idx]) if x in ('正在进行中','未开始','已结束')),'')
            stages=dated(b)
            status='待开启' if bucket=='未开始' else '流程终止' if bucket=='已结束' else stages[-1][0] if stages else ''
            add(title,status,'\n'.join(b),field(b,'工作地点'),preference=b[1])
    elif site_id=='ctrip':
        for i,x in enumerate(lines):
            if re.search(r'\(MJ\d+\)$',x):
                add(x,lines[i+3] if i+3<len(lines) else '', '\n'.join(lines[i:]),lines[i+1],note='网站未展示具体阶段')
    elif site_id=='mihoyo':
        for i,x in enumerate(lines):
            m=re.search(DATE+r' \d{2}:\d{2}:\d{2} (.+?)(?: 更新|$)',x)
            if m and i>=2: add(lines[i-2],m.group(1),x,x.split()[0])
    elif site_id=='10jqka':
        for i,x in enumerate(lines):
            if '工程师' in x: add(x,lines[-1],note='网站未展示具体阶段')
    elif site_id=='netease':
        for title,b in segments([i-1 for i,x in enumerate(lines) if i and ' | 投递时间：' in x]):
            pref=re.search(r'第[一二三四五]+志愿',title)
            add(re.sub(r'内推第[一二三四五]+志愿$','',title),field(b,'应聘状态'),'\n'.join(b),preference=pref.group() if pref else '')
    elif site_id=='iflytek':
        for pref,b in segments([i for i,x in enumerate(lines) if re.fullmatch(r'第\s*\d+\s*志愿',x)]):
            if len(b)>1: add(b[1],field(b,'当前进度'),'\n'.join(b),preference=pref,note='测评已完成' if '测评已完成' in b else '')
    if not records:
        add('投递记录待确认','待确认',note='暂无可识别的岗位记录，请查看官网或原始记录')
    return records

# Stage names must be present in this job's source; no generic invented funnel.
STAGES = {'投递简历','简历投递','投递','投递成功','简历筛选','简历评估','评估','测评','笔试','笔试/测评',
          'AI面试','用人部门筛选','部门筛选','HR初筛','初筛','面试','一面','二面','三面','HR面','HR面试',
          '笔试阶段','初试','复试','加面','技术面试','业务面试','录用评估','Offer','offer','意向书','入职','预入职','等待筛选结果'}

def progress_details(site_id, title, status, block, current):
    lines=[s.strip() for s in block.splitlines() if s.strip()]
    if site_id=='netease' and '投递成功' in lines:
        lines=lines[lines.index('投递成功'):]
    steps=[]
    for i,line in enumerate(lines):
        following=lines[i+1] if i+1<len(lines) else ''
        if line not in STAGES and not (re.fullmatch(DATE,following) and re.search('笔试|面试|筛选|测评|终止',line)):
            continue
        label='Offer' if line.lower()=='offer' else '笔试' if line=='笔试中' else line
        if any(s['label']==label for s in steps): continue
        date=following if re.fullmatch(DATE,following) else ''
        completed=following in ('已完成','简历筛选通过','通过')
        ended=following=='流程结束' or label=='流程终止'
        steps.append(dict(label=label,date=date,state='ended' if ended else 'done' if completed else 'unknown'))
    explicit=''
    match=re.search(re.escape(title)+r'：([^\n]+)',current)
    if match: explicit=match.group(1)
    if site_id=='ant':
        match=re.search(r'当前流程：\d+\n([^\n]+)',current)
        if match and category(status)!='ended': explicit=match.group(1)
    aliases={'新投递':'简历投递','面试流程中':'面试','简历筛选中':'简历筛选','待部门简历筛选':'部门筛选','笔试中':'笔试'}
    active_label=explicit or aliases.get(status,status)
    if not steps and status:
        steps=[dict(label=active_label,date='',state='ended' if category(status)=='ended' else 'unknown')]
    if site_id=='netease':
        for step in steps:
            if step['label']=='投递成功': step['state']='done'
    active=next((i for i,s in enumerate(steps) if s['label']==active_label),None)
    if active is None and category(status)=='applied':
        active=next((i for i,s in enumerate(steps) if s['label'] in ('投递简历','简历投递','投递','投递成功')),None)
    # Status-only sources still show their exact screening level rather than a generic screen.
    if active is None and category(status) not in ('ended','waiting','other'):
        steps.append(dict(label=active_label,date='',state='unknown'));active=len(steps)-1
    if active is not None and category(status) not in ('ended','waiting'):
        for i,s in enumerate(steps):
            if i==active: s['state']='current'
            elif i>active and s['state']=='unknown': s['state']='future'
            elif i<active and s['date'] and s['state']=='unknown': s['state']='done'
    if category(status)=='ended':
        for s in steps:
            if s['date'] and s['state']=='unknown': s['state']='done'
        if not any(s['state']=='ended' for s in steps):
            steps.append(dict(label='流程结束',date='',state='ended'))
    screen_level=''
    if category(status)=='screening':
        screen_level='用人部门筛选' if re.search('部门',status) else 'HR 初筛' if re.search('HR|初筛',status) else '简历筛选（官网未细分）'
    auxiliary=[]
    if site_id=='ant':
        auxiliary=[s for s in steps if s['label'] in ('笔试','测评')]
        steps=[s for s in steps if s['label'] not in ('笔试','测评')]
    if site_id=='iflytek' and '测评已完成' in block:
        auxiliary=[dict(label='测评',state='done',date='')]
    complete=any(s['label'] in ('Offer','入职','预入职') for s in steps)
    return dict(steps=steps,auxiliary=auxiliary,screen_level=screen_level,pipeline_complete=complete,
                pipeline_note='' if complete else '官网仅公开以上阶段，后续流程未展示')
