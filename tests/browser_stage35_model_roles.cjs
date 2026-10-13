/* Strict model.1 import seam: explicit role prefixes, unknowns, two volumes,
 * evidence and realistic summaries at 720px. Only synthetic authored content.
 * Start tests/browser_server.py with the original .venv; no model is called.
 * XUMAI_BROWSER_URL=http://127.0.0.1:8045 NODE_PATH=<playwright> node this-file
 * --setup-only leaves a single-volume fixture + login/URLs under test-results.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {chromium} = require('playwright');
const origin = process.env.XUMAI_BROWSER_URL || 'http://127.0.0.1:8045';
assert.equal(new URL(origin).hostname, '127.0.0.1');
const out = path.join(__dirname, '..', 'test-results/stage35-model-roles');
const roles = [
  ['主要人物：负责核对木牌，发现缺号后召集同伴重新检查。', '主要人物'],
  ['主要人物:整理交接记录。', '主要人物'], ['主角', '主要人物'], ['主人公：记录者。', '主要人物'],
  ['实质配角：在交接处补充记录，并提供一条核对线索。', '配角'],
  ['配角：运送木牌。', '配角'], ['次要人物:协助整理。', '配角'], ['配角', '配角'],
  ['主要人物的朋友', '未分级'], ['不是主要人物：仅被提及。', '未分级'],
  ['身份：主要人物', '未分级'], ['尚无明确分类的记录员', '未分级'],
];
const quote = '合成甲把蓝色木牌交给合成乙，合成乙逐一核对编号，把缺少的一项写在登记簿上。';
const portrait = '做事细致，交接前会逐项复核；遇到缺号时先保留记录，再向在场同伴询问，并不直接归责。这里仅依据合成正文中的行动描述为人，不将一次行动推断为固定信念。';
const change = '最初只负责交接木牌，发现清单与实物不符后暂停登记，邀请同伴一起复核。待缺失项被补记，他把新记录交回保管处，继续核对下一批物品；其经历范围仅限本章。';
function report(chapter) {
  const claim = (text, status='fact') => ({text,status,evidence_ids:['Q1']});
  return {schema_version:'1',producer:'synthetic-strict-role-seam',title:'合成人物分组合同核对',scope:`第${chapter}章`,chapter_numbers:[chapter],
    findings:[{id:'F1',title:'核对交接',...claim(quote)}],
    characters:roles.map(([role],i)=>({id:`C${i}`,name:`合成人物${String(i+1).padStart(2,'0')}`,aliases:[],role,
      identity:claim('参与本次交接的合成记录员。'),motivation:claim('正文未提供动机。','unknown'),
      portrait:claim(portrait,'inferred'),change:claim(change),insights:[]})),
    events:[{id:'E1',title:'核对交接并记录缺号',chapter_number:chapter,story_time:'本章当日',actor_ids:['C0','C4'],
      action:claim(quote),consequence:claim('记录员保留缺号，等待后续核对。'),sub_events:[]}],
    relations:[],story_order:['E1'],time_note:'按正文顺序记录。',
    evidence:[{id:'Q1',chapter_number:chapter,quote}],open_questions:[],contradictions:[]};
}
async function visibleIds(root) {
  const pages=root.locator(':scope > nav select'), count=await pages.locator('option').count(), ids=[];
  for(let n=1;n<=count;n++) {
    if(count>1)await pages.selectOption(String(n));
    ids.push(...await root.locator('.analysis-person-link').evaluateAll(nodes=>nodes.map(n=>n.dataset.reportPerson)));
  }
  return ids;
}
(async()=>{
  await fs.mkdir(out,{recursive:true});
  const browser=await chromium.launch({headless:true,channel:process.env.XUMAI_BROWSER_CHANNEL || 'chrome'});
  try {
    const context=await browser.newContext({viewport:{width:1280,height:720},reducedMotion:'reduce'});
    const page=await context.newPage(),errors=[],metrics=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('request',r=>{assert.equal(new URL(r.url()).origin,origin);assert.ok(!r.url().endsWith('/book/start'));});
    const email=`stage35-roles-${Date.now()}@example.test`;
    await page.goto(`${origin}/login`);await page.locator('#emailInput').fill(email);await page.locator('#emailSubmitButton').click();await page.waitForURL('**/library');
    await page.locator('#newProjectButton').click();await page.locator('[data-mode="independent"]').click();
    await page.locator('#projectTitleInput').fill('合成验收 · 角色前缀与双卷');await page.locator('#createProjectButton').click();await page.waitForURL('**/independent/*');
    const projectUrl=page.url().split('?')[0],id=new URL(projectUrl).pathname.split('/').pop();
    await page.locator('#importFileInput').setInputFiles({name:'角色合同合成.txt',mimeType:'text/plain',buffer:Buffer.from(`第1章 合成交接\n${quote}\n第2章 合成复核\n${quote}`)});
    await page.locator('#analyzeWholeImport').uncheck();await page.locator('[data-action="confirm-import"]').click();
    await page.locator('#chapterEditor').waitFor();
    await page.waitForFunction(()=>document.querySelectorAll('.chapter-list-item').length===2);
    const api=`${origin}/api/independent/projects/${id}/deconstruction`;
    async function importReport(chapter) {
      const authored=report(chapter);
      assert.ok(authored.characters.every(p=>!Object.hasOwn(p,'importance')));
      const response=await context.request.post(`${api}/import`,{data:{report:authored}});
      assert.equal(response.status(),200,await response.text());
      const data=await response.json();assert.equal(data.result.analysis_contract_version,'model.1');
      assert.deepEqual(data.result.report.characters.map(p=>p.role),roles.map(([role])=>role));
      assert.ok(data.result.report.characters.every(p=>!Object.hasOwn(p,'importance')));
      return data.result.document_id;
    }
    const first=await importReport(1),url=`${projectUrl}?view=deconstruction&volume=${first}&section=characters`;
    const invalid=report(1);invalid.characters[0].importance='main';
    const rejected=await context.request.post(`${api}/import`,{data:{report:invalid}});
    assert.equal(rejected.status(),422,'Contract must reject invented importance, not silently accept fixture extras');
    const afterRejected=await context.request.get(api);assert.equal(afterRejected.status(),200);
    assert.equal((await afterRejected.json()).result.document_id,first,'Rejected fixture must leave the valid report unchanged');
    const fixture={email,url,projectUrl,documentId:first,expectedGroups:{主要人物:4,配角:4,未分级:4},synthetic:true};
    await fs.writeFile(path.join(out,'fixture.json'),JSON.stringify(fixture,null,2));
    if(process.argv.includes('--setup-only')){console.log(JSON.stringify(fixture));return;}
    for(const width of [1280,390]) {
      await page.setViewportSize({width,height:720});await page.goto(url);await page.locator('.analysis-person').first().waitFor();
      const nav=page.locator('.deconstruction-volume-bar'),people=page.locator('[data-model-people]');
      assert.equal(await nav.locator('[data-action="deconstruction-volume"]').count(),1);
      assert.equal(await nav.locator('[data-section="guide"]').count(),1);
      assert.ok((await nav.getAttribute('class')).includes('is-single-volume'));
      const note=nav.locator('.single-volume-nav');assert.equal(await note.getAttribute('open'),null);
      await note.locator('summary').focus();await page.keyboard.press('Enter');
      assert.equal(await note.locator('p').isVisible(),true);assert.match(await note.innerText(),/已拆卷不会/);
      assert.equal(await nav.locator('[data-action="deconstruction-volume"]').isVisible(),true);
      assert.equal(await nav.locator('[data-section="guide"]').isVisible(),true);
      await page.keyboard.press('Enter');assert.equal(await note.getAttribute('open'),null);
      await page.evaluate(()=>scrollTo(0,0));
      const metric=await page.evaluate(()=>{
        const card=document.querySelector('.analysis-person'),summary=card.querySelector('.analysis-card-summary');
        return {width:innerWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth,
          cardTop:card.getBoundingClientRect().top,summaryBottom:summary.getBoundingClientRect().bottom,
          fontSize:parseFloat(getComputedStyle(summary.querySelector('p')).fontSize),
          volumeHeight:document.querySelector('.deconstruction-volume-bar').getBoundingClientRect().height};
      });metrics.push(metric);
      assert.equal(await people.locator('.analysis-card-summary > p').first().textContent(),portrait);
      assert.equal(await people.locator('.analysis-card-summary > p').nth(1).textContent(),change);
      await page.screenshot({path:path.join(out,`${width}-model-people.png`)});
      assert.ok(metric.scroll<=width && metric.body<=width,'Horizontal overflow');
      assert.ok(metric.fontSize>=14.4-.01,'Summary font must not shrink');
      assert.ok(metric.volumeHeight<140,'Single-volume controls must be compact');
      assert.ok(metric.summaryBottom<=720,`Complete portrait + change ends at ${metric.summaryBottom} (${width})`);
      assert.deepEqual(new Set(await visibleIds(people)),new Set(roles.map((_,i)=>`C${i}`)));
      assert.equal(await people.locator(':scope > .report-browser-items').evaluate(n=>n===document.activeElement),true);
      const filter=people.locator('[data-browser-filter="importance"]');
      for(const group of ['主要人物','配角','未分级']) {
        assert.equal(await filter.locator(`option[value="${group}"]`).textContent(),`${group} · 4`);
        await filter.selectOption(group);
        assert.deepEqual(new Set(await visibleIds(people)),new Set(roles.flatMap(([,value],i)=>value===group?[`C${i}`]:[])));
      }
      await filter.selectOption('');const search=people.locator('input[type=search]');
      await search.fill('合成人物12');assert.equal(await search.evaluate(n=>n===document.activeElement),true);
      assert.equal(await people.locator('.analysis-person-link').getAttribute('data-report-person'),'C11');
      await people.locator('.analysis-details > summary').click();
      const [proof]=await Promise.all([page.waitForResponse(r=>r.url().includes('/evidence/Q1')),people.locator('.deconstruction-evidence-link').first().click()]);
      const payload=await proof.json();assert.equal(new URL(proof.url()).searchParams.get('document_id'),first);
      assert.equal(payload.evidence.chapter_number,1);await page.locator('#deconstructionEvidenceDialog[open]').waitFor();
      await page.locator('#dismissDeconstructionEvidenceButton').click();
    }
    const second=await importReport(2);
    for(const width of [1280,390]) {
      await page.setViewportSize({width,height:720});await page.goto(url);await page.locator('.analysis-person').first().waitFor();
      const nav=page.locator('.deconstruction-volume-bar');
      assert.equal(await nav.locator('[data-action="deconstruction-volume"]').count(),2);
      assert.ok(!(await nav.getAttribute('class')).includes('is-single-volume'));
      const secondButton=nav.locator(`[data-document-id="${second}"]`);await secondButton.focus();await page.keyboard.press('Enter');
      await page.waitForURL(u=>u.searchParams.get('volume')===second);
      await page.locator(`.deconstruction-volume[aria-current=page][data-document-id="${second}"]`).waitFor();
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
      await page.screenshot({path:path.join(out,`${width}-two-volumes.png`)});
    }
    assert.deepEqual(errors,[]);
    const result={browser:browser.version(),strictImport:true,extraImportanceRejected:true,characterCount:roles.length,expectedGroups:fixture.expectedGroups,metrics,multiVolumeKeyboard:true,errors};
    await fs.writeFile(path.join(out,'report.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));await context.close();
  }finally{await browser.close();}
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
