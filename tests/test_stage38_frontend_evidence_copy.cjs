/* Narrow presentation regression: real app functions and section locator in a
 * deterministic DOM/VM. No server, author store, model or external requests. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'frontend/app.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'frontend/index.html'), 'utf8');
const body = '开头😀\r\n合成原句<&>。结尾';
const excerpt = '合成原句<&>。';
const rawEvidence = () => ({evidence_id:'Q1', document_id:'doc', source_version_id:'v1', source_revision:1,
  source_hash:'hash', chapter_id:'c2', chapter_number:2, granularity:'span',
  start_offset:body.indexOf(excerpt), end_offset:body.indexOf(excerpt)+excerpt.length,
  offset_unit:'utf16_code_unit', excerpt, label:'重复的证据标签'});
function environment(model = 'model.2', sections = true) {
  const nodes = new Map(), calls = [], navigations = [], timers = [];
  let document, currentError = null, endpointError = null;
  class Node {
    constructor(id='') { Object.assign(this, {id, innerHTML:'', textContent:'', value:'', disabled:false,
      dataset:{}, attrs:{}, style:{}, open:false, offsetTop:0, clientHeight:300, clientWidth:600,
      classList:{add(){}, remove(){}, toggle(){}}}); }
    setAttribute(k,v) { this.attrs[k]=v; } getAttribute(k) { return this.attrs[k]; }
    set value(v) { this._value=String(v).replace(/\r\n?/g,'\n'); } get value() { return this._value; }
    removeAttribute(k) { delete this.attrs[k]; }
    showModal() { this.open=true; } close() { this.open=false; }
    focus() { document.activeElement=this; }
    setSelectionRange(a,b) { this.selectionStart=a; this.selectionEnd=b; }
    querySelector(s) { return get(this.id+' '+s); } querySelectorAll() { return []; }
    insertAdjacentHTML(_,s) { this.innerHTML+=s; }
    append() {} remove() {} scrollIntoView() {} addEventListener() {}
  }
  const get = key => { if (!nodes.has(key)) nodes.set(key,new Node(key)); return nodes.get(key); };
  document = {querySelector:get, querySelectorAll:()=>[], getElementById:id=>get('#'+id),
    body:get('body'), activeElement:get('trigger'), createElement:()=>new Node(), addEventListener(){}};
  const e = rawEvidence();
  const result = {document_id:'doc',status:'completed',analysis_contract_version:model,source_version_id:'v1',
    source_revision:1,source_hash:'hash',scope_start:1,scope_end:2,scope_hash:'scope',
    report:{schema_version:model==='model.2'?'2':'1',characters:[],events:[],evidence:[],chapter_numbers:[1,2]},evidence:[e]};
  const canonical = {project_id:'p',effective_status:'completed',run_status:'completed',source_match:true,
    source:{version_id:'v1',revision:1,hash:'hash',match:true},progress:{percent:100},actions:{},
    result,active_run:{...result,run_status:'completed'},focus_document_id:'doc'};
  const endpoint = {evidence:e,source_matches_current:true,historical:false,
    chapter:{chapter_id:'c2',chapter_number:2,title:'合成第二章',source_version_id:'v1',source_available:true}};
  const context = {document,URL,URLSearchParams,console,Map,Set,WeakMap,Promise,
    location:new URL('http://evidence.invalid/independent/p?view=deconstruction'),
    getComputedStyle:()=>({}),setTimeout:f=>{timers.push(f);return timers.length;},clearTimeout(){},
    requestAnimationFrame:f=>f(),fetch:()=>{throw Error('No network allowed');}};
  context.window=context;
  context.read = async url => {
    calls.push(url);
    assert.ok(url.includes('/api/independent/projects/p/deconstruction'));
    assert.ok(url.includes('document_id=doc'), 'Both server reads remain scoped to the report');
    if (url.includes('/evidence/')) { if(endpointError) throw endpointError; return endpoint; }
    if(currentError) throw currentError;
    return canonical;
  };
  context.go = async route => { navigations.push(route); return true; };
  context.load = async id => {
    assert.equal(id,'p');
    context.api.state.workspace={active_version:{version_id:'v1',chapters:[{chapter_id:'c2',chapter_number:2,content:body}]}};
  };
  context.render = () => { context.api.elements.chapterEditor.value=body.replace(/\r\n?/g,'\n'); };
  context.sync = id => { assert.equal(id,'c2'); };
  const hook='  start();\n})();';
  assert.equal(source.split(hook).length,2);
  vm.runInNewContext(source.replace(hook, `
    window.api={state,elements,normalizeEvidenceRef,normalizeDeconstructionResponse,
      renderDeconstructionEvidenceDialog,renderDeconstructionEvidenceLoading,
      openDeconstructionEvidence,locateDeconstructionEvidence};
    requestJson=(...args)=>window.read(...args);
    navigate=(...args)=>window.go(...args);
    loadIndependentWorkspace=(...args)=>window.load(...args);
    renderEditorWorkspace=()=>window.render(); syncActiveChapterUrl=id=>window.sync(id);
  })();`),context);
  if(sections) vm.runInNewContext(fs.readFileSync(path.join(root,'frontend/chapter-sections.js'),'utf8'),context);
  const a=context.api;
  Object.assign(a.state,{deconstructionProjectId:'p',deconstructionWorkspace:a.normalizeDeconstructionResponse(canonical)});
  const clicked = () => ({dataset:{evidenceId:'Q1',documentId:'doc',sourceVersionId:'v1',sourceRevision:'1',
    sourceHash:'hash',chapterId:'c2',chapterNumber:'2',granularity:'span',charStart:String(e.start_offset),
    charEnd:String(e.end_offset),offsetUnit:e.offset_unit,excerpt:e.excerpt}});
  return {a,e,endpoint,canonical,document,calls,navigations,context,clicked,
    error(kind,error){if(kind==='endpoint')endpointError=error;else currentError=error;},
    render:()=>a.renderDeconstructionEvidenceDialog(endpoint,null,true)};
}
const cases=[];
async function test(name,run) { await run(); cases.push(name); }
(async()=>{
  await test('current exact drawer is chapter, quote and normal action only',()=>{
    const x=environment();x.render();const h=x.a.elements.deconstructionEvidenceContent.innerHTML;
    assert.match(h,/第 2 章/);assert.match(h,/<h3>合成第二章<\/h3>/);
    assert.match(h,/<blockquote>“合成原句&lt;&amp;&gt;。”<\/blockquote>/);
    assert.doesNotMatch(h,/<dl|UTF-16|字符范围|字符位移|回看边界|重复的证据标签/);
    assert.equal(x.a.elements.locateDeconstructionEvidenceButton.disabled,false);
    assert.equal(x.a.elements.locateDeconstructionEvidenceButton.textContent,'在正文中定位');
    assert.doesNotMatch(x.a.elements.locateDeconstructionEvidenceButton.title,/UTF|位移/);
  });
  await test('chapter-only and invalid span guards still disable locating',()=>{
    for(const change of [{granularity:'chapter',excerpt:''},{offset_unit:'code_point'},
      {start_offset:null},{start_offset:-1},{end_offset:null},{end_offset:0}]){
      const x=environment();Object.assign(x.e,change);x.render();
      assert.equal(x.a.elements.locateDeconstructionEvidenceButton.disabled,true,JSON.stringify(change));
      assert.equal(x.a.elements.locateDeconstructionEvidenceButton.textContent,'仅可回看章节');
      assert.ok(x.a.state.pendingEvidence);
    }
  });
  await test('history stays read-only, selects only the old textarea, never offers current locating',()=>{
    const x=environment();Object.assign(x.endpoint,{source_matches_current:false,historical:true});
    Object.assign(x.endpoint.chapter,{read_only:true,content:body});x.render();
    const h=x.a.elements.deconstructionEvidenceContent.innerHTML;
    assert.match(h,/历史稿本 · 只读/);assert.match(h,/<textarea readonly/);
    const old=x.a.elements.deconstructionEvidenceContent.querySelector('.historical-source textarea');
    assert.equal(old.value,body.replace(/\r\n/g,'\n'));
    assert.equal(old.value.slice(old.selectionStart,old.selectionEnd),excerpt);
    assert.equal(x.a.elements.chapterEditor.selectionStart,undefined);
    assert.equal(x.a.state.pendingEvidence,null);
    assert.equal(x.a.elements.locateDeconstructionEvidenceButton.disabled,true);
    assert.equal(x.a.elements.locateDeconstructionEvidenceButton.textContent,'历史稿本不可定位');
    assert.match(x.a.elements.locateDeconstructionEvidenceButton.title,/只读.*不能定位/);
  });
  await test('unavailable or mismatched historical source cannot expose a guessed old chapter',()=>{
    for(const change of [{source_available:false},{source_version_id:'different'},{chapter_id:'different'}]){
      const x=environment();Object.assign(x.endpoint,{source_matches_current:false,historical:true});
      Object.assign(x.endpoint.chapter,{read_only:true,content:body},change);x.render();
      assert.doesNotMatch(x.a.elements.deconstructionEvidenceContent.innerHTML,/<textarea/);
      assert.equal(x.a.state.pendingEvidence,null);
    }
  });
  await test('quote, chapter title and failure reasons remain escaped',()=>{
    const x=environment();x.e.excerpt='<img src=x onerror=alert(1)>';x.endpoint.chapter.title='<script>bad()</script>';
    x.a.renderDeconstructionEvidenceDialog(x.endpoint,null,true,'<svg onload=bad()>');
    const h=x.a.elements.deconstructionEvidenceContent.innerHTML;
    assert.doesNotMatch(h,/<img|<script|<svg/);assert.match(h,/&lt;img/);assert.match(h,/&lt;script/);assert.match(h,/&lt;svg/);
  });
  await test('server read failure retains a safe retry and the actual error reason',async()=>{
    const x=environment();x.error('endpoint',Error('合成失败 <img src=x>'));await x.a.openDeconstructionEvidence(x.clicked());
    assert.equal(x.calls.length,2);assert.equal(x.a.state.pendingEvidence,null);
    assert.equal(x.a.elements.deconstructionEvidenceTitle.textContent,'原文暂时读不到');
    assert.equal(x.a.elements.locateDeconstructionEvidenceButton.disabled,true);
    assert.match(x.a.elements.deconstructionEvidenceContent.innerHTML,/合成失败 &lt;img src=x&gt;/);
    assert.match(x.a.elements.deconstructionEvidenceContent.innerHTML,/data-action="open-deconstruction-evidence"/);
  });
  await test('opening still rejects mismatched evidence identities and historical endpoints',async()=>{
    for(const change of [{evidence:{...rawEvidence(),source_hash:'other'}},{historical:true},{source_matches_current:false}]){
      const x=environment();Object.assign(x.endpoint,change);await x.a.openDeconstructionEvidence(x.clicked());
      assert.equal(x.a.state.pendingEvidence,null);assert.equal(x.a.elements.locateDeconstructionEvidenceButton.disabled,true);
      assert.match(x.a.elements.deconstructionEvidenceContent.innerHTML,/不一致|变化/);
      assert.deepEqual(x.navigations,[]);
    }
  });
  for(const model of ['model.1','model.2']) await test(`${model} successful locate keeps CRLF/surrogate selection and focus; notice does not repeat quote`,async()=>{
    const x=environment(model);await x.a.openDeconstructionEvidence(x.clicked());await x.a.locateDeconstructionEvidence();
    assert.deepEqual(x.navigations,['/independent/p']);assert.equal(x.calls.length,4);
    const editor=x.a.elements.chapterEditor;
    assert.equal(editor.selectionStart,x.e.start_offset-1);assert.equal(editor.selectionEnd,x.e.end_offset-1);
    assert.equal(editor.value.slice(editor.selectionStart,editor.selectionEnd),excerpt);
    assert.equal(x.document.activeElement,editor);assert.equal(x.a.state.pendingEvidence,null);
    assert.equal(x.a.elements.editorNotice.innerHTML,'<strong>第 2 章</strong> · 已选中原句。');
    assert.doesNotMatch(x.a.elements.editorNotice.innerHTML,/UTF|字符|合成原句|editor-evidence-excerpt/);
  });
  await test('fallback textarea locator still selects identical LF content',async()=>{
    const x=environment('model.2',false);const lf=body.replace(/\r\n/g,'\n');
    x.e.start_offset=lf.indexOf(excerpt);x.e.end_offset=x.e.start_offset+excerpt.length;
    x.context.load=async()=>{x.a.state.workspace={active_version:{version_id:'v1',chapters:[{chapter_id:'c2',chapter_number:2,content:lf}]}};};
    await x.a.openDeconstructionEvidence(x.clicked());await x.a.locateDeconstructionEvidence();
    assert.equal(x.a.elements.chapterEditor.selectionStart,x.e.start_offset);
    assert.equal(x.a.elements.chapterEditor.selectionEnd,x.e.end_offset);
  });
  await test('quote mismatch opens chapter without selecting or duplicating an unsafe quote',async()=>{
    const x=environment();x.e.excerpt='<img src=x onerror=bad()>';await x.a.openDeconstructionEvidence(x.clicked());
    await x.a.locateDeconstructionEvidence();assert.equal(x.a.elements.chapterEditor.selectionStart,undefined);
    assert.match(x.a.elements.editorNotice.innerHTML,/原句与正文不一致/);
    assert.doesNotMatch(x.a.elements.editorNotice.innerHTML,/<img|&lt;img|UTF/);
  });
  await test('source change and re-read failure after navigation never select text',async()=>{
    for(const fail of [false,true]){
      const x=environment();await x.a.openDeconstructionEvidence(x.clicked());
      if(fail)x.error('endpoint',Error('合成重读失败'));else x.endpoint.source_matches_current=false;
      await x.a.locateDeconstructionEvidence();assert.equal(x.a.elements.chapterEditor.selectionStart,undefined);
      assert.equal(x.a.state.pendingEvidence,null);assert.match(x.a.elements.editorNotice.textContent,/未定位原句/);
    }
  });
  await test('pre-navigation stale guard still prevents leaving the report',async()=>{
    const x=environment();await x.a.openDeconstructionEvidence(x.clicked());x.a.state.deconstructionWorkspace.sourceMatch=false;
    await x.a.locateDeconstructionEvidence();assert.deepEqual(x.navigations,[]);
    assert.match(x.a.elements.deconstructionNotice.textContent,/正文已变化/);
  });
  await test('shell labels are human-readable and actions/disabled semantics remain',()=>{
    const drawer=html.slice(html.indexOf('<dialog id="deconstructionEvidenceDialog"'),html.indexOf('<script src="/static/report-browser.js'));
    assert.match(drawer,/来源原文/);assert.doesNotMatch(drawer,/证据回链|UTF/);
    assert.match(drawer,/data-action="locate-deconstruction-evidence" disabled>在正文中定位/);
    assert.match(drawer,/aria-labelledby="deconstructionEvidenceTitle"/);
  });
  assert.equal(cases.length,14);
  console.log(JSON.stringify({synthetic:true,passed:cases.length,cases},null,2));
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
