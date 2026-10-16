/* Real HTTP against the isolated fake service. Uses the large synthetic
 * fixture created by browser_stage35_reading --setup-only. No paid calls. */
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const {chromium}=require('playwright');
const origin=process.env.XUMAI_BROWSER_URL || 'http://127.0.0.1:8054';
assert.equal(new URL(origin).hostname,'127.0.0.1');
const out=path.join(__dirname,'../test-results/stage37-final');
const fixturePath=process.env.XUMAI_BROWSER_FIXTURE || path.join(__dirname,'../test-results/stage35-reading/fixture.json');
async function ids(root,selector,attribute) {
  const seen=[],pages=root.locator(':scope > nav select'),count=await pages.locator('option').count();
  for(let i=1;i<=count;i++) {if(count>1)await pages.selectOption(String(i));seen.push(...await root.locator(selector).evaluateAll((nodes,key)=>nodes.map(n=>n.getAttribute(key)),attribute));}
  return seen;
}
async function capture(page,width,label) {
  await page.evaluate(()=>scrollTo(0,0));
  const metric=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth,text:document.body.innerText.length,dom:document.querySelectorAll('*').length,
    first:document.querySelector('.screen:not(.is-hidden) :is(.workspace-person-row,.plot-node,.workspace-event-stop,.workspace-object-heading,#chapterEditor)')?.getBoundingClientRect().top,
    spine:document.querySelector('#deconstructionScreen:not(.is-hidden) .deconstruction-spine,#independentScreen:not(.is-hidden) .editor-spine')?.getBoundingClientRect().width}));
  assert.ok(metric.scroll<=width && metric.body<=width,`${label}: overflow ${JSON.stringify(metric)}`);
  assert.ok(metric.dom<4000 && metric.text<18000,`${label}: bounded primary view ${JSON.stringify(metric)}`);
  assert.ok(metric.first>0 && metric.first<720,`${label}: first visible object must be on the first screen (${metric.first})`);
  if(width>=1024)assert.equal(metric.spine,246);
  const screenshot=path.join(out,`${width}-${label}.png`);await page.screenshot({path:screenshot,fullPage:true});return {label,...metric,screenshot};
}
(async()=>{
  await fs.mkdir(out,{recursive:true});const fixture=JSON.parse(await fs.readFile(fixturePath,'utf8'));
  for(const key of ['modelUrl','ruleUrl'])assert.equal(new URL(fixture[key]).origin,origin);
  const browser=await chromium.launch({headless:true,channel:process.env.XUMAI_BROWSER_CHANNEL || 'chrome'}),results=[];
  try {
    for(const width of [1440,1024,390]) {
      const context=await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce'}),page=await context.newPage(),errors=[],metrics=[];
      page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(['warning','error'].includes(m.type()))errors.push(m.text());});
      page.on('request',r=>{assert.equal(new URL(r.url()).origin,origin);assert.ok(!/\/(book\/start|analyze-preview)$/.test(r.url()));});
      try {
        await page.goto(`${origin}/login`);await page.locator('#emailInput').fill(fixture.email);await page.locator('#emailSubmitButton').click();await page.waitForURL('**/library');
        for(const kind of ['model','rule']) {
          const url=fixture[`${kind}PeopleUrl`];await page.goto(url);await page.locator('[data-person-index]').waitFor();
          metrics.push(await capture(page,width,`${kind}-people`));
          assert.equal(await page.locator('[data-reader-detail],.visual-selected,.visual-caption').count(),0);
          assert.equal(await page.locator('#workspaceToolsDialog').isVisible(),false);
          const root=page.locator('[data-person-index]');
          const all=await ids(root,'[data-person-id]','data-person-id');assert.equal(new Set(all).size,fixture[`${kind}Counts`].characters);
          const last=all.at(-1);await root.locator(`[data-reader-open="${last}"]`).focus();await page.keyboard.press('Enter');
          await page.locator('[data-reader-detail=characters]').waitFor();assert.equal(await page.locator('[data-person-index]').count(),0);
          assert.equal(new URL(page.url()).searchParams.get('character'),last);assert.ok(new URL(page.url()).searchParams.get('volume'));
          const detailUrl=page.url();await page.reload();await page.locator('[data-reader-detail=characters]').waitFor();assert.equal(page.url(),detailUrl);
          await page.locator('#deconstructionSubnav [data-section=plot]').click();await page.locator('[data-event-index]').waitFor();
          // Check BEFORE capture(), which intentionally scrolls screenshot fixtures to the top.
          const entry=await page.evaluate(()=>({y:scrollY,title:document.querySelector('#deconstructionPageTitle').getBoundingClientRect().top,
            logo:document.querySelector('#deconstructionScreen a[aria-label="返回书架"]').getBoundingClientRect().top}));
          assert.equal(entry.y,0);assert.ok(entry.title>=0 && entry.title<900);assert.ok(entry.logo>=0);
          await page.reload();await page.locator('[data-event-index]').waitFor();assert.equal(await page.evaluate(()=>scrollY),0);
          await page.goBack();await page.locator('[data-reader-detail=characters]').waitFor();
          if(kind==='model')assert.equal(await page.locator('.workspace-empty').innerText(),'暂无已记录的关系');
          metrics.push(await capture(page,width,`${kind}-person-relations`));
          await page.locator('[data-reader-pane=experiences]').click();assert.equal(await page.locator('[data-reader-pane=experiences]').getAttribute('aria-pressed'),'true');
          metrics.push(await capture(page,width,`${kind}-person-experiences`));
          await page.locator('[data-reader-back]').click();await page.locator('[data-person-index]').waitFor();
          assert.equal(await page.locator('[data-reader-open]:focus').getAttribute('data-reader-open'),last);
          assert.ok(Number(await page.locator('[data-person-index] > nav select').inputValue())>1);
          await page.goBack();await page.locator('[data-reader-detail=characters]').waitFor();
          await page.goForward();await page.locator('[data-person-index]').waitFor();
          assert.equal(await page.locator('[data-reader-open]:focus').getAttribute('data-reader-open'),last);
          await page.locator('[data-person-index] input[type=search]').fill(kind==='model'?'合成编号60':'柳测');
          const search=await page.locator('[data-person-index] input[type=search]').inputValue();
          await page.locator('[data-person-index] [data-reader-open]').first().click();await page.locator('[data-reader-back]').click();
          assert.equal(await page.locator('[data-person-index] input[type=search]').inputValue(),search);
          await page.goto(fixture[`${kind}Url`]);await page.locator('[data-event-index]').waitFor();
          metrics.push(await capture(page,width,`${kind}-plot`));
          const events=await ids(page.locator('[data-event-index]'),'[data-event-id]','data-event-id');assert.equal(new Set(events).size,fixture[`${kind}Counts`].events);
          const selected=events.at(-1);await page.locator(`[data-reader-open="${selected}"]`).click();await page.locator('[data-reader-detail=plot]').waitFor();
          assert.equal(await page.locator('[data-event-index]').count(),0);metrics.push(await capture(page,width,`${kind}-event`));
          await page.locator('[data-reader-back]').click();assert.equal(await page.locator('[data-reader-open]:focus').getAttribute('data-reader-open'),selected);
          if(kind==='model')await page.locator('[data-reader-order=story]').click();
          else assert.equal(await page.locator('[data-reader-order=story]').isDisabled(),true,'Rules cannot invent story order');
          assert.equal(new URL(page.url()).searchParams.get('selected'),selected);
          await page.reload();await page.locator('[data-event-index]').waitFor();assert.equal(await page.locator(`[data-reader-order=${kind==='model'?'story':'narrative'}]`).getAttribute('aria-pressed'),'true');
          assert.equal(await page.locator('[data-reader-open]:focus').getAttribute('data-reader-open'),selected);
        }
        await page.goto(fixture.modelUrl);await page.locator('[data-event-index]').waitFor();await page.locator('[data-event-index] input[type=search]').fill('合成大事件 180');await page.locator('[data-reader-open=E179]').click();
        await page.locator('.workspace-event-body .analysis-proof > summary').first().click();
        const proof=page.locator('.workspace-event-body .deconstruction-evidence-link').first();
        const expected=await proof.getAttribute('data-excerpt');await proof.click();await page.locator('#deconstructionEvidenceDialog[open]').waitFor();await page.locator('#locateDeconstructionEvidenceButton').click();
        await page.waitForFunction(text=>{const e=document.querySelector('#chapterEditor');return e.value.slice(e.selectionStart,e.selectionEnd)===text;},expected);
        assert.equal(await page.locator('[data-action=select-section],.chapter-section-list,.chapter-section-status').count(),0);
        metrics.push(await capture(page,width,'editor'));
        await page.goto(fixture.modelPeopleUrl);await page.locator('[data-person-index]').waitFor();await page.locator('[data-action=open-workspace-tools]').click();
        await page.locator('#workspaceToolsDialog[open]').waitFor();await page.keyboard.press('Escape');assert.equal(await page.locator('[data-action=open-workspace-tools]').evaluate(n=>n===document.activeElement),true);
        await page.reload();const assets=await page.evaluate(()=>[...document.querySelectorAll('script[src],link[rel=stylesheet]')].map(n=>n.src || n.href));
        assert.ok(assets.every(url=>new URL(url).searchParams.get('v')==='stage37-final2'));
        assert.deepEqual(errors,[]);results.push({width,metrics,errors});
      } catch(error) {await page.screenshot({path:path.join(out,`${width}-failure.png`),fullPage:true});console.error({url:page.url(),errors});throw error;}
      finally {await context.close();}
    }
    await fs.writeFile(path.join(out,'report.json'),JSON.stringify({synthetic:true,results},null,2));console.log(JSON.stringify({results}));
  } finally {await browser.close();}
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
