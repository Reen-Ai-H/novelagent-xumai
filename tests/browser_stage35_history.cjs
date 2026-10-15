/* History UX: actual renderer + synthetic legacy upgrade/revision cases, then real-HTTP
 * history navigation on the isolated reading fixture. No model/store writes.
 * Prerequisite: browser_stage35_reading.cjs --setup-only on the same origin. */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const vm = require('node:vm');
const {chromium} = require('playwright');
const root = path.join(__dirname, '..');
const origin = process.env.XUMAI_BROWSER_URL || 'http://127.0.0.1:8045';
assert.equal(new URL(origin).hostname, '127.0.0.1');
const out = path.join(root, 'test-results/stage35-history');
(async()=>{
  await fs.mkdir(out,{recursive:true});
  const source = await fs.readFile(path.join(root,'frontend/app.js'),'utf8');
  const hook='  start();\n})();';assert.ok(source.includes(hook));
  const sandbox={window:{},document:{querySelector:()=>null,querySelectorAll:()=>[]},URL,URLSearchParams};
  vm.runInNewContext(source.replace(hook,`  globalThis.historyUX = {normalizeHistoryItem, renderDeconstructionHistoryItem,
    normalizeDeconstructionResponse, legacyResult(data) {
      state.deconstructionWorkspace=data; state.deconstructionView='characters';
      return renderDeconstructionResult(data);
    }};\n})();`),sandbox);
  const {normalizeHistoryItem:normalize,renderDeconstructionHistoryItem:render,
    normalizeDeconstructionResponse:normalizeReport,legacyResult}=sandbox.historyUX;
  const raw={document_id:'history-legacy-document',status:'completed',analysis_contract_version:'2.0',engine_revision:null,
    source_version_id:'source-do-not-display',source_revision:1,source_hash:'source-hash-do-not-display',
    created_at:'2026-10-13T01:02:01Z',completed_at:'2026-10-13T01:02:03Z'};
  const old=normalize(raw),current=normalize({...raw,document_id:'history-current-document',engine_revision:'synthetic.rules.2',completed_at:'2026-10-13T01:02:04Z'});
  const data={source:{versionId:old.sourceVersionId,revision:1,contentHash:old.sourceHash},requiredEngineRevision:'synthetic.rules.2',volumes:[],result:{documentId:current.documentId}};
  assert.equal(current.engineRevision,'synthetic.rules.2');
  const oldHTML=render(data,old),currentHTML=render(data,current);
  assert.match(oldHTML,/旧版规则/);assert.match(currentHTML,/现行规则/);
  assert.ok(!oldHTML.includes('aria-current="true"'));assert.ok(currentHTML.includes('aria-current="true"'));
  assert.match(oldHTML,/生成于[^<]+:03/);assert.match(currentHTML,/生成于[^<]+:04/);
  const viewingOld=render({...data,result:{documentId:old.documentId}},old);
  assert.match(viewingOld,/旧版规则/);assert.match(viewingOld,/当前查看/);assert.ok(!viewingOld.includes('现行规则'));
  const missing=render({...data,requiredEngineRevision:null},normalize({...raw,created_at:null,completed_at:null}));
  assert.match(missing,/规则版本未记录/);assert.match(missing,/时间未记录/);
  const invalid=render(data,normalize({...raw,completed_at:'not-a-date'}));assert.match(invalid,/创建于/);assert.ok(!invalid.includes('Invalid Date'));
  const historical=render({...data,source:{...data.source,contentHash:'different'}},old);
  assert.ok(!historical.includes('data-action="deconstruction-volume"'));assert.match(historical,/历史证据保留只读/);
  const model=render(data,normalize({...raw,document_id:current.documentId,analysis_contract_version:'model.1'}));
  assert.match(model,/模型报告/);assert.ok(!model.includes('现行规则')&&!model.includes('旧版规则'));
  const fixture=JSON.parse(await fs.readFile(process.env.XUMAI_BROWSER_FIXTURE || path.join(root,'test-results/stage35-reading/fixture.json'),'utf8'));
  assert.equal(new URL(fixture.modelUrl).origin,origin);
  const browser=await chromium.launch({headless:true,channel:process.env.XUMAI_BROWSER_CHANNEL || 'chrome'}),results=[];
  try{
    for(const width of [1280,390]) {
      const context=await browser.newContext({viewport:{width,height:720},reducedMotion:'reduce'}),page=await context.newPage(),errors=[];
      await context.addInitScript(()=>sessionStorage.setItem('xumai-reading-view','list'));
      page.on('pageerror',e=>errors.push(e.message));
      page.on('request',r=>{assert.equal(new URL(r.url()).origin,origin);assert.ok(!r.url().endsWith('/book/start'));});
      await page.goto(`${origin}/login`);await page.locator('#emailInput').fill(fixture.email);await page.locator('#emailSubmitButton').click();await page.waitForURL('**/library');
      assert.equal(new URL(fixture.ruleUrl).origin,origin);
      const ruleId=new URL(fixture.ruleUrl).pathname.split('/').pop();
      const response=await context.request.get(`${origin}/api/independent/projects/${ruleId}/deconstruction`);
      assert.equal(response.status(),200);const payload=await response.json();
      // Emulate only the documented old-engine metadata on a real synthetic
      // report. Rendering is tested, but no backend upgrade is claimed/run.
      const originalId=payload.result.document_id;
      Object.assign(payload,{effective_status:'rebuild_required',update_available:true,engine_revision:null,
        required_engine_revision:'synthetic.rules.2',error:{code:'engine_update_available',message:'规则可更新',retryable:false}});
      payload.actions.rebuild=true;payload.result.engine_revision=null;
      delete payload.result.report.plot.reading_segments;delete payload.result.report.plot.overview;
      delete payload.result.report.engine_revision;
      const legacy=normalizeReport(payload);
      assert.equal(legacy.result.documentId,originalId,'Old readable report must remain attached');
      assert.equal(legacy.updateAvailable,true);assert.equal(legacy.engineRevision,null);
      const legacyHTML=legacyResult(legacy);
      assert.match(legacyHTML,/旧版规则报告/);assert.match(legacyHTML,/data-action="deconstruction-rebuild"/);
      assert.match(legacyHTML,/更新规则报告/);assert.match(legacyHTML,/data-rule-reading="characters"/);
      const refreshHTML=legacyResult({...legacy,actions:{...legacy.actions,rebuild:false}});
      assert.match(refreshHTML,/data-action="deconstruction-refresh"/);assert.match(refreshHTML,/检查可用更新/);
      assert.ok(!refreshHTML.includes('data-action="deconstruction-rebuild"'));
      for(const change of [{update_available:false},{run_status:'running'},{source_match:false},
        {error:{code:'pending_changes'}},{result:{...payload.result,source_hash:'b'.repeat(64)}}]) {
        assert.throws(()=>normalizeReport({...payload,...change}),'Legacy upgrade cannot bypass source/run guards');
      }
      // Component-only evidence uses the real rendering function and shipped
      // styles; it is deliberately not represented as a backend upgrade run.
      await page.setContent(`<!doctype html><html lang="zh-CN"><link rel="stylesheet" href="${origin}/static/styles.css"><link rel="stylesheet" href="${origin}/static/workspace-ui.css"><body><section class="deconstruction-screen"><main class="deconstruction-main"><p>合成合同展示 · 同一正文修订的两次规则报告</p><details class="deconstruction-history-panel analysis-details" open><summary>拆解记录 · 只读</summary>${currentHTML}${oldHTML}</details>${legacyHTML}</main></section></body></html>`);
      const text=await page.locator('body').innerText();
      for(const technical of [current.engineRevision,raw.source_version_id,raw.source_hash,old.documentId,current.documentId])assert.ok(!text.includes(technical));
      assert.equal(await page.locator('[aria-current=true]').count(),1);
      assert.equal(await page.locator('time').count(),2);
      const upgrade=page.locator('.report-update-note [data-action="deconstruction-rebuild"]');
      assert.equal(await upgrade.isVisible(),true);await upgrade.focus();
      assert.equal(await upgrade.evaluate(n=>n===document.activeElement),true);
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(out,`${width}-synthetic-old-current.png`),fullPage:true});
      await page.goto(fixture.modelUrl);await page.locator('.analysis-node').first().waitFor();
      await page.locator('#deconstructionHistoryTitle').click();
      const rows=page.locator('.report-history-item'),active=page.locator('.report-history-item[aria-current=true]');
      const documentId=new URL(fixture.modelUrl).searchParams.get('volume');
      assert.equal(await active.locator('[data-document-id]').getAttribute('data-document-id'),documentId);
      assert.match(await active.innerText(),/模型报告[\s\S]*当前查看[\s\S]*生成于/);
      assert.equal(await rows.locator('time').count(),await rows.count());
      const previous=rows.filter({hasText:'规则线索'}).first();
      const previousId=await previous.locator('[data-document-id]').getAttribute('data-document-id');
      await previous.locator('button').click();await page.locator('.deconstruction-depth-result').waitFor();
      await page.locator('#deconstructionHistoryTitle').click();
      assert.equal(await active.locator('[data-document-id]').getAttribute('data-document-id'),previousId);
      assert.match(await active.innerText(),/规则线索[\s\S]*当前查看/);
      await active.scrollIntoViewIfNeeded();
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      await page.screenshot({path:path.join(out,`${width}-live-history.png`)});
      assert.deepEqual(errors,[]);results.push({width,historyItems:await rows.count(),currentMarkerFollowsSelection:true,errors});await context.close();
    }
    const result={browser:browser.version(),syntheticRevisionCases:true,legacyUpgradeRenderer:true,legacySourceGuards:true,backendUpgradeRun:false,results};
    await fs.writeFile(path.join(out,'report.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
