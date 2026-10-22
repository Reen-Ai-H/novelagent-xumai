/* Real Chromium, deterministic intercepted reports only. No listening service,
 * author data, backend imports, model or paid requests. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {chromium}=require('playwright'),{fixture,root}=require('./test_stage38_frontend_browser.cjs');
const origin='http://sparse-report.invalid';
function fixtures(){
 const {workspace,response}=fixture(),old=structuredClone(response),fresh=structuredClone(response);
 const extra=workspace.active_version.chapters.map(c=>({...c,chapter_id:`c${c.chapter_number+6}`,chapter_number:c.chapter_number+6}));
 workspace.active_version.chapters.push(...extra);
 for(const [doc,version,offset]of [[old,'1',0],[fresh,'2',6]]){
  const id=`doc${version}`,r=doc.result;r.document_id=id;r.analysis_contract_version=`model.${version}`;r.scope_start=1+offset;r.scope_end=6+offset;
  r.report.schema_version=version;r.report.title=`合成报告 ${version}`;r.report.chapter_numbers=r.report.chapter_numbers.map(n=>n+offset);
  r.report.events.forEach(e=>{e.chapter_number+=offset;if(e.chapter_end)e.chapter_end+=offset;});r.report.evidence.forEach(e=>e.chapter_number+=offset);
  r.evidence.forEach(e=>{e.document_id=id;e.chapter_number+=offset;e.chapter_id=`c${e.chapter_number}`;});
  doc.focus_document_id=id;doc.source.chapter_count=12;doc.source.total_word_count=600;doc.active_run={...r,run_status:'completed'};
 }
 const people=fresh.result.report.characters;
 people.forEach((p,i)=>{
  if([0,1,4,5].includes(i))p.motivation=null;
  else p.motivation={text:`有据动机 ${i}`,status:'inferred',evidence_ids:[`Q${i}`]};
  if([0,2,4,5].includes(i))p.change=null;
  else p.change={text:`有据变化 ${i}`,status:'reported',evidence_ids:[`Q${i}`]};
  if([4,5].includes(i))p.portrait=null;
  p.insights=[0,5].includes(i)?[{title:'合成补充经历',text:`${p.name}留下了有据补充。`,status:'fact',evidence_ids:[`Q${i}`]}]:[];
 });
 const volumes=[old,fresh].map(doc=>({document_id:doc.result.document_id,scope_start:doc.result.scope_start,scope_end:doc.result.scope_end,scope_label:`第${doc.result.scope_start}–${doc.result.scope_end}章`,status:'completed',run_status:'completed',match:true,chapter_count:6,evidence_count:6}));
 for(const doc of [old,fresh]){doc.volumes=volumes;doc.history=[old,fresh].map(d=>({...d.result,created_at:'2026-01-01T00:00:00Z',completed_at:'2026-01-01T00:01:00Z'}));}
 const characters=people.map((p,i)=>({name:p.name,aliases:p.aliases,stages:[old,fresh].map(doc=>({scope_start:doc.result.scope_start,scope_end:doc.result.scope_end,identity:doc.result.report.characters[i].identity,change:doc.result.report.characters[i].change}))}));
 return {workspace,old,fresh,characters};
}
(async()=>{
 const out=await fs.mkdtemp(path.join(os.tmpdir(),'xumai-stage38-sparse-')),browser=await chromium.launch({headless:true,channel:'chrome'}),cases=[],screenshots=[];
 try{for(const [width,height]of [[1440,900],[1024,768],[390,844]]){
  const context=await browser.newContext({viewport:{width,height},offline:true,serviceWorkers:'block',reducedMotion:'reduce'}),page=await context.newPage();
  const data=fixtures(),before=JSON.stringify(data),errors=[],requests=[];
  let formal=true,job={kind:'report-v2',status:'completed',stage:'completed',document_id:'doc2'};
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(['error','warning'].includes(m.type()))errors.push(m.text());});
  await context.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname;assert.equal(url.origin,origin);assert.equal(req.method(),'GET','This read-only acceptance must never send a write');requests.push(p);
   const json=body=>route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
   if(p.startsWith('/static/')){const n=p.slice(8);assert.match(n,/^[a-z0-9.-]+$/);return route.fulfill({contentType:n.endsWith('.css')?'text/css':n.endsWith('.svg')?'image/svg+xml':'text/javascript',body:await fs.readFile(path.join(root,'frontend',n))});}
   if(p==='/standalone'){
    const css=['styles','deconstruction-report','visual-reading'].map(n=>`<link rel="stylesheet" href="/static/${n}.css">`).join('');
    return route.fulfill({contentType:'text/html',body:`<!doctype html><html lang="zh-CN"><meta charset="utf-8">${css}<body><main id="standalone"></main><script src="/static/report-browser.js"></script><script src="/static/visual-reading.js"></script><script src="/static/deconstruction-report.js"></script></body></html>`});
   }
   if(!p.startsWith('/api/'))return route.fulfill({contentType:'text/html',body:await fs.readFile(path.join(root,'frontend/index.html'))});
   if(p==='/api/auth/session')return json({authenticated:true,account:{account_id:'synthetic',email:'sparse.reader@example.test'}});
   if(p==='/api/notifications')return json({notifications:[],unread_count:0});
   if(p.endsWith('/model-budget'))return json({model_available:false,budget:{budget_cny:5,estimated_spent_cny:0,reserved_cny:0,remaining_cny:5}});
   if(p.endsWith('/book'))return json({job});
   if(p.endsWith('/deconstruction/guide'))return json({characters:data.characters});
   if(p.includes('/deconstruction/evidence/')){
    const doc=url.searchParams.get('document_id')==='doc1'?data.old:data.fresh,ref=doc.result.evidence.find(e=>e.evidence_id===p.split('/').at(-1));assert.ok(ref);
    return json({evidence:ref,source_matches_current:true,historical:false,chapter:{...data.workspace.active_version.chapters.find(c=>c.chapter_id===ref.chapter_id),source_available:true}});
   }
   if(p.endsWith('/deconstruction'))return json(formal?(url.searchParams.get('document_id')==='doc1'?data.old:data.fresh):{...data.fresh,result:null,active_run:null,focus_document_id:'',effective_status:'empty',run_status:'none',source_match:false,source:{...data.fresh.source,match:false},volumes:[],history:[]});
   if(p==='/api/independent/projects/p1')return json(data.workspace);
   throw Error(`Unexpected synthetic GET ${p}`);
  });
  const detail=page.locator('[data-reader-detail]'),workflow=page.locator('#reportWorkflow');
  async function geometry(){
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No whole-page horizontal overflow');
   assert.equal(await page.locator('#deconstructionPageContent').getAttribute('aria-busy'),'false');
  }
  async function capture(name){await geometry();const file=path.join(out,`${width}x${height}-${name}.png`);await page.screenshot({path:file,fullPage:true});screenshots.push(file);}
  async function enter(version,section='characters'){
   await page.goto(`${origin}/independent/p1?view=deconstruction&volume=doc${version}&section=${section}`);await page.locator('.total-graph-scroll').waitFor();
   await page.waitForFunction(()=>document.querySelector('#reportWorkflow')?.hidden);
   assert.equal(await page.locator('.total-graph-node').count(),6);assert.equal(await workflow.count(),1);await geometry();
  }
  async function key(locator,key='Enter'){await locator.focus();await page.keyboard.press(key);}
  async function returnIndex(id){await key(page.locator('[data-reader-back]'));await page.locator('.total-graph-scroll').waitFor();assert.equal(await page.locator(`[data-reader-open=${id}]`).evaluate(n=>n===document.activeElement),true);await geometry();}
  async function proof(section,version,locate=false){
   await key(section.locator('.analysis-proof > summary').first());
   const link=section.locator('.deconstruction-evidence-link').first(),quote=await link.getAttribute('data-excerpt');await key(link);
   await page.locator('#deconstructionEvidenceDialog[open]').waitFor();await page.waitForFunction(()=>!document.querySelector('#locateDeconstructionEvidenceButton').disabled);
   assert.ok((await page.locator('#deconstructionEvidenceDialog').innerText()).includes(quote));
   // Native Tab/Shift-Tab stays inside the source dialog.
   await page.keyboard.press('Tab');assert.equal(await page.evaluate(()=>document.querySelector('#deconstructionEvidenceDialog').contains(document.activeElement)),true);
   await page.keyboard.press('Shift+Tab');assert.equal(await page.evaluate(()=>document.querySelector('#deconstructionEvidenceDialog').contains(document.activeElement)),true);
   if(!locate){await page.keyboard.press('Escape');assert.equal(await link.evaluate(n=>n===document.activeElement),true);}
   else{
    await key(page.locator('#locateDeconstructionEvidenceButton'));await page.waitForFunction(q=>{const e=document.querySelector('#chapterEditor');return e?.value.slice(e.selectionStart,e.selectionEnd)===q;},quote);
    await page.goBack();await detail.waitFor();assert.equal(new URL(page.url()).searchParams.get('volume'),`doc${version}`);
   }
  }
  try{
   for(const version of ['1','2']){
    await enter(version);await capture(`schema${version}-people-graph`);
    await page.evaluate(()=>{window.__sparseWorkflow=document.querySelector('#reportWorkflow');});
    // Every person remains reachable; sparse cases cover main/support, both,
    // either, neither, no portrait and no insights, plus retained insight.
    for(let i=0;i<6;i++){
     await key(page.locator(`[data-reader-open=C${i}]`));await detail.waitFor();
     const analysis=detail.locator('details').filter({has:page.locator('summary', {hasText:'人物分析与原文'})}).last();
     await key(analysis.locator(':scope > summary'));
     const p=(version==='1'?data.old:data.fresh).result.report.characters[i],headings=await analysis.locator('h3').allTextContents();
     assert.equal(headings.includes('动机'),p.motivation!==null);assert.equal(headings.includes('关键经历与变化'),p.change!==null);
     assert.ok((await analysis.innerText()).includes(p.identity.text));assert.equal(await analysis.locator('section').evaluateAll(nodes=>nodes.every(n=>n.querySelector('h3')&&n.querySelector('p')?.textContent.trim())),true);
     assert.equal(await analysis.locator('.analysis-phrase').count(),p.insights.length);
     if(version==='2')assert.doesNotMatch(await analysis.innerText(),/暂无可确认分析|暂未绑定原文依据|未交代|当前报告没有经历记录/);
     if(i===0){await capture(`schema${version}-sparse-detail`);await proof(analysis,version);
      if(version==='2'){
       await key(analysis.locator('.analysis-phrase'));await page.locator('.analysis-modal').waitFor();assert.match(await page.locator('.analysis-modal').innerText(),/有据补充/);
       await page.keyboard.press('Escape');assert.equal(await analysis.locator('.analysis-phrase').evaluate(n=>n===document.activeElement),true);
      }
     }
     await key(page.locator('[data-reader-pane=experiences]'));assert.ok(await page.locator('.workspace-event-stop').count());
     await returnIndex(`C${i}`);cases.push({width,version,person:i,sparseSections:true,realExperiences:true});
    }
    // Source navigation from event graph -> detail -> exact editor quote ->
    // browser Back -> detail -> keyboard Back to the selected graph node.
    await key(page.locator('#deconstructionSubnav [data-section=plot]'));await page.locator('.total-graph-scroll').waitFor();
    assert.equal(await page.locator('[data-total-from]').count(),2);await capture(`schema${version}-event-graph`);
    await key(page.locator('[data-reader-open=E2]'));await detail.waitFor();await proof(page.locator('.workspace-event-body'),version,true);await returnIndex('E2');
    cases.push({width,version,eventSourceEditorAndBack:true});
    // Person graph -> detail -> exact source -> editor -> Back as well.
    await key(page.locator('#deconstructionSubnav [data-section=characters]'));await page.locator('.total-graph-scroll').waitFor();
    await key(page.locator('[data-reader-open=C0]'));await detail.waitFor();
    const analysis=detail.locator('details').filter({has:page.locator('summary', {hasText:'人物分析与原文'})}).last();await key(analysis.locator(':scope > summary'));
    await proof(analysis,version,true);await returnIndex('C0');cases.push({width,version,personSourceEditorAndBack:true});
    // Guide mixes the two explicit versions. Read it through native UI, then
    // follow a volume back into the corresponding report.
    await page.evaluate(()=>{window.__sparseWorkflow=document.querySelector('#reportWorkflow');});
    await key(page.locator('[data-action=open-workspace-tools]'));await key(page.locator('#workspaceToolsDialog [data-section=guide]'));
    await page.waitForFunction(()=>document.querySelector('[data-guide-note]')?.textContent==='2 卷生效');
    assert.equal(await workflow.count(),1);assert.equal(await workflow.evaluate(n=>n===window.__sparseWorkflow),true);assert.equal(await workflow.isVisible(),false);
    assert.equal(await page.locator('.deconstruction-guide-volume').count(),2);assert.ok((await page.locator('#deconstructionGuideBody').innerText()).includes(data.fresh.result.report.characters[0].identity.text));
    assert.doesNotMatch(await page.locator('#deconstructionGuideBody').innerText(),/阶段信息待补充/);await capture(`from-schema${version}-mixed-guide`);
    await key(page.locator(`.guide-node-card[data-document-id=doc${version}]`).first());await page.locator('.total-graph-scroll').waitFor();
    assert.equal(new URL(page.url()).searchParams.get('volume'),`doc${version}`);assert.equal(await workflow.count(),1);await geometry();
    cases.push({width,version,mixedGuideAndReturn:true,sameConnectedWorkflow:true});
   }
   // A newly completed schema 2 task must clear the body empty state using
   // the original DOM node, rather than leaving the reader aria-busy.
   formal=false;job={kind:'report-v2',run_id:'new-synthetic',status:'running',stage:'draft',document_id:null};
   await page.goto(origin+'/independent/p1?view=deconstruction&section=characters');
   await page.locator('#deconstructionPageContent > #reportWorkflow h2').waitFor();
   assert.equal(await page.locator('#deconstructionPageContent').getAttribute('aria-busy'),'true');
   await page.evaluate(()=>{window.__sparseWorkflow=document.querySelector('#reportWorkflow');});
   formal=true;job={...job,status:'completed',stage:'completed',document_id:'doc2'};
   await page.locator('.total-graph-scroll').waitFor({timeout:12000});await page.waitForFunction(()=>document.querySelector('#reportWorkflow')?.hidden);
   assert.equal(await workflow.count(),1);assert.equal(await workflow.evaluate(n=>n===window.__sparseWorkflow),true);await geometry();
   cases.push({width,schema2TaskCompletion:true,sameConnectedWorkflow:true,busyCleared:true});
   // Standalone embedded viewer: both full lists and the existing local map.
   for(const version of ['1','2'])for(const mode of ['list','map']){
    await page.goto(origin+'/standalone');await page.waitForFunction(()=>window.XumaiAnalysis);
    await page.evaluate(({report,mode})=>{
     sessionStorage.setItem('xumai-reading-view',mode);const root=document.querySelector('#standalone');root.innerHTML=window.XumaiAnalysis.render(report);
     window.XumaiAnalysis.mount(root,report,[],null,{section:'characters'});
    },{report:(version==='1'?data.old:data.fresh).result.report,mode});
    if(mode==='list'){
     const card=page.locator('.analysis-person').filter({has:page.locator('[data-report-person=C0]')});assert.equal(await card.locator('.analysis-card-summary').innerText().then(t=>t.includes('关键经历')),version==='1');
     await key(card.locator('[data-report-person]').last());
    }else{
     await key(page.locator('[data-visual-pick=C0]'));
     const summary=page.locator('.visual-person-summary[data-summary-kind=change]');assert.equal(await summary.count(),version==='1'?1:0);
     await key(page.locator('.visual-selected details > summary').first());await key(page.locator('.analysis-read-more').first());
    }
    await page.locator('.analysis-person-page').waitFor();const headings=await page.locator('.analysis-person-page h3').allTextContents();
    assert.equal(headings.includes('想要什么，为什么行动'),version==='1');assert.equal(headings.includes('关键经历与变化'),version==='1');assert.ok(headings.includes('身份与处境'));
    if(version==='2')assert.doesNotMatch(await page.locator('.analysis-person-page').innerText(),/暂无可确认分析|暂未绑定原文依据|当前报告没有经历记录|未交代/);
    await key(page.locator('[data-report-back]'));assert.equal(await page.locator('.analysis-person-page').count(),0);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));cases.push({width,version,standalone:mode});
   }
   assert.deepEqual(errors,[]);assert.equal(JSON.stringify(data),before,'The viewer must not mutate either stored report or synthetic manuscript');
   assert.ok(!requests.some(p=>/start-report|analyze-preview|\/pause$/.test(p)));
  }catch(e){await page.screenshot({path:path.join(out,`${width}-failure.png`),fullPage:true});console.error({width,out,url:page.url(),errors});throw e;}
  finally{await context.close();}
 }
 const result={synthetic:true,out,count:cases.length,cases,screenshots};await fs.writeFile(path.join(out,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
