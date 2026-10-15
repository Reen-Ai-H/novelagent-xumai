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
async function setup(browser) {
  const context=await browser.newContext(),page=await context.newPage(),email=`stage36-visual-${Date.now()}@example.test`;
  await page.goto(`${origin}/login`);await page.locator('#emailInput').fill(email);await page.locator('#emailSubmitButton').click();await page.waitForURL('**/library');
  async function project(title) {
    await page.goto(`${origin}/library`);await page.locator('#newProjectButton').click();await page.locator('[data-mode=independent]').click();
    await page.locator('#projectTitleInput').fill(title);await page.locator('#createProjectButton').click();await page.waitForURL('**/independent/*');return page.url().split('?')[0];
  }
  const url=await project('合成验收 · 十人六事件与章内小节'),id=new URL(url).pathname.split('/').pop(),api=`${origin}/api/independent/projects/${id}`;
  const preview=page.waitForResponse(r=>r.url().endsWith('/imports/preview'));
  await page.locator('#importFileInput').setInputFiles({name:'章内目录合成.txt',mimeType:'text/plain',buffer:Buffer.from(`第1章 合成记录\r\n${body1}第2章 后续记录\r\n${body2}`)});
  const parsed=(await (await preview).json()).preview;
  assert.equal(parsed.chapter_count,2);assert.equal(parsed.chapters[0].content,body1);assert.equal(parsed.chapters[1].content,body2);
  assert.equal(parsed.chapter_sections['1'].length,7);assert.equal(parsed.chapter_sections['2'].length,1);
  await page.locator('.import-chapter-preview summary').first().click();
  assert.equal(await page.locator('.import-section-outline').first().locator('li').count(),7);
  assert.equal(await page.locator('.import-chapter-body').first().textContent(),body1.replace(/\r\n/g,'\n'),'HTML normalizes CRLF only for display');
  await page.screenshot({path:path.join(out,'import-preview.png')});
  await page.locator('[data-action=confirm-import]').click();await page.locator('#chapterEditor').waitFor();
  let workspace=await (await context.request.get(api)).json();
  assert.equal(workspace.active_version.chapters[0].content,body1);assert.equal(workspace.active_version.chapters[1].content,body2);
  assert.equal(workspace.active_version.chapters.length,2,'Small sections must not become official chapters');
  const response=await context.request.post(`${api}/deconstruction/import`,{data:{report:modelReport()}});
  assert.equal(response.status(),200,await response.text());const report=(await response.json()).result;
  assert.equal(report.analysis_contract_version,'model.1');assert.ok(report.report.characters.every(p=>!Object.hasOwn(p,'importance')));
  const fixture={email,url,id,api,documentId:report.document_id,charactersUrl:`${url}?view=deconstruction&volume=${report.document_id}&section=characters`,plotUrl:`${url}?view=deconstruction&volume=${report.document_id}&section=plot`,synthetic:true};
  await fs.writeFile(path.join(out,'fixture.json'),JSON.stringify(fixture,null,2));
  // New Markdown and DOCX imports, each through the same real browser preview.
  const md='## 第1章 起点\r\n开篇。\r\n### 小节甲\r\n甲正文。\r\n### 小节乙\r\n乙正文。\r\n## 第2章 后续\r\n丙正文。';
  const localPython=path.join(__dirname,'..','.venv',...(process.platform==='win32'?['Scripts','python.exe']:['bin','python']));
  const python=process.env.XUMAI_TEST_PYTHON || (existsSync(localPython)?localPython:(process.platform==='win32'?'python':'python3'));
  const docx=execFileSync(python,['-c',`import io,zipfile,sys\nb=io.BytesIO()\nwith zipfile.ZipFile(b,'w') as z:\n z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'+''.join('<w:p><w:r><w:t>'+t+'</w:t></w:r></w:p>' for t in ['第一章 起点','开篇。','第一节 小节甲','甲正文。','第二节 小节乙','乙正文。','第二章 后续','丙正文。'])+'</w:body></w:document>')\nsys.stdout.buffer.write(b.getvalue())`]);
  for(const [name,buffer] of [['目录合成.md',Buffer.from(md)],['目录合成.docx',docx]]) {
    const extraUrl=await project(`导入格式验证 ${name}`),extraApi=`${origin}/api/independent/projects/${new URL(extraUrl).pathname.split('/').pop()}`;
    const pending=page.waitForResponse(r=>r.url().endsWith('/imports/preview'));
    await page.locator('#importFileInput').setInputFiles({name,mimeType:'application/octet-stream',buffer});
    const data=(await (await pending).json()).preview;assert.equal(data.chapter_count,2);assert.equal(data.chapter_sections['1'].length,3);
    await page.locator('.import-chapter-preview summary').first().click();assert.equal(await page.locator('.import-section-outline').first().locator('li').count(),3);
    await page.locator('[data-action=confirm-import]').click();await page.locator('#chapterEditor').waitFor();
    const saved=await (await context.request.get(extraApi)).json();assert.deepEqual(saved.active_version.chapters.map(c=>c.content),data.chapters.map(c=>c.content));
  }
  const storageState=await context.storageState();await context.close();return {...fixture,storageState};
}
async function capture(page,width,label) {
  await page.evaluate(()=>scrollTo(0,0));
  const data=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scroll:document.documentElement.scrollWidth,body:document.body.scrollWidth,
    elements:document.querySelectorAll('*').length,text:document.body.innerText.length,
    nodes:[...document.querySelectorAll('.visual-node')].map(n=>({id:n.dataset.visualNode || n.dataset.visualNeighbor,top:n.getBoundingClientRect().top,bottom:n.getBoundingClientRect().bottom})),
    overlaps:[...document.querySelectorAll('.visual-edge text,.visual-coactors')].filter(t=>t.textContent).flatMap(t=>{const a=t.getBoundingClientRect();return [...document.querySelectorAll('.visual-node')].filter(n=>{const b=n.getBoundingClientRect();return a.left<b.right && a.right>b.left && a.top<b.bottom && a.bottom>b.top;}).map(n=>({label:t.textContent,node:n.title}));}),
    clippedActors:[...document.querySelectorAll('.visual-coactors')].filter(n=>n.getBoundingClientRect().bottom>n.closest('.visual-canvas').getBoundingClientRect().bottom).length,
    graphBottom:document.querySelector('.visual-map-items').getBoundingClientRect().bottom,detailTop:document.querySelector('.visual-selected').getBoundingClientRect().top}));
  assert.ok(data.scroll<=width && data.body<=width,`${label} overflow: ${JSON.stringify(data)}`);
  assert.ok(data.nodes[0].bottom<=data.height,`${label}: first graph node outside first screen ${JSON.stringify(data)}`);
  assert.ok(data.elements<2000 && data.text<12000,'Bounded primary DOM/text');assert.deepEqual(data.overlaps,[],`${label}: edge labels or participant chips cover nodes`);
  assert.equal(data.clippedActors,0,'All participant chips must fit inside the graph');
  if(width<=1100)assert.ok(data.detailTop>=data.graphBottom,'Graph must precede the selected summary');
  await page.screenshot({path:path.join(out,`${width}-${label}.png`)});
  await page.screenshot({path:path.join(out,`${width}-${label}-full.png`),fullPage:true});
  if(label==='model-people')await page.locator('.visual-map-items').screenshot({path:path.join(out,`${width}-people-graph.png`)});
  return {label,...data};
}
async function verify(browser,fixture,width) {
  const context=await browser.newContext({storageState:fixture.storageState,viewport:{width,height:width===390?844:900},reducedMotion:'reduce'}),page=await context.newPage(),errors=[],metrics=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(['error','warning'].includes(m.type()))errors.push(m.text());});
  let saves=0;page.on('request',r=>{assert.equal(new URL(r.url()).origin,origin);assert.ok(!r.url().endsWith('/book/start'));if(r.method()==='PUT' && r.url().endsWith('/draft'))saves++;});
  try {
    await page.goto(fixture.charactersUrl);await page.locator('.visual-node').first().waitFor();
    assert.equal(await page.locator('[data-reading-mode=map]').getAttribute('aria-pressed'),'true');
    assert.match(await page.locator('.visual-caption').innerText(),/共同经历.*不代表敌友或亲属/);
    assert.ok(await page.locator('[data-visual-actor]').count()>0,'Other participants must be on the graph, not hidden in long details');
    assert.equal(await page.locator('.visual-selected').count(),1);metrics.push(await capture(page,width,'model-people'));
    const summaryStatuses=()=>page.locator('.visual-person-summary .visual-summary-status').allTextContents();
    assert.deepEqual(await summaryStatuses(),['分析推断','正文可证']);
    const people=page.locator('[data-model-map]');
    await people.locator('[data-visual-roster]').first().click();await page.locator('.analysis-modal').waitFor();
    assert.equal(await page.locator('.visual-roster button').count(),6);await page.keyboard.press('Escape');
    await page.locator('[data-visual-actor=C1]').first().click();assert.equal(await page.locator('.visual-selected').getAttribute('data-selected-id'),'C1');
    assert.deepEqual(await summaryStatuses(),['人物说法','尚未确定']);
    await page.locator('[data-visual-pick=C2]').click();assert.deepEqual(await summaryStatuses(),['尚未确定','人物说法']);
    await page.locator('[data-visual-pick=C3]').click();assert.deepEqual(await summaryStatuses(),['正文可证','分析推断']);
    await page.locator('[data-visual-pick=C0]').click();
    const shared=[];
    while(true) {
      shared.push(...await page.locator('[data-visual-neighbor]').evaluateAll(ns=>ns.map(n=>n.dataset.visualNeighbor)));
      const next=page.locator('[data-neighbor-page]').last();if(await next.isDisabled())break;
      await next.focus();await page.keyboard.press('Enter');
      assert.equal(await page.locator('[data-visual-node=C0]').evaluate(n=>n===document.activeElement),true);
    }
    assert.deepEqual(new Set(shared),new Set(narrative.filter(id=>actors[id].includes(0))),'Every shared event must remain reachable');
    // All ten people remain reachable through real pagination and full search.
    const seen=[];for(const n of ['1','2']) {await people.locator(':scope > nav select').selectOption(n);seen.push(...await page.locator('[data-visual-pick]').evaluateAll(ns=>ns.map(n=>n.dataset.visualPick)));}
    assert.deepEqual(new Set(seen),new Set(names.map((_,i)=>`C${i}`)));
    const search=people.locator(':scope > form input[type=search]');await search.fill('全量检索编号10');
    assert.equal(await search.evaluate(n=>n===document.activeElement),true);assert.equal(await page.locator('[data-visual-pick]').getAttribute('data-visual-pick'),'C9');
    await search.evaluate(n=>{n.value='组合输入';n.dispatchEvent(new InputEvent('input',{bubbles:true,isComposing:true}));});
    assert.equal(await page.locator('[data-visual-pick]').getAttribute('data-visual-pick'),'C9');
    await search.evaluate(n=>n.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true})));assert.equal(await page.locator('[data-visual-pick]').count(),0);
    await page.locator('[data-reading-mode=list]').click();assert.equal(await page.locator('[data-reading-mode=list]').getAttribute('aria-pressed'),'true');
    await page.locator('[data-model-people] [data-browser-clear]').click();assert.equal(await page.locator('.analysis-person').count(),8);
    await page.locator('[data-reading-mode=map]').click();await page.goto(fixture.plotUrl);await page.locator('[data-visual-node]').first().waitFor();
    const nodeIds=()=>page.locator('[data-visual-node]').evaluateAll(ns=>ns.map(n=>n.dataset.visualNode));
    assert.deepEqual(await nodeIds(),narrative);
    assert.equal(await page.locator('[data-edge-kind=follows]').count(),2);assert.equal(await page.locator('[data-edge-kind=causes]').count(),2);
    const strokes=await page.evaluate(()=>['follows','causes'].map(kind=>{const n=document.querySelector(`[data-edge-kind=${kind}] path`),s=getComputedStyle(n);return [s.stroke,s.strokeDasharray];}));assert.notDeepEqual(strokes[0],strokes[1]);
    await page.locator('[data-visual-node=E5]').click();await page.locator('[data-report-time=story]').click();assert.deepEqual(await nodeIds(),story);assert.equal(await page.locator('.visual-selected').getAttribute('data-selected-id'),'E5');
    await page.locator('[data-report-time=narrative]').click();assert.deepEqual(await nodeIds(),narrative);assert.equal(await page.locator('.visual-selected').getAttribute('data-selected-id'),'E5');
    await page.locator('[data-visual-node=E5]').focus();await page.keyboard.press('ArrowRight');assert.equal(await page.locator('[data-visual-node=E6]').getAttribute('aria-pressed'),'true');await page.keyboard.press('Home');assert.equal(await page.locator('[data-visual-node=E3]').evaluate(n=>n===document.activeElement),true);
    metrics.push(await capture(page,width,'model-plot'));
    // Evidence retains exact source selection; chapter navigation uses a caret.
    await page.locator('[data-visual-node=E5]').click();await page.locator('.visual-selected > article > details > summary').click();
    await page.locator('.visual-selected .analysis-proof > summary').first().click();await page.locator('.visual-selected .deconstruction-evidence-link').first().click();
    await page.locator('#deconstructionEvidenceDialog[open]').waitFor();await page.locator('#locateDeconstructionEvidenceButton').click();await page.locator('#chapterEditor').waitFor();
    await page.waitForFunction(q=>{const e=document.querySelector('#chapterEditor');return e.value.slice(e.selectionStart,e.selectionEnd)===q;},quotes.E5);
    assert.equal(saves,0,'Evidence navigation must not write the manuscript');
    let workspace=await (await context.request.get(fixture.api)).json();assert.equal(workspace.active_version.chapters[0].content,body1);
    const chapter=workspace.active_version.chapters[0],sections=workspace.chapter_sections[chapter.chapter_id],last=sections.at(-1);
    assert.equal(await page.locator('#openVersionButton').isVisible(),false);assert.equal(await page.locator('#archiveDrawer').isVisible(),false);
    assert.equal(await page.locator('.chapter-list-item').count(),2);
    const target=page.locator(`[data-action=select-section][data-section-id="${last.section_id}"]`);
    await target.focus();await page.keyboard.press('Enter');
    const start=body1.slice(0,last.start).replace(/\r\n/g,'\n').length;
    await page.waitForFunction(n=>{const e=document.querySelector('#chapterEditor');return e.selectionStart===n && e.selectionEnd===n;},start);
    assert.ok(await page.locator('#chapterEditor').evaluate(n=>n.scrollTop>100));assert.equal(saves,0);
    const afterNavigation=await (await context.request.get(fixture.api)).json();assert.equal(afterNavigation.active_version.chapters[0].content,body1);assert.equal(afterNavigation.active_version.chapters[0].server_revision,chapter.server_revision);
    metrics.push(await (async()=>{
      await page.evaluate(()=>scrollTo(0,0));
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth && document.body.scrollWidth<=innerWidth));
      await page.screenshot({path:path.join(out,`${width}-editor-full.png`),fullPage:true});
      await page.locator('#chapterEditor').evaluate(n=>n.scrollIntoView({block:'center',behavior:'instant'}));
      const viewport=await page.locator('#chapterEditor').evaluate(n=>{const r=n.getBoundingClientRect();return {top:r.top,bottom:r.bottom,height:innerHeight};});
      assert.ok(viewport.top<viewport.height && viewport.bottom>0,'The editor screenshot must contain the manuscript');
      await page.screenshot({path:path.join(out,`${width}-editor.png`)});return {label:'editor',exactCRLF:true,caret:start,viewport};
    })());
    // Exercise the old-backend fallback and invalid projection boundary directly.
    assert.deepEqual(await page.evaluate(()=>window.XumaiChapterSections.read(undefined,'old-chapter','正文')),[]);
    assert.deepEqual(await page.evaluate(()=>window.XumaiChapterSections.read({x:[{section_id:'bad',title:'越界',start:0,end:9,kind:'explicit'}]},'x','正文')),[]);
    assert.equal(await page.evaluate(()=>window.XumaiChapterSections.locate(document.querySelector('#chapterEditor'),{start:0,end:1},'不同版本的正文')),false);
    // Last viewport only: change this old chapter, click its stale section entry
    // immediately, then require a new projection before any caret navigation.
    if(width===390) {
      const changed='新增一行😀。\n'+body1.replace(/\r\n/g,'\n');
      await page.locator('#chapterEditor').fill(changed);
      assert.match(await page.locator('#chapterSectionStatus').innerText(),/先保存/);
      await target.click();await page.waitForFunction(()=>document.querySelector('#chapterSectionStatus')?.textContent.includes('位置已变化'));
      const updated=await (await context.request.get(fixture.api)).json(),updatedChapter=updated.active_version.chapters[0];
      assert.equal(updatedChapter.content,changed);assert.equal(updatedChapter.chapter_id,chapter.chapter_id);assert.equal(updated.active_version.chapters.length,2);
      const newLast=updated.chapter_sections[chapter.chapter_id].at(-1);assert.notEqual(newLast.section_id,last.section_id);
      const saveCount=saves;await page.locator(`[data-action=select-section][data-section-id="${newLast.section_id}"]`).click();
      await page.waitForFunction(n=>{const e=document.querySelector('#chapterEditor');return e.selectionStart===n && e.selectionEnd===n;},newLast.start);
      assert.equal(saves,saveCount,'Fresh navigation must not initiate another save');
      const stale=await (await context.request.get(`${fixture.api}/deconstruction`)).json();
      assert.equal(stale.effective_status,'rebuild_required');assert.equal(stale.error.code,'pending_changes');assert.equal(stale.actions.rebuild,false,'Unconfirmed author changes must gate report rebuilding');
    }
    assert.deepEqual(errors,[]);return {width,metrics,errors};
  } catch(error) {await page.screenshot({path:path.join(out,`${width}-failure.png`),fullPage:true});throw error;} finally {await context.close();}
}
(async()=>{
  await fs.mkdir(out,{recursive:true});const browser=await chromium.launch({headless:true,channel:process.env.XUMAI_BROWSER_CHANNEL || 'chrome'});
  try {const fixture=await setup(browser);if(process.argv.includes('--setup-only')){console.log(JSON.stringify({...fixture,storageState:undefined}));return;}
    const results=[];for(const width of [1440,1100,1024,390])results.push(await verify(browser,fixture,width));
    await fs.writeFile(path.join(out,'report.json'),JSON.stringify({browser:browser.version(),results},null,2));console.log(JSON.stringify(results));
  } finally {await browser.close();}
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
