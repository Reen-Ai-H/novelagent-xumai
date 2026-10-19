/* Permanent lifecycle counterexample: native clicks, intercepted synthetic data.
 * No app-function hook, listening service, author data, model or paid request. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {chromium}=require('playwright');
const {fixture,root}=require('./test_stage38_frontend_browser.cjs');
const origin='http://guide-workflow.invalid';
(async()=>{
 const out=await fs.mkdtemp(path.join(os.tmpdir(),'xumai-stage38-guide-workflow-'));
 const browser=await chromium.launch({headless:true,channel:'chrome'}),cases=[],screenshots=[];
 try{for(const [width,height]of [[1440,900],[1024,768],[390,844]]){
  const context=await browser.newContext({viewport:{width,height},reducedMotion:'reduce',serviceWorkers:'block',offline:true}),page=await context.newPage();
  const {response}=fixture(),errors=[],posts=[];
  let formal=false,job=null;
  const task=(status,error_code=null)=>({kind:'report-v2',run_id:'synthetic-guide',status,stage:status==='completed'?'completed':'review',cursor:1,total:2,document_id:status==='completed'?'doc':null,error_code,message:status==='failed'?'合成核对未通过。':''});
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(['warning','error'].includes(m.type()))errors.push(m.text());});
  await context.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname;
   assert.equal(url.origin,origin,'Every request is intercepted; no external origin');
   const json=data=>route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
   if(p.startsWith('/static/')){const n=p.slice(8);assert.match(n,/^[a-z0-9.-]+$/);return route.fulfill({contentType:n.endsWith('.css')?'text/css':n.endsWith('.svg')?'image/svg+xml':'text/javascript',body:await fs.readFile(path.join(root,'frontend',n))});}
   if(!p.startsWith('/api/'))return route.fulfill({contentType:'text/html',body:await fs.readFile(path.join(root,'frontend/index.html'))});
   if(p==='/api/auth/session')return json({authenticated:true,account:{account_id:'synthetic',email:'guide.reader@example.test'}});
   if(p==='/api/notifications')return json({notifications:[],unread_count:0});
   if(p.endsWith('/model-budget'))return json({model_available:true,budget:{budget_cny:5,estimated_spent_cny:1,reserved_cny:0,remaining_cny:4}});
   if(p.endsWith('/book'))return json({job});
   if(p.endsWith('/book/start-report')){
    assert.equal(req.method(),'POST');assert.deepEqual(req.postDataJSON(),{expected_source_version_id:'v1',expected_source_revision:1,expected_source_hash:'a'.repeat(64)});
    posts.push('start');job=task('running');return json({job});
   }
   if(p.endsWith('/book/pause')){assert.equal(req.method(),'POST');posts.push('pause');job={...job,status:'paused'};return json({job});}
   if(p.endsWith('/deconstruction/guide'))return json({characters:[]});
   if(p.endsWith('/deconstruction'))return json(formal?response:{...response,effective_status:'empty',run_status:'none',source_match:false,source:{...response.source,match:false},focus_document_id:'',active_run:null,result:null});
   throw Error(`Unexpected synthetic operation ${req.method()} ${p}`);
  });
  const workflow=page.locator('#reportWorkflow'),primary=workflow.locator('[data-action=open-report-confirm]'),main=page.locator('#deconstructionPageContent');
  async function open(status,hasReport=false,error=null){
   formal=hasReport;job=task(status,error);
   await page.goto(origin+'/independent/p1?view=deconstruction&section=characters'+(formal?'&volume=doc':''));
   await workflow.waitFor({state:'attached'});
   await page.waitForFunction(()=>{const r=document.querySelector('#reportWorkflow');return r?.textContent && !r.textContent.includes('正在读取状态') && !r.textContent.includes('正在读取任务状态');});
   if(status==='paused'&&!error || status==='failed')await page.waitForFunction(()=>!document.querySelector('[data-action=open-report-confirm]')?.disabled);
   if(formal)await page.locator('.total-graph-scroll').waitFor();
   await page.evaluate(()=>{window.__originalGuideWorkflow=document.querySelector('#reportWorkflow');});
  }
  async function sameNode(){
   assert.equal(await workflow.count(),1,'The sole workflow must remain connected');
   assert.equal(await workflow.evaluate(n=>n===window.__originalGuideWorkflow),true,'Move the same node; do not clone/recreate it');
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }
  async function guide(){
   await page.locator('[data-action=open-workspace-tools]').click();
   await page.locator('#workspaceToolsDialog [data-section=guide]').click();
   await page.waitForFunction(()=>document.querySelector('[data-guide-note]')?.textContent==='0 卷生效');
   assert.equal(await page.locator('.deconstruction-guide').count(),1);await sameNode();
   assert.equal(await workflow.evaluate(n=>n.parentElement.className),'deconstruction-header-actions');
   assert.equal(await main.getAttribute('aria-busy'),'false');
   assert.equal(await workflow.locator('.report-stage-list').count(),0);
  }
  async function back(section){
   await page.locator(`#deconstructionSubnav [data-section=${section}]`).click();
   await page.waitForFunction(()=>!document.querySelector('.deconstruction-guide'));await sameNode();
   assert.equal(await workflow.evaluate(n=>n.parentElement.id),formal?'':'deconstructionPageContent');
   if(formal)assert.equal(await page.locator('.total-graph-node').count(),6);
  }
  try{
   for(const hasReport of [false,true])for(const status of ['paused','running','failed']){
    await open(status,hasReport);const before=posts.length;await guide();
    assert.equal(await workflow.isVisible(),true);assert.equal(await primary.isDisabled(),status==='running');
    if(status==='paused'){
     assert.equal(await primary.innerText(),'继续拆书');
     // A paused job has no poll to rescue a detached node after this delay.
     await page.waitForTimeout(3500);await sameNode();assert.equal(await primary.isVisible(),true);
     await primary.focus();await page.keyboard.press('Enter');await page.locator('#reportConfirmDialog[open]').waitFor();
     assert.equal(posts.length,before);await page.keyboard.press('Escape');
     await page.waitForFunction(()=>document.activeElement?.dataset.action==='open-report-confirm');
     if(!hasReport){const file=path.join(out,`${width}x${height}-paused-guide.png`);await page.screenshot({path:file});screenshots.push(file);}
    }else if(status==='failed'){
     assert.equal(await primary.innerText(),'重新分析');await primary.click();await page.locator('#reportConfirmDialog[open]').waitFor();await page.keyboard.press('Escape');assert.equal(posts.length,before);
    }else{
     await workflow.locator('[data-action=pause-report]').click();
     await page.waitForFunction(()=>document.querySelector('[data-action=open-report-confirm]')?.textContent==='继续拆书');
     assert.equal(posts.length,before+1);assert.equal(job.status,'paused');await sameNode();
    }
    await back('characters');await guide();await back('plot');
    assert.equal(await primary.innerText(),status==='failed'?'重新分析':'继续拆书');
    assert.equal(await main.getAttribute('aria-busy'),'false');
    cases.push({width,hasReport,status,guideAndBothReturns:true,sameConnectedNode:true});
   }
   // Resume from the guide still goes through the original reviewed fee/CAS.
   await open('paused');await guide();const before=posts.length;
   await primary.click();await page.locator('#reportConfirmDialog[open]').waitFor();assert.equal(posts.length,before);
   await page.locator('#reportConfirmButton').click();await page.waitForFunction(()=>!document.querySelector('#reportConfirmDialog').open);
   assert.equal(posts.length,before+1);assert.equal(posts.at(-1),'start');assert.equal(job.status,'running');await sameNode();
   assert.equal(await page.locator('.deconstruction-guide').count(),1);assert.equal(await primary.isDisabled(),true);assert.equal(await main.getAttribute('aria-busy'),'false');
   cases.push({width,case:'guide resume uses existing fee confirmation and exact CAS'});
   await open('paused',false,'report_request_unknown');assert.match(await workflow.innerText(),/上次请求尚待确认/);await guide();assert.equal(await primary.isDisabled(),true);const writes=posts.length;
   await back('characters');assert.equal(await primary.isDisabled(),true);await guide();await back('plot');assert.equal(await primary.isDisabled(),true);assert.equal(posts.length,writes);
   cases.push({width,case:'unknown remains blocked in guide and both returns'});
   await open('completed',true);await guide();assert.equal(await workflow.isVisible(),false);await back('characters');await guide();await back('plot');assert.equal(await workflow.isVisible(),false);
   cases.push({width,case:'completed report keeps hidden single workflow and readable graph'});
   assert.deepEqual(errors,[]);
  }catch(e){await page.screenshot({path:path.join(out,`${width}-failure.png`)});console.error({out,width,errors});throw e;}
  finally{await context.close();}
 }
 const result={synthetic:true,out,count:cases.length,cases,screenshots};await fs.writeFile(path.join(out,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
