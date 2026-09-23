"""Local interview appointments; independent from scraped application history."""
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
import file_lock

FIELDS={'company':120,'role':200,'round':80,'start':16,'end':16,'location':500,'notes':2000,'status':20}

def validate(value):
    if not isinstance(value,dict) or set(value)-set(FIELDS)-{'id','action'}:
        raise ValueError('排期字段无效。')
    result={}
    for key,limit in FIELDS.items():
        item=value.get(key,'scheduled' if key=='status' else '')
        if not isinstance(item,str) or len(item)>limit:raise ValueError('排期内容过长或格式不正确。')
        result[key]=item.strip()
    if not result['company']:raise ValueError('请填写公司名称。')
    for key in ('start','end'):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}',result[key]):raise ValueError('请填写开始和结束时间。')
        try:datetime.fromisoformat(result[key])
        except ValueError:raise ValueError('日期或时间无效。')
    if result['end']<=result['start']:raise ValueError('结束时间必须晚于开始时间。')
    if result['status'] not in ('scheduled','completed','cancelled'):raise ValueError('排期状态无效。')
    return result

class Interviews:
    def __init__(self,directory):self.directory=Path(directory)
    def _read(self):
        path=self.directory/'interviews.json'
        if not path.exists():return []
        try:
            value=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(value,list):raise ValueError()
            ids=set()
            for event in value:
                validate(event)
                if not isinstance(event.get('id'),str) or not event['id'] or event['id'] in ids:raise ValueError()
                ids.add(event['id'])
            return value
        except (ValueError,TypeError):raise ValueError('排期文件无法读取，请保留 interviews.json 并检查文件，避免覆盖已有安排。')
    def access(self,change=None):
        self.directory.mkdir(parents=True,exist_ok=True)
        with (self.directory/'interviews.lock').open('a+') as lock:
            try:file_lock.acquire(lock)
            except BlockingIOError:raise ValueError('排期正在保存，请稍后重试。')
            events=self._read()
            if change is not None:
                if not isinstance(change,dict):raise ValueError('排期请求无效。')
                action=change.get('action');identifier=change.get('id')
                index=next((i for i,e in enumerate(events) if e['id']==identifier),None)
                if action=='delete':
                    if index is None:raise ValueError('该排期已不存在，请刷新日历。')
                    events.pop(index)
                elif action=='save':
                    event=validate(change)
                    if identifier and index is None:raise ValueError('该排期已不存在，请刷新日历。')
                    event['id']=identifier or uuid.uuid4().hex
                    if index is None:events.append(event)
                    else:events[index]=event
                else:raise ValueError('不支持的排期操作。')
                events.sort(key=lambda e:e['start'])
                target=self.directory/'interviews.json';temporary=target.with_suffix('.tmp')
                with temporary.open('w',encoding='utf-8') as stream:
                    json.dump(events,stream,ensure_ascii=False,indent=2)
                temporary.replace(target)
            return events
