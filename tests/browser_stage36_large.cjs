/* Default-graph large report regression. Prerequisite on the same fake origin:
 * node tests/browser_stage35_reading.cjs (or --setup-only). No source/model writes. */
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path');
const {chromium}=require('playwright');
const origin=process.env.XUMAI_BROWSER_URL || 'http://127.0.0.1:8053',out=path.join(__dirname,'../test-results/stage36-large');
assert.equal(new URL(origin).hostname,'127.0.0.1');
(async()=>{
  await fs.mkdir(out,{recursive:true});const fixture=JSON.parse(await fs.readFile(path.join(__dirname,'../test-results/stage35-reading/fixture.json'),'utf8'));
  assert.equal(new URL(fixture.ruleUrl).origin,origin);
  const browser=await chromium.launch({channel:process.env.XUMAI_BROWSER_CHANNEL || 'chrome',headless:true}),results=[];
  try {
    const context=await browser.newContext({reducedMotion:'reduce'}),page=await context.newPage(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('console',m=>{if(['error','warning'].includes(m.type()))errors.push(m.text());});
    // Email auth is the only POST; register the read-only guard after login.
    await page.goto(`${origin}/login`);await page.locator('#emailInput').fill(fixture.email);await page.locator('#emailSubmitButton').click();await page.waitForURL('**/library');
    page.on('request',r=>{assert.equal(new URL(r.url()).origin,origin);assert.equal(r.method(),'GET');});
    const read=async url=>{const id=new URL(url).pathname.split('/').pop(),r=await context.request.get(`${origin}/api/independent/projects/${id}/deconstruction`);assert.equal(r.status(),200);return (await r.json()).result.report;};
    const rule=await read(fixture.ruleUrl),model=await read(fixture.modelUrl);
    const views=[['rule-people',fixture.rulePeopleUrl,'[data-rule-people]','data-visual-pick',rule.characters.characters.map(p=>p.item_id),rule.characters.characters.at(-1).name],
      ['rule-plot',fixture.ruleUrl,'[data-rule-segments]','data-visual-node',rule.plot.reading_segments.map(s=>s.segment_id),rule.plot.reading_segments.at(-1).title],
      ['model-people',fixture.modelPeopleUrl,'[data-model-map]','data-visual-pick',model.characters.map(p=>p.id),model.characters.at(-1).name],
      ['model-plot',fixture.modelUrl,'[data-model-map]','data-visual-node',model.events.map(e=>e.id),model.events.at(-1).title]];
    for(const width of [1440,1024,390]) {
      await page.setViewportSize({width,height:width===390?844:900});
      for(const [label,url,selector,attr,expected,keyword] of views) {
        await page.goto(url);await page.locator('.visual-node').first().waitFor();const root=page.locator(selector);
        assert.equal(await page.locator('[data-reading-mode=map]').getAttribute('aria-pressed'),'true');
        const metric=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth,
          dom:document.querySelectorAll('*').length,text:document.body.innerText.length,nodeBottom:document.querySelector('.visual-node').getBoundingClientRect().bottom}));
        assert.ok(metric.scroll<=width && metric.body<=width,JSON.stringify(metric));assert.ok(metric.dom<2500 && metric.text<14000,JSON.stringify(metric));
        assert.ok(metric.nodeBottom<= (width===390?844:900),`${label}: first node not on screen`);
        await page.screenshot({path:path.join(out,`${width}-${label}.png`)});
        const seen=[],pages=root.locator(':scope > nav select'),count=await pages.locator('option').count();
        for(let n=1;n<=count;n++) {
          if(count>1)await pages.selectOption(String(n));
          const ids=await root.locator(`.visual-map-items [${attr}]`).evaluateAll((nodes,a)=>nodes.map(n=>n.getAttribute(a)),attr);
          assert.ok(ids.length<=6);seen.push(...ids);
        }
        assert.deepEqual(new Set(seen),new Set(expected),`${label}: every record must remain reachable`);
        if(count>1)assert.equal(await root.locator(':scope > .report-browser-items').evaluate(n=>n===document.activeElement),true);
        if(label==='model-plot') {
          const last=expected.at(-1);
          await root.locator(`[data-visual-node="${last}"]`).click();
          for(const mode of ['story','narrative']) {
            await page.locator(`[data-report-time="${mode}"]`).click();
            assert.equal(await page.locator('.visual-selected').getAttribute('data-selected-id'),last,'Order switching must retain a node selected on the last page');
            assert.equal(await root.locator(`[data-visual-node="${last}"]`).getAttribute('aria-pressed'),'true');
            assert.equal(await root.locator(':scope > nav select').inputValue(),String(count));
          }
        }
        await root.locator(':scope > form input[type=search]').fill(keyword);
        assert.ok((await root.locator(`.visual-map-items [${attr}]`).evaluateAll((nodes,a)=>nodes.map(n=>n.getAttribute(a)),attr)).includes(expected.at(-1)),'Search must reach the last page');
        assert.equal(await root.locator(':scope > form input[type=search]').evaluate(n=>n===document.activeElement),true);
        results.push({label,...metric,reached:seen.length,searchLast:true});
      }
    }
    assert.deepEqual(errors,[]);await fs.writeFile(path.join(out,'report.json'),JSON.stringify({results,errors},null,2));console.log(JSON.stringify({results,errors}));
    await context.close();
  } finally {await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
