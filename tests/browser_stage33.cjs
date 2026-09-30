/* Real app/HTTP persistence and isolated synthetic author content. No model,
 * route interception or fixture responses. Requires Playwright and Chromium.
 * XUMAI_BROWSER_URL can select an already running isolated server; otherwise
 * this script starts tests/browser_server.py using XUMAI_PYTHON or python.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
const origin = process.env.XUMAI_BROWSER_URL || 'http://127.0.0.1:8033';
assert.equal(new URL(origin).hostname, '127.0.0.1', 'Test only isolated localhost');
const out = path.join(root, 'test-results', 'stage33-browser');
let server;

async function layout(page, width, label) {
  const size = await page.evaluate(() => ({width:innerWidth, height:innerHeight, scroll:document.documentElement.scrollWidth, body:document.body.scrollWidth}));
  assert.equal(size.width, width);
  assert.equal(size.height, 900);
  assert.ok(size.scroll <= width && size.body <= width, `${label}: ${JSON.stringify(size)}`);
  await page.screenshot({path:path.join(out, `${width}-${label}.png`), fullPage:true});
}
async function project(page, mode, title) {
  await page.goto(`${origin}/library`);
  await page.locator('#newProjectButton').click();
  await page.locator(`[data-mode='${mode}']`).click();
  await page.locator('#projectTitleInput').fill(title);
  await page.locator('#createProjectButton').click();
  await page.waitForURL(mode === 'independent' ? '**/independent/*' : '**/ai/*');
  return new URL(page.url()).pathname.split('/').pop();
}
async function viewport(width) {
  const launch = {headless:true};
  if (process.env.XUMAI_CHROMIUM_PATH) launch.executablePath=process.env.XUMAI_CHROMIUM_PATH;
  if (process.env.XUMAI_CHROMIUM_ARGS) launch.args=JSON.parse(process.env.XUMAI_CHROMIUM_ARGS);
  const browser = await chromium.launch(launch);
  const context = await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce',acceptDownloads:true});
  const page = await context.newPage();
  const errors=[];
  page.on('pageerror', error=>errors.push(String(error)));
  page.on('console', message=>{if(['warning','error'].includes(message.type()))errors.push(message.text());});
  page.on('requestfailed', request=>errors.push(`${request.url()}: ${request.failure()?.errorText}`));
  try {
    await page.goto(`${origin}/login`);
    await page.locator('#emailInput').fill(`stage33-${width}-${Date.now()}@example.test`);
    await page.locator('#emailSubmitButton').click();
    await page.waitForURL('**/library');
    const pid=await project(page,'independent',`海边的信 ${width}`);
    await page.locator('[data-action="start-blank"]').click();
    await page.locator('#chapterEditor').waitFor({state:'visible'});
    await page.locator('#chapterTitleInput').fill('第一章 潮声');
    const original='林舟把那封信放回抽屉，海风从窗缝里涌进来。\n\n他决定在涨潮前，把没有说完的话带到灯塔。🧭';
    await page.locator('#chapterEditor').fill(original);
    await page.locator('#focusEditorButton').click();
    assert.equal(await page.locator('#focusEditorButton').getAttribute('aria-pressed'),'true');
    await layout(page,width,'focused-editor');
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#focusEditorButton').getAttribute('aria-pressed'),'false');
    const edited=original+'\n最后一句必须被保存后再导出。';
    await page.locator('#chapterEditor').fill(edited);
    const downloadWait=page.waitForEvent('download');
    await page.locator('[data-action="export-manuscript"]').click();
    const download=await downloadWait;
    const exported=await fs.readFile(await download.path(),'utf8');
    assert.ok(exported.includes(edited));
    assert.ok(exported.includes('第一章 潮声'));
    assert.equal(download.suggestedFilename(),`海边的信 ${width}.txt`);
    const saved=(await (await context.request.get(`${origin}/api/independent/projects/${pid}`)).json()).active_version.chapters[0];
    assert.equal(saved.content,edited);
    await page.locator('#addChapterButton').click();
    await page.locator('#chapterEditor').waitFor({state:'visible'});
    await page.waitForFunction(()=>document.querySelector('#editorChapterHeading').textContent.includes('2'));
    assert.equal(await page.locator('#chapterEditor').inputValue(),'');
    await page.locator('#chapterEditor').fill('顾遥站在灯塔下，打开新的信封。她答应等到潮水退去，再读给林舟听。');
    await page.locator('#completeChapterButton').click();
    await page.locator('[data-action="add-next-chapter"]').waitFor({state:'visible'});
    await layout(page,width,'chapter-complete');
    await page.locator('[data-action="add-next-chapter"]').click();
    await page.waitForFunction(()=>document.querySelector('#editorChapterHeading').textContent.includes('3'));
    assert.equal(await page.locator('#chapterEditor').inputValue(),'');
    const bodyAfter=(await (await context.request.get(`${origin}/api/independent/projects/${pid}`)).json()).active_version.chapters;
    assert.equal(bodyAfter[0].content,edited);
    assert.equal(bodyAfter.length,3);

    const aiPid=await project(page,'ai_assisted',`潮汐路 ${width}`);
    await page.locator('#aiMessageInput').fill('我想写一个寻找失踪信件的故事，主角是林舟。');
    await page.locator('#aiMessageButton').click();
    await page.waitForFunction(()=>document.querySelector('#aiConversationCount').textContent==='1 轮');
    const world='山城与海港由一条只在退潮时出现的道路相连。';
    await page.locator('#blueprintWorldRules').fill(world);
    await page.locator('#aiMessageInput').fill('补充：顾遥负责看守灯塔。');
    await page.locator('#aiMessageButton').click();
    await page.waitForFunction(()=>document.querySelector('#aiConversationCount').textContent==='2 轮');
    assert.equal(await page.locator('#blueprintWorldRules').inputValue(),world,'discussion must preserve unsaved author fields');
    await page.locator('#saveBlueprintButton').click();
    await page.waitForFunction(()=>document.querySelector('#aiStudioNotice').textContent.includes('字段已保存'));
    const aiWs=await (await context.request.get(`${origin}/api/ai/projects/${aiPid}`)).json();
    assert.equal(aiWs.blueprint.world_rules,world);
    if(process.env.XUMAI_BROWSER_FAKE === '1'){
      // The prior proposal predates the author's direct edit. Dismiss it,
      // then request a fresh suggestion with a current before-value.
      await page.locator('[data-action="dismiss-blueprint-suggestion"]').click();
      await page.locator('.blueprint-suggestion').waitFor({state:'hidden'});
      await page.locator('#aiMessageInput').fill('再讨论一次潮汐道路的规则。');
      await page.locator('#aiMessageButton').click();
      await page.locator('[data-action="accept-blueprint-suggestion"]').waitFor({state:'visible'});
      assert.ok((await page.locator('.blueprint-diff').textContent()).includes(world));
      const proposed=(await (await context.request.get(`${origin}/api/ai/projects/${aiPid}`)).json()).blueprint_suggestions[0].after;
      assert.notEqual(proposed,world);
      await layout(page,width,'blueprint-suggestion');
      await page.locator('[data-action="accept-blueprint-suggestion"]').click();
      await page.locator('.blueprint-suggestion').waitFor({state:'hidden'});
      assert.equal(await page.locator('#blueprintWorldRules').inputValue(),proposed);
      await page.locator('#aiMessageInput').fill('可以再提供一条规则建议。');
      await page.locator('#aiMessageButton').click();
      await page.locator('[data-action="dismiss-blueprint-suggestion"]').waitFor({state:'visible'});
      await page.locator('[data-action="dismiss-blueprint-suggestion"]').click();
      await page.locator('.blueprint-suggestion').waitFor({state:'hidden'});
      assert.equal(await page.locator('#blueprintWorldRules').inputValue(),proposed);
    }
    await layout(page,width,'blueprint-cards');
    await page.locator('#confirmBlueprintButton').click();
    await page.waitForURL('**/director');
    await page.locator('.writing-preferences summary').click();
    await page.locator('[data-writing-brief="genre"]').fill('悬疑');
    await page.locator('[data-writing-brief="point_of_view"]').fill('第三人称有限视角');
    await page.locator('[data-writing-brief="tone"]').fill('克制，以具体动作表现情绪');
    await page.locator('[data-writing-brief="avoid"]').fill('不要大段回顾前文');
    await page.locator('[data-action="save-writing-preferences"]').click();
    await page.reload();
    await page.locator('.writing-preferences summary').click();
    assert.equal(await page.locator('[data-writing-brief="tone"]').inputValue(),'克制，以具体动作表现情绪');
    await page.locator('#chapterGoalInput').fill('让顾遥主动核对信件，承担一个错误判断的代价。');
    await layout(page,width,'chapter-direction');
    await page.locator('[data-action="start-ai-director"][data-strategy="pause_at_key_nodes"]').click();
    await page.locator('[data-action="choose-ai-choice"]').first().waitFor({state:'visible',timeout:20000});
    assert.equal(await page.locator('[data-action="choose-ai-choice"]').count(),3);
    assert.ok((await page.locator('.director-choice-panel h2').textContent()).includes('由你决定'));
    const waiting=await (await context.request.get(`${origin}/api/ai/projects/${aiPid}`)).json();
    assert.equal(waiting.active_run.chapter_goal,'让顾遥主动核对信件，承担一个错误判断的代价。');
    assert.equal(waiting.active_run.writing_preferences.genre,'悬疑');
    await page.locator('[data-action="choose-ai-choice"]').filter({hasText:'把决定交给角色'}).click();
    await page.locator('.chapter-review').waitFor({state:'visible',timeout:20000});
    await page.locator('.chapter-reading summary').click();
    assert.ok((await page.locator('.chapter-reading-body').textContent()).length>0);
    await layout(page,width,'chapter-review');
    const finished=await (await context.request.get(`${origin}/api/ai/projects/${aiPid}`)).json();
    assert.equal(finished.active_run.status,'completed');
    assert.equal(finished.manuscript.active_version.chapters.length,1);
    assert.equal(await page.locator('#chapterGoalInput').inputValue(),'','next chapter starts with a fresh goal');
    assert.deepEqual(errors,[],'unexpected browser diagnostics');
    console.log(JSON.stringify({width,height:900,flows:['save-before-export','focus','next-chapter','chapter-completion','blueprint-draft-preservation','preferences-refresh','chapter-goal','choice','full-reading'],errors:0,passed:true}));
  } finally { await browser.close(); }
}
(async()=>{
 await fs.mkdir(out,{recursive:true});
 if(!process.env.XUMAI_BROWSER_URL){
   const args=['-W','ignore','tests/browser_server.py','--port',String(new URL(origin).port)];
   if(process.env.XUMAI_BROWSER_FAKE==='1')args.push('--fake-model');
   server=spawn(process.env.XUMAI_PYTHON||'python',args,{cwd:root,stdio:['ignore','ignore','pipe']});
   let logs='';server.stderr.on('data',data=>{logs+=data.toString();});
   let ready=false;
   for(let attempt=0;attempt<80;attempt++){
     if(server.exitCode!==null)throw new Error(`Server exited: ${logs}`);
     try {const response=await fetch(`${origin}/login`);if(response.ok){ready=true;break;}}catch{}
     await new Promise(resolve=>setTimeout(resolve,100));
   }
   assert.ok(ready,`isolated server failed to start: ${logs}`);
 }
 for(const width of [1440,1024])await viewport(width);
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{if(server)server.kill('SIGTERM');});
