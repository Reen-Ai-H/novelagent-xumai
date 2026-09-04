/* Real Windows browser + real local HTTP worker; no intercepted/fake responses.
 * Start tests/browser_server.py in a clean worktree first. Requires Playwright
 * and installed Microsoft Edge. Evidence is ignored by Git in test-results/.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');
const origin = process.env.XUMAI_BROWSER_URL || 'http://127.0.0.1:8032';
assert.equal(new URL(origin).hostname, '127.0.0.1', 'Only the isolated localhost server may be tested');
const out = path.join(__dirname, '..', 'test-results', 'stage32-browser');
const manuscript = `# 第一章 一把钥匙
  🧭林舟捡起铜钥匙，发现齿口少了一角。他想找到失踪的姐姐，却害怕再次走进旧站。
顾遥拦住林舟，说：“我会替你守住站门，你去找她。”林舟把手里的地图交给顾遥。
那枚钥匙为什么会出现在水里？林舟没有答案，只把它藏进了口袋。

# 第二章 雨前
三年前，林舟曾独自走进旧站。那时顾遥还不认识他。姐姐留下过一句话：“缺角的钥匙能开钟楼的门。”
与此同时，顾遥在站外发现了脚印。因为雨水即将冲掉痕迹，她决定先追向河岸。
脚步声越来越近。谁在跟着她？

# 第三章 钟楼
林舟终于用那枚缺角的铜钥匙打开钟楼。姐姐藏在门后的信解释了钥匙为何沉入水中。
顾遥从河岸赶回来，把找到的信封交给林舟。他不再后退，决定和顾遥一起公开真相。
钟声像一条长长的线，穿过雨后的街巷。两人推开窗，站前已经空了。
`;

async function layout(page, width, label) {
  const actual = await page.evaluate(() => ({
    width: innerWidth, height: innerHeight,
    scroll: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  assert.equal(actual.width, width);
  assert.equal(actual.height, 900);
  assert.ok(actual.scroll <= width && actual.body <= width, `${label}: ${JSON.stringify(actual)}`);
  await page.screenshot({path: path.join(out, `${width}-${label}.png`), fullPage: true});
  return actual;
}

async function waitComplete(page) {
  await page.locator('#deconstructionStatusPill.is-completed').waitFor({timeout: 60000});
}

async function oneViewport(browser, width) {
  const context = await browser.newContext({viewport: {width, height: 900}, reducedMotion: 'reduce'});
  const page = await context.newPage();
  const diagnostics = [];
  page.on('console', msg => {
    if (['warning', 'error'].includes(msg.type())) diagnostics.push(`${msg.type()}: ${msg.text()}`);
  });
  page.on('pageerror', error => diagnostics.push(`pageerror: ${error.message}`));
  page.on('requestfailed', req => diagnostics.push(`requestfailed: ${req.url()} ${req.failure()?.errorText}`));
  const email = `stage32-browser-${width}-${Date.now()}@example.test`;
  try {
    await page.goto(`${origin}/login`);
    await page.locator('#emailInput').fill(email);
    await page.locator('#emailSubmitButton').click();
    await page.waitForURL('**/library');
    await page.locator('#newProjectButton').click();
    await page.locator('[data-mode="independent"]').click();
    await page.locator('#projectTitleInput').fill(`钥匙与回声 ${width}`);
    await page.locator('#createProjectButton').click();
    await page.waitForURL('**/independent/*');
    const editorUrl = page.url().split('?')[0];
    const projectId = new URL(editorUrl).pathname.split('/').pop();
    await page.locator('#importFileInput').setInputFiles({
      name: '钥匙与回声.md', mimeType: 'text/markdown', buffer: Buffer.from(manuscript),
    });
    await page.locator('[data-action="confirm-import"]').click();
    await page.locator('#chapterEditor').waitFor({state: 'visible'});
    const initialBody = await page.locator('#chapterEditor').inputValue();
    assert.ok(initialBody.includes('铜钥匙'));
    await page.locator('[data-action="show-deconstruction"]').click();
    await waitComplete(page);
    await layout(page, width, 'overview');
    assert.equal(await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches), true);

    // Six real views must be reachable by keyboard with evidence available.
    const views = ['人物', '剧情', '伏笔', '节奏', '读者', '文笔'];
    for (let index = 0; index < views.length; index += 1) {
      const tab = page.getByRole('tab', {name: new RegExp(views[index])});
      await tab.focus();
      await page.keyboard.press('Enter');
      assert.equal(await tab.getAttribute('aria-selected'), 'true');
      await layout(page, width, `view-${index + 1}`);
    }
    await page.reload();
    await waitComplete(page);
    const response = await context.request.get(`${origin}/api/independent/projects/${projectId}/deconstruction`);
    assert.equal(response.status(), 200);
    const result = await response.json();
    assert.equal(result.effective_status, 'completed');
    assert.ok(result.result.evidence.length);
    const oldHash = result.source.hash;

    // Re-login restores the same real project and completed result.
    await page.goto(`${origin}/library`);
    await page.locator('#logoutButton').click();
    await page.locator('#emailInput').fill(email);
    await page.locator('#emailSubmitButton').click();
    await page.waitForURL('**/library');
    await page.goto(`${editorUrl}?view=deconstruction`);
    await waitComplete(page);
    await layout(page, width, 'relogin');

    // Author editing/rebuild is performed through the actual UI, not store edits.
    await page.goto(editorUrl);
    await page.locator('#chapterEditor').waitFor({state: 'visible'});
    assert.equal(await page.locator('#chapterEditor').inputValue(), initialBody);
    const revised = initialBody + '\n林舟在门上刻下一个新的记号。';
    const saved = page.waitForResponse(r => r.url().endsWith('/draft') && r.request().method() === 'PUT' && r.ok());
    await page.locator('#chapterEditor').fill(revised);
    await saved;
    await page.locator('[data-action="review-changes"]').click();
    await page.locator('#rebuildChangesButton').click();
    await page.locator('#pendingChangesDialog').waitFor({state: 'hidden'});
    await page.locator('[data-action="show-deconstruction"]').click();
    await waitComplete(page);
    const rebuilt = await (await context.request.get(`${origin}/api/independent/projects/${projectId}/deconstruction`)).json();
    assert.notEqual(rebuilt.source.hash, oldHash);
    const oldEvidence = result.result.evidence[0];
    const historical = await (await context.request.get(`${origin}/api/independent/projects/${projectId}/deconstruction/evidence/${oldEvidence.evidence_id}`)).json();
    assert.equal(historical.historical, true);
    assert.equal(historical.chapter.read_only, true);
    await layout(page, width, 'rebuilt');
    assert.deepEqual(diagnostics, [], 'Browser must have zero errors and warnings');
    return {width, height: 900, completed: true, consoleErrorsAndWarnings: diagnostics.length, views: views.length};
  } catch (error) {
    await page.screenshot({path: path.join(out, `${width}-failure.png`), fullPage: true});
    console.error(JSON.stringify({width, diagnostics, error: error.message}));
    throw error;
  } finally {
    await context.close();
  }
}

(async () => {
  await fs.mkdir(out, {recursive: true});
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  try {
    const results = [];
    for (const width of [1440, 1024]) results.push(await oneViewport(browser, width));
    const report = {browser: `Microsoft Edge ${browser.version()}`, platform: process.platform, results};
    await fs.writeFile(path.join(out, 'report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
