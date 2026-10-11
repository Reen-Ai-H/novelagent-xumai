/* Read-only display acceptance of the user-authorized, privately seeded reports.
 * No model requests, report writes, manuscript edits or public screenshots.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {chromium} = require('playwright');

async function main() {
  const origin = process.env.XUMAI_BROWSER_URL || 'http://127.0.0.1:8034';
  assert.equal(new URL(origin).hostname, '127.0.0.1');
  const directory = process.env.XUMAI_REVIEW_DATA;
  assert.ok(directory, 'Explicit private review data directory required');
  const info = JSON.parse(await fs.readFile(path.join(directory, 'review.json'), 'utf8'));
  const output = path.join(directory, 'browser');
  await fs.mkdir(output, {recursive: true, mode: 0o700});
  const browser = await chromium.launch({channel: process.env.XUMAI_BROWSER_CHANNEL || 'chrome'});
  const summaries = [];
  try {
    for (const width of [1440, 390]) {
      const context = await browser.newContext({viewport: {width, height: 900}, reducedMotion: 'reduce'});
      const page = await context.newPage();
      const diagnostics = [];
      page.on('console', message => {if (['warning', 'error'].includes(message.type())) diagnostics.push(message.type());});
      page.on('pageerror', () => diagnostics.push('pageerror'));
      page.on('requestfailed', () => diagnostics.push('requestfailed'));
      await page.goto(`${origin}/login`);
      await page.locator('#emailInput').fill(info.email);
      await page.locator('#emailSubmitButton').click();
      await page.waitForURL('**/library');
      const api = `${origin}/api/independent/projects/${info.project_id}/deconstruction`;
      const stateResponse = await context.request.get(api);
      assert.equal(stateResponse.status(), 200);
      const state = await stateResponse.json();
      const volumes = state.volumes.filter(volume => volume.match && volume.status === 'completed');
      assert.equal(volumes.length, 2);
      let references = 0;
      for (const volume of volumes) {
        const response = await context.request.get(`${api}?document_id=${volume.document_id}`);
        assert.equal(response.status(), 200);
        const document = (await response.json()).document;
        assert.equal(document.report.producer, 'mimo-v2.6-pro');
        for (const ref of document.evidence) {
          const evidence = await context.request.get(`${api}/evidence/${encodeURIComponent(ref.evidence_id)}?document_id=${volume.document_id}`);
          assert.equal(evidence.status(), 200);
          const value = await evidence.json();
          assert.equal(value.source_matches_current, true);
          assert.equal(value.evidence.document_id, volume.document_id);
          assert.equal(value.evidence.excerpt, ref.excerpt);
          references += 1;
        }
        for (const section of ['characters', 'plot', 'time']) {
          await page.goto(`${origin}/independent/${info.project_id}?view=deconstruction&volume=${volume.document_id}&section=${section}`);
          await page.locator(section === 'characters' ? '.analysis-person-link' : section === 'plot' ? '.analysis-node' : '.analysis-time-toggle').first().waitFor();
          const layout = await page.evaluate(() => ({viewport: innerWidth, root: document.documentElement.scrollWidth, body: document.body.scrollWidth}));
          assert.ok(layout.root <= width && layout.body <= width, JSON.stringify({section, width, layout}));
          await page.screenshot({path: path.join(output, `${width}-${volume.scope_start}-${section}.png`), fullPage: true});
        }
      }
      await page.goto(`${origin}/independent/${info.project_id}?view=deconstruction&section=guide`);
      await page.locator('.guide-node-card').first().waitFor();
      const layout = await page.evaluate(() => ({root: document.documentElement.scrollWidth, body: document.body.scrollWidth}));
      assert.ok(layout.root <= width && layout.body <= width, JSON.stringify({section: 'guide', width, layout}));
      await page.screenshot({path: path.join(output, `${width}-guide.png`), fullPage: true});
      assert.deepEqual(diagnostics, []);
      summaries.push({width, height: 900, volumes: volumes.length, sourceVerifiedReferences: references, unexpectedDiagnostics: 0, overflow: false});
      await context.close();
    }
    const result = {browser: browser.version(), summaries};
    await fs.writeFile(path.join(output, 'result.json'), JSON.stringify(result, null, 2), {mode: 0o600});
    console.log(JSON.stringify(result));
  } finally {await browser.close();}
}
main().catch(error => {console.error(error); process.exitCode = 1;});
