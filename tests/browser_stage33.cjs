/* browser_stage33: Real Windows browser + real local HTTP worker; no intercepted/fake responses.
 * Start tests/browser_server.py in a clean worktree first. Requires Playwright
 * and installed Microsoft Edge. Evidence is ignored by Git in test-results/.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = process.env.XUMAI_BROWSER_URL || 'http://127.0.0.1:8033';
assert.equal(new URL(origin).hostname, '127.0.0.1', 'Only the isolated localhost server may be tested');
const out = path.join(__dirname, '..', 'test-results', 'stage33-browser');
const firstChapter = '林舟在旧站门口写下第一封信。顾遥把钥匙交给他，他决定先留在雨里。';
const secondChapter = '雨停之后，林舟打开第二章的门。顾遥在河岸留下新的线索。';

async function layout(page, width, label) {
  const actual = await page.evaluate(() => ({
    width: innerWidth,
    height: innerHeight,
    scroll: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  assert.equal(actual.width, width);
  assert.equal(actual.height, 900);
  assert.ok(actual.scroll <= width && actual.body <= width, `${label}: ${JSON.stringify(actual)}`);
  await page.screenshot({path: path.join(out, `${width}-${label}.png`), fullPage: true});
  return actual;
}

async function waitForSaved(page) {
  await page.waitForFunction(() => document.querySelector('#editorSaveState')?.textContent !== '已保存');
  await page.locator('#editorSaveState').filter({hasText: '已保存'}).waitFor({timeout: 10000});
}

async function waitForNextChapterAction(page) {
  await page.waitForFunction(() => {
    const button = document.querySelector('#completeChapterButton');
    return button?.dataset.nextChapter === 'true' && !button.disabled;
  }, {timeout: 20000});
}

async function oneViewport(browser, width) {
  const context = await browser.newContext({viewport: {width, height: 900}, reducedMotion: 'reduce'});
  const page = await context.newPage();
  const rawDiagnostics = [];
  const observedHttpResponses = [];
  const expectedFailures = [];
  let expectedFailurePhase = null;
  const attachDiagnostics = (target, label) => {
    target.on('response', response => {
      if ([401, 409].includes(response.status())) observedHttpResponses.push({label, status: response.status(), method: response.request().method(), url: response.url()});
    });
    target.on('console', msg => {
      if (['warning', 'error'].includes(msg.type())) rawDiagnostics.push({kind: 'console', label, level: msg.type(), text: msg.text(), phase: expectedFailurePhase});
    });
    target.on('pageerror', error => rawDiagnostics.push({kind: 'pageerror', label, text: error.message, phase: expectedFailurePhase}));
    target.on('requestfailed', request => rawDiagnostics.push({kind: 'requestfailed', label, text: `${request.url()} ${request.failure()?.errorText}`, phase: expectedFailurePhase}));
  };
  attachDiagnostics(page, 'main');

  async function expectHttpFailure({target, label, phase, status, method, urlIncludes}, action) {
    const previousPhase = expectedFailurePhase;
    expectedFailurePhase = phase;
    const diagnosticStart = rawDiagnostics.length;
    try {
      const responsePromise = target.waitForResponse(response => response.status() === status
        && response.request().method() === method
        && response.url().includes(urlIncludes), {timeout: 10000});
      const actionPromise = action();
      const response = await responsePromise;
      assert.equal(response.status(), status, `${phase}: unexpected status`);
      await actionPromise;
      await new Promise(resolve => setTimeout(resolve, 50));
      const matchingResponses = observedHttpResponses.filter(observed => observed.label === label
        && observed.status === status
        && observed.method === method
        && observed.url.includes(urlIncludes));
      assert.equal(matchingResponses.length, 1, `${phase}: expected exactly one matching HTTP failure, got ${matchingResponses.length}`);
      const consoleEventCount = rawDiagnostics.slice(diagnosticStart).filter(event => event.kind === 'console'
        && event.level === 'error'
        && event.label === label
        && event.text.includes(`status of ${status} `)).length;
      expectedFailures.push({label, phase, status: response.status(), method, url: response.url(), consoleEventCount});
      return response;
    } finally {
      expectedFailurePhase = previousPhase;
    }
  }

  function unexpectedDiagnostics() {
    const expectedConsoleBudget = expectedFailures.map(failure => ({...failure, remaining: failure.consoleEventCount}));
    return rawDiagnostics
      .filter(event => {
        if (event.kind !== 'console' || event.level !== 'error') return true;
        const expected = expectedConsoleBudget.find(failure => failure.remaining > 0
          && event.label === failure.label
          && event.text.includes(`status of ${failure.status} `));
        if (!expected) return true;
        expected.remaining -= 1;
        return false;
      })
      .map(event => `${event.label} ${event.kind}${event.level ? ` ${event.level}` : ''}: ${event.text}`);
  }

  const email = `stage33-browser-${width}-${Date.now()}@example.test`;
  let expectedDeconstructionUrlForDebug = null;
  try {
    await page.goto(`${origin}/login`);
    await page.locator('#emailInput').fill(email);
    await page.locator('#emailSubmitButton').click();
    await page.waitForURL('**/library');
    await page.locator('#newProjectButton').click();
    await page.locator('[data-mode="independent"]').click();
    await page.locator('#projectTitleInput').fill(`连续写作 ${width}`);
    await page.locator('#createProjectButton').click();
    await page.waitForURL('**/independent/*');
    const projectId = new URL(page.url()).pathname.split('/').pop();
    await page.locator('[data-action="start-blank"]').click();
    await page.locator('#chapterEditor').waitFor({state: 'visible'});
    const firstResolvedChapterId = new URL(page.url()).searchParams.get('chapter');
    assert.ok(firstResolvedChapterId);
    await page.goto(`${origin}/independent/${projectId}`);
    await page.locator('#chapterEditor').waitFor({state: 'visible'});
    assert.equal(new URL(page.url()).searchParams.get('chapter'), firstResolvedChapterId, 'missing chapter query must use the safe fallback');
    await page.goto(`${origin}/independent/${projectId}?chapter=stage33-invalid-chapter`);
    await page.locator('#chapterEditor').waitFor({state: 'visible'});
    assert.equal(new URL(page.url()).searchParams.get('chapter'), firstResolvedChapterId, 'invalid chapter query must use the safe fallback');
    const chapterOneId = new URL(page.url()).searchParams.get('chapter');
    assert.ok(chapterOneId);
    await page.locator('#chapterTitleInput').fill('第一章');
    await waitForSaved(page);

    // A real expired session must leave the local buffer visible, expose a
    // normal save failure, and block a cross-surface navigation until login is restored.
    const failureContext = await browser.newContext({viewport: {width, height: 900}, reducedMotion: 'reduce'});
    const failurePage = await failureContext.newPage();
    attachDiagnostics(failurePage, 'failure');
    const failureEmail = `stage33-browser-failure-${width}-${Date.now()}@example.test`;
    await failurePage.goto(`${origin}/login`);
    await failurePage.locator('#emailInput').fill(failureEmail);
    await failurePage.locator('#emailSubmitButton').click();
    await failurePage.waitForURL('**/library');
    await failurePage.locator('#newProjectButton').click();
    await failurePage.locator('[data-mode="independent"]').click();
    await failurePage.locator('#projectTitleInput').fill(`保存失败探测 ${width}`);
    await failurePage.locator('#createProjectButton').click();
    await failurePage.waitForURL('**/independent/*');
    const failureProjectId = new URL(failurePage.url()).pathname.split('/').pop();
    await failurePage.locator('[data-action="start-blank"]').click();
    await failurePage.locator('#chapterEditor').waitFor({state: 'visible'});
    const failureChapterId = new URL(failurePage.url()).searchParams.get('chapter');
    await failurePage.evaluate(async () => {
      const response = await fetch('/api/auth/logout', {method: 'POST', credentials: 'same-origin'});
      if (!response.ok) throw new Error(`logout failed: ${response.status}`);
    });
    const unsavedAfterExpiry = '会话过期时仍保留的本地草稿。';
    await expectHttpFailure({
      target: failurePage,
      label: 'failure',
      phase: `expired-save-${width}`,
      status: 401,
      method: 'PUT',
      urlIncludes: `/api/independent/projects/${failureProjectId}/chapters/${failureChapterId}/draft`,
    }, async () => {
      await failurePage.locator('#chapterEditor').fill(unsavedAfterExpiry);
      await failurePage.locator('#editorSaveState').filter({hasText: '保存失败'}).waitFor({timeout: 10000});
    });
    assert.equal(await failurePage.locator('#chapterEditor').inputValue(), unsavedAfterExpiry);
    await failurePage.locator('[data-action="show-archive"]').click();
    assert.match(new URL(failurePage.url()).pathname, new RegExp(`/independent/${failureProjectId}`));
    await failurePage.goto(`${origin}/login`);
    await failurePage.locator('#emailInput').fill(failureEmail);
    await failurePage.locator('#emailSubmitButton').click();
    await failurePage.waitForURL('**/library');
    await failurePage.goto(`${origin}/independent/${failureProjectId}?chapter=${failureChapterId}`);
    await failurePage.locator('#chapterEditor').waitFor({state: 'visible'});
    assert.notEqual(await failurePage.locator('#chapterEditor').inputValue(), unsavedAfterExpiry);
    await failureContext.close();

    // A second real browser tab advances the server revision. The stale first
    // tab must keep its local buffer and expose a conflict instead of overwriting it.
    const remotePage = await context.newPage();
    attachDiagnostics(remotePage, 'remote');
    await remotePage.goto(`${origin}/independent/${projectId}?chapter=${chapterOneId}`);
    await remotePage.locator('#chapterEditor').waitFor({state: 'visible'});
    await remotePage.locator('#chapterEditor').fill('远端版本先写入这里。');
    await waitForSaved(remotePage);
    await expectHttpFailure({
      target: page,
      label: 'main',
      phase: `revision-conflict-${width}`,
      status: 409,
      method: 'PUT',
      urlIncludes: `/api/independent/projects/${projectId}/chapters/${chapterOneId}/draft`,
    }, async () => {
      await page.locator('#chapterEditor').fill(firstChapter);
      await page.locator('#editorSaveState').filter({hasText: '保存冲突'}).waitFor({timeout: 10000});
    });
    assert.ok((await page.locator('#editorNotice').textContent()).includes('没有被静默覆盖'));
    await page.locator('[data-action="reload-server"]').click();
    await page.locator('#chapterEditor').fill(firstChapter);
    await waitForSaved(page);
    await remotePage.close();

    await page.locator('#chapterEditor').fill(firstChapter);
    await waitForSaved(page);
    assert.equal(await page.locator('#editorAnalysisState').textContent(), '写作中');

    // A refresh and a cross-surface round trip must keep the same chapter id.
    await page.reload();
    await page.locator('#chapterEditor').waitFor({state: 'visible'});
    assert.equal(new URL(page.url()).searchParams.get('chapter'), chapterOneId);
    assert.equal(await page.locator('#chapterEditor').inputValue(), firstChapter);
    await page.locator('[data-action="show-archive"]').click();
    await page.waitForFunction(expected => {
      const [expectedProjectId, expectedChapterId] = expected.split('|');
      return location.pathname === `/archive/${expectedProjectId}` && new URLSearchParams(location.search).get('chapter') === expectedChapterId;
    }, `${projectId}|${chapterOneId}`);
    assert.equal(new URL(page.url()).searchParams.get('chapter'), chapterOneId);
    await page.locator('[data-action="archive-open-editor"]').click();
    await page.locator('#chapterEditor').waitFor({state: 'visible'});
    assert.equal(new URL(page.url()).searchParams.get('chapter'), chapterOneId);

    // Complete chapter one, then create the next chapter. The completed chapter
    // stays readable and the new chapter becomes the active URL/focus target.
    await page.locator('#completeChapterButton').click();
    await page.locator('#completeChapterButton').filter({hasText: '新建下一章'}).waitFor({timeout: 20000});
    await waitForNextChapterAction(page);
    assert.equal(await page.locator('#chapterEditor').inputValue(), firstChapter);

    // Editing a completed chapter immediately switches the primary action back
    // to completion and the backend gate appears before any new chapter exists.
    const chapterCountBeforeEditGate = await page.locator('.chapter-list-item').count();
    await page.locator('#chapterTitleInput').fill('第一章（修改）');
    assert.equal(await page.locator('#completeChapterButton').getAttribute('data-next-chapter'), 'false');
    assert.match(await page.locator('#completeChapterButton').textContent(), /完成本章/);
    await expectHttpFailure({
      target: page,
      label: 'main',
      phase: `completed-edit-gate-${width}`,
      status: 409,
      method: 'POST',
      urlIncludes: `/api/independent/projects/${projectId}/chapters/${chapterOneId}/complete`,
    }, async () => {
      await page.locator('#completeChapterButton').click();
      await page.locator('[data-action="review-changes"]').waitFor({timeout: 10000});
    });
    assert.equal(await page.locator('.chapter-list-item').count(), chapterCountBeforeEditGate);
    await page.locator('[data-action="review-changes"]').click();
    await page.locator('#pendingChangesDialog[open]').waitFor();
    await page.locator('#ignoreChangesButton').click();
    await page.locator('#pendingChangesDialog').waitFor({state: 'hidden'});
    const actionAfterIgnore = page.locator('#completeChapterButton');
    if (await actionAfterIgnore.getAttribute('data-next-chapter') !== 'true') {
      await actionAfterIgnore.click();
      await page.locator('#completeChapterButton').filter({hasText: '新建下一章'}).waitFor({timeout: 20000});
      await waitForNextChapterAction(page);
    }

    await page.locator('#completeChapterButton').click();
    await page.waitForFunction(expected => {
      const [expectedProjectId, oldChapterId] = expected.split('|');
      const chapter = new URLSearchParams(location.search).get('chapter');
      return location.pathname === `/independent/${expectedProjectId}` && Boolean(chapter && chapter !== oldChapterId);
    }, `${projectId}|${chapterOneId}`, {timeout: 10000});
    await page.locator('#chapterEditor').waitFor({state: 'visible'});
    const chapterTwoId = new URL(page.url()).searchParams.get('chapter');
    assert.ok(chapterTwoId && chapterTwoId !== chapterOneId, `new chapter URL missing: ${page.url()} (old ${chapterOneId})`);
    await page.waitForFunction(() => document.activeElement?.id === 'chapterTitleInput');
    assert.equal(await page.locator('#chapterTitleInput').evaluate(node => node === document.activeElement), true);
    await page.locator('#chapterTitleInput').fill('第二章');
    await page.locator('#chapterEditor').fill(secondChapter);
    await waitForSaved(page);
    assert.equal(await page.locator('#editorAnalysisState').textContent(), '写作中');
    await layout(page, width, 'two-chapters');

    // The current chapter id survives the deconstruction surface and returns to
    // the exact editor chapter. The page is still the real app/worker path.
    await page.locator('[data-action="show-deconstruction"]').click();
    expectedDeconstructionUrlForDebug = `${projectId}|${chapterTwoId}`;
    await page.waitForFunction(expected => {
      const [expectedProjectId, expectedChapterId] = expected.split('|');
      const params = new URLSearchParams(location.search);
      return location.pathname === `/independent/${expectedProjectId}` && params.get('view') === 'deconstruction' && params.get('chapter') === expectedChapterId;
    }, `${projectId}|${chapterTwoId}`);
    assert.equal(new URL(page.url()).searchParams.get('chapter'), chapterTwoId);
    await page.locator('[data-action="deconstruction-open-editor"]').first().click();
    await page.locator('#chapterEditor').waitFor({state: 'visible'});
    assert.equal(new URL(page.url()).searchParams.get('chapter'), chapterTwoId);

    // Change the completed first chapter through the real editor so the worker
    // creates a historical version. The old version remains read-only.
    await page.locator('.chapter-list-item').filter({hasText: '第一章'}).first().click();
    await page.locator('#chapterEditor').fill(`${firstChapter}\n这一行用于验证旧章重建。`);
    await waitForSaved(page);
    await page.locator('[data-action="review-changes"]').click();
    await page.locator('#pendingChangesDialog[open]').waitFor();
    await page.locator('#rebuildChangesButton').click();
    await page.locator('#pendingChangesDialog').waitFor({state: 'hidden'});

    // 版本预览 must show every readable chapter before the restore confirmation.
    // 保存失败 remains a visible save-state boundary when a real worker rejects a draft.
    let versionCount = 0;
    for (let attempt = 0; attempt < 20; attempt += 1) {
      if (!(await page.locator('#versionHistoryDialog[open]').count())) await page.locator('#openVersionButton').click();
      versionCount = await page.locator('.version-history-item').count();
      if (versionCount >= 2) break;
      await page.locator('#closeVersionHistoryButton').click();
      await page.waitForTimeout(350);
      await page.reload();
      await page.locator('#chapterEditor').waitFor({state: 'visible'});
    }
    assert.ok(versionCount >= 2, `rebuild did not create history: ${versionCount}`);
    await page.locator('.version-history-item:not(.is-active) [data-action="preview-version"]').first().click();
    await page.locator('#versionPreviewContent').waitFor({state: 'visible'});
    assert.ok(await page.locator('.version-preview-chapter').count() >= 2);
    assert.ok((await page.locator('.version-preview-body').first().textContent()).includes(firstChapter));
    await page.locator('[data-action="open-restore-confirm"]').click();
    await page.locator('#restoreVersionDialog[open]').waitFor();
    assert.match(await page.locator('#restoreVersionTitle').textContent(), /恢复确认/);
    const beforeCancel = await page.locator('#restoreVersionDialog').getAttribute('data-request-count');
    await page.locator('[data-action="cancel-restore-version"]').last().click();
    assert.equal(await page.locator('#restoreVersionDialog').getAttribute('open'), null);
    assert.equal(await page.locator('#restoreVersionDialog').getAttribute('data-request-count'), beforeCancel);

    await page.locator('[data-action="open-restore-confirm"]').click();
    let restoreRequests = 0;
    const restoreRequestListener = request => {
      if (request.method() === 'POST' && request.url().includes('/versions/') && request.url().endsWith('/restore')) restoreRequests += 1;
    };
    page.on('request', restoreRequestListener);
    const restoreResponse = page.waitForResponse(response => response.url().includes('/versions/') && response.url().endsWith('/restore') && response.request().method() === 'POST');
    await page.locator('#confirmRestoreVersionButton').click();
    await page.locator('#confirmRestoreVersionButton').evaluate(button => button.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window})));
    await restoreResponse;
    await page.locator('#chapterEditor').waitFor({state: 'visible'});
    page.off('request', restoreRequestListener);
    assert.equal(restoreRequests, 1, `rapid restore confirmation must create one request, got ${restoreRequests}`);
    assert.equal(await page.locator('#restoreVersionDialog').getAttribute('open'), null);
    assert.ok(new URL(page.url()).searchParams.get('chapter'));
    await layout(page, width, 'restored');
    const diagnostics = unexpectedDiagnostics();
    assert.deepEqual(diagnostics, [], 'Browser must have zero unexpected errors and warnings');
    assert.deepEqual(expectedFailures.map(({status}) => status), [401, 409, 409], 'Expected HTTP failure evidence must be explicit');
    return {width, height: 900, completed: true, consoleErrorsAndWarnings: diagnostics.length, expectedHttpFailures: expectedFailures};
  } catch (error) {
    await page.screenshot({path: path.join(out, `${width}-failure.png`), fullPage: true});
    const pageState = await page.evaluate(() => ({
      url: location.href,
      activeElement: document.activeElement?.id || null,
      saveState: document.querySelector('#editorSaveState')?.textContent || null,
      analysisState: document.querySelector('#editorAnalysisState')?.textContent || null,
      chapterTitle: document.querySelector('#chapterTitleInput')?.value || null,
      chapterTitleDisabled: document.querySelector('#chapterTitleInput')?.disabled ?? null,
      bodyLength: document.querySelector('#chapterEditor')?.value.length || 0,
      nextChapter: document.querySelector('#completeChapterButton')?.dataset.nextChapter || null,
      buttonDisabled: document.querySelector('#completeChapterButton')?.disabled ?? null,
    }));
    pageState.expectedDeconstructionUrl = expectedDeconstructionUrlForDebug;
    console.error(JSON.stringify({width, diagnostics: unexpectedDiagnostics(), expectedFailures, rawDiagnostics, pageState, error: error.message}));
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
