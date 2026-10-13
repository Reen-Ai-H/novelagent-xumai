/* Large synthetic, real-HTTP fixture and browser acceptance. No interception,
 * private manuscript, model calls, or direct store writes. Run with --setup-only
 * to leave two projects for manual CUA review; fixture.json has login + URLs.
 * Setup: original .venv/bin/python tests/browser_server.py --port 8045
 * NODE_PATH=<Playwright node_modules> node tests/browser_stage35_reading.cjs
 */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const vm = require('node:vm');
const {chromium} = require('playwright');
const origin = process.env.XUMAI_BROWSER_URL || 'http://127.0.0.1:8045';
assert.equal(new URL(origin).hostname, '127.0.0.1');
const out = path.join(__dirname,'..','test-results','stage35-reading');
// Deliberately mechanical invented names, unrelated to any private work.
const names = Array.from('赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳').map(x=>`${x}测`);
const lines = Array.from({length:780},(_,i)=>`${names[i%60]}拿起第${String(i+1).padStart(4,'0')}号木牌，${names[(i+1)%60]}把木牌交给${names[i%60]}。`);
const manuscript = [0,1,2].map(c=>`第${c+1}章 合成核对${c+1}\n${lines[c*260]}\n人物：${names.join('、')}。\n${lines.slice(c*260+1,(c+1)*260).join('\n')}`).join('\n');
function modelReport() {
  const claim = (text,q='Q0',status='fact')=>({text,status,evidence_ids:[q]});
  const events = Array.from({length:180},(_,i)=>({id:`E${i}`,title:`合成大事件 ${String(i+1).padStart(3,'0')}`,
    chapter_number:Math.floor(i/60)+1, story_time:`正文序号 ${i+1}`,actor_ids:[`C${i%60}`,`C${(i+1)%60}`],
    action:claim(lines[Math.floor(i/60)*260+i%60],`Q${i}`), consequence:claim(`木牌 ${i+1} 完成交接。`,`Q${i}`),
    sub_events:Array.from({length:20},(_,j)=>({title:`细节 ${j+1}`, ...claim(`第 ${i+1} 项的核对细节 ${j+1}。`,`Q${i}`)}))}));
  return {schema_version:'1',producer:'synthetic-ui-volume-check',title:'合成大规模报告（非文学质量结论）',scope:'第1至3章',chapter_numbers:[1,2,3],
    findings:[{id:'F1',title:'合成核对',...claim('木牌逐次交接。')}],
    characters:names.map((name,i)=>({id:`C${i}`,entity_key:`synthetic${i}`,name,aliases:[`合成编号${i+1}`],role:i<10?'主要人物':'配角',
      identity:claim(`${name}参与木牌交接。`),motivation:claim('当前材料不足以判断心理动机。','Q0','unknown'),
      portrait:claim('按序号核对物品；这是合成摘要。','Q0','inferred'),change:claim(`参与第 ${i+1} 号交接。`),
      insights:[{title:'核对木牌',...claim('人物参与交接。')}]})),events,
    relations:Array.from({length:350},(_,i)=>({from_id:`E${i%180}`,to_id:`E${(i%180+1+Math.floor(i/180))%180}`,kind:'follows',...claim(`仅记录先后关系 ${i+1}，不表示因果。`)})),
    story_order:events.map(e=>e.id),time_note:'合成报告按正文顺序排列，未额外推断故事时间。',
    evidence:events.map((e,i)=>({id:`Q${i}`,chapter_number:e.chapter_number,quote:e.action.text})),open_questions:['合成疑问可在这里核对。'],contradictions:[]};
}
async function setup(browser) {
  const context = await browser.newContext(); const page = await context.newPage();
  const email=`stage35-large-${Date.now()}@example.test`;
  await page.goto(`${origin}/login`); await page.locator('#emailInput').fill(email); await page.locator('#emailSubmitButton').click(); await page.waitForURL('**/library');
  async function project(title) {
    await page.goto(`${origin}/library`); await page.locator('#newProjectButton').click(); await page.locator('[data-mode="independent"]').click();
    await page.locator('#projectTitleInput').fill(title); await page.locator('#createProjectButton').click(); await page.waitForURL('**/independent/*');
    const url=page.url().split('?')[0],id=new URL(url).pathname.split('/').pop();
    await page.locator('#importFileInput').setInputFiles({name:'大规模合成.txt',mimeType:'text/plain',buffer:Buffer.from(manuscript)});
    await page.locator('#analyzeWholeImport').check();
    const paid=[];page.on('request',r=>{if(r.url().endsWith('/book/start'))paid.push(r.url());});
    await page.locator('[data-action="confirm-import"]').click();
    await page.locator('#deconstructionStatusPill.is-completed').waitFor({timeout:60000});
    assert.deepEqual(paid,[],'Import checkbox must not start paid analysis');
    const response=await context.request.get(`${origin}/api/independent/projects/${id}/deconstruction`);assert.equal(response.status(),200);
    return {id,url,data:await response.json()};
  }
  const rule=await project('合成验收 · 780条原文记录');
  assert.ok(rule.data.result.report.plot.events.length>=700,'Need genuinely large rule output');
  const model=await project('合成验收 · 60人物180大事件');
  const report=modelReport();
  const imported=await context.request.post(`${origin}/api/independent/projects/${model.id}/deconstruction/import`,{data:{report}});
  assert.equal(imported.status(),200,await imported.text());model.data=await imported.json();
  const fixture={email,ruleUrl:`${rule.url}?view=deconstruction&section=plot`,rulePeopleUrl:`${rule.url}?view=deconstruction&section=characters`,
    modelUrl:`${model.url}?view=deconstruction&volume=${model.data.result.document_id}&section=plot`,
    modelPeopleUrl:`${model.url}?view=deconstruction&volume=${model.data.result.document_id}&section=characters`,
    ruleCounts:{characters:rule.data.result.report.characters.characters.length,events:rule.data.result.report.plot.events.length,relations:rule.data.result.report.plot.relations.length},modelCounts:{characters:60,events:180,relations:350},
    setup:'Start tests/browser_server.py on 8045 from this worktree; run this script with --setup-only. Log in with email above (isolated dev login), then open the URLs. No production data or model calls.'};
  await fs.writeFile(path.join(out,'fixture.json'),JSON.stringify(fixture,null,2));
  const storageState=await context.storageState();await context.close();
  return {fixture,storageState,ruleResponse:rule.data,rule:rule.data.result.report,model:report};
}
async function verifyUpgradeAdapter(fixture) {
  // Narrow compatibility probe for the forwarded engine-update contract.
  // This is a unit probe, not a claim that the baseline server supports it.
  const source=await fs.readFile(path.join(__dirname,'..','frontend','app.js'),'utf8');
  const hook='  start();\n})();';assert.ok(source.includes(hook));
  const sandbox={window:{},document:{querySelector:()=>null,querySelectorAll:()=>[]},URL,URLSearchParams};
  vm.runInNewContext(source.replace(hook,'  globalThis.normalize = normalizeDeconstructionResponse;\n})();'),sandbox);
  const payload=structuredClone(fixture.ruleResponse);
  Object.assign(payload,{effective_status:'rebuild_required',update_available:true,required_engine_revision:'synthetic-next',error:{code:'engine_update_available',message:'显式升级',retryable:false}});
  payload.actions.rebuild=true;
  assert.equal(sandbox.normalize(payload).result.documentId,fixture.ruleResponse.result.document_id);
  for(const change of [{update_available:false},{run_status:'running'},{source_match:false},{error:{code:'pending_changes'}},{result:{...payload.result,source_hash:'b'.repeat(64)}}]) {
    assert.throws(()=>sandbox.normalize({...payload,...change}),'Upgrade must not bypass source/run guards');
  }
}
async function allIds(root,selector,attribute) {
  const seen=[];const pages=root.locator(':scope > .report-browser-pages select');
  const count=await pages.locator('option').count();
  for(let i=1;i<=count;i++) {
    if(count>1) await pages.selectOption(String(i));
    seen.push(...await root.locator(`:scope > .report-browser-items ${selector}`).evaluateAll((nodes,attr)=>nodes.map(n=>n.getAttribute(attr)),attribute));
  }
  return seen;
}
async function capture(page,width,label,firstSelector) {
  await page.evaluate(()=>scrollTo(0,0));
  const metrics=await page.evaluate(selector=>({width:innerWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth,
    elements:document.querySelectorAll('*').length,visibleText:document.body.innerText.length,firstTop:document.querySelector(selector)?.getBoundingClientRect().top,
    summaryBottom:(document.querySelector(selector)?.querySelector('.analysis-node-summary') || document.querySelector(selector)?.querySelector('p, strong'))?.getBoundingClientRect().bottom}),firstSelector);
  assert.ok(metrics.scroll<=width && metrics.body<=width,`${label}: overflow ${JSON.stringify(metrics)}`);
  assert.ok(metrics.elements<4000,`${label}: DOM not bounded ${JSON.stringify(metrics)}`);
  assert.ok(metrics.visibleText<18000,`${label}: excessive primary text ${JSON.stringify(metrics)}`);
  assert.ok(metrics.firstTop<780 && metrics.summaryBottom<900,`${label}: first actual summary below first screen ${JSON.stringify(metrics)}`);
  await page.screenshot({path:path.join(out,`${width}-${label}.png`),fullPage:true});return {label,...metrics};
}
async function verify(browser,fixture,width) {
  const context=await browser.newContext({storageState:fixture.storageState,viewport:{width,height:900},reducedMotion:'reduce'});
  const page=await context.newPage();const errors=[],metrics=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(['warning','error'].includes(m.type()))errors.push(m.text());});
  page.on('request',r=>{assert.equal(new URL(r.url()).origin,origin);assert.ok(!r.url().endsWith('/book/start'));});
  const rule=fixture.rule;
  try {
    await page.goto(fixture.fixture.rulePeopleUrl);await page.locator('[data-rule-people]').waitFor();
    assert.equal(await page.getByRole('tab',{name:/人物/}).getAttribute('aria-selected'),'true');
    assert.equal(await page.locator('#deconstructionSubnav [data-section="characters"]').getAttribute('aria-current'),'page');
    assert.match(await page.locator('#deconstructionStatusPill').innerText(),/规则/);
    metrics.push(await capture(page,width,'rule-people','[data-reading-person]'));
    const people=page.locator('[data-rule-people]');
    await people.locator(':scope > nav [data-browser-page="2"]').click();
    assert.equal(await people.locator(':scope > .report-browser-items').evaluate(n=>n===document.activeElement),true);
    assert.ok(await people.locator(':scope > .report-browser-items').evaluate(n=>n.getBoundingClientRect().top<40),'pagination should scroll to the new results');
    assert.deepEqual(new Set(await allIds(people,'[data-reading-person]','data-reading-person')),new Set(rule.characters.characters.map(p=>p.item_id)));
    const search=people.locator('input[type=search]');
    await search.fill(names[59]);assert.equal(await search.evaluate(n=>n===document.activeElement),true);
    assert.equal(await people.locator('[data-reading-person] h3').textContent(),names[59]);
    const beforeComposition=await people.locator('[data-reading-person]').count();
    await search.evaluate(node=>{node.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true}));node.value='暂存组合输入';node.dispatchEvent(new InputEvent('input',{bubbles:true,isComposing:true}));});
    assert.equal(await people.locator('[data-reading-person]').count(),beforeComposition,'IME composition must not redraw prematurely');
    await search.evaluate(node=>node.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true})));
    assert.equal(await people.locator('[data-reading-person]').count(),0);
    await page.locator('#deconstructionSubnav [data-section="plot"]').click();await page.locator('[data-rule-segments]').waitFor();
    assert.equal(new URL(page.url()).searchParams.get('section'),'plot');await page.reload();await page.locator('[data-rule-segments]').waitFor();
    metrics.push(await capture(page,width,'rule-plot','[data-reading-segment]'));
    await page.locator('.depth-range-options > summary').click();
    await page.locator('#depthChapterFilter').selectOption(rule.chapters[1].chapter_id);
    assert.equal(await page.locator('#depthChapterFilter').evaluate(n=>n===document.activeElement),true);
    assert.ok((await page.locator('[data-rule-segments] .reading-segment .eyebrow').allTextContents()).every(text=>text.includes('第 2 章')));
    await page.locator('#depthChapterFilter').selectOption('');
    await page.locator('.depth-range-options > summary').click();
    await page.locator('.depth-events-section > summary').click();
    const events=page.locator('[data-rule-events]');
    assert.deepEqual(new Set(await allIds(events,'[data-reading-event]','data-reading-event')),new Set(rule.plot.events.map(e=>e.item_id)));
    const last=rule.plot.events.at(-1);
    await events.locator('input[type=search]').fill(last.action);
    assert.ok(await events.locator(`[data-reading-event="${last.item_id}"]`).count());
    await events.locator(`[data-reading-event="${last.item_id}"] summary`).click();
    await events.locator(`[data-reading-event="${last.item_id}"] .deconstruction-evidence-link`).first().click();
    await page.locator('#deconstructionEvidenceDialog[open]').waitFor();await page.locator('.deconstruction-evidence-dialog-card.is-current').waitFor();
    await page.locator('#dismissDeconstructionEvidenceButton').click();
    await events.locator('input[type=search]').fill('绝无匹配的合成串xyz');await events.locator('[data-browser-clear]').click();
    assert.equal(await events.locator('input[type=search]').inputValue(),'');
    const relationDetails=page.locator('details[data-browser-lazy="all-event-relations"]');await relationDetails.locator('summary').click();
    const relationRoot=relationDetails.locator('[data-browser-slot]');
    await relationRoot.locator(':scope > form').waitFor();
    let total=0;const relationPages=relationRoot.locator(':scope > nav select');const pages=await relationPages.locator('option').count();
    for(let n=1;n<=pages;n++){if(pages>1)await relationPages.selectOption(String(n));total+=await relationRoot.locator('.depth-relation-card').count();}
    assert.equal(total,rule.plot.relations.length,'Every relation must remain reachable');
    await page.goto(fixture.fixture.modelPeopleUrl);await page.locator('.analysis-person-link').first().waitFor();
    metrics.push(await capture(page,width,'model-people','.analysis-person'));
    const modelPeople=page.locator('[data-model-people]');
    assert.deepEqual(new Set(await allIds(modelPeople,'.analysis-person-link','data-report-person')),new Set(fixture.model.characters.map(p=>p.id)));
    await modelPeople.locator('input[type=search]').fill(names[59]);await page.locator('.analysis-person-link').click();
    await page.locator('[data-report-back]').click();assert.equal(await page.locator('.analysis-person-link').evaluate(n=>n===document.activeElement),true);
    await page.goto(fixture.fixture.modelUrl);await page.locator('.analysis-node').first().waitFor();
    metrics.push(await capture(page,width,'model-plot','.analysis-node'));
    const modelEvents=page.locator('[data-model-events]');
    assert.deepEqual(new Set(await allIds(modelEvents,'.analysis-node','data-report-node')),new Set(fixture.model.events.map(e=>e.id)));
    await modelEvents.locator('input[type=search]').fill('合成大事件 180');await page.locator('[data-report-node="E179"]').click();
    assert.equal(await page.locator('.analysis-node-detail h3').textContent(),'合成大事件 180');
    await page.locator('.analysis-node-detail .analysis-proof summary').first().click();
    const [response]=await Promise.all([page.waitForResponse(r=>r.url().includes('/evidence/Q179')),page.locator('.analysis-node-detail .deconstruction-evidence-link').first().click()]);
    assert.equal(new URL(response.url()).searchParams.get('document_id'),new URL(fixture.fixture.modelUrl).searchParams.get('volume'));
    await page.locator('#deconstructionEvidenceDialog[open]').waitFor();await page.locator('#dismissDeconstructionEvidenceButton').click();
    assert.deepEqual(errors,[]);return {width,metrics,ruleEventsReached:rule.plot.events.length,ruleRelationsReached:total,modelEventsReached:180,modelPeopleReached:60,errors};
  } catch(e) {await page.screenshot({path:path.join(out,`${width}-failure.png`),fullPage:true});throw e;} finally {await context.close();}
}
(async()=>{await fs.mkdir(out,{recursive:true});const browser=await chromium.launch({headless:true,channel:process.env.XUMAI_BROWSER_CHANNEL || 'chrome'});
  try{const fixture=await setup(browser);console.log(JSON.stringify(fixture.fixture));await verifyUpgradeAdapter(fixture);if(process.argv.includes('--setup-only'))return;
    const results=[];for(const width of [1440,1024,390])results.push(await verify(browser,fixture,width));
    const result={browser:browser.version(),synthetic:true,results};await fs.writeFile(path.join(out,'report.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
