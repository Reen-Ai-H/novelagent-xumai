/* Real Microsoft Edge + the real local HTTP worker. No intercepted responses.
 * Start tests/browser_server.py in a clean worktree first. The server uses an
 * isolated deterministic data directory and never calls a paid model runtime.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.XUMAI_BROWSER_URL || 'http://127.0.0.1:8032';
assert.equal(new URL(origin).hostname, '127.0.0.1', 'Only the isolated localhost server may be tested');
const out = path.join(__dirname, '..', 'test-results', 'stage33-browser');

async function waitForText(page, selector, text, timeout = 30000) {
  await page.waitForFunction(({selector, text}) => {
    const node = document.querySelector(selector);
    return node && node.textContent.includes(text);
  }, {selector, text}, {timeout});
}

async function readWorkspace(request, projectId) {
  const response = await request.get(`${origin}/api/independent/projects/${projectId}`);
  assert.equal(response.status(), 200);
  return response.json();
}

async function saveDraft(page, body, title) {
  const draft = page.waitForResponse(response => (
    response.url().endsWith('/draft') && response.request().method() === 'PUT' && response.ok()
  ));
  await page.locator('#chapterTitleInput').fill(title);
  await page.locator('#chapterEditor').fill(body);
  await draft;
  await waitForText(page, '#editorSaveState', '已保存');
}

async function completeChapter(page) {
  const complete = page.waitForResponse(response => (
    response.url().endsWith('/complete') && response.request().method() === 'POST' && response.ok()
  ));
  await page.locator('#completeChapterButton').click();
  await complete;
  await waitForText(page, '#editorAnalysisState', '已完成', 60000);
}

async function layout(page, width, label) {
  const metrics = await page.evaluate(() => ({
    width: innerWidth,
    height: innerHeight,
    documentWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body.scrollWidth,
  }));
  assert.equal(metrics.width, width);
  assert.equal(metrics.height, 900);
  assert.ok(metrics.documentWidth <= width && metrics.bodyWidth <= width, `${label}: ${JSON.stringify(metrics)}`);
  await page.screenshot({path: path.join(out, `${width}-${label}.png`), fullPage: true});
  return metrics;
}

async function oneViewport(browser, width) {
  const context = await browser.newContext({
    viewport: {width, height: 900},
    reducedMotion: 'reduce',
  });
  const page = await context.newPage();
  const diagnostics = [];
  page.on('console', message => {
    if (['warning', 'error'].includes(message.type())) diagnostics.push(`${message.type()}: ${message.text()}`);
  });
  page.on('pageerror', error => diagnostics.push(`pageerror: ${error.message}`));
  page.on('requestfailed', request => diagnostics.push(`requestfailed: ${request.url()} ${request.failure()?.errorText}`));
  const email = `stage33-browser-${width}-${Date.now()}@example.test`;
  let projectId;
  try {
    await page.goto(`${origin}/login`);
    await page.locator('#emailInput').fill(email);
    await page.locator('#emailSubmitButton').click();
    await page.waitForURL('**/library');
    await page.locator('#newProjectButton').click();
    await page.locator('[data-mode="independent"]').click();
    await page.locator('#projectTitleInput').fill(`独立体验 ${width}`);
    await page.locator('#createProjectButton').click();
    await page.waitForURL('**/independent/*');
    projectId = new URL(page.url()).pathname.split('/').pop();
    await page.locator('[data-action="start-blank"]').click();
    await page.locator('#chapterEditor').waitFor({state: 'visible'});

    // Friction 3: a durable draft is saved even while analysis is not complete.
    const chapterOneBody = '第一章正文尾部标记：保存与分析必须分离。';
    await saveDraft(page, chapterOneBody, '第一章 保存状态');
    assert.equal(await page.locator('#editorSaveState').textContent(), '已保存');
    assert.ok((await page.locator('#editorAnalysisState').textContent()).includes('待完成'));
    const savedWorkspace = await readWorkspace(context.request, projectId);
    const savedChapter = savedWorkspace.active_version.chapters.find(chapter => chapter.chapter_number === 1);
    assert.equal(savedChapter.status, 'drafting', 'a saved unfinished chapter must remain independently analyzable');

    // Complete chapter one, then use the primary action to create chapter two.
    await completeChapter(page);
    assert.equal(await page.locator('#completeChapterButton').textContent(), '新建下一章 →');
    const createNext = page.waitForResponse(response => (
      response.url().endsWith('/chapters') && response.request().method() === 'POST' && response.ok()
    ));
    await page.locator('#completeChapterButton').click();
    await createNext;
    await page.waitForFunction(() => document.querySelector('#chapterTitleInput')?.value === '第2章', null, {timeout: 30000});
    const chapterTwoUrl = new URL(page.url());
    const chapterTwoId = chapterTwoUrl.searchParams.get('chapter');
    assert.ok(chapterTwoId);
    assert.equal(await page.locator('#chapterTitleInput').inputValue(), '第2章');
    assert.equal(await page.locator('#chapterTitleInput').evaluate(node => node === document.activeElement), true);

    // Friction 1/2: the new chapter is selected and refresh preserves it.
    const chapterTwoBody = '第二章正文尾部标记：刷新后仍然回到第二章。';
    await saveDraft(page, chapterTwoBody, '第二章 当前草稿');
    assert.equal(new URL(page.url()).searchParams.get('chapter'), chapterTwoId);
    await page.reload();
    await page.locator('#chapterEditor').waitFor({state: 'visible'});
    await waitForText(page, '#editorSaveState', '已保存');
    assert.equal(new URL(page.url()).searchParams.get('chapter'), chapterTwoId);
    assert.equal(await page.locator('#chapterEditor').inputValue(), chapterTwoBody);
    assert.equal(await page.locator('#chapterTitleInput').inputValue(), '第二章 当前草稿');

    // Invalid or missing chapter ids use the largest unfinished chapter.
    await page.goto(`${origin}/independent/${projectId}?chapter=does-not-exist`);
    await page.locator('#chapterEditor').waitFor({state: 'visible'});
    assert.equal(new URL(page.url()).searchParams.get('chapter'), chapterTwoId);
    assert.equal(await page.locator('#chapterEditor').inputValue(), chapterTwoBody);

    // Round trips retain the chapter identity in every independent surface.
    await page.locator('[data-action="show-deconstruction"]').click();
    await page.waitForURL(url => {
      const parsed = new URL(url);
      return parsed.pathname.includes(`/independent/${projectId}`) && parsed.searchParams.get('view') === 'deconstruction';
    });
    const deconstructionUrl = new URL(page.url());
    assert.equal(deconstructionUrl.searchParams.get('chapter'), chapterTwoId);
    await page.locator('[data-action="deconstruction-open-editor"]').click();
    await page.waitForURL(url => new URL(url).searchParams.get('chapter') === chapterTwoId && !new URL(url).searchParams.has('view'));
    await page.locator('[data-action="show-archive"]').click();
    await page.waitForURL(url => {
      const parsed = new URL(url);
      return parsed.pathname === `/archive/${projectId}` && parsed.searchParams.get('chapter') === chapterTwoId;
    });
    await page.locator('[data-action="archive-open-editor"]').click();
    await page.waitForURL(url => new URL(url).searchParams.get('chapter') === chapterTwoId && new URL(url).pathname.includes('/independent/'));
    await page.locator('#chapterEditor').waitFor({state: 'visible'});
    await layout(page, width, 'round-trip');

    // Make a real old-chapter edit, rebuild it through the confirmation UI,
    // then exercise full historical preview and explicit restore confirmation.
    await page.locator('[data-action="select-chapter"]').first().click();
    const revisedChapterOne = `${chapterOneBody}\n旧章修改尾部标记：重建会同步档案与拆解。`;
    await saveDraft(page, revisedChapterOne, '第一章 已修改');
    await page.locator('[data-action="review-changes"]').click();
    await page.locator('#pendingChangesDialog[open]').waitFor();
    assert.ok((await page.locator('#pendingChangesDialog').textContent()).includes('档案'));
    await page.locator('#rebuildChangesButton').click();
    await page.locator('#pendingChangesDialog').waitFor({state: 'hidden'});
    await page.locator('#openVersionButton').click();
    await page.locator('#versionHistoryDialog[open]').waitFor();
    const historical = page.locator('.version-history-item:not(.is-active) [data-action="preview-version"]').first();
    await historical.click();
    await page.locator('#versionPreviewTitle').waitFor();
    assert.ok(await page.locator('.version-preview-chapter-tab').count() >= 2, 'historical preview must expose every chapter');
    assert.ok((await page.locator('.version-preview-body').textContent()).includes('保存与分析必须分离'), 'historical preview must include full chapter content');
    const previewVersionId = await page.locator('[data-action="open-restore-confirmation"]').first().getAttribute('data-version-id');
    assert.ok(previewVersionId, 'historical preview must identify its version');

    let restoreRequests = 0;
    page.on('request', request => {
      if (request.url().endsWith(`/versions/${previewVersionId}/restore`) && request.method() === 'POST') restoreRequests += 1;
    });
    await page.locator(`.version-preview-footer [data-action="open-restore-confirmation"][data-version-id="${previewVersionId}"]`).click();
    await page.locator('#restoreVersionDialog[open]').waitFor();
    assert.ok((await page.locator('#restoreVersionDialog').textContent()).includes('创建新的当前稿本'));
    await page.locator('#cancelRestoreVersionButton').click();
    assert.equal(restoreRequests, 0, 'cancel must not call restore');
    await page.locator('#versionHistoryDialog[open]').waitFor();
    await page.locator(`.version-preview-footer [data-action="open-restore-confirmation"][data-version-id="${previewVersionId}"]`).click();
    await page.locator('#confirmRestoreVersionButton').click();
    await page.waitForFunction(() => !document.querySelector('#restoreVersionDialog')?.open, null, {timeout: 30000});
    await page.waitForFunction(() => !document.querySelector('#versionHistoryDialog')?.open, null, {timeout: 30000});
    assert.equal(restoreRequests, 1, 'confirm must call restore once');
    await page.locator('#chapterEditor').waitFor({state: 'visible'});
    await layout(page, width, 'versions');

    assert.equal(await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches), true);
    assert.deepEqual(diagnostics, [], 'Browser must have zero errors and warnings');
    return {width, height: 900, completed: true, consoleErrorsAndWarnings: diagnostics.length};
  } catch (error) {
    await page.screenshot({path: path.join(out, `${width}-failure.png`), fullPage: true});
    console.error(JSON.stringify({width, projectId, diagnostics, error: error.message}));
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
