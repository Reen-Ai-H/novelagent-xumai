/* report-v2 UI contract against intercepted in-memory responses only.
 * No real service, model, account or author data is accessed. */
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {chromium}=require('playwright');
const {fixture,origin,root}=require('./test_stage38_frontend_browser.cjs');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 const out=await fs.mkdtemp(path.join(os.tmpdir(),'xumai-stage38-report-ui-'));
 const results=[];
 try{for(const width of [1440,390]){
  const context=await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce'}),page=await context.newPage();
  const {workspace,response}=fixture();
  let available=false,job=null,revision=1,formal=false,budgetFailure=false;
  let starts=0,posts=0;
  const errors=[],paths=[],sources=[],expectedHttpErrors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(['warning','error'].includes(m.type()))errors.push(m.text());});
  function current(){
   const value=structuredClone(response);value.source.revision=revision;
   if(!formal){value.result=null;value.active_run=null;value.effective_status='failed_retryable';value.run_status='failed_retryable';value.source_match=false;value.source.match=false;value.actions.retry=true;value.error={code:'synthetic_rule_failed',message:'基础索引未完成',retryable:true};}
   else{value.result.source_revision=revision;value.active_run.source_revision=revision;value.result.evidence.forEach(e=>e.source_revision=revision);}
   return value;
  }
  await context.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname;
   assert.equal(url.origin,origin);paths.push(`${req.method()} ${p}`);
   const send=(data,status=200)=>{
    if(status>=400)expectedHttpErrors.push(`Failed to load resource: the server responded with a status of ${status} (${status===409?'Conflict':'Service Unavailable'})`);
    return route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
   };
   if(p.startsWith('/static/')){const n=p.slice(8);assert.ok(/^[a-z0-9.-]+$/.test(n));return route.fulfill({status:200,contentType:n.endsWith('.css')?'text/css':n.endsWith('.svg')?'image/svg+xml':'text/javascript',body:await fs.readFile(path.join(root,'frontend',n))});}
   if(!p.startsWith('/api/'))return route.fulfill({status:200,contentType:'text/html',body:await fs.readFile(path.join(root,'frontend/index.html'))});
   if(p==='/api/auth/session')return send({authenticated:true,account:{account_id:'fake',email:'pipeline.reader@example.test'}});
   if(p==='/api/notifications')return send({notifications:[],unread_count:0});
   if(/\/model-budget$/.test(p))return budgetFailure?send({detail:{message:'预算暂时不可读'}},503):send({model_available:available,budget:{budget_cny:5,estimated_spent_cny:1.8,reserved_cny:0,remaining_cny:3.2}});
   if(/\/book$/.test(p))return send({job});
   if(/\/book\/start-report$/.test(p)){
    posts++;const body=req.postDataJSON();sources.push(body);
    assert.deepEqual(Object.keys(body).sort(),['expected_source_hash','expected_source_revision','expected_source_version_id']);
    assert.equal(body.expected_source_version_id,'v1');assert.equal(body.expected_source_hash,'a'.repeat(64));
    if(body.expected_source_revision!==revision)return send({detail:{code:'source_changed',message:'正文已更新，请重新确认本次范围。'}},409);
    starts++;job={kind:'report-v2',run_id:'run1',status:'running',stage:'draft',cursor:0,total:2,document_id:null,error_code:null,message:'正在生成报告'};return send({job});
   }
   if(/\/book\/pause$/.test(p)){job={...job,status:'paused'};return send({job});}
   if(/\/deconstruction$/.test(p))return send(current());
   if(p==='/api/independent/projects/p1')return send(workspace);
   throw Error(`Unexpected operation ${req.method()} ${p}`);
  });
  const url=origin+'/independent/p1?view=deconstruction&section=characters';
  const button=page.locator('[data-action=open-report-confirm]');
  const waitReady=()=>page.waitForFunction(()=>{const b=document.querySelector('[data-action=open-report-confirm]');return b && !b.disabled;});
  const screenshot=async name=>{
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   await page.screenshot({path:path.join(out,`${width}-${name}.png`),fullPage:true});
  };
  try{
   await page.goto(url);await button.waitFor();
   await page.waitForFunction(()=>document.querySelector('#reportWorkflow').textContent.includes('模型服务当前未启用'));
   assert.equal(await button.isDisabled(),true);assert.equal(posts,0);
   assert.equal(await page.locator('#deconstructionPageContent [data-action=deconstruction-retry]').count(),0);
   assert.equal(await page.locator('#workspaceToolsDialog').isVisible(),false);
   await screenshot('disabled-runtime');
   available=undefined;await page.reload();await page.waitForFunction(()=>document.querySelector('#reportWorkflow').textContent.includes('模型服务状态待确认'));
   assert.equal(await button.isDisabled(),true);assert.equal(posts,0);
   available=true;await page.reload();await waitReady();
   assert.equal(await button.innerText(),'开始拆书');
   await button.click();await page.locator('#reportConfirmDialog[open]').waitFor();
   assert.match(await page.locator('#reportConfirmScope').innerText(),/6 章/);
   assert.match(await page.locator('#reportConfirmBudget').innerText(),/3.2000/);
   await screenshot('fee-confirmation');
   await page.keyboard.press('Escape');assert.equal(posts,0);
   await page.waitForFunction(()=>document.querySelector('[data-action=open-report-confirm]')===document.activeElement);
   assert.equal(await button.evaluate(n=>n===document.activeElement),true);
   // A source changing after review must be rejected without silently rerouting.
   await button.click();await page.locator('#reportConfirmDialog[open]').waitFor();revision=2;
   await page.locator('#reportConfirmButton').click();
   await page.waitForFunction(()=>document.querySelector('#reportConfirmError').textContent.includes('正文已更新'));
   assert.equal(starts,0);assert.equal(posts,1);assert.equal(await page.locator('#reportConfirmButton').isDisabled(),true);
   await page.locator('[data-action=close-report-confirm]').first().click();
   // Availability can change while the review dialog is open; recheck before POST.
   await waitReady();await button.click();await page.locator('#reportConfirmDialog[open]').waitFor();available=false;
   await page.locator('#reportConfirmButton').click();await page.waitForFunction(()=>document.querySelector('#reportConfirmError').textContent.includes('未启用'));
   assert.equal(posts,1);await page.locator('[data-action=close-report-confirm]').first().click();
   available=true;await page.reload();await waitReady();await button.click();await page.locator('#reportConfirmDialog[open]').waitFor();
   await page.locator('#reportConfirmButton').evaluate(n=>{n.click();n.click();});
   await page.waitForFunction(()=>!document.querySelector('#reportConfirmDialog').open);
   assert.equal(starts,1);assert.equal(posts,2);assert.equal(sources[1].expected_source_revision,2);
   assert.equal(await button.isDisabled(),true);await screenshot('running');
   await page.locator('[data-action=pause-report]').click();await waitReady();
   assert.equal(await button.innerText(),'继续拆书');assert.equal(job.status,'paused');
   await button.click();await page.locator('#reportConfirmDialog[open]').waitFor();await page.locator('#reportConfirmButton').click();
   await page.waitForFunction(()=>!document.querySelector('#reportConfirmDialog').open);assert.equal(starts,2);assert.equal(sources[2].expected_source_revision,2);
   await page.reload();await page.waitForFunction(()=>document.querySelector('#reportWorkflow').textContent.includes('后台') || document.querySelector('#reportWorkflow').textContent.includes('分析正文'));
   assert.equal(await button.isDisabled(),true);assert.equal(starts,2);
   await page.locator('[data-action=deconstruction-open-editor]').first().click();await page.locator('#chapterEditor').waitFor();
   assert.equal(job.status,'running');
   job.stage='review';await page.goto(url);await button.waitFor();assert.equal(await button.isDisabled(),true);
   formal=true;job={...job,status:'completed',stage:'completed',document_id:'doc',message:'报告已采用'};
   await page.locator('.total-graph-scroll').waitFor({timeout:12000});
   assert.equal(await page.locator('.total-graph-node').count(),6);await waitReady();
   assert.equal(await button.innerText(),'重新分析');assert.equal(starts,2);
   await screenshot('auto-published');
   // A failed later job retains the last valid report and shows its real reason.
   job={kind:'report-v2',run_id:'run2',status:'failed',stage:'review',cursor:1,total:2,document_id:null,error_code:'synthetic_invalid',message:'合成检查未通过，请稍后重试。'};
   await page.reload();await page.locator('.total-graph-scroll').waitFor();await waitReady();
   assert.match(await page.locator('#reportWorkflow').innerText(),/原报告保留/);
   budgetFailure=true;await page.reload();await page.waitForFunction(()=>document.querySelector('#reportWorkflow').textContent.includes('预算'));
   assert.equal(await button.isDisabled(),true);
   budgetFailure=false;await page.locator('[data-action=refresh-report-status]').click();await waitReady();
   assert.equal(await page.locator('.total-graph-node').count(),6);
   assert.deepEqual([...errors].sort(),[...expectedHttpErrors].sort(),'Only explicitly injected HTTP errors may reach the console');
   assert.ok(!paths.some(p=>/\/retry$|\/rebuild$|\/book\/start$|analyze-preview/.test(p)));
   results.push({width,starts,posts,expectedHttpErrors:expectedHttpErrors.length,unexpectedConsoleErrors:errors.length-expectedHttpErrors.length});
  }catch(error){await page.screenshot({path:path.join(out,`${width}-failure.png`),fullPage:true});console.error({url:page.url(),out,errors,starts,posts});throw error;}
  finally{await context.close();}
 }
 console.log(JSON.stringify({synthetic:true,out,results},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
