 'use strict';
const $ = id => document.getElementById(id);
let state=null,requesting=false,timer=null,previousList='';
function timeLabel(value,full=false){if(!value)return '尚未查询';const d=new Date(value);if(Number.isNaN(d.valueOf()))return '时间未知';return new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',...(full?{month:'2-digit',day:'2-digit'}:{}),hour:'2-digit',minute:'2-digit',hour12:false}).format(d);}
function el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text)e.textContent=text;return e;}
function render(){
 const sites=state.sites,p=state.progress;
 const rows=sites.flatMap(s=>(s.applications||[]).filter(a=>!a.internship).map(a=>({...a,site:s,group:s.stale?'other':a.group})));
 $('overview').textContent=sites.length+' 家公司 · '+rows.length+' 条岗位记录';
 const last=sites.map(s=>s.checked_at).filter(Boolean).sort().at(-1);
 $('lastTime').textContent='最近检查 '+timeLabel(last,true);
 $('schedule').textContent=state.automation.enabled?'每天 '+state.times.join(' / ')+' 自动检查':'本地保存 · 无需注册 · 首次使用请先登录招聘网站';
 $('refresh').disabled=state.running||requesting;
 $('refresh').textContent=state.running||requesting?'正在查询…':'↻ 一键查询全部';
 $('runText').textContent=state.running?(p.current?'正在查询 '+p.current:'正在启动查询…'):state.interrupted?'上次查询中断，可重新查询':'已显示最近一次查询结果';
 $('runCount').textContent=state.running?`${p.completed||0} / ${p.total||sites.length}`:'';
 $('runProgress').hidden=!state.running;$('runProgress').max=p.total||sites.length||1;$('runProgress').value=p.completed||0;
 const failed=sites.filter(s=>s.stale).length;
 $('notice').textContent=failed?`${failed} 家读取失败，旧记录已标为“上次结果”，请查看对应提示。`:state.running?'每完成一家，页面会自动更新。':'首次使用：点击各公司官网完成登录，再查询。请保持内置浏览器打开。';
 const key=JSON.stringify(sites);
 if(key===previousList)return;previousList=key;
 const groups=document.createDocumentFragment(),summary=document.createDocumentFragment();
 const counts=[['interview','面试中'],['written','笔试 / 测评'],['screening','筛选中'],['applied','已投递'],['waiting','待开启'],['other','待确认'],['ended','已结束']];
 for(const [id,label] of counts){const stat=el('div',id);stat.append(el('strong','',String(rows.filter(a=>a.group===id).length)),el('span','',label));summary.append(stat);}
 const ordered=[...sites].sort((a,b)=>{
   const rank=s=>Math.min(...rows.filter(r=>r.site.id===s.id).map(r=>counts.findIndex(c=>c[0]===r.group)),99);
   return rank(a)-rank(b);
 });
 for(const s of ordered){
  const apps=rows.filter(a=>a.site.id===s.id);
  const section=el('section','company-block');section.id='company-'+s.id;
  const heading=el('div','company-heading'),name=el('div','company-name');name.append(el('h2','',s.company),el('span','',apps.length+' 个岗位'));
  if(s.status==='内容变化')name.append(el('span','changed','记录有更新'));
  const source=el('a','','官网 ↗');source.href=s.url;source.target='_blank';source.rel='noopener noreferrer';heading.append(name,source);section.append(heading);
  if(s.error)section.append(el('div','error',s.error+(s.text?' · 下方为上次成功读取的进度':'')));
  if(!apps.length)section.append(el('p','empty',s.status==='尚未查询'?'点击官网在内置浏览器登录，然后点击一键查询全部。':'暂未读取到岗位记录，请在官网确认登录状态。'));
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
   section.append(card);
  }
  const bottom=el('div','company-bottom');bottom.append(el('span','stamp',(s.stale?'上次成功 ':'检查于 ')+timeLabel(s.stale?s.last_success:s.checked_at,true)));
  const raw=el('details');raw.append(el('summary','','核对官网原始记录'),el('pre','',s.text||'暂无记录'));if(s.diff)raw.append(el('p','','本次变化'),el('pre','',s.diff));bottom.append(raw);section.append(bottom);groups.append(section);
 }
 $('summary').replaceChildren(summary);$('groups').replaceChildren(groups);
}
async function load() {
  const response=await fetch('/api/status',{cache:'no-store'});
  if(!response.ok)throw new Error('本地服务暂时无法读取记录');
  state=await response.json();render();return state;
}
async function queryAll() {
  if(requesting || state?.running)return {started:false,message:'已有查询正在进行'};
  requesting=true;render();
  try {
    const response=await fetch('/api/refresh',{method:'POST',headers:{'X-Query-Token':state.csrf_token}});
    const data=await response.json();
    if(!response.ok && response.status!==409)throw new Error(data.error||'查询未能启动');
    await load();return data;
  } finally {requesting=false;if(state)render();}
}
function showError(error){$('runText').textContent=error.message||'无法连接本地服务';$('notice').textContent='请确认本地网页服务正在运行，然后刷新页面。';$('refresh').disabled=true;}
$('refresh').addEventListener('click',()=>queryAll().catch(showError));
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
