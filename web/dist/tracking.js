'use strict';
(()=>{
 const get=id=>document.getElementById(id),form=get('trackingForm'),dialog=get('trackingDialog');
 const node=(tag,cls,text)=>{const e=document.createElement(tag);e.className=cls||'';e.textContent=text||'';return e;};
 const labels={waiting:'等待反馈',scheduled:'准备下一轮',offer:'已获 Offer',ended:'已结束'};
 let rows=[],token='',editing=null,busy=false,archiveOpen=false;
 const fail=(id,message)=>{get(id).textContent=message;get(id).hidden=!message;};
 async function request(body){
  const r=await fetch('/api/interview-tracking',body?{method:'POST',headers:{'Content-Type':'application/json','X-Query-Token':token},body:JSON.stringify(body)}:{cache:'no-store'});
  const data=await r.json();if(!r.ok)throw new Error(r.status===403?'页面会话已过期，请关闭编辑窗口后重新进入面试跟进。':data.error||'无法保存跟进');
  if(data.csrf_token)token=data.csrf_token;return data.events;
 }
 async function load(){try{rows=await request();fail('trackingError','');render();return true;}catch(e){fail('trackingError',e.message==='Failed to fetch'?'无法连接本地服务，请重新启动软件。':e.message);return false;}}
 function render(){
  const list=node('div','tracking-grid'),archive=node('details','tracking-archive');archive.open=archiveOpen;archive.ontoggle=()=>{if(archive.isConnected)archiveOpen=archive.open;};
  const finished=rows.filter(r=>r.status==='ended');archive.append(node('summary','',`已结束的跟进（${finished.length}）`));
  if(!rows.some(r=>r.status!=='ended'))list.append(node('p','calendar-hint','暂无正在跟进的岗位，点击“添加跟进”开始记录。'));
  const ordered=[...rows].sort((a,b)=>(b.rounds.at(-1)?.date||'').localeCompare(a.rounds.at(-1)?.date||''));
  for(const row of ordered){
   const card=node('article','tracking-card');card.append(node('span','tracking-status',labels[row.status]),node('h3','',row.company),node('p','tracking-role',row.role||'岗位待确认'));
   const history=node('ol','tracking-history');
   for(const round of row.rounds){const entry=node('li','');entry.append(node('time','',round.date),node('strong','',round.round+' · 已完成'));if(round.notes)entry.append(node('p','',round.notes));history.append(entry);}
   card.append(history);if(!row.rounds.length)card.append(node('p','calendar-hint','尚未记录已完成的轮次'));
   card.append(node('p','tracking-next','下一步：'+(row.next_step||'待补充')));
   if(row.notes)card.append(node('p','tracking-notes',row.notes));
   const editButton=node('button','','编辑跟进 / 记录下一轮');editButton.onclick=()=>edit(row);card.append(editButton);(row.status==='ended'?archive:list).append(card);
  }
  get('trackingList').replaceChildren(list,...(finished.length?[archive]:[]));
 }
 function addRound(value={}){
  const row=node('fieldset','tracking-round');row.append(node('legend','','已完成的面试'));
  for(const [key,title,type,limit] of [['date','日期','date',10],['round','轮次','text',80],['notes','本轮备注','text',1000]]){const label=node('label','',title);const input=node('input');input.type=type;input.dataset.field=key;input.maxLength=limit;input.required=key!=='notes';input.value=value[key]||'';label.append(input);row.append(label);}
  const remove=node('button','','移除此轮');remove.type='button';remove.onclick=()=>row.remove();row.append(remove);get('trackingRounds').append(row);
 }
 function edit(row){editing=row?.id||null;form.reset();get('trackingRounds').replaceChildren();fail('trackingFormError','');
  if(row){for(const key of ['company','role','status','next_step','notes'])form.elements.namedItem(key).value=row[key];for(const round of row.rounds)addRound(round);}
  get('deleteTracking').hidden=!editing;get('deleteTracking').textContent='删除跟进';dialog.showModal();form.elements.company.focus();
 }
 async function save(body){if(busy)return;busy=true;for(const e of form.elements)e.disabled=true;
  try{rows=await request(body);dialog.close();render();get('trackingFeedback').textContent=body.action==='delete'?'跟进已删除':'跟进已保存';}catch(e){fail('trackingFormError',e.message==='Failed to fetch'?'连接失败，填写内容已保留，请重试。':e.message);}finally{busy=false;for(const e of form.elements)e.disabled=false;}
 }
 form.onsubmit=e=>{e.preventDefault();const value=Object.fromEntries(new FormData(form));value.rounds=[...get('trackingRounds').children].map(row=>Object.fromEntries([...row.querySelectorAll('input')].map(input=>[input.dataset.field,input.value])));save({...value,action:'save',...(editing?{id:editing}:{})});};
 get('addTrackingRound').onclick=()=>addRound();get('closeTracking').onclick=()=>dialog.close();dialog.oncancel=e=>{if(busy)e.preventDefault();};
 get('deleteTracking').onclick=()=>{if(get('deleteTracking').textContent!=='确认删除'){get('deleteTracking').textContent='确认删除';return;}save({action:'delete',id:editing});};
 get('addTracking').onclick=async()=>{if(await load())edit();};
 get('trackingTab').onclick=()=>{get('applicationsView').hidden=get('calendarView').hidden=true;get('trackingView').hidden=false;document.querySelector('.company-directory').hidden=true;document.querySelector('main').classList.add('calendar-open');for(const name of ['applicationsTab','calendarTab','trackingTab'])get(name).setAttribute('aria-pressed',String(name==='trackingTab'));load();};
 for(const name of ['applicationsTab','calendarTab'])get(name).addEventListener('click',()=>{get('trackingView').hidden=true;get('trackingTab').setAttribute('aria-pressed','false');});
})();
