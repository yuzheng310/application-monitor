 'use strict';
const $ = id => document.getElementById(id);
let state=null,requesting=false,timer=null,previousList='';
let requestError='';
const expandedEndedCompanies=new Set();
const formatDuration=value=>value>=60?`${Math.floor(value/60)}分${Math.round(value%60)}秒`:`${Math.round(value)}秒`;
function requestMessage(message){requestError=message;$('requestError').textContent=message;$('requestError').hidden=!message;}
function timeLabel(value,full=false){if(!value)return '尚未查询';const d=new Date(value);if(Number.isNaN(d.valueOf()))return '时间未知';return new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',...(full?{month:'2-digit',day:'2-digit'}:{}),hour:'2-digit',minute:'2-digit',hour12:false}).format(d);}
function el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text)e.textContent=text;return e;}

let navigationFrame=null;
function updateCompanyNavigation(){
 navigationFrame=null;
 const sections=[...document.querySelectorAll('.company-block')];
 let current=sections[0];
 for(const section of sections){if(section.getBoundingClientRect().top<=120)current=section;else break;}
 if(window.scrollY>0&&window.scrollY+window.innerHeight>=document.documentElement.scrollHeight-2)current=sections.at(-1);
 for(const link of $('companyNav').children){
  if(current&&link.hash==='#'+current.id)link.setAttribute('aria-current','location');
  else link.removeAttribute('aria-current');
 }
}
function scheduleCompanyNavigation(){if(navigationFrame===null)navigationFrame=requestAnimationFrame(updateCompanyNavigation);}
window.addEventListener('scroll',scheduleCompanyNavigation,{passive:true});
window.addEventListener('resize',scheduleCompanyNavigation);

function changeList(changes){
 const list=el('ul','change-list');
 for(const change of changes){const item=el('li','change-'+change.kind);item.append(el('strong','',change.title),el('span','change-message',change.message));if(change.context)item.append(el('small','',change.context));list.append(item);}
 return list;
}
let previousChangeSummary='';
function renderChanges(){
 const panel=$('changeSummary'),batch=state.batch_changes||[],updates=batch.filter(r=>r.status!=='检查失败'&&r.changes?.length);
 const summaryKey=JSON.stringify([batch,state.running,state.progress.started_at,state.interrupted,state.batch_error]);
 if(summaryKey===previousChangeSummary)return;previousChangeSummary=summaryKey;
 panel.hidden=!batch.length;if(!batch.length)return;
 const content=document.createDocumentFragment();
 content.append(el('h2','',state.running?'本次查询 · 变化摘要':'最近一次查询 · 变化摘要'),el('p','calendar-hint',timeLabel(state.progress.started_at,true)+(state.running?' · 查询进行中，结果逐家更新':'')));
 if(updates.length){content.append(el('p','',`${updates.length} 家公司有岗位变化`));for(const result of updates){const section=el('div','change-company');const link=el('a','',result.company+' ↗');link.href='#company-'+result.id;section.append(link,changeList(result.changes));content.append(section);}}
 else content.append(el('p','',batch.some(r=>r.status!=='检查失败'&&!r.summarized)?'此前的查询尚未生成岗位变化摘要，下次查询起会显示详细变化。':state.running?'暂未发现岗位变化，正在继续查询。':'本次未发现可明确识别的岗位进度变化。'));
 const initial=batch.filter(r=>r.status==='首次记录').length,failed=batch.filter(r=>r.status==='检查失败').length;
 const unclassified=batch.filter(r=>r.status==='内容变化'&&!r.changes?.length).length;
 if(initial)content.append(el('p','calendar-hint',`${initial} 家首次读取，已建立基准，不计为进度更新。`));
 if(failed)content.append(el('p','calendar-hint',`${failed} 家查询失败，无法判断是否有变化，已保留上次结果。`));
 if(unclassified)content.append(el('p','calendar-hint',`${unclassified} 家网页内容有变化，但未识别出明确的岗位变化，可展开官网原始记录核对。`));
 if(state.interrupted||state.batch_error)content.append(el('p','calendar-hint','本次查询未完整结束，以上仅汇总已返回的公司。'));
 panel.replaceChildren(content);
}
function render(){
 const sites=state.sites,p=state.progress;
 const rows=sites.flatMap(s=>(s.applications||[]).filter(a=>!a.internship).map(a=>({...a,site:s,group:s.stale?'other':a.group})));
 $('overview').textContent=sites.length+' 家公司 · '+rows.length+' 条岗位记录';
 const last=sites.map(s=>s.checked_at).filter(Boolean).sort().at(-1);
 $('lastTime').textContent='最近检查 '+timeLabel(last,true);
 $('schedule').textContent=state.automation.enabled?'每天 '+state.times.join(' / ')+' 自动检查':'本地保存 · 无需注册 · 首次使用请先登录招聘网站';
 $('refresh').disabled=state.running||requesting;
 $('workers').disabled=state.running||requesting;
 $('retryFailed').disabled=state.running||requesting;
 $('refresh').textContent=state.running||requesting?'正在查询…':'↻ 一键查询全部';
 $('runText').textContent=state.running?(p.current?'正在查询 '+p.current:'正在启动查询…'):state.interrupted?'上次查询中断，可重新查询':'已显示最近一次查询结果';
 $('runCount').textContent=p.total?`${p.completed||0} / ${p.total}`:'';
 const elapsed=state.running&&p.started_at?(Date.now()-new Date(p.started_at).valueOf())/1000:p.elapsed_seconds;
 $('runStats').textContent=elapsed!=null?`${state.running?'已用时':'上次查询用时'} ${formatDuration(Math.max(0,elapsed))} · 并发 ${p.concurrency||4} 家`:'';
 $('runProgress').hidden=!state.running;$('runProgress').max=p.total||sites.length||1;$('runProgress').value=p.completed||0;
 const failed=sites.filter(s=>s.stale).length;
 $('retryFailed').hidden=!failed;$('retryFailed').textContent=`仅重试失败的 ${failed} 家`;
 if(state.batch_error)requestMessage(state.batch_error.error+'。'+(state.batch_error.suggestion||''));
 $('notice').textContent=failed?`${failed} 家未能读取，请按各公司的提示处理后重试；已有的成功记录会保留。`:state.running?'每完成一家，页面会自动更新。':'首次使用：点击各公司官网完成登录，再查询。请保持内置浏览器打开。';
 renderChanges();
 const key=JSON.stringify([sites,state.running,requesting]);
 if(key===previousList)return;previousList=key;
 const groups=document.createDocumentFragment(),summary=document.createDocumentFragment();
 const counts=[['interview','面试中'],['written','笔试 / 测评'],['screening','筛选中'],['applied','已投递'],['waiting','待开启'],['other','待确认'],['ended','已结束']];
 for(const [id,label] of counts){const stat=el('div',id);stat.append(el('strong','',String(rows.filter(a=>a.group===id).length)),el('span','',label));summary.append(stat);}
 const ordered=[...sites].sort((a,b)=>{
   const rank=s=>Math.min(...rows.filter(r=>r.site.id===s.id).map(r=>counts.findIndex(c=>c[0]===r.group)),99);
   return Number(b.status==='内容变化')-Number(a.status==='内容变化') || rank(a)-rank(b);
 });
 const navigation=document.createDocumentFragment();
 for(const s of ordered){
  const link=el('a','');link.href='#company-'+s.id;link.append(el('span','',s.company));
  if(s.status==='内容变化')link.append(el('span','nav-update','更新'));
  navigation.append(link);
  const apps=rows.filter(a=>a.site.id===s.id);
  const section=el('section','company-block');section.id='company-'+s.id;section.tabIndex=-1;
  const heading=el('div','company-heading'),name=el('div','company-name');name.append(el('h2','',s.company),el('span','',apps.length+' 个岗位'));
  if(s.status==='内容变化')name.append(el('span','changed','记录有更新'));
  const actions=el('div','company-actions');
  if(s.query_state==='running'||s.query_state==='pending')actions.append(el('span','query-badge',s.query_state==='running'?'查询中…':'等待查询'));
  const retry=el('button','site-retry',s.stale?'重试此公司':'查询此公司');retry.disabled=state.running||requesting;retry.dataset.siteId=s.id;retry.addEventListener('click',()=>queryAll([s.id]).catch(showRequestError));actions.append(retry);
  const source=el('a','','官网 ↗');source.href=s.url;source.target='_blank';source.rel='noopener noreferrer';actions.append(source);heading.append(name,actions);section.append(heading);
  if(s.changes?.length&&!s.stale){const updates=el('div','company-changes');updates.append(el('strong','','最近检查的变化 · '+timeLabel(s.checked_at,true)),changeList(s.changes));section.append(updates);}
  if(s.error){const error=el('div','error');error.append(el('strong','',s.error),el('p','',s.suggestion||'打开官网确认登录和页面状态后，重试此公司。'));
   error.append(el('small','',`${s.error_code||'READ_ERROR'} · ${s.text?'保留上次成功结果':'尚无成功记录'}`));section.append(error);}
  if(!apps.length)section.append(el('p','empty',s.status==='尚未查询'?'点击官网在内置浏览器登录，然后点击一键查询全部。':'暂未读取到岗位记录，请在官网确认登录状态。'));
  const endedApps=apps.filter(a=>a.group==='ended');
  const endedSection=el('details','ended-jobs');endedSection.open=expandedEndedCompanies.has(s.id);
  endedSection.append(el('summary','',`已结束的岗位（${endedApps.length}）`));
  endedSection.addEventListener('toggle',()=>{if(endedSection.isConnected){if(endedSection.open)expandedEndedCompanies.add(s.id);else expandedEndedCompanies.delete(s.id);}});
  for(const a of apps){
   const card=el('article','job '+a.group),head=el('div','job-heading');
   head.append(el('h3','',a.title),el('span','status',(s.stale?'上次结果 · ':'')+a.status));card.append(head);
   const meta=el('div','meta');for(const text of [a.preference,a.location,a.applied_at?'投递 '+a.applied_at:'',a.department])if(text)meta.append(el('span','',text));card.append(meta);
   if(a.screen_level)card.append(el('p','screen-level',a.screen_level));
   const track=el('ol','timeline');
   for(const step of a.steps||[]){
    const li=el('li','step '+step.state);li.append(el('span','step-dot',step.state==='done'?'✓':step.state==='ended'?'×':''),el('strong','',step.label));
    const label={done:'已完成',current:'当前阶段',future:'后续阶段',unknown:'完成情况未公开',ended:'在此结束'}[step.state];
    li.append(el('span','step-state',label),el('time','',step.date));track.append(li);
   }
   card.append(track);
   if(a.auxiliary?.length){const aux=el('div','auxiliary');for(const x of a.auxiliary)aux.append(el('span','',x.label+' · '+({done:'已完成',current:'进行中',future:'待进行',unknown:'未公开'}[x.state]||x.state)));card.append(aux);}
   if(a.pipeline_note)card.append(el('p','pipeline-note',a.pipeline_note));
   if(a.note && !a.auxiliary?.length)card.append(el('p','note',a.note));
   (a.group==='ended'?endedSection:section).append(card);
  }
  if(endedApps.length)section.append(endedSection);
  const bottom=el('div','company-bottom');bottom.append(el('span','stamp',(s.stale?'上次成功 ':'检查于 ')+timeLabel(s.stale?s.last_success:s.checked_at,true)));
  const raw=el('details');raw.append(el('summary','','核对官网原始记录'),el('pre','',s.text||'暂无记录'));if(s.diff)raw.append(el('p','','本次变化'),el('pre','',s.diff));bottom.append(raw);section.append(bottom);groups.append(section);
 }
 $('summary').replaceChildren(summary);$('groups').replaceChildren(groups);
 $('companyNav').replaceChildren(navigation);scheduleCompanyNavigation();
}
async function load() {
  const response=await fetch('/api/status',{cache:'no-store'});
  if(!response.ok){let data={};try{data=await response.json();}catch{}throw new Error([data.error||'本地服务暂时无法读取记录',data.suggestion].filter(Boolean).join('。'));}
  const first=state===null;state=await response.json();
  if(first){const value=String(state.concurrency||4);if(![...$('workers').options].some(o=>o.value===value)){const option=el('option','',value+' 家');option.value=value;$('workers').append(option);}$('workers').value=value;}
  render();return state;
}
async function queryAll(siteIds=null) {
  if(requesting || state?.running)return {started:false,message:'已有查询正在进行'};
  requestMessage('');requesting=true;render();
  try {
    const body={workers:Number($('workers').value)};if(siteIds)body.site_ids=siteIds;
    const response=await fetch('/api/refresh',{method:'POST',headers:{'X-Query-Token':state.csrf_token,'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data=await response.json();
    if(!response.ok)throw new Error(response.status===403?'页面会话已过期，请刷新网页后重试。':data.error||data.message||'查询未能启动');
    await load();return data;
  } finally {requesting=false;if(state)render();}
}
function showRequestError(error){requestMessage(error.message==='Failed to fetch'?'无法连接本地服务，请重新双击启动软件后重试。':error.message||'查询未能启动，请重试。');}
function showError(error){$('runText').textContent='无法读取本地服务状态';$('notice').textContent=error.message==='Failed to fetch'?'服务可能已退出，请重新双击启动软件。页面会自动尝试恢复连接。':error.message;$('refresh').disabled=true;}
$('refresh').addEventListener('click',()=>queryAll().catch(showRequestError));
$('retryFailed').addEventListener('click',()=>queryAll(state.sites.filter(s=>s.stale).map(s=>s.id)).catch(showRequestError));
async function poll(){try{await load();}catch(error){showError(error);}timer=setTimeout(poll,state?.running?1800:8000);}
poll();
if(document.modelContext?.registerTool){
  const lifecycle=new AbortController();
  const validate=input=>{if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).length)throw new Error('此操作无需参数');};
  const tools=[{name:'get_application_status',title:'读取投递检查状态',description:'读取各家公司最新检查状态及查询进度。',inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:true,untrustedContentHint:true},execute:async input=>{validate(input);const s=await load();return {running:s.running,progress:s.progress,companies:s.sites.map(x=>({company:x.company,status:x.status,checked_at:x.checked_at,applications:x.applications}))};}},
  {name:'start_application_check',title:'开始查询全部公司',description:'调用内置浏览器登录状态，开始检查全部公司的投递进度。只查询，不提交或修改申请。',inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:false,untrustedContentHint:true},execute:async input=>{validate(input);if(!state)await load();return await queryAll();}}];
  for(const tool of tools)Promise.resolve(document.modelContext.registerTool(tool,{signal:lifecycle.signal})).catch(()=>{});
  window.addEventListener('pagehide',()=>{lifecycle.abort();clearTimeout(timer);},{once:true});
}
