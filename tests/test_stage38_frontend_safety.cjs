/* Permanent regressions for the independent 21 + 4 audit scenarios.
 * Real app control flow; deterministic DOM/fetch/timers, never author data or
 * a listening service. Original external audit files are not loaded/modified. */
'use strict';
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),source=fs.readFileSync(path.join(root,'frontend/app.js'),'utf8').replace(/\r\n/g,'\n');
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const tick=async()=>{for(let i=0;i<16;i++)await Promise.resolve();};
const budget=()=>({budget_cny:5,estimated_spent_cny:1.8,reserved_cny:0,remaining_cny:3.2});
const job=(status='completed')=>({kind:'report-v2',run_id:'run-A',status,stage:status==='completed'?'adopt':'draft',document_id:'current-report'});
function canonical(project='A',documentId='current-report'){
 const result={document_id:documentId,status:'completed',analysis_contract_version:'model.1',source_version_id:'v1',source_revision:1,source_hash:'h1',scope_start:1,scope_end:1,scope_hash:'scope1',report:{report_version:'1.0',title:'Synthetic report',characters:[],events:[],evidence:[],chapter_numbers:[1]}};
 return {project_id:project,title:`Synthetic ${project}`,effective_status:'completed',run_status:'completed',source_match:true,source:{version_id:'v1',revision:1,hash:'h1',match:true,chapter_count:1,total_word_count:100},progress:{percent:100,current_stage:'completed'},actions:{retry:false,rebuild:true},result,active_run:{...result,run_status:'completed'},focus_document_id:documentId,history:[],volumes:[]};
}
function environment(){
 const nodes=new Map(),timers=new Map(),calls=[],renders=[];let serial=0,location=new URL('http://safety.invalid/independent/A?view=deconstruction'),responder;
 class Node{
  constructor(id=''){Object.assign(this,{id,textContent:'',innerHTML:'',value:'',dataset:{},disabled:false,open:false,hidden:false,events:{},attrs:{},classList:{toggle(){},add(){},remove(){},contains(){return false;}}});}
  setAttribute(k,v){this.attrs[k]=v;} getAttribute(k){return this.attrs[k];} removeAttribute(k){delete this.attrs[k];}
  addEventListener(k,f){(this.events[k]||=[]).push(f);} dispatch(k,e={}){for(const f of this.events[k]||[])f(e);}
  close(){this.open=false;this.dispatch('close');} showModal(){this.open=true;}
  focus(){} append(){} appendChild(){} remove(){} scrollIntoView(){} setSelectionRange(a,b){this.selectionStart=a;this.selectionEnd=b;}
  querySelector(s){return get(this.id+' '+s);} querySelectorAll(){return [];} closest(){return this;} insertAdjacentHTML(p,s){this.innerHTML+=s;}
 }
 const get=s=>{if(!nodes.has(s))nodes.set(s,new Node(s));return nodes.get(s);};
 const document={querySelector:get,querySelectorAll:()=>[],getElementById:id=>get('#'+id),body:get('body'),createElement:()=>new Node(),activeElement:get('active'),addEventListener(){},visibilityState:'visible'};
 const history={state:{},pushState(s,t,u){this.state=s;location=new URL(String(u),location);},replaceState(s,t,u){this.state=s;location=new URL(String(u),location);}};
 const context={URL,URLSearchParams,console,document,history,WeakMap,Map,Set,Promise,CSS:{escape:String},setTimeout(f,ms){const id=++serial;timers.set(id,{f,ms});return id;},clearTimeout(id){timers.delete(id);},requestAnimationFrame:f=>f(),scrollTo(){},matchMedia:()=>({matches:true}),addEventListener(){},fetch:async(url,options={})=>{calls.push({url,method:options.method||'GET',body:options.body});const data=await responder(url,options);return data?.__response||{ok:true,status:200,json:async()=>data};}};
 Object.defineProperty(context,'location',{get:()=>location});context.window=context;
 const hook='  start();\n})();';assert.equal(source.split(hook).length,2);
 vm.runInNewContext(source.replace(hook,`window.safety={state,elements,ensureReportTask,pollBook,refreshModelBudget,openReportConfirmation,confirmReport,pauseReport,reportStartBlock,loadIndependentWorkspace,loadDeconstructionWorkspace,selectDeconstructionVolume,normalizeDeconstructionResponse,navigate,setActiveScreen,logout,submitEmail,handleEditorInput,flushPendingSave,selectEditorChapter,bindEvents,renderEditorWorkspace};renderDeconstructionPage=data=>{state.deconstructionWorkspace=data;state.deconstructionProjectId=data.projectId;ensureReportTask(data.projectId);window.onRender(data);};\n})();`),context);
 const a=context.safety;context.onRender=d=>renders.push({project:d.projectId,document:d.focusDocumentId});
 const base=async url=>{
  if(url.endsWith('/model-budget'))return {budget:budget(),model_available:true};
  if(url.endsWith('/book'))return {job:null};
  if(url.includes('/deconstruction'))return canonical(url.includes('/projects/B/')?'B':'A',new URL(url,location).searchParams.get('document_id')||'current-report');
  if(url==='/api/notifications')return {notifications:[],unread_count:0};
  if(url==='/api/auth/logout')return {};
  throw Error('Unexpected synthetic request: '+url);
 };responder=base;
 const ready=(project='A',documentId='history-report')=>{
  Object.assign(a.state,{account:{email:'audit.reader@example.test'},screen:'deconstruction',deconstructionProjectId:project,deconstructionWorkspace:a.normalizeDeconstructionResponse(canonical(project,documentId))});
  Object.assign(a.ensureReportTask(project),{loaded:true,available:true,budget:budget()});
  location=new URL(`http://safety.invalid/independent/${project}?view=deconstruction&volume=${documentId}&section=characters&character=person-old`);
 };
 return {a,context,get,calls,renders,timers,ready,base,setResponder:f=>{responder=f;},setLocation:s=>{location=new URL(s,location);},getLocation:()=>location};
}
const review=e=>{e.a.state.reportConfirmation={projectId:'A',source:{...e.a.state.deconstructionWorkspace.source}};e.get('#reportConfirmDialog').showModal();};
const chapter=(prefix,n)=>({chapter_id:prefix+n,chapter_number:n,title:`${prefix}合成章${n}`,content:`${prefix}合成正文${n}😀\r\n`,status:'ready',server_revision:1});
const workspace=(id,chapters)=>({project_id:id,title:`合成作品${id}`,initialized:true,mode:'independent',archive:{},tasks:[],active_version:{version_id:`v${id}`,chapters}});
function seedEditor(){
 const e=environment(),old=workspace('A',Array.from({length:6},(_,i)=>chapter('a',i+1)));
 e.setLocation('/independent/A?chapter=a1');Object.assign(e.a.state,{screen:'independent',account:{email:'reader@example.test'},workspace:old,editorProjectId:'A',activeChapterId:'a1',editorBuffer:old.active_version.chapters[0].content,editorTitleBuffer:old.active_version.chapters[0].title,editorRevision:1});
 e.a.renderEditorWorkspace();assert.equal((e.a.elements.chapterList.innerHTML.match(/class="chapter-directory-entry"/g)||[]).length,6);return e;
}
const cases=[];
async function test(name,run){await run();cases.push(name);}
(async()=>{
 await test('UI-1 explicit historical deep link survives completed discovery',async()=>{
  const e=environment();e.ready();e.setResponder(u=>u.endsWith('/book')?{job:job()}:e.base(u));await e.a.pollBook('A');
  assert.equal(e.a.state.deconstructionWorkspace.focusDocumentId,'history-report');assert.equal(e.getLocation().searchParams.get('volume'),'history-report');assert.ok(!e.calls.some(c=>c.url==='/api/independent/projects/A/deconstruction'));
 });
 await test('UI-1 selection while book GET pending survives completed discovery',async()=>{
  const e=environment();e.ready('A','current-report');const gate=deferred();e.setResponder(u=>u.endsWith('/book')?gate.promise:e.base(u));
  const poll=e.a.pollBook('A');await tick();await e.a.selectDeconstructionVolume('history-report');gate.resolve({job:job()});await poll;
  assert.equal(e.a.state.deconstructionWorkspace.focusDocumentId,'history-report');assert.ok(e.renders.every(r=>r.document==='history-report'));
 });
 await test('late A job response after switching B is ignored',async()=>{
  const e=environment();e.ready();const gate=deferred();e.setResponder(u=>u.endsWith('/book')?gate.promise:e.base(u));const poll=e.a.pollBook('A');await tick();await e.a.loadDeconstructionWorkspace('B',{silent:true,documentId:'B-history'});gate.resolve({job:job()});await poll;assert.equal(e.a.state.deconstructionWorkspace.focusDocumentId,'B-history');
 });
 await test('late A workspace refresh after switching B is ignored',async()=>{
  const e=environment();e.ready('A','current-report');e.setLocation('/independent/A?view=deconstruction');const gate=deferred();e.setResponder(u=>u.endsWith('/book')?{job:job()}:u==='/api/independent/projects/A/deconstruction'?gate.promise:e.base(u));
  const poll=e.a.pollBook('A');await tick();assert.ok(e.calls.some(c=>c.url==='/api/independent/projects/A/deconstruction'));await e.a.loadDeconstructionWorkspace('B',{silent:true,documentId:'B-history'});gate.resolve(canonical());await poll;assert.equal(e.renders.at(-1).project,'B');
 });
 await test('completed read failure can recover without explicit selection',async()=>{
  const e=environment();e.ready('A','current-report');e.setLocation('/independent/A?view=deconstruction');let fail=true;e.setResponder(u=>u.endsWith('/book')?{job:job()}:u==='/api/independent/projects/A/deconstruction'&&fail?Promise.reject(Error('synthetic offline')):e.base(u));
  await e.a.pollBook('A');assert.equal(e.a.state.reportTask.published,'');assert.ok(e.a.state.reportTask.pollError);fail=false;await e.a.pollBook('A');assert.equal(e.a.state.deconstructionWorkspace.focusDocumentId,'current-report');
 });
 await test('UI-2 closing fee dialog during validation sends zero POST',async()=>{
  const e=environment();e.ready();e.a.bindEvents();review(e);const gate=deferred();e.setResponder(u=>u.endsWith('/book')?gate.promise:e.base(u));const sending=e.a.confirmReport();await tick();e.get('#reportConfirmDialog').close();assert.equal(e.a.state.reportConfirmation,null);gate.resolve({job:null});await sending;assert.equal(e.calls.filter(c=>c.method==='POST').length,0);
 });
 await test('parallel confirm submits once with exactly reviewed CAS',async()=>{
  const e=environment();e.ready();review(e);e.setResponder(u=>u.endsWith('/start-report')?{}:e.base(u));await Promise.all([e.a.confirmReport(),e.a.confirmReport()]);const posts=e.calls.filter(c=>c.method==='POST');assert.equal(posts.length,1);assert.deepEqual(JSON.parse(posts[0].body),{expected_source_version_id:'v1',expected_source_revision:1,expected_source_hash:'h1'});
 });
 await test('UI-3 late A failure cannot cancel B polling owner',async()=>{
  const e=environment();e.ready();e.a.bindEvents();review(e);const gate=deferred();e.setResponder(u=>u.endsWith('/start-report')?gate.promise:u==='/api/independent/projects/B/deconstruction/book'?{job:{...job('running'),run_id:'run-B'}}:e.base(u));
  const sending=e.a.confirmReport();await tick();assert.ok(e.calls.some(c=>c.method==='POST'));e.get('#reportConfirmDialog').close();await e.a.loadDeconstructionWorkspace('B');await tick();const timer=e.a.state.bookPollTimer;assert.ok(e.timers.has(timer));gate.reject(Error('synthetic late failure'));await sending;
  assert.ok(e.timers.has(timer));assert.equal(e.a.state.bookPollTimer,timer);assert.equal(e.a.state.reportTask.projectId,'B');assert.equal(e.a.state.reportTask.job.status,'running');
  const before=e.calls.length;await e.a.pollBook('A');assert.equal(e.calls.length,before);assert.ok(e.timers.has(timer));
  e.setResponder(u=>u==='/api/independent/projects/B/deconstruction/book'?{job:{...job(),run_id:'run-B'}}:e.base(u));await e.timers.get(timer).f();await tick();assert.equal(e.a.state.reportTask.job.status,'completed');
 });
 await test('source changed after review retains reviewed CAS for server rejection',async()=>{
  const e=environment();e.ready();review(e);e.a.state.deconstructionWorkspace.source.versionId='v2';e.a.state.deconstructionWorkspace.source.contentHash='h2';e.setResponder(u=>u.endsWith('/start-report')?{}:e.base(u));await e.a.confirmReport();const post=e.calls.find(c=>c.method==='POST');assert.equal(JSON.parse(post.body).expected_source_version_id,'v1');assert.equal(JSON.parse(post.body).expected_source_hash,'h1');
 });
 await test('unknown provider result blocks paid start',async()=>{
  const e=environment();e.ready();e.a.state.reportTask.job={...job('paused'),error_code:'report_request_unknown'};assert.match(e.a.reportStartBlock(e.a.state.deconstructionWorkspace,e.a.state.reportTask),/尚待确认/);await e.a.openReportConfirmation();assert.equal(e.calls.length,0);
 });
 await test('logout ignores old job completion',async()=>{
  const e=environment();e.ready();const gate=deferred();e.setResponder(u=>u.endsWith('/book')?gate.promise:e.base(u));const poll=e.a.pollBook('A');await tick();await e.a.logout();gate.resolve({job:job()});await poll;assert.equal(e.a.state.screen,'login');assert.equal(e.a.state.account,null);assert.equal(e.renders.length,0);
 });
 await test('disabled runtime cannot POST',async()=>{
  const e=environment();e.ready();review(e);e.setResponder(u=>u.endsWith('/model-budget')?{budget:budget(),model_available:false}:e.base(u));await e.a.confirmReport();assert.equal(e.calls.filter(c=>c.method==='POST').length,0);
 });
 await test('409 invalidates review and never retries POST automatically',async()=>{
  const e=environment();e.ready();review(e);e.setResponder(u=>u.endsWith('/start-report')?{__response:{ok:false,status:409,json:async()=>({detail:{code:'source_conflict',message:'synthetic CAS rejection'}})}}:e.base(u));await e.a.confirmReport();await e.a.confirmReport();assert.equal(e.calls.filter(c=>c.method==='POST').length,1);assert.equal(e.a.state.reportConfirmation,null);
 });
 await test('title-only edits retain CRLF and emoji body',async()=>{
  const e=seedEditor(),body=e.a.state.editorBuffer;e.a.elements.chapterEditor.value=body.replace(/\r\n/g,'\n');e.a.elements.chapterTitleInput.value='新题';e.a.handleEditorInput({target:e.a.elements.chapterTitleInput});assert.equal(e.a.state.editorBuffer,body);assert.equal(e.a.state.editorTitleBuffer,'新题');
 });
 await test('failed save blocks navigation without losing local buffer',async()=>{
  const e=seedEditor();Object.assign(e.a.state,{editorDirty:true,editorSaveFailed:true,editorBuffer:'未保存😀\r\n'});const before=e.getLocation().href;assert.equal(await e.a.navigate('/independent/A?view=deconstruction'),false);assert.equal(e.getLocation().href,before);assert.equal(e.a.state.editorBuffer,'未保存😀\r\n');
 });
 await test('observed completed token does not repeatedly refresh selection',async()=>{
  const e=environment();e.ready();const done=job();e.a.state.reportTask.published=`${done.run_id}:${done.status}:${done.stage}:${done.document_id}`;e.setResponder(u=>u.endsWith('/book')?{job:done}:e.base(u));await e.a.selectDeconstructionVolume('history-report');const before=e.calls.length;await e.a.pollBook('A');assert.equal(e.a.state.deconstructionWorkspace.focusDocumentId,'history-report');assert.ok(e.calls.slice(before).every(c=>!c.url.includes('document_id')));
 });
 await test('paused resume still opens fee review before POST',async()=>{
  const e=environment();e.ready();e.a.state.reportTask.job=job('paused');e.setResponder(u=>u.endsWith('/book')?{job:job('paused')}:e.base(u));await e.a.openReportConfirmation();assert.equal(e.get('#reportConfirmDialog').open,true);assert.ok(e.a.state.reportConfirmation);assert.equal(e.calls.filter(c=>c.method==='POST').length,0);
 });
 await test('leaving while opening fee review cannot reopen it',async()=>{
  const e=environment();e.ready();const gate=deferred();e.setResponder(u=>u==='/api/independent/projects/A/deconstruction'?gate.promise:e.base(u));const opening=e.a.openReportConfirmation();await tick();e.a.setActiveScreen('library');gate.resolve(canonical());await opening;assert.equal(e.get('#reportConfirmDialog').open,false);assert.equal(e.a.state.reportConfirmation,undefined);
 });
 await test('switch account to B ignores A late response',async()=>{
  const e=environment();e.ready();const gate=deferred();e.setResponder(u=>u==='/api/independent/projects/A/deconstruction/book'?gate.promise:e.base(u));const poll=e.a.pollBook('A');await tick();await e.a.logout();
  e.setResponder(u=>u==='/api/auth/email'?{account:{email:'beta@example.test'}}:u.startsWith('/api/library')?{account:{email:'beta@example.test'},projects:[]}:e.base(u));e.a.elements.emailInput.value='beta@example.test';await e.a.submitEmail({preventDefault(){}});await tick();await e.a.loadDeconstructionWorkspace('B',{silent:true,documentId:'B-history'});gate.resolve({job:job()});await poll;assert.equal(e.a.state.account.email,'beta@example.test');assert.equal(e.a.state.deconstructionProjectId,'B');
 });
 await test('chapter switch waits for exact CAS body save',async()=>{
  const e=seedEditor(),body='修改后的正文😀\r\n';Object.assign(e.a.state,{editorBuffer:body,editorTitleBuffer:'新题',editorDirty:true});
  e.setResponder((u,o)=>{if(o?.method==='PUT'){const sent=JSON.parse(o.body);assert.equal(sent.content,body);assert.equal(sent.expected_revision,1);const saved={...e.a.state.workspace.active_version.chapters[0],title:sent.title,content:sent.content,server_revision:2},next=structuredClone(e.a.state.workspace);next.active_version.chapters[0]=saved;return {workspace:next,chapter:saved};}return e.base(u);});
  await e.a.selectEditorChapter('a2');assert.equal(e.a.state.workspace.active_version.chapters[0].content,body);assert.equal(e.a.state.editorBuffer,chapter('a',2).content);
 });
 await test('actual reader rejects mismatched source but accepts matching history URL',async()=>{
  const e=environment();e.ready();for(const name of ['report-browser.js','workspace-reader.js'])vm.runInNewContext(fs.readFileSync(path.join(root,'frontend',name),'utf8'),e.context);
  const reader=e.get('reader'),report={characters:[],events:[],relations:[]},options={projectId:'A',section:'characters',evidence:()=>'',claim:()=>''};
  e.context.XumaiWorkspaceReader.mountModel(reader,report,{...options,documentId:'current-report'});assert.ok(reader.innerHTML.includes('此链接缺少报告来源'));
  e.context.XumaiWorkspaceReader.mountModel(reader,report,{...options,documentId:'history-report'});assert.ok(!reader.innerHTML.includes('此链接缺少报告来源'));assert.equal(e.calls.length,0);
 });
 await test('UI-4 six-chapter A to uninitialized B clears directory and all buffers',async()=>{
  const e=seedEditor();e.setLocation('/independent/B');e.setResponder(u=>u==='/api/independent/projects/B'?{project_id:'B',title:'合成空书B',initialized:false,mode:'independent',archive:{},tasks:[],active_version:null}:e.base(u));await e.a.loadIndependentWorkspace('B');
  assert.equal(e.a.elements.editorProjectTitle.textContent,'合成空书B');assert.equal(e.a.elements.editorWordCount.textContent,'0 字');assert.equal(e.a.elements.chapterList.innerHTML,'');assert.equal(e.a.elements.chapterEditor.value,'');assert.equal(e.a.state.activeChapterId,null);
 });
 await test('UI-4 pending new workspace has no old scope and disabled editing',async()=>{
  const e=seedEditor(),gate=deferred();e.setResponder(u=>u==='/api/independent/projects/B'?gate.promise:e.base(u));const loading=e.a.loadIndependentWorkspace('B');await tick();
  assert.equal(e.a.state.workspace,null);assert.equal(e.a.state.activeArchive,null);assert.equal(e.a.elements.chapterList.innerHTML,'');assert.equal(e.a.elements.chapterEditor.value,'');assert.equal(e.a.elements.chapterEditor.disabled,true);assert.equal(e.a.elements.chapterTitleInput.disabled,true);assert.equal(e.get('[data-action="save-editor"]').disabled,true);
  gate.resolve(workspace('B',[chapter('b',1)]));await loading;assert.equal(e.a.elements.chapterEditor.disabled,false);assert.equal(e.a.elements.chapterEditor.value,chapter('b',1).content);
 });
 await test('UI-4 failed B cannot reopen A through stale chapter selection',async()=>{
  const e=seedEditor();e.setLocation('/independent/B');e.setResponder(u=>u==='/api/independent/projects/B'?Promise.reject(Error('synthetic read failure')):e.base(u));await e.a.loadIndependentWorkspace('B');await e.a.selectEditorChapter('a2');
  assert.equal(e.a.state.workspace,null);assert.equal(e.a.state.activeChapterId,null);assert.equal(e.a.elements.editorProjectTitle.textContent,'读取失败');assert.equal(e.a.elements.chapterList.innerHTML,'');assert.equal(e.a.elements.chapterEditor.value,'');assert.equal(e.calls.filter(c=>c.method==='PUT').length,0);
 });
 await test('UI-5 input is locked until B scope resolves; old buffer cannot become dirty',async()=>{
  const e=seedEditor(),gate=deferred(),previous=e.a.state.workspace,original=JSON.stringify(previous);e.setResponder(u=>u==='/api/independent/projects/B'?gate.promise:e.base(u));const loading=e.a.loadIndependentWorkspace('B');await tick();
  assert.equal(e.a.elements.chapterEditor.disabled,true);e.a.elements.chapterEditor.value+='模拟不应可输入的新句😀';e.a.handleEditorInput({target:e.a.elements.chapterEditor});assert.equal(e.a.state.editorDirty,false);assert.equal(e.a.state.editorBuffer,'');
  gate.resolve(workspace('B',[chapter('b',1)]));await loading;assert.equal(e.a.state.editorBuffer,chapter('b',1).content);assert.equal(e.a.state.workspace.project_id,'B');assert.equal(JSON.stringify(previous),original);assert.equal(e.calls.filter(c=>c.method==='PUT').length,0);
 });
 await test('closing after POST does not stop current-book background observation',async()=>{
  const e=environment();e.ready();e.a.bindEvents();review(e);const gate=deferred();let started=false;
  e.setResponder(u=>u.endsWith('/start-report')?gate.promise:u.endsWith('/book')?{job:started?job('running'):null}:e.base(u));
  const sending=e.a.confirmReport();await tick();assert.equal(e.calls.filter(c=>c.method==='POST').length,1);e.get('#reportConfirmDialog').close();started=true;gate.resolve({job:job('running')});await sending;
  assert.equal(e.get('#reportConfirmDialog').open,false);assert.equal(e.a.state.reportTask.job.status,'running');assert.ok(e.timers.has(e.a.state.bookPollTimer));
 });
 assert.equal(cases.length,26);console.log(JSON.stringify({synthetic:true,auditScenarios:25,extraSafety:1,passed:cases,unexpectedErrors:0},null,2));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
