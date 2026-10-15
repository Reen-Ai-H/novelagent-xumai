/* Current-native rule and model density on the real isolated server.
 * Legacy upgrade/history is a separate browser_stage35_history.cjs scenario.
 * First run browser_stage35_reading.cjs --setup-only; no request interception,
 * manuscript mutation, real data, or model calls are used here. */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {chromium} = require('playwright');
const origin = process.env.XUMAI_BROWSER_URL || 'http://127.0.0.1:8045';
assert.equal(new URL(origin).hostname, '127.0.0.1');
const root = path.join(__dirname, '..');
const out = path.join(root, 'test-results', process.env.XUMAI_DENSITY_OUTPUT || 'stage35-density');
const views = [
  ['rulePeopleUrl', 'rule-people', '[data-reading-person]', '.analysis-card-summary', 14.4],
  ['ruleUrl', 'rule-plot', '[data-reading-segment]', 'p', 14.4],
  ['modelPeopleUrl', 'model-people', '.analysis-person', '.analysis-card-summary', 14.4],
  ['modelUrl', 'model-plot', '.analysis-node', '.analysis-node-summary', 13.12],
];
(async () => {
  await fs.mkdir(out, {recursive:true});
  const fixture = JSON.parse(await fs.readFile(process.env.XUMAI_BROWSER_FIXTURE || path.join(root, 'test-results/stage35-reading/fixture.json'), 'utf8'));
  const browser = await chromium.launch({headless:true, channel:process.env.XUMAI_BROWSER_CHANNEL || 'chrome'});
  const metrics = [], errors = [];
  try {
    const context = await browser.newContext({reducedMotion:'reduce'});
    // Preserve the full-list density thresholds; graph-first is tested in stage36.
    await context.addInitScript(()=>sessionStorage.setItem('xumai-reading-view','list'));
    const page = await context.newPage();
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', request => {
      assert.equal(new URL(request.url()).origin, origin);
      assert.ok(!request.url().endsWith('/book/start'));
    });
    await page.goto(`${origin}/login`);
    await page.locator('#emailInput').fill(fixture.email);
    await page.locator('#emailSubmitButton').click();
    await page.waitForURL('**/library');
    assert.equal(new URL(fixture.ruleUrl).origin, origin);
    const projectId = new URL(fixture.ruleUrl).pathname.split('/').pop();
    const response = await context.request.get(`${origin}/api/independent/projects/${projectId}/deconstruction`);
    assert.equal(response.status(), 200);
    const native = await response.json();
    assert.equal(native.effective_status, 'completed');
    assert.equal(native.update_available, false);
    assert.equal(typeof native.engine_revision, 'string');
    assert.ok(native.engine_revision.length > 0);
    assert.equal(native.engine_revision, native.required_engine_revision);
    assert.equal(native.result.engine_revision, native.engine_revision);
    assert.equal(native.result.report.engine_revision, native.engine_revision);
    assert.ok(native.result.report.plot.reading_segments.length > 0);
    for (const width of [1280, 390]) {
      await page.setViewportSize({width, height:720});
      for (const [key, label, card, summary, fontFloor] of views) {
        assert.equal(new URL(fixture[key]).origin, origin);
        await page.goto(fixture[key]);
        await page.locator(card).first().waitFor();
        await page.evaluate(() => scrollTo(0, 0));
        const result = await page.evaluate(({card, summary}) => {
          const first = document.querySelector(card), content = first.querySelector(summary);
          const source = document.querySelector('.analysis-source-banner');
          return {width:innerWidth, height:innerHeight, scroll:document.documentElement.scrollWidth,
            body:document.body.scrollWidth, cardTop:first.getBoundingClientRect().top,
            summaryBottom:content.getBoundingClientRect().bottom,
            fontSize:parseFloat(getComputedStyle(content.querySelector('p') || content).fontSize),
            sourceHeight:source.getBoundingClientRect().height, sourceText:source.innerText,
            topBlocks:[...document.querySelectorAll('.deconstruction-header, .model-analysis-options, .analysis-source-banner, .report-update-note, .depth-tablist, .depth-range-options, .report-reading-heading, .report-browser-tools')].slice(0,12).map(n=>({class:n.className,y:n.getBoundingClientRect().top,height:n.getBoundingClientRect().height}))};
        }, {card, summary});
        metrics.push({label, fontFloor, ...result});
        await page.screenshot({path:path.join(out, `${width}-${label}.png`)});
        const sourceDetails = page.locator('.analysis-source-banner details');
        assert.equal(await sourceDetails.getAttribute('open'), null);
        await sourceDetails.locator('summary').focus();
        await page.keyboard.press('Enter');
        assert.notEqual(await sourceDetails.getAttribute('open'), null);
        assert.ok(await sourceDetails.locator('dl').isVisible());
        assert.match(await sourceDetails.innerText(), /稿本/);
        await page.keyboard.press('Enter');
        assert.equal(await sourceDetails.getAttribute('open'), null);
        if (label.startsWith('rule')) {
          assert.equal(await page.locator('.report-update-note').count(), 0, 'Current native rules must not show an upgrade notice');
          const selected = page.locator('[role=tab][aria-selected=true]');
          const original = await selected.getAttribute('id');
          await selected.focus(); await page.keyboard.press('ArrowRight');
          assert.notEqual(await page.locator('[role=tab][aria-selected=true]').getAttribute('id'), original);
          assert.equal(await page.locator('[role=tab][aria-selected=true]').evaluate(n=>n===document.activeElement), true);
        }
      }
    }
    await fs.writeFile(path.join(out, 'report.json'), JSON.stringify({browser:browser.version(), engineRevision:native.engine_revision, updateAvailable:native.update_available, metrics, errors}, null, 2));
    console.log(JSON.stringify({engineRevision:native.engine_revision, updateAvailable:native.update_available, metrics, errors}));
    assert.deepEqual(errors, []);
    for (const m of metrics) {
      assert.ok(m.scroll <= m.width && m.body <= m.width, `${m.label} ${m.width}: horizontal overflow`);
      assert.ok(m.fontSize >= m.fontFloor - .01, `${m.label}: summary text must not shrink`);
      assert.ok(m.summaryBottom <= 720, `${m.label} ${m.width}: complete first summary ends at ${m.summaryBottom}`);
    }
    await context.close();
  } finally { await browser.close(); }
})().catch(error => {console.error(error.stack); process.exitCode = 1;});
