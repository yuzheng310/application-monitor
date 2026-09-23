"""Conservative, human-readable differences between parsed application records."""
from collections import defaultdict
from records import parse_records


def stage(record):
    current = [s['label'] for s in record.get('steps', []) if s.get('state') in ('current', 'ended')]
    return ' / '.join(current) or record.get('status') or '待确认'


def describe_changes(site_id, before, after):
    if before is None:
        return []  # Establish a baseline, not a progress notification.
    old = [r for r in parse_records(site_id, before) if not r.get('internship')]
    new = [r for r in parse_records(site_id, after) if not r.get('internship')]
    groups = defaultdict(lambda: [[], []])
    for index, records in enumerate((old, new)):
        for record in records:
            groups[record['title']][index].append(record)
    changes = []
    def emit(kind, record, message):
        context = ' · '.join(filter(None, [record.get('department'), record.get('preference'), record.get('applied_at')]))
        changes.append(dict(kind=kind, title=record['title'], context=context, message=message))
    def compare(a, b):
        if a.get('status') != b.get('status'):
            emit('status', b, f"状态：{a.get('status') or '待确认'} → {b.get('status') or '待确认'}")
        elif stage(a) != stage(b):
            emit('stage', b, f'当前阶段：{stage(a)} → {stage(b)}')
        else:
            done_a = {s['label'] for s in a.get('steps', []) if s.get('state') == 'done'}
            done_b = {s['label'] for s in b.get('steps', []) if s.get('state') == 'done'}
            if done_b - done_a:
                emit('stage', b, '官网新增已完成标记：' + '、'.join(sorted(done_b - done_a)))
        for key, label in [('location', '地点'), ('department', '部门'), ('preference', '志愿'), ('applied_at', '投递日期')]:
            if a.get(key, '') != b.get(key, ''):
                emit('details', b, f"{label}：{a.get(key) or '未显示'} → {b.get(key) or '未显示'}")
    for title, (left, right) in groups.items():
        if len(left) == len(right) == 1:
            compare(left[0], right[0])
            continue
        if not left:
            for record in right:
                emit('added', record, '本次新读取到岗位，当前状态：' + (record.get('status') or '待确认'))
            continue
        if not right:
            for record in left:
                emit('missing', record, '本次页面未显示此岗位，请核对官网；不代表被拒绝或流程结束')
            continue
        # Same-title roles can refer to distinct applications; never pair by row order.
        key = lambda r: tuple(r.get(k, '') for k in ('department', 'preference', 'applied_at', 'location'))
        before_groups, after_groups = defaultdict(list), defaultdict(list)
        for r in left: before_groups[key(r)].append(r)
        for r in right: after_groups[key(r)].append(r)
        ambiguous = False
        for identity in before_groups.keys() | after_groups.keys():
            a, b = before_groups[identity], after_groups[identity]
            if len(a) == len(b) == 1:
                compare(a[0], b[0])
            elif a != b:
                ambiguous = True
        if ambiguous:
            emit('uncertain', right[0], '同名岗位记录有变化，无法可靠对应前后申请，请展开官网原始记录核对')
    return changes
