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
    const overviewTab = page.getByRole('tab', {name: '总览'});
    await overviewTab.focus();
    assert.equal(await overviewTab.getAttribute('aria-selected'), 'true');
    for (let index = 0; index < views.length; index += 1) {
      await page.keyboard.press('ArrowRight');
      const tab = page.getByRole('tab', {name: new RegExp(views[index])});
      assert.equal(await tab.getAttribute('aria-selected'), 'true');
      assert.equal(await tab.evaluate(node => node === document.activeElement), true);
      await layout(page, width, `view-${index + 1}`);
    }

    // A current span must open the real evidence endpoint and select the exact
    // UTF-16 range in the author editor. This exercises the drawer and the
    // navigation boundary instead of validating only the JSON response.
    const currentEvidenceButton = page.locator('.deconstruction-evidence-link').first();
    await currentEvidenceButton.waitFor();
    const currentEvidence = await currentEvidenceButton.evaluate(node => ({
      excerpt: node.dataset.excerpt,
      start: Number(node.dataset.charStart),
      end: Number(node.dataset.charEnd),
    }));
    assert.ok(currentEvidence.excerpt);
    await currentEvidenceButton.click();
    await page.locator('#deconstructionEvidenceDialog[open]').waitFor();
    await page.locator('.deconstruction-evidence-dialog-card.is-current').waitFor();
    assert.equal(await page.locator('#deconstructionEvidenceTitle').textContent(), '证据回链');
    assert.equal(await page.locator('#locateDeconstructionEvidenceButton').isEnabled(), true);
    await page.locator('#locateDeconstructionEvidenceButton').click();
    await page.locator('#chapterEditor').waitFor({state: 'visible'});
    await page.waitForFunction(({start, end}) => {
      const editor = document.querySelector('#chapterEditor');
      return editor && editor.selectionStart === start && editor.selectionEnd === end;
    }, currentEvidence, {timeout: 10000});
    const selectedEvidence = await page.locator('#chapterEditor').evaluate(editor => ({
      start: editor.selectionStart,
      end: editor.selectionEnd,
      text: editor.value.slice(editor.selectionStart, editor.selectionEnd),
    }));
    assert.deepEqual(selectedEvidence, {
      start: currentEvidence.start,
      end: currentEvidence.end,
      text: currentEvidence.excerpt,
    });
    await page.locator('[data-action="show-deconstruction"]').click();
    await waitComplete(page);
    await page.reload();
    await waitComplete(page);
    const response = await context.request.get(`${origin}/api/independent/projects/${projectId}/deconstruction`);
    assert.equal(response.status(), 200);
    const result = await response.json();
    assert.equal(result.effective_status, 'completed');
    assert.equal(result.result.analysis_contract_version, '2.0');
    const depth = result.result.report;
    assert.equal(depth.report_version, '2.0');
    for (const key of ['characters', 'plot', 'foreshadowing', 'rhythm', 'reader_experience', 'technique']) {
      assert.ok(depth[key] && typeof depth[key] === 'object', `missing depth view: ${key}`);
    }
    assert.ok(depth.evidence.length);
    assert.ok(depth.evidence.every(ref => ref.source_hash === result.source.hash));
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

    // Keep one tab on the old DOM while another tab performs a real author
    // edit and rebuild. Clicking that stale button afterwards must produce a
    // historical, read-only drawer and must never enable current-text locate.
    const stalePage = await context.newPage();
    stalePage.on('console', msg => {
      if (['warning', 'error'].includes(msg.type())) diagnostics.push(`stale ${msg.type()}: ${msg.text()}`);
    });
    stalePage.on('pageerror', error => diagnostics.push(`stale pageerror: ${error.message}`));
    stalePage.on('requestfailed', req => diagnostics.push(`stale requestfailed: ${req.url()} ${req.failure()?.errorText}`));
    await stalePage.goto(`${editorUrl}?view=deconstruction`);
    await waitComplete(stalePage);
    await stalePage.getByRole('tab', {name: /文笔/}).click();
    const staleEvidenceButton = stalePage.locator('.deconstruction-evidence-link').first();
    await staleEvidenceButton.waitFor();

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
    assert.equal(rebuilt.result.analysis_contract_version, '2.0');
    assert.equal(rebuilt.result.report.report_version, '2.0');
    const oldEvidence = depth.evidence[0];
    const historical = await (await context.request.get(`${origin}/api/independent/projects/${projectId}/deconstruction/evidence/${oldEvidence.evidence_id}`)).json();
    assert.equal(historical.historical, true);
    assert.equal(historical.chapter.read_only, true);
    await staleEvidenceButton.click();
    await stalePage.locator('#deconstructionEvidenceDialog[open]').waitFor();
    await stalePage.locator('.deconstruction-evidence-dialog-card.is-historical').waitFor();
    assert.equal(await stalePage.locator('#deconstructionEvidenceTitle').textContent(), '历史证据回链');
    assert.equal(await stalePage.locator('#locateDeconstructionEvidenceButton').isDisabled(), true);
    await stalePage.close();
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
