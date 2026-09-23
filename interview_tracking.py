"""Manual interview follow-up records, separate from website status and calendar."""
import json
import hashlib
import re
import uuid
from datetime import date
from pathlib import Path
import file_lock


def validate(value):
    if not isinstance(value, dict) or set(value) - {'action', 'id', 'company', 'role', 'status', 'next_step', 'notes', 'rounds', 'source_key'}:
        raise ValueError('跟进字段无效。')
    result = {}
    for key, limit in {'company': 120, 'role': 200, 'status': 20, 'next_step': 500, 'notes': 2000}.items():
        item = value.get(key, 'waiting' if key == 'status' else '')
        if not isinstance(item, str) or len(item) > limit:
            raise ValueError('跟进内容过长或格式不正确。')
        result[key] = item.strip()
    if not result['company']:
        raise ValueError('请填写公司。')
    if result['status'] not in ('interviewing', 'waiting', 'scheduled', 'offer', 'ended'):
        raise ValueError('跟进状态无效。')
    if 'source_key' in value:
        if not isinstance(value['source_key'], str) or not re.fullmatch(r'[0-9a-f]{64}', value['source_key']):
            raise ValueError('官网关联编号无效。')
        result['source_key'] = value['source_key']
    rounds = value.get('rounds', [])
    if not isinstance(rounds, list) or len(rounds) > 50:
        raise ValueError('面试轮次格式无效或超过 50 条。')
    result['rounds'] = []
    for item in rounds:
        if not isinstance(item, dict) or set(item) != {'date', 'round', 'notes'}:
            raise ValueError('轮次字段无效。')
        for key, limit in {'date': 10, 'round': 80, 'notes': 1000}.items():
            if not isinstance(item[key], str) or len(item[key]) > limit:
                raise ValueError('轮次内容过长或格式不正确。')
        if not item['round'].strip() or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', item['date']):
            raise ValueError('请填写面试日期和轮次。')
        try:
            date.fromisoformat(item['date'])
        except ValueError:
            raise ValueError('面试日期无效。')
        result['rounds'].append({key: text.strip() for key, text in item.items()})
    result['rounds'].sort(key=lambda item: item['date'])
    return result


class InterviewTracking:
    def __init__(self, directory):
        self.directory = Path(directory)

    def sync_sites(self, sites):
        candidates = []
        for site in sites:
            if site.get('stale') or site.get('status') in ('检查失败', '尚未查询'):
                continue
            for app in site.get('applications', []):
                if app.get('group') != 'interview' or app.get('internship') or not app.get('title'):
                    continue
                identity = [site['id'], app['title'], app.get('department', ''), app.get('preference', ''), app.get('applied_at', '')]
                source_key = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
                context = ' · '.join(filter(None, [app.get('department'), app.get('preference'), app.get('applied_at')]))
                candidates.append(dict(company=site['company'], role=app['title'], status='interviewing', rounds=[],
                                       next_step='请手动更新当前面试轮次与下一步安排',
                                       notes='从官网面试中岗位自动加入。'+context, source_key=source_key))
        return self.access(_candidates=candidates)

    def access(self, change=None, *, _candidates=None):
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / 'interview-tracking.json'
        with (self.directory / 'interview-tracking.lock').open('a+') as lock:
            try:
                file_lock.acquire(lock)
            except BlockingIOError:
                raise ValueError('跟进正在保存，请稍后重试。')
            try:
                rows = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
                if not isinstance(rows, list):
                    raise ValueError()
                ids = set()
                for row in rows:
                    validate(row)
                    identifier = row.get('id')
                    if not isinstance(identifier, str) or not identifier or identifier in ids:
                        raise ValueError()
                    ids.add(identifier)
            except (ValueError, TypeError):
                raise ValueError('跟进文件无法读取，请保留 interview-tracking.json 并检查文件。')
            changed = False
            if _candidates is not None:
                company_key = lambda name: re.split(r'[（(]', name)[0].strip().casefold()
                for candidate in _candidates:
                    candidate = validate(candidate)
                    if any(row.get('source_key') == candidate['source_key'] for row in rows):
                        continue
                    matches = [row for row in rows if not row.get('source_key') and
                               company_key(row['company']) == company_key(candidate['company']) and row['role'] == candidate['role']]
                    if matches:
                        # Associate existing manual history; never replace its content or rounds.
                        if len(matches) == 1:
                            matches[0]['source_key'] = candidate['source_key']
                            changed = True
                        continue
                    rows.append(dict(candidate, id=uuid.uuid4().hex))
                    changed = True
            if change is not None:
                if not isinstance(change, dict):
                    raise ValueError('跟进请求无效。')
                identifier = change.get('id')
                if identifier is not None and (not isinstance(identifier, str) or not identifier):
                    raise ValueError('跟进编号无效。')
                index = next((i for i, row in enumerate(rows) if row['id'] == identifier), None)
                if identifier is not None and index is None:
                    raise ValueError('该跟进已不存在，请重新打开跟进页。')
                if change.get('action') == 'save':
                    row = dict(validate(change), id=identifier or uuid.uuid4().hex)
                    if index is not None and rows[index].get('source_key'):
                        row['source_key'] = rows[index]['source_key']
                    if index is None:
                        rows.append(row)
                    else:
                        rows[index] = row
                elif change.get('action') == 'delete' and index is not None:
                    rows.pop(index)
                else:
                    raise ValueError('不支持的跟进操作。')
                changed = True
            if changed:
                temporary = path.with_suffix('.tmp')
                temporary.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
                temporary.replace(path)
            return rows
