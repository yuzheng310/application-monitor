'use strict';
(()=>{
 const get=id=>document.getElementById(id),form=get('interviewForm'),dialog=get('interviewDialog');
 const today=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 let month=today().slice(0,7),selected=null,events=[],token='',editing=null,busy=false,loaded=false,historyOpen=false;
 const label={scheduled:'待参加',completed:'已完成',cancelled:'已取消'};
 const node=(tag,cls,text)=>{const e=document.createElement(tag);e.className=cls||'';if(text)e.textContent=text;return e;};
 const dayString=d=>d.toISOString().slice(0,10);
 const fail=(id,message)=>{get(id).textContent=message;get(id).hidden=!message;};
 const occurs=(e,date)=>e.start.slice(0,10)<=date&&e.end>date+'T00:00';
 async function request(body){
  const r=await fetch('/api/interviews',body?{method:'POST',headers:{'Content-Type':'application/json','X-Query-Token':token},body:JSON.stringify(body)}:{cache:'no-store'});
  const d=await r.json();if(!r.ok)throw new Error(r.status===403?'页面会话已过期，请关闭此窗口后重新打开面试日历。':d.error||'无法读取排期');
  if(d.csrf_token)token=d.csrf_token;return d.events;
 }
 async function load(){try{events=await request();loaded=true;fail('calendarError','');render();}catch(e){fail('calendarError',e.message==='Failed to fetch'?'无法连接本地服务，请重新启动软件后重试。':e.message);}}
 const ended=e=>e.status!=='scheduled'||new Date(e.end+'+08:00').getTime()<=Date.now();
 const range=e=>e.start.slice(11)+' – '+(e.end.slice(0,10)===e.start.slice(0,10)?e.end.slice(11):e.end.replace('T',' '));
 function selectDay(date){selected=date;render();get('agendaTitle').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'center'});}
 function render(){
  const [year,m]=month.split('-').map(Number);get('monthLabel').textContent=`${year} 年 ${m} 月`;
  const first=new Date(Date.UTC(year,m-1,1));first.setUTCDate(first.getUTCDate()-(first.getUTCDay()+6)%7);
  const grid=document.createDocumentFragment();
  for(let i=0;i<42;i++){
   const d=new Date(first);d.setUTCDate(first.getUTCDate()+i);const date=dayString(d);
   const cell=node('div','calendar-day'+(date.slice(0,7)!==month?' outside':'')+(date===today()?' today':'')+(date===selected?' selected':''));
   const pick=node('button','day-number',String(d.getUTCDate()));pick.setAttribute('aria-label',date+' 查看排期');pick.onclick=()=>selectDay(date);cell.append(pick);
   const all=events.filter(e=>occurs(e,date)).sort((a,b)=>Number(ended(a))-Number(ended(b))||a.start.localeCompare(b.start));
   const active=all.filter(e=>!ended(e));
   const items=historyOpen?all:active;
   if(active.length){cell.classList.add('has-interviews');pick.append(node('span','day-count',String(active.length)+' 场'));}
   for(const event of items.slice(0,3)){
    const button=node('button','calendar-event '+event.status+(ended(event)?' past':''));
    button.append(node('strong','event-time',range(event)),node('span','event-company',event.company),node('span','event-role',event.role||'岗位未填写'));
    button.title=event.start.replace('T',' ')+' — '+event.end.replace('T',' ')+' · '+event.company+' · '+event.role;
    button.onclick=()=>selectDay(date);cell.append(button);
   }
   if(items.length>3){const more=node('button','calendar-more',`还有 ${items.length-3} 场，查看详情`);more.onclick=()=>selectDay(date);cell.append(more);}
   if(!historyOpen&&all.length>active.length){const history=node('button','calendar-more',`已结束 ${all.length-active.length} 场`);history.onclick=()=>{historyOpen=true;selectDay(date);};cell.append(history);}
   grid.append(cell);
  }
  get('calendarGrid').replaceChildren(grid);get('agendaTitle').textContent=selected?selected+' 的安排':'近期安排';
  const list=events.filter(e=>!selected||occurs(e,selected)).sort((a,b)=>a.start.localeCompare(b.start));
  const active=list.filter(e=>!ended(e)),past=list.filter(ended).reverse();
  const history=node('details','calendar-history');history.open=historyOpen;
  history.append(node('summary','',`已结束 / 已取消的安排（${past.length}）`));
  history.addEventListener('toggle',()=>{if(history.isConnected&&historyOpen!==history.open){historyOpen=history.open;render();}});
  const agenda=document.createDocumentFragment();
  if(!active.length){agenda.append(node('p','calendar-hint',selected?'这一天暂无待参加的面试。':'暂无待参加的面试。'));}
  for(const e of [...active,...past]){
   const card=node('article','interview-card '+e.status+(ended(e)?' past':' upcoming'));card.append(node('span','interview-date',e.start.slice(0,10)+' · 北京时间'),node('strong','interview-time',range(e)),node('h4','',e.company),node('p','interview-role',e.role||'岗位未填写'),node('p','interview-round',e.round||''),node('span','interview-status',e.status==='scheduled'&&ended(e)?'时间已过 · 待确认结果':label[e.status]));
   if(e.location){let url;try{url=new URL(e.location);}catch{}const place=node(url&&['http:','https:'].includes(url.protocol)?'a':'p','interview-location',e.location);if(place.tagName==='A'){place.href=url.href;place.target='_blank';place.rel='noopener noreferrer';}card.append(place);}
   if(e.notes)card.append(node('p','interview-notes',e.notes));
   if(e.status==='scheduled'&&events.some(x=>x.id!==e.id&&x.status==='scheduled'&&x.start<e.end&&x.end>e.start))card.append(node('p','conflict','与另一场面试时间重叠'));
   const button=node('button','','编辑排期');button.onclick=()=>edit(e);card.append(button);(ended(e)?history:agenda).append(card);
  }
  if(past.length)agenda.append(history);
  get('interviewList').replaceChildren(agenda);
 }
 function edit(event){
  editing=event?.id||null;form.reset();fail('interviewFormError','');get('interviewFormTitle').textContent=editing?'编辑排期':'添加排期';get('deleteInterview').hidden=!editing;get('deleteInterview').textContent='删除排期';
  if(event){for(const [key,value] of Object.entries(event)){const input=form.elements.namedItem(key);if(input)input.value=value;}}
  else{const date=selected||today();form.elements.start.value=date+'T09:00';form.elements.end.value=date+'T10:00';}
  const companies=[...document.querySelectorAll('.company-name h2')].map(e=>e.textContent);get('interviewCompanies').replaceChildren(...companies.map(c=>{const o=document.createElement('option');o.value=c;return o;}));
  dialog.showModal();form.elements.company.focus();
 }
 async function save(body){
  if(busy)return;busy=true;get('saveInterview').disabled=get('deleteInterview').disabled=get('closeInterview').disabled=true;
  try{events=await request(body);dialog.close();fail('interviewFormError','');get('calendarFeedback').textContent=body.action==='delete'?'排期已删除':'排期已保存';if(body.start){month=body.start.slice(0,7);selected=body.start.slice(0,10);}render();}
  catch(e){fail('interviewFormError',e.message==='Failed to fetch'?'无法连接本地服务，内容已保留，请重试。':e.message);}
  finally{busy=false;get('saveInterview').disabled=get('deleteInterview').disabled=get('closeInterview').disabled=false;}
 }
 form.onsubmit=e=>{e.preventDefault();const value=Object.fromEntries(new FormData(form));if(value.end<=value.start){fail('interviewFormError','结束时间必须晚于开始时间。');return;}save({...value,action:'save',...(editing?{id:editing}:{})});};
 get('deleteInterview').onclick=()=>{if(get('deleteInterview').textContent!=='确认删除'){get('deleteInterview').textContent='确认删除';return;}save({action:'delete',id:editing});};
 get('closeInterview').onclick=()=>dialog.close();dialog.addEventListener('cancel',e=>{if(busy)e.preventDefault();});
 get('addInterview').onclick=async()=>{if(!loaded)await load();if(loaded)edit();};
 function shift(n){const [y,m]=month.split('-').map(Number);month=dayString(new Date(Date.UTC(y,m-1+n,1))).slice(0,7);selected=null;render();}
 get('previousMonth').onclick=()=>shift(-1);get('nextMonth').onclick=()=>shift(1);get('calendarToday').onclick=()=>{month=today().slice(0,7);selected=today();render();};get('showUpcoming').onclick=()=>{selected=null;render();};
 function switchView(calendar){get('calendarView').hidden=!calendar;get('applicationsView').hidden=calendar;document.querySelector('.company-directory').hidden=calendar;document.querySelector('main').classList.toggle('calendar-open',calendar);get('calendarTab').setAttribute('aria-pressed',String(calendar));get('applicationsTab').setAttribute('aria-pressed',String(!calendar));if(calendar)load();}
 get('calendarTab').onclick=()=>switchView(true);get('applicationsTab').onclick=()=>switchView(false);
})();
