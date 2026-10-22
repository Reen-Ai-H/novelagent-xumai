/* Real Chromium, synthetic responses only; no service, author store or model.
 * Exercise native refresh/section/confirmation paths without app hooks. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {chromium}=require('playwright'),{fixture,root}=require('./test_stage38_frontend_browser.cjs');
const origin='http://report-provenance.invalid';
(async()=>{
 const out=await fs.mkdtemp(path.join(os.tmpdir(),'xumai-stage38-provenance-'));
 const browser=await chromium.launch({headless:true,channel:'chrome'}),cases=[],screenshots=[];
 try{for(const [width,height] of [[1440,900],[1024,768],[390,844]]){
  const context=await browser.newContext({viewport:{width,height},offline:true,serviceWorkers:'block',reducedMotion:'reduce'}),page=await context.newPage();
  const {workspace,response}=fixture(),errors=[],httpErrors=[],writes=[];
  let version='1',scenario='ordinary',reads=0;
  const producer='Luna · 合成生产者';
  function current(){
   const d=structuredClone(response),r=d.result;
   r.analysis_contract_version=`model.${version}`;r.report.schema_version=version;delete r.report.report_version;r.report.producer=producer;
   if(version==='2')r.report.characters.forEach(p=>{p.motivation=null;p.change=null;});
   if(scenario==='stale'||scenario==='invalidsource'){d.source_match=false;d.source.match=false;d.effective_status='stale';}
   if(scenario==='rule'){
    r.analysis_contract_version='2.0';
    const item={item_id:'synthetic-rule-item',epistemic_status:'unknown',conclusion:'合成规则观察',chapter_ids:['c1'],evidence_ids:['Q0']};
    r.report={report_version:'2.0',source:{project_id:'p1',document_id:'doc',source_version_id:'v1',source_revision:1,source_hash:'a'.repeat(64)},
     chapters:workspace.active_version.chapters.map(c=>({...c,utf16_length:c.content.length,normalized_start:0,normalized_end:100})),evidence:r.evidence,
     characters:{characters:[],states:[],relations:[]},plot:{events:[],plotlines:[],relations:[],reading_segments:[]},foreshadowing:{},
     rhythm:{items:[item]},reader_experience:{items:[item]},technique:{items:[item]}};
   }
   d.active_run={...r,run_status:'completed'};
   if(scenario==='stale'){d.result=null;d.active_run=null;}
   if(scenario==='noresult'){d.result=null;d.active_run=null;d.effective_status='empty';d.source_match=false;d.source.match=false;}
   return d;
  }
  function job(){return {kind:'report-v2',run_id:'synthetic-failure',status:['queued','running','paused'].includes(scenario)?scenario:'failed',stage:'review',cursor:1,total:2,document_id:null,error_code:scenario==='unknown'?'report_request_unknown':'synthetic_invalid',message:'合成分析失败，原报告保留。'};}
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(['warning','error'].includes(m.type()))errors.push(m.text());});
  await context.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname;
   assert.equal(url.origin,origin,'Every request stays on the intercepted synthetic origin');
   const json=(data,status=200)=>{
    if(status!==200)httpErrors.push('Failed to load resource: the server responded with a status of 503 (Service Unavailable)');
    return route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
   };
   if(p.startsWith('/static/')){const n=p.slice(8);assert.match(n,/^[a-z0-9.-]+$/);return route.fulfill({contentType:n.endsWith('.css')?'text/css':n.endsWith('.svg')?'image/svg+xml':'text/javascript',body:await fs.readFile(path.join(root,'frontend',n))});}
   if(!p.startsWith('/api/'))return route.fulfill({contentType:'text/html',body:await fs.readFile(path.join(root,'frontend/index.html'))});
   if(req.method()!=='GET'){writes.push(`${req.method()} ${p}`);throw Error('This read/cancel-only test must send no mutation');}
   if(p==='/api/auth/session')return json({authenticated:true,account:{account_id:'synthetic',email:'provenance.reader@example.test'}});
   if(p==='/api/notifications')return json({notifications:[],unread_count:0});
   if(p.endsWith('/model-budget'))return scenario==='budgeterror'?json({detail:{message:'合成预算读取失败'}},503):json({model_available:scenario!=='disabled',budget:{budget_cny:5,estimated_spent_cny:1,reserved_cny:0,remaining_cny:4}});
   if(p.endsWith('/book'))return scenario==='fetcherror'?json({detail:{message:'合成任务读取失败'}},503):json({job:job()});
   if(p.endsWith('/deconstruction/guide'))return json({characters:[]});
   if(p.endsWith('/deconstruction')){reads++;return json(current());}
   if(p==='/api/independent/projects/p1')return json(workspace);
   throw Error(`Unexpected synthetic request ${p}`);
  });
  const workflow=page.locator('#reportWorkflow'),button=workflow.locator('[data-action=open-report-confirm]'),tools=page.locator('#workspaceToolsDialog');
  async function openTools(){if(!await tools.evaluate(n=>n.open))await page.locator('[data-action=open-workspace-tools]').click();}
  async function same(){
   assert.equal(await workflow.count(),1);assert.equal(await button.count(),1);
   assert.equal(await workflow.evaluate(n=>n===window.__provenanceNode),true,'Keep the same connected node across every render');
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No page overflow');
  }
  async function load(next){
   scenario=next;await page.goto(`${origin}/independent/p1?view=deconstruction&section=characters`);
   if(next==='invalidsource'){
    await page.locator('.deconstruction-error-panel').waitFor();
    assert.match(await page.locator('.deconstruction-error-panel').innerText(),/正式结果没有绑定当前来源/);
    return;
   }
   await button.waitFor({state:'attached'});
   await page.waitForFunction(()=>{const r=document.querySelector('#reportWorkflow');return r?.textContent && !/正在读取状态|正在读取任务状态/.test(r.textContent);});
   if(next==='budgeterror')await page.waitForFunction(()=>document.querySelector('#reportWorkflow').textContent.includes('预算'));
   if(next==='fetcherror')await page.waitForFunction(()=>document.querySelector('#reportWorkflow').textContent.includes('刷新重试'));
   await page.evaluate(()=>{window.__provenanceNode=document.querySelector('#reportWorkflow');});
  }
  async function capture(name){const file=path.join(out,`${width}-model${version}-${name}.png`);await page.screenshot({path:file,fullPage:true});screenshots.push(file);}
  try{for(version of ['1','2']){
   await load('ordinary');await page.locator('.total-graph-scroll').waitFor();
   assert.equal(await page.locator('#deconstructionStatusPill').innerText(),`报告已就绪 · ${producer}`);
   assert.equal(await workflow.evaluate(n=>n.parentElement.id),'workspaceSource');
   assert.equal(await workflow.isVisible(),false);assert.equal(await page.locator('.deconstruction-header-actions #reportWorkflow').count(),0);
   assert.doesNotMatch(await page.locator('.deconstruction-header-actions').innerText(),/合成分析失败|重新分析/);
   await capture('ready');await openTools();await same();
   assert.match(await workflow.innerText(),/合成分析失败/);assert.equal(await button.innerText(),'重新分析');assert.equal(await button.isEnabled(),true);
   await button.focus();await page.keyboard.press('Enter');await page.locator('#reportConfirmDialog[open]').waitFor();
   assert.match(await page.locator('#reportConfirmBudget').innerText(),/4.0000/);assert.deepEqual(writes,[]);
   await page.keyboard.press('Escape');await page.waitForFunction(()=>document.activeElement?.dataset.action==='open-report-confirm');
   assert.equal(await tools.evaluate(n=>n.open),true);await same();await capture('source');
   // Native refresh rebuilds workspaceSource, then the same workflow returns.
   for(let i=0;i<2;i++){
    const before=reads;await page.locator('#deconstructionRefreshButton').click();
    await page.waitForFunction(()=>document.querySelector('#workspaceSource > #reportWorkflow [data-action=open-report-confirm]')?.disabled===false);
    assert.ok(reads>before);await same();assert.equal(await button.isVisible(),true);
   }
   await page.locator('#workspaceToolsDialog [data-section=guide]').click();
   await page.waitForFunction(()=>document.querySelector('[data-guide-note]')?.textContent==='0 卷生效');await same();
   assert.equal(await workflow.evaluate(n=>n.parentElement.id),'workspaceSource');assert.equal(await workflow.isVisible(),false);
   for(const section of ['characters','plot']){
    await page.locator(`#deconstructionSubnav [data-section=${section}]`).click();await page.locator('.total-graph-scroll').waitFor();await same();
    await openTools();assert.equal(await button.isVisible(),true);await page.keyboard.press('Escape');
   }
   assert.equal(await page.locator('#deconstructionPageContent').getAttribute('aria-busy'),'false');
   cases.push({width,version,case:'ready provenance, original reason, single node, refresh, guide, both returns, keyboard fee cancel'});
   for(const next of ['queued','running','paused','unknown','stale','invalidsource','rule','noresult','fetcherror','budgeterror','disabled']){
    await load(next);
    if(next==='invalidsource'){
     assert.equal(await page.locator('#deconstructionStatusPill').innerText(),'读取失败');
     assert.equal(await workflow.isVisible(),false);cases.push({width,version,case:next});continue;
    }
    await same();
    if(next==='disabled'){
     assert.equal(await workflow.evaluate(n=>n.parentElement.id),'workspaceSource');await openTools();
     assert.equal(await button.isDisabled(),true);assert.match(await page.locator('#deconstructionStatusPill').innerText(),/报告已就绪/);
    }else{
     assert.equal(await workflow.isVisible(),true,`${next} cannot be hidden in source tools`);
     assert.equal(await workflow.evaluate(n=>n.parentElement.id),['stale','noresult'].includes(next)?'deconstructionPageContent':'');
     assert.equal(await page.locator('#deconstructionStatusPill').isVisible(),false);
     assert.equal(await button.isDisabled(),['queued','running','unknown','fetcherror','budgeterror'].includes(next));
     if(next==='unknown')assert.match(await workflow.innerText(),/上次请求尚待确认/);
     if(next==='paused')assert.equal(await button.innerText(),'继续拆书');
     if(next==='running')assert.equal(await workflow.locator('[data-action=pause-report]').count(),1);
     if(next==='fetcherror'||next==='budgeterror'){
      scenario='ordinary';await workflow.locator('[data-action=refresh-report-status]').click();
      await page.waitForFunction(()=>document.querySelector('#workspaceSource > #reportWorkflow [data-action=open-report-confirm]')?.disabled===false);
      await same();assert.equal(await page.locator('#deconstructionStatusPill').isVisible(),true);
     }
    }
    cases.push({width,version,case:next});
   }
  }
  assert.deepEqual(writes,[]);assert.deepEqual([...errors].sort(),[...httpErrors].sort(),'Only injected HTTP failures may appear in console');
  }catch(e){await page.screenshot({path:path.join(out,`${width}-failure.png`),fullPage:true});console.error({out,width,version,scenario,errors});throw e;}
  finally{await context.close();}
 }
 const result={synthetic:true,out,count:cases.length,cases,screenshots};await fs.writeFile(path.join(out,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
