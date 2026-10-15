/* Real isolated server + Chrome. Synthetic prose and authored imported report
 * exercise presentation/contracts only, never claim literary quality. No HTTP
 * interception, direct store mutation, model call or paid service. */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {chromium} = require('playwright');
const origin = process.env.XUMAI_BROWSER_URL || 'http://127.0.0.1:8045';
assert.equal(new URL(origin).hostname, '127.0.0.1');
const out = path.join(__dirname, '..', 'test-results', 'stage35-workspace-ui');
const body1 = '林舟在旧站门口写下第一封信。顾遥把钥匙交给他，他决定先留在雨里。';
const body2 = '雨停之后，林舟打开钟楼的门。顾遥在河岸留下新的线索。';
const fragment = '合成检查材料，章节前的说明需由作者核对。';
const manuscript = `${fragment}\n\n第一章 旧站\n${body1}\n\n第二章 钟楼\n${body2}`;
const claim = text => ({text, status:'fact', evidence_ids:['Q1']});
function report() {
  return {schema_version:'1', producer:'stage35-synthetic-authored-report', title:'合成展示检查',
    scope:'第 1 章', chapter_numbers:[1], findings:[{id:'F1', title:'正文行动', ...claim('林舟写信。')}],
    characters:[{id:'C1', entity_key:'linzhou', name:'林舟', aliases:[], role:'写信的人',
      identity:claim('林舟出现在旧站。'), motivation:claim('林舟决定留在雨里。'),
      portrait:claim('愿意等待，尚不能据此判断完整性格。'), change:claim('在旧站写下第一封信。'),
      insights:[{title:'在雨中等待', ...claim('林舟决定留在雨里。')}]}],
    events:[{id:'E1', title:'旧站写信', chapter_number:1, story_time:'当前', actor_ids:['C1'],
      action:claim('林舟写信，顾遥交来钥匙。'), consequence:claim('林舟决定留在雨里。'),
      sub_events:[{title:'接过钥匙', ...claim('顾遥把钥匙交给他。')}]}],
    relations:[], story_order:['E1'], time_note:'仅记录第一章。',
    evidence:[{id:'Q1',chapter_number:1,quote:body1}], open_questions:[], contradictions:[]};
}
async function capture(page, width, label) {
  await page.waitForFunction(()=>document.querySelectorAll('#toastRegion .toast').length===0);
  const size = await page.evaluate(() => ({width:innerWidth, scroll:document.documentElement.scrollWidth, body:document.body.scrollWidth}));
  assert.equal(size.width, width);
  assert.ok(size.scroll <= width && size.body <= width, `${label}: ${JSON.stringify(size)}`);
  await page.screenshot({path:path.join(out,`${width}-${label}.png`),fullPage:true});
  return {label,...size};
}
async function verify(browser, width) {
  const context = await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce'});
  // Stage36 defaults to diagrams; this suite retains all full-list contracts.
  await context.addInitScript(()=>sessionStorage.setItem('xumai-reading-view','list'));
  const page = await context.newPage();
  const diagnostics = [], layouts = [];
  page.on('pageerror', error => diagnostics.push(error.message));
  page.on('console', msg => { if (['error','warning'].includes(msg.type())) diagnostics.push(msg.text()); });
  page.on('requestfailed', request => diagnostics.push(`${request.url()}: ${request.failure()?.errorText}`));
  page.on('request', request => assert.ok(new URL(request.url()).origin === origin, 'External requests are forbidden'));
  try {
    await page.goto(`${origin}/login`);
    await page.locator('#emailInput').fill(`stage35-ui-${width}-${Date.now()}@example.test`);
    await page.locator('#emailSubmitButton').click();
    await page.waitForURL('**/library');
    await page.locator('#newProjectButton').click();
    await page.locator('[data-mode="independent"]').click();
    await page.locator('#projectTitleInput').fill(`旧站来信 · 合成检查 ${width}`);
    await page.locator('#createProjectButton').click();
    await page.waitForURL('**/independent/*');
    const editorUrl = page.url().split('?')[0];
    const projectId = new URL(editorUrl).pathname.split('/').pop();
    await page.locator('#importFileInput').setInputFiles({name:'合成检查.txt', mimeType:'text/plain', buffer:Buffer.from(manuscript)});
    await page.locator('.import-chapter-preview').first().waitFor();
    assert.equal(await page.locator('.import-chapter-preview').count(),2);
    assert.equal(await page.locator('#analyzeWholeImport').isChecked(),false);
    await page.locator('.import-chapter-preview summary').first().focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('.import-chapter-body').first().textContent(),body1 + '\n\n');
    assert.ok((await page.locator('.unrecognized-fragments').textContent()).includes(fragment));
    layouts.push(await capture(page,width,'import-preview'));
    await page.locator('[data-action="confirm-import"]').click();
    await page.locator('#chapterEditor').waitFor();
    await page.locator('.chapter-list-item').first().click();
    await page.waitForFunction(expected=>document.querySelector('#chapterEditor')?.value===expected,body1 + '\n\n');
    assert.equal(await page.locator('#chapterEditor').inputValue(),body1 + '\n\n');
    layouts.push(await capture(page,width,'editor'));
    assert.equal(await page.locator('#archiveDrawer').isVisible(),false,'Independent editor no longer duplicates the report sidebar');
    await page.locator('#chapterTitleInput').fill('第一章 旧站来信');
    await page.locator('[data-action="save-editor"]').click();
    await page.locator('#editorSaveState.is-saved').waitFor();
    assert.equal(await page.locator('#archiveDrawer').isVisible(),false,'save must preserve the uncluttered independent editor');
    await page.locator('.chapter-list-item').nth(1).click();
    await page.waitForFunction(expected=>document.querySelector('#chapterEditor')?.value===expected,body2);
    assert.equal(await page.locator('#chapterEditor').inputValue(),body2);
    await page.locator('#chapterTitleInput').fill('第二章 钟楼回声');
    await page.keyboard.press('Control+s');
    await page.locator('#editorSaveState.is-saved').waitFor();
    layouts.push(await capture(page,width,'editor-collapsed'));
    await page.locator('[data-action="review-changes"]').click();
    await page.locator('#rebuildChangesButton').click();
    await page.locator('.spine-link[data-action="show-deconstruction"]').click();
    await page.locator('#deconstructionStatusPill.is-completed').waitFor({timeout:30000});
    await page.getByRole('tab',{name:/人物/}).click();
    const ruleData = await (await context.request.get(`${origin}/api/independent/projects/${projectId}/deconstruction`)).json();
    assert.equal(ruleData.result.analysis_contract_version,'2.0');
    assert.equal(await page.locator('.depth-entity-card').count(),ruleData.result.report.characters.characters.length,'no candidates may be cut');
    assert.ok((await page.locator('.analysis-source-banner').textContent()).includes('未调用模型'));
    layouts.push(await capture(page,width,'rule-characters-summary'));
    await page.locator('.analysis-source-banner .analysis-details > summary').click();
    assert.ok((await page.locator('.analysis-source-facts').textContent()).includes('2.0'));
    layouts.push(await capture(page,width,'rule-source'));
    await page.locator('.analysis-source-banner .analysis-details > summary').click();
    const ruleDetails = page.locator('.depth-entity-card .analysis-details summary').first();
    await ruleDetails.focus();
    await page.keyboard.press('Enter');
    layouts.push(await capture(page,width,'rule-characters'));
    const ruleProof = page.locator('.depth-entity-card .deconstruction-evidence-link').first();
    const ruleSpan = await ruleProof.evaluate(node=>({start:Number(node.dataset.charStart),end:Number(node.dataset.charEnd),excerpt:node.dataset.excerpt}));
    await ruleProof.click();
    await page.locator('#deconstructionEvidenceDialog[open]').waitFor();
    await page.locator('.deconstruction-evidence-dialog-card.is-current').waitFor();
    assert.equal(await page.locator('#locateDeconstructionEvidenceButton').isEnabled(),true);
    await page.locator('#locateDeconstructionEvidenceButton').click();
    await page.locator('#chapterEditor').waitFor();
    await page.waitForFunction(span=>{
      const node=document.querySelector('#chapterEditor');
      return node?.selectionStart===span.start && node?.selectionEnd===span.end && node.value.slice(span.start,span.end)===span.excerpt;
    },ruleSpan);
    const selectedText = await page.locator('#chapterEditor').evaluate(node => node.value.slice(node.selectionStart,node.selectionEnd));
    assert.ok(selectedText.length > 0);
    await page.locator('.spine-link[data-action="show-deconstruction"]').click();
    await page.getByRole('tab',{name:/剧情/}).click();
    assert.equal(await page.locator('.depth-event-list .depth-track-item').count(),ruleData.result.report.plot.events.length);
    layouts.push(await capture(page,width,'rule-plot-summary'));
    await page.locator('.depth-events-section > summary').click();
    await page.locator('.depth-event-list .analysis-details summary').first().click();
    layouts.push(await capture(page,width,'rule-plot'));
    const imported = await context.request.post(`${origin}/api/independent/projects/${projectId}/deconstruction/import`,{data:{report:report()}});
    assert.equal(imported.status(),200,await imported.text());
    const documentId = (await imported.json()).result.document_id;
    await page.goto(`${editorUrl}?view=deconstruction&volume=${documentId}&section=characters`);
    await page.locator('.analysis-person').waitFor();
    assert.equal(await page.locator('.analysis-person').count(),1);
    layouts.push(await capture(page,width,'model-characters-summary'));
    await page.locator('.analysis-person .analysis-details summary').click();
    assert.equal(await page.locator('.analysis-person .deconstruction-evidence-link').count(),2);
    layouts.push(await capture(page,width,'model-characters'));
    await page.locator('.analysis-person-link').click();
    assert.equal(await page.locator('[data-report-back]').evaluate(node=>node===document.activeElement),true);
    await page.locator('[data-report-phrase]').click();
    await page.locator('.analysis-modal-backdrop .analysis-proof summary').focus();
    await page.keyboard.press('Enter');
    await page.keyboard.press('Shift+Tab');
    assert.equal(await page.locator('.analysis-modal-backdrop').evaluate(node=>node.contains(document.activeElement)),true);
    await page.keyboard.press('Escape');
    await page.locator('[data-report-back]').click();
    assert.equal(await page.locator('.analysis-person-link').evaluate(node=>node===document.activeElement),true);
    await page.locator('#deconstructionSubnav [data-section="plot"]').click();
    await page.locator('.analysis-node').waitFor();
    layouts.push(await capture(page,width,'model-plot'));
    await page.locator('.analysis-node-detail .analysis-proof summary').first().click();
    const [proofResponse] = await Promise.all([
      page.waitForResponse(r=>r.url().includes('/evidence/Q1')),
      page.locator('.analysis-node-detail .deconstruction-evidence-link').first().click()
    ]);
    assert.equal(new URL(proofResponse.url()).searchParams.get('document_id'),documentId);
    await page.locator('#deconstructionEvidenceDialog[open]').waitFor();
    await page.locator('.deconstruction-evidence-dialog-card.is-current').waitFor();
    layouts.push(await capture(page,width,'evidence'));
    await page.locator('#locateDeconstructionEvidenceButton').click();
    await page.locator('#chapterEditor').waitFor();
    await page.waitForFunction(expected=>{
      const node=document.querySelector('#chapterEditor');
      return node && node.value.slice(node.selectionStart,node.selectionEnd)===expected;
    },body1);
    assert.equal(await page.locator('#chapterEditor').evaluate(node=>node.value.slice(node.selectionStart,node.selectionEnd)),body1);
    assert.deepEqual(diagnostics,[]);
    return {width,layouts,ruleCharacters:ruleData.result.report.characters.characters.length,ruleEvents:ruleData.result.report.plot.events.length,diagnostics};
  } catch(error) {
    await page.screenshot({path:path.join(out,`${width}-failure.png`),fullPage:true});
    console.error({width,url:page.url(),diagnostics});
    throw error;
  } finally { await context.close(); }
}
(async()=>{
  await fs.mkdir(out,{recursive:true});
  const browser = await chromium.launch({headless:true,channel:process.env.XUMAI_BROWSER_CHANNEL || 'chrome'});
  try {
    const results=[];
    for (const width of [1440,1024,390]) results.push(await verify(browser,width));
    const result={browser:browser.version(),synthetic:true,results};
    await fs.writeFile(path.join(out,'report.json'),JSON.stringify(result,null,2),'utf8');
    console.log(JSON.stringify(result));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
