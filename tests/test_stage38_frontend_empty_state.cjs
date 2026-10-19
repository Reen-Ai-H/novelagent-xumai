/* First-report empty state: real Chromium DOM, all traffic intercepted.
 * No server, author data, external network, model or paid request. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {chromium}=require('playwright');
const {fixture,root}=require('./test_stage38_frontend_browser.cjs');
const origin='http://empty-state.invalid';
(async()=>{
 const out=await fs.mkdtemp(path.join(os.tmpdir(),'xumai-stage38-empty-state-'));
 const browser=await chromium.launch({headless:true,channel:'chrome'}),cases=[],screenshots=[];
 try{for(const [width,height]of [[1440,900],[1024,768],[390,844]]){
  const context=await browser.newContext({viewport:{width,height},reducedMotion:'reduce',serviceWorkers:'block'}),page=await context.newPage();
  const {workspace,response}=fixture(),errors=[],posts=[],calls=[];
  let job=null,formal=false,historical=false,available=true,holdReport=null;
  const task=(status,stage)=>({kind:'report-v2',run_id:'synthetic-run',status,stage,cursor:1,total:3,document_id:status==='completed'?'doc':null,error_code:null,message:status==='failed'?'本次核对未通过。':''});
  const current=()=>{
   const data=structuredClone(response);
   if(!formal)Object.assign(data,{effective_status:'failed_retryable',run_status:'failed_retryable',source_match:false,result:null,active_run:null,focus_document_id:'',error:{code:'synthetic_rule_failed',message:'基础索引未完成',retryable:true},actions:{retry:true,rebuild:false}});
   if(!formal){data.source_match=false;data.source.match=false;}
   if(historical){data.focus_document_id='history';data.result.document_id='history';data.active_run.document_id='history';data.result.evidence.forEach(e=>e.document_id='history');}
   return data;
  };
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(['warning','error'].includes(m.type()))errors.push(m.text());});
  await context.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname;
   assert.equal(url.origin,origin,'No request may leave the synthetic origin');calls.push(`${req.method()} ${p}`);
   const json=data=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
   if(p.startsWith('/static/')){const name=p.slice(8);assert.match(name,/^[a-z0-9.-]+$/);let body=await fs.readFile(path.join(root,'frontend',name));
    if(name==='app.js'){
     const hook='  start();\n})();',source=body.toString('utf8');assert.equal(source.split(hook).length,2);
     body=source.replace(hook,'  window.__emptyStateAudit={renderReportWorkflow,activateDeconstructionSection,selectDeconstructionVolume,loadDeconstructionWorkspace};\n'+hook);
    }
    return route.fulfill({contentType:name.endsWith('.css')?'text/css':name.endsWith('.svg')?'image/svg+xml':'text/javascript',body});}
   if(!p.startsWith('/api/'))return route.fulfill({contentType:'text/html',body:await fs.readFile(path.join(root,'frontend/index.html'))});
   if(p==='/api/auth/session')return json({authenticated:true,account:{account_id:'synthetic',email:'empty.reader@example.test'}});
   if(p==='/api/notifications')return json({notifications:[],unread_count:0});
   if(p.endsWith('/model-budget'))return json({model_available:available,budget:{budget_cny:5,estimated_spent_cny:1,reserved_cny:0,remaining_cny:4}});
   if(p.endsWith('/book'))return json({job});
   if(p.endsWith('/deconstruction/guide'))return json({characters:[]});
   if(p.endsWith('/book/pause')){assert.equal(req.method(),'POST');posts.push(p);job={...job,status:'paused'};return json({job});}
   if(p.endsWith('/book/start-report')){
    assert.equal(req.method(),'POST');assert.deepEqual(req.postDataJSON(),{expected_source_version_id:'v1',expected_source_revision:1,expected_source_hash:'a'.repeat(64)});
    posts.push(p);job=task('running','draft');return json({job});
   }
   if(p.endsWith('/deconstruction')){if(holdReport)await holdReport;return json(current());}
   if(p==='/api/independent/projects/p1')return json(workspace);
   throw Error(`Unexpected synthetic operation ${req.method()} ${p}`);
  });
  const workflow=page.locator('#reportWorkflow'),start=workflow.locator('[data-action=open-report-confirm]');
  const title=()=>workflow.locator('h2').innerText();
  async function navigate(section='characters',extra=''){
   await page.goto(`${origin}/independent/p1?view=deconstruction&section=${section}${extra}`);
   await page.waitForFunction(()=>document.querySelector('#reportWorkflow')?.textContent && !document.querySelector('#reportWorkflow')?.textContent.includes('正在读取状态'));
   await page.evaluate(()=>document.fonts.ready);
  }
  async function geometry(){
   const m=await workflow.evaluate(n=>{
    const r=n.getBoundingClientRect(),main=document.querySelector('#deconstructionPageContent').getBoundingClientRect();
    return {body:n.parentElement.id,inside:r.left>=main.left-.5&&r.right<=main.right+.5,visible:r.top>=0&&r.bottom<=innerHeight-64,overflow:document.documentElement.scrollWidth>innerWidth};
   });
   assert.equal(m.body,'deconstructionPageContent');assert.equal(m.inside,true);assert.equal(m.visible,true);assert.equal(m.overflow,false);
   assert.deepEqual(await workflow.locator('.report-stage-list strong').allTextContents(),['整理','核对','完成']);
   assert.equal(await workflow.locator('.report-stage-list li').nth(2).getAttribute('aria-current'),null,'Completion is never inferred from a job alone');
   assert.equal(await page.locator('.deconstruction-header-actions #reportWorkflow').count(),0);
   assert.equal(await page.locator('#deconstructionStatusPill').isVisible(),false);
   assert.equal(await page.locator('[data-action=open-report-confirm]').count(),1,'One existing action, not a cloned second control');
   assert.doesNotMatch(await workflow.innerText(),/\d+%|倒计时|离开页面也会继续|原报告保留/);
  }
  async function shot(name){await geometry();const file=path.join(out,`${width}x${height}-${name}.png`);await page.screenshot({path:file});screenshots.push(file);}
  try{
   for(const section of ['characters','plot'])for(const [stage,index]of [['queued',0],['draft',0],['review',1],['revise',1],['verify',1],['adopt',1]]){
    job=task('running',stage);await navigate(section);await geometry();
    assert.equal(await workflow.locator('[aria-current=step]').innerText(),`${index+1}`.padStart(2,'0')+'\n'+['整理','核对'][index]);
    assert.equal(await start.isDisabled(),true);assert.equal(await workflow.locator('[data-action=pause-report]').isEnabled(),true);
    if(stage==='adopt')assert.equal(await title(),'正在保存报告');
    if(section==='characters'&&stage==='draft')await shot('people-draft');
    if(section==='plot'&&stage==='review')await shot('plot-review');
    cases.push({width,section,stage,active:index+1});
   }
   // Pause by keyboard, refresh while paused, then review and cancel/resume.
   job=task('running','review');await navigate('plot');
   await workflow.locator('[data-action=pause-report]').focus();await page.keyboard.press('Enter');
   await page.waitForFunction(()=>document.querySelector('#reportWorkflow h2')?.textContent==='拆书已暂停');
   assert.equal(await start.innerText(),'继续拆书');assert.equal(job.status,'paused');await shot('plot-paused');
   await page.reload();await start.waitFor();await page.waitForFunction(()=>!document.querySelector('[data-action=open-report-confirm]')?.disabled);
   assert.equal(await title(),'拆书已暂停');
   const before=posts.length;
   await start.focus();await page.keyboard.press('Enter');await page.locator('#reportConfirmDialog[open]').waitFor();
   assert.equal(posts.length,before);assert.match(await page.locator('#reportConfirmBudget').innerText(),/4.0000/);
   await page.keyboard.press('Escape');await page.waitForFunction(()=>document.activeElement?.dataset.action==='open-report-confirm');assert.equal(posts.length,before);
   await page.keyboard.press('Enter');await page.locator('#reportConfirmDialog[open]').waitFor();
   await page.locator('#reportConfirmButton').focus();await page.keyboard.press('Enter');
   await page.waitForFunction(()=>!document.querySelector('#reportConfirmDialog').open);
   assert.equal(posts.length,before+1);assert.ok(posts.at(-1).endsWith('/start-report'));
   await page.waitForFunction(()=>document.querySelector('#reportWorkflow h2')?.textContent==='正在整理');
   // A polling repaint must not throw keyboard focus out of the controls.
   await workflow.locator('[data-action=pause-report]').focus();
   await page.waitForTimeout(3400);assert.equal(await page.evaluate(()=>document.activeElement?.dataset.action),'pause-report');
   cases.push({width,case:'keyboard pause / reload / fee cancellation / resume / polling focus',posts:posts.length});
   job=task('failed','verify');await navigate('plot');assert.equal(await title(),'拆书未完成');
   assert.equal(await start.innerText(),'重新分析');assert.match(await workflow.innerText(),/本次核对未通过/);await shot('plot-failed');
   await start.focus();await page.keyboard.press('Space');await page.locator('#reportConfirmDialog[open]').waitFor();await page.keyboard.press('Escape');
   cases.push({width,case:'failure reuses fee confirmation'});
   job={...task('failed','draft'),error_code:'report_request_unknown'};await navigate();
   assert.equal(await start.isDisabled(),true);assert.match(await workflow.innerText(),/上次请求尚待确认/);cases.push({width,case:'unknown blocks retry'});
   job=null;available=false;await navigate();assert.equal(await title(),'尚未开始');assert.equal(await start.isDisabled(),true);assert.match(await workflow.innerText(),/模型服务当前未启用/);
   cases.push({width,case:'unavailable runtime blocks first start'});available=true;
   // A completed task while the actual report is still loading is not ready.
   let release;
   // Start with adopt, then let the existing 3-second poll discover completion.
   holdReport=null;job=task('running','adopt');await navigate('plot');
   holdReport=new Promise(resolve=>release=resolve);job=task('completed','completed');
   await page.waitForFunction(()=>document.querySelector('#reportWorkflow h2')?.textContent==='报告尚未载入',{},{timeout:6000});
   await shot('plot-completed-awaiting-report');assert.equal(await page.locator('.report-stage-list .is-done').count(),0);
   formal=true;holdReport=null;release();await page.locator('.total-graph-scroll').waitFor();
   assert.equal(await workflow.locator('.report-stage-list').count(),0);assert.equal(await workflow.isVisible(),false);
   assert.equal(await page.locator('#deconstructionStatusPill').innerText(),'模型报告已就绪');
   cases.push({width,case:'completed waits for real report, then removes body state'});
   // New-source/old-completed cannot masquerade as a new-source completion.
   formal=false;await navigate();assert.equal(await title(),'报告尚未载入');await geometry();cases.push({width,case:'old completed without displayable report is not ready'});
   formal=true;historical=true;
   for(const status of ['running','paused','failed','completed']){
    job=task(status,status==='completed'?'completed':'review');await navigate('characters','&volume=history&map=total');
    await page.locator('.total-graph-scroll').waitFor();assert.equal(await page.locator('.total-graph-node').count(),6);
    assert.equal(await workflow.locator('.report-stage-list').count(),0);assert.equal(await workflow.locator('h2').count(),0);
    assert.equal(await workflow.evaluate(n=>n.parentElement.className),'deconstruction-header-actions');
    assert.ok(page.url().includes('volume=history'));assert.equal(await page.locator('#deconstructionPageContent #reportWorkflow').count(),0);
    cases.push({width,case:`historical report retained during ${status}`});
   }
   const file=path.join(out,`${width}x${height}-people-history-preserved.png`);await page.screenshot({path:file});screenshots.push(file);
   // Same mounted page: a readable report/history/guide is not busy simply
   // because the preceding first-report empty state was running.
   const content=page.locator('#deconstructionPageContent');
   for(const target of ['guide','report','history']){
    formal=false;historical=false;job=task('running','review');await navigate('plot');
    assert.equal(await content.getAttribute('aria-busy'),'true');
    if(target==='guide'){
     await page.evaluate(()=>window.__emptyStateAudit.activateDeconstructionSection('guide'));
     await page.waitForFunction(()=>document.querySelector('[data-guide-note]')?.textContent==='0 卷生效');
    }else{
     formal=true;historical=target==='history';
     if(historical)await page.evaluate(()=>window.__emptyStateAudit.selectDeconstructionVolume('history'));
     else await page.evaluate(()=>window.__emptyStateAudit.loadDeconstructionWorkspace('p1',{silent:true,documentId:'doc'}));
     await page.locator('.total-graph-scroll').waitFor();
     assert.equal(await page.locator('.total-graph-node').count(),6);
    }
    assert.equal(await content.getAttribute('aria-busy'),'false',`Running empty -> ${target} must clear busy`);
    // Exercise the workflow-only repaint too, independently of the full
    // reader's initial aria-busy assignment. This is the residual-state case.
    assert.equal(await content.evaluate(n=>{
     n.setAttribute('aria-busy','true');window.__emptyStateAudit.renderReportWorkflow();return n.getAttribute('aria-busy');
    }),'false',`${target} workflow-only repaint must clear residual busy`);
    cases.push({width,case:`running empty -> ${target}; workflow-only residual busy reset`});
   }
   assert.deepEqual(errors,[]);assert.ok(!calls.some(p=>/analyze-preview|\/book\/start$|\/retry$|\/rebuild$/.test(p)));
  }catch(error){await page.screenshot({path:path.join(out,`${width}-failure.png`)});console.error({out,width,errors});throw error;}
  finally{await context.close();}
 }
 const results={synthetic:true,out,caseCount:cases.length,cases,screenshots};await fs.writeFile(path.join(out,'results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results,null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
