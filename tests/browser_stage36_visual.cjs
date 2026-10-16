/* Stage36 real-HTTP synthetic acceptance. No private text, interception, model
 * or paid calls. Start tests/browser_server.py --port 8053 with the original
 * .venv; NODE_PATH=<Playwright> XUMAI_BROWSER_URL=http://127.0.0.1:8053 node
 * tests/browser_stage36_visual.cjs. --setup-only leaves a CUA-ready fixture. */
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const {existsSync}=require('node:fs');
const path=require('node:path');
const {execFileSync}=require('node:child_process');
const {chromium}=require('playwright');
const origin=process.env.XUMAI_BROWSER_URL || 'http://127.0.0.1:8053';
assert.equal(new URL(origin).hostname,'127.0.0.1');
const out=path.join(__dirname,'../test-results/stage36-visual');
const assetRelease='stage37-final';
const assetFiles=['styles.css','deconstruction-report.css','workspace-ui.css','visual-reading.css','workspace-reader.css',
  'report-browser.js','visual-reading.js','chapter-sections.js','chapter-preview.js','workspace-reader.js','rule-report.js','deconstruction-report.js','app.js'];
const shellAssets=html=>[...html.matchAll(/(?:href|src)="(\/static\/[^"?]+\.(?:css|js)\?[^\"]+)"/g)].map(m=>m[1]);
function assertAssetVersions(urls) {
  const assets=urls.map(value=>new URL(value,origin));
  assert.deepEqual(assets.map(url=>url.pathname),assetFiles.map(name=>`/static/${name}`),'The shell must include every runtime CSS/JS asset in dependency order');
  for(const url of assets) {
    assert.equal(url.origin,origin);
    assert.equal(url.search,`?v=${assetRelease}`,`${url.pathname}: stale release token`);
  }
}
const narrative=['E3','E1','E2','E4','E5','E6'],story=['E1','E2','E4','E3','E5','E6'];
const actors={E3:[0,1,2,3,4,5,6],E1:[0,1],E2:[0,2,4],E4:[4,5],E5:[0,3,6,8,9],E6:[0,6,7,9]};
const names=Array.from({length:10},(_,i)=>`合成录员${String(i+1).padStart(2,'0')}`);
const quotes=Object.fromEntries(narrative.map(id=>[id,`${actors[id].map(i=>names[i]).join('、')}一起核对${id}号木牌，记录员留下核对结果。`]));
const body=narrative.map((id,i)=>`## 合成小节${i+1}😀\r\n${quotes[id]}\r\n${'　灯下的册页保留了原来的行距，记录员逐字核对。\r\n'.repeat(14)}`).join('\r\n');
const body1=`  😀开篇原文。\r\n\r\n${body}\r\n\r\n`,body2='  这一章只用于旧章切换。\r\n尾行保留空格。  \r\n';
function modelReport() {
  const claim=(text,id='E3',status='fact')=>({text,status,evidence_ids:[`Q${id}`]});
  return {schema_version:'1',producer:'synthetic-stage36',title:'合成节点顺序反例',scope:'第1章',chapter_numbers:[1],
    findings:[{id:'F1',title:'木牌核对',...claim(quotes.E3)}],
    characters:names.map((name,i)=>({id:`C${i}`,name,aliases:[`全量检索编号${i+1}`],role:i<4?'主要人物：参与核对':i<9?'实质配角：参与核对':'未明确分级',
      identity:claim('参与登记的合成人物。'),motivation:claim('尚未提供动机。','E3','unknown'),portrait:claim('核对前保留原始册页，发现记录差异后请同伴一起核查。','E3',['inferred','reported','unknown','fact'][i%4]),
      change:claim(`合成录员${i+1}从交接木牌到复核记录。`,'E3',['fact','unknown','reported','inferred'][i%4]),insights:[]})),
    events:narrative.map(id=>({id,title:`核对${id}号木牌`,chapter_number:1,story_time:`顺序标记${id}`,actor_ids:actors[id].map(i=>`C${i}`),
      action:claim(quotes[id],id),consequence:claim(`${id}的核对结果被保留。`,id),sub_events:[{title:'核对细节',...claim(quotes[id],id)}]})),
    relations:[['E1','E2','follows'],['E5','E6','follows'],['E2','E4','causes'],['E4','E3','causes']].map(([from_id,to_id,kind])=>({from_id,to_id,kind,...claim(kind==='follows'?'只记录先后，不表示因果。':'报告注明前一事件促成后一事件。',from_id,'inferred')})),
    story_order:story,time_note:'正文先揭示E3，再回看E1、E2；故事发生顺序另列。',
    evidence:narrative.map(id=>({id:`Q${id}`,chapter_number:1,quote:quotes[id]})),open_questions:[],contradictions:[]};
}

// Stage37 decision: official chapter preview replaces section navigation;
// exclusive object pages replace simultaneous co-occurrence graph + details.
// All whitespace/evidence/save barriers and full-collection checks remain.
const text1='第1章 合成记录\r\n'+body1,text2='第2章 后续记录\r\n'+body2,manuscript=text1+text2;
async function setup(browser) {
  const context=await browser.newContext(),page=await context.newPage(),email='stage37-regression-'+Date.now()+'@example.test';
  await page.goto(origin+'/login');await page.locator('#emailInput').fill(email);await page.locator('#emailSubmitButton').click();await page.waitForURL('**/library');
  async function project(title) {
    await page.goto(origin+'/library');await page.locator('#newProjectButton').click();await page.locator('[data-mode=independent]').click();
    await page.locator('#projectTitleInput').fill(title);await page.locator('#createProjectButton').click();await page.waitForURL('**/independent/*');return page.url().split('?')[0];
  }
  async function importFile(name,buffer) {
    const pending=page.waitForResponse(r=>r.url().endsWith('/chapter-previews/import'));
    await page.locator('#importFileInput').setInputFiles({name,mimeType:'application/octet-stream',buffer});
    const response=await pending;assert.equal(response.status(),200);
    const preview=(await response.json()).preview;
    assert.equal(await page.locator('[data-preview-chapter]').count(),preview.chapters.length);
    assert.equal(preview.chapters.map(c=>preview.source_text.slice(c.start,c.end)).join(''),preview.source_text);
    assert.equal(await page.locator('[data-preview-source]').inputValue(),preview.source_text.slice(preview.chapters[0].start,preview.chapters[0].end).replace(/\r\n/g,'\n'));
    assert.equal(await page.locator('.import-section-outline,[data-action=select-section]').count(),0);
    await page.locator('[data-preview-confirm]').click();await page.locator('#chapterEditor').waitFor();
    return preview;
  }
  const url=await project('合成验收 · 十人六事件与正式章节'),id=new URL(url).pathname.split('/').pop(),api=origin+'/api/independent/projects/'+id;
  const parsed=await importFile('正式章节合成.txt',Buffer.from(manuscript));
  assert.equal(parsed.chapters.length,2);assert.equal(parsed.source_text,manuscript);
  let workspace=await (await context.request.get(api)).json();
  assert.deepEqual(workspace.active_version.chapters.map(c=>c.content),[text1,text2]);
  const response=await context.request.post(api+'/deconstruction/import',{data:{report:modelReport()}});
  assert.equal(response.status(),200,await response.text());const report=(await response.json()).result;
  const fixture={email,url,id,api,documentId:report.document_id,charactersUrl:url+'?view=deconstruction&volume='+report.document_id+'&section=characters',plotUrl:url+'?view=deconstruction&volume='+report.document_id+'&section=plot',synthetic:true};
  await fs.writeFile(path.join(out,'fixture.json'),JSON.stringify(fixture,null,2));
  const md='## 第1章 起点\r\n开篇。\r\n### 小节甲\r\n甲正文。\r\n### 小节乙\r\n乙正文。\r\n## 第2章 后续\r\n丙正文。';
  const localPython=path.join(__dirname,'..','.venv',...(process.platform==='win32'?['Scripts','python.exe']:['bin','python']));
  const python=process.env.XUMAI_TEST_PYTHON || (existsSync(localPython)?localPython:(process.platform==='win32'?'python':'python3'));
  const docx=execFileSync(python,['-c',"import io,zipfile,sys\nb=io.BytesIO()\nwith zipfile.ZipFile(b,'w') as z:\n z.writestr('word/document.xml','<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body>'+''.join('<w:p><w:r><w:t>'+t+'</w:t></w:r></w:p>' for t in ['第一章 起点','开篇。','第一节 小节甲','甲正文。','第二节 小节乙','乙正文。','第二章 后续','丙正文。'])+'</w:body></w:document>')\nsys.stdout.buffer.write(b.getvalue())"]);
  for(const [name,buffer] of [['目录合成.md',Buffer.from(md)],['目录合成.docx',docx]]) {
    const extraUrl=await project('导入格式验证 '+name),extraApi=origin+'/api/independent/projects/'+new URL(extraUrl).pathname.split('/').pop();
    const data=await importFile(name,buffer);assert.equal(data.chapters.length,2);
    const saved=await (await context.request.get(extraApi)).json();
    assert.deepEqual(saved.active_version.chapters.map(c=>c.content),data.chapters.map(c=>data.source_text.slice(c.start,c.end)));
  }
  const storageState=await context.storageState();await context.close();return {...fixture,storageState};
}
async function capture(page,width,label) {
  await page.evaluate(()=>scrollTo(0,0));
  const metric=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth,
    dom:document.querySelectorAll('*').length,text:document.body.innerText.length,
    first:document.querySelector('.screen:not(.is-hidden) [data-reader-open],.screen:not(.is-hidden) #chapterEditor')?.getBoundingClientRect().top,
    overlaps:[...document.querySelectorAll('.workspace-participants')].filter(n=>n.nextElementSibling && n.getBoundingClientRect().bottom>n.nextElementSibling.getBoundingClientRect().top).length}));
  assert.ok(metric.scroll<=width && metric.body<=width,JSON.stringify(metric));
  assert.ok(metric.dom<2000 && metric.text<12000,JSON.stringify(metric));
  assert.equal(metric.overlaps,0);assert.ok(metric.first>=0 && metric.first<720,JSON.stringify(metric));
  await page.screenshot({path:path.join(out,width+'-'+label+'.png')});return metric;
}
async function verify(browser,fixture,width) {
  const context=await browser.newContext({storageState:fixture.storageState,viewport:{width,height:width===390?844:900},reducedMotion:'reduce'}),page=await context.newPage(),errors=[],metrics=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(['error','warning'].includes(m.type()))errors.push(m.text());});
  let saves=0;page.on('request',r=>{assert.equal(new URL(r.url()).origin,origin);assert.ok(!/book\/start|analyze-preview/.test(r.url()));if(r.method()==='PUT' && r.url().endsWith('/draft'))saves++;});
  try {
    await page.goto(fixture.charactersUrl);await page.locator('[data-person-index]').waitFor();
    await page.reload({waitUntil:'networkidle'});await page.locator('[data-person-index]').waitFor();
    const assets=await page.evaluate(()=>[...document.querySelectorAll('link[rel=stylesheet],script[src]')].map(n=>n.href||n.src));assertAssetVersions(assets);
    assert.deepEqual(new Set(await page.evaluate(()=>performance.getEntriesByType('resource').map(r=>r.name).filter(name=>/\/static\/[^?]+\.(?:css|js)(?:\?|$)/.test(name)))),new Set(assets));
    assert.equal(await page.locator('.visual-caption').count(),0,'No permanent co-occurrence disclaimer or map');
    assert.deepEqual(new Set(await page.locator('[data-person-id]').evaluateAll(ns=>ns.map(n=>n.dataset.personId))),new Set(names.map((_,i)=>'C'+i)));
    metrics.push(await capture(page,width,'model-people'));
    for(let i=0;i<4;i++) {
      await page.locator('[data-reader-open=C'+i+']').click();assert.equal(await page.locator('[data-reader-index]').count(),0);
      assert.match(await page.locator('[data-person-body]').innerText(),/暂无已记录的关系/);
      await page.locator('.workspace-object-page > .analysis-details > summary').click();
      const statuses=await page.locator('.analysis-details-body .analysis-badge').allTextContents();
      assert.ok(statuses.includes(['分析推断','人物说法','尚未确定','正文可证'][i]));
      assert.ok(statuses.includes(['正文可证','尚未确定','人物说法','分析推断'][i]));
      await page.locator('[data-reader-pane=experiences]').click();
      assert.deepEqual(new Set(await page.locator('[data-person-body] h3 [data-reader-open]').evaluateAll(ns=>ns.map(n=>n.dataset.readerOpen))),new Set(narrative.filter(id=>actors[id].includes(i))));
      const participants=await page.locator('[data-person-body] .workspace-participants [data-reader-open]').evaluateAll(ns=>ns.map(n=>n.dataset.readerOpen));
      for(const id of narrative.filter(id=>actors[id].includes(i)))for(const p of actors[id])assert.ok(participants.includes('C'+p));
      await page.locator('[data-reader-back]').click();assert.equal(await page.locator('[data-reader-open]:focus').getAttribute('data-reader-open'),'C'+i);
    }
    const search=page.locator('[data-person-index] input[type=search]');await search.fill('全量检索编号10');
    assert.equal(await page.locator('[data-person-id]').getAttribute('data-person-id'),'C9');
    await search.evaluate(n=>{n.value='组合输入';n.dispatchEvent(new InputEvent('input',{bubbles:true,isComposing:true}));});
    assert.equal(await page.locator('[data-person-id]').getAttribute('data-person-id'),'C9');
    await search.evaluate(n=>n.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true})));assert.equal(await page.locator('[data-person-id]').count(),0);
    await page.goto(fixture.plotUrl);await page.locator('[data-event-index]').waitFor();
    const ids=()=>page.locator('[data-event-id]').evaluateAll(ns=>ns.map(n=>n.dataset.eventId));
    assert.deepEqual(await ids(),narrative);
    await page.locator('[data-reader-open=E5]').click();await page.locator('[data-reader-back]').click();
    await page.locator('[data-reader-order=story]').click();assert.deepEqual(await ids(),story);assert.equal(new URL(page.url()).searchParams.get('selected'),'E5');
    await page.locator('[data-reader-order=narrative]').click();assert.deepEqual(await ids(),narrative);assert.equal(new URL(page.url()).searchParams.get('selected'),'E5');
    await page.locator('[data-reader-open=E5]').focus();await page.keyboard.press('ArrowRight');assert.equal(await page.locator('[data-reader-open]:focus').getAttribute('data-reader-open'),'E6');
    await page.keyboard.press('Home');assert.equal(await page.locator('[data-reader-open]:focus').getAttribute('data-reader-open'),'E3');
    metrics.push(await capture(page,width,'model-plot'));
    // Event semantics retain kind labels + uncertainty, separately from the path.
    await page.locator('[data-reader-open=E2]').click();await page.locator('.workspace-object-page > details').filter({hasText:'事件联系'}).locator('summary').first().click();
    assert.match(await page.locator('[data-event-relations]').innerText(),/促成/);assert.match(await page.locator('[data-event-relations]').innerText(),/先后/);
    assert.match(await page.locator('[data-event-relations]').innerText(),/分析推断/);await page.locator('[data-reader-back]').click();
    await page.locator('[data-reader-open=E5]').click();await page.locator('.workspace-event-body .analysis-proof > summary').first().click();
    await page.locator('.workspace-event-body .deconstruction-evidence-link').first().click();await page.locator('#locateDeconstructionEvidenceButton').click();
    await page.waitForFunction(q=>{const e=document.querySelector('#chapterEditor');return e.value.slice(e.selectionStart,e.selectionEnd)===q;},quotes.E5);
    assert.equal(saves,0);let workspace=await (await context.request.get(fixture.api)).json(),chapter=workspace.active_version.chapters[0];
    assert.equal(chapter.content,text1);assert.equal(await page.locator('[data-action=select-section],.chapter-section-list').count(),0);
    assert.equal(await page.locator('#archiveDrawer').isVisible(),false);
    // Official navigation puts only the caret in another chapter, never a section selection.
    const second=workspace.active_version.chapters[1];
    if(width===390)await page.locator('.mobile-chapter-navigation').selectOption(second.chapter_id);
    else await page.locator('[data-chapter-id="'+second.chapter_id+'"]').click();
    assert.equal(await page.locator('#chapterEditor').inputValue(),text2.replace(/\r\n/g,'\n'));
    assert.equal(await page.locator('#chapterEditor').evaluate(n=>n.selectionStart===n.selectionEnd),true);
    assert.equal(saves,0);
    metrics.push(await capture(page,width,'editor'));
    assert.deepEqual(await page.evaluate(()=>window.XumaiChapterSections.read(undefined,'old-chapter','正文')),[]);
    assert.deepEqual(await page.evaluate(()=>window.XumaiChapterSections.read({x:[{section_id:'bad',title:'越界',start:0,end:9,kind:'explicit'}]},'x','正文')),[]);
    assert.equal(await page.evaluate(()=>window.XumaiChapterSections.locate(document.querySelector('#chapterEditor'),{start:0,end:1},'不同版本的正文')),false);
    if(width===390) {
      // Replaces obsolete stale-section projection with the formal resegmentation barrier.
      await page.locator('.mobile-chapter-navigation').selectOption(chapter.chapter_id);
      const changed='新增一行😀。\n'+text1.replace(/\r\n/g,'\n');
      await page.locator('#chapterEditor').fill(changed);
      await page.locator('.chapter-management > summary').click();await page.locator('[data-action=resegment-chapters]').click();
      await page.waitForFunction(()=>/确认|草稿|修改/.test(document.querySelector('#editorNotice').textContent));
      assert.equal(await page.locator('.chapter-preview-dialog').count(),0);
      const updated=await (await context.request.get(fixture.api)).json();
      assert.equal(updated.active_version.chapters[0].content,changed);assert.equal(updated.active_version.chapters[0].chapter_id,chapter.chapter_id);
      assert.equal(updated.active_version.chapters.length,2);
      const stale=await (await context.request.get(fixture.api+'/deconstruction')).json();
      assert.equal(stale.effective_status,'rebuild_required');assert.equal(stale.error.code,'pending_changes');assert.equal(stale.actions.rebuild,false);
      const saved=saves;await page.locator('.mobile-chapter-navigation').selectOption(second.chapter_id);assert.equal(saves,saved);
    }
    assert.deepEqual(errors,[]);return {width,assetRelease,assets,metrics,errors};
  } catch(error){await page.screenshot({path:path.join(out,width+'-failure.png'),fullPage:true});throw error;}finally{await context.close();}
}
(async()=>{
  assertAssetVersions(shellAssets(await fs.readFile(path.join(__dirname,'../frontend/index.html'),'utf8')));
  await fs.mkdir(out,{recursive:true});const browser=await chromium.launch({headless:true,channel:process.env.XUMAI_BROWSER_CHANNEL||'chrome'});
  try {const fixture=await setup(browser);if(process.argv.includes('--setup-only')){console.log(JSON.stringify({...fixture,storageState:undefined}));return;}
    const results=[];for(const width of [1440,1100,1024,390])results.push(await verify(browser,fixture,width));
    await fs.writeFile(path.join(out,'report.json'),JSON.stringify({results},null,2));console.log(JSON.stringify(results));
  }finally{await browser.close();}
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
