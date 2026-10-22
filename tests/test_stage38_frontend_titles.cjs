/* Structural numbering and save boundaries on intercepted synthetic pages.
 * No service, real account, author manuscript or model is accessed. */
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path');
const {chromium}=require('playwright');
const {fixture,origin,root}=require('./test_stage38_frontend_browser.cjs');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'}),results=[];
 try{for(const width of [1440,390]){
  const context=await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce'}),page=await context.newPage();
  const {workspace,response}=fixture(),errors=[],writes=[];
  const rawTitles=['Chapter 7 Departure','第九章：归航','第三章 故人','Chapter 4 Return','Chapter 7 Explicit','第九章—旧约'];
  const numbers=[1,2,3,4,7,9],expected=['第一章 Departure','第二章 归航','第三章 故人','Chapter 4 Return','Chapter 7 Explicit','第九章—旧约'];
  workspace.active_version.chapters.forEach((chapter,i)=>{chapter.title=rawTitles[i];chapter.chapter_number=numbers[i];});
  const original=JSON.stringify(workspace),bodies=workspace.active_version.chapters.map(c=>c.content);
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(['error','warning'].includes(m.type()))errors.push(m.text());});
  await context.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname;assert.equal(url.origin,origin);
   const json=data=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
   if(p.startsWith('/static/')){const n=p.slice(8);assert.ok(/^[a-z0-9.-]+$/.test(n));return route.fulfill({status:200,contentType:n.endsWith('.css')?'text/css':n.endsWith('.svg')?'image/svg+xml':'text/javascript',body:await fs.readFile(path.join(root,'frontend',n))});}
   if(!p.startsWith('/api/'))return route.fulfill({status:200,contentType:'text/html',body:await fs.readFile(path.join(root,'frontend/index.html'))});
   if(p==='/api/auth/session')return json({authenticated:true,account:{account_id:'synthetic',email:'chapter.reader@example.test'}});
   if(p==='/api/notifications')return json({notifications:[],unread_count:0});
   if(p==='/api/independent/projects/p1')return json(workspace);
   if(p.endsWith('/deconstruction'))return json({...response,effective_status:'empty',run_status:'none',source_match:false,source:{...response.source,match:false},result:null,active_run:null});
   const draft=p.match(/\/chapters\/(c\d+)\/draft$/);
   if(draft && req.method()==='PUT'){
    const chapter=workspace.active_version.chapters.find(c=>c.chapter_id===draft[1]),body=req.postDataJSON();
    const i=writes.length;
    if(i===0){assert.equal(body.title,rawTitles[0]);assert.equal(body.content,bodies[0].replace(/\r\n/g,'\n')+'作者新增一行。');}
    if(i===1){assert.equal(body.title,'新的离岸');assert.equal(body.content,chapter.content);}
    if(i===2){assert.equal(body.title,'第九章—作者新题');assert.equal(body.content,bodies[1]);}
    assert.ok(i<3,'Viewing/reopening must never create an extra save');
    writes.push(body);Object.assign(chapter,{title:body.title,content:body.content,server_revision:chapter.server_revision+1});return json({workspace,chapter});
   }
   throw Error(`Unexpected request: ${req.method()} ${p}`);
  });
  const save=async()=>{
   const response=page.waitForResponse(r=>r.request().method()==='PUT'&&r.url().endsWith('/draft'));
   await page.locator('[data-action=save-editor]').click();await response;
   await page.waitForFunction(()=>document.querySelector('#editorSaveState').textContent==='已保存');
  };
  try{
   await page.goto(origin+'/independent/p1?chapter=c1');await page.locator('#chapterEditor').waitFor();
   assert.deepEqual(await page.locator('.chapter-list-copy strong').allTextContents(),expected);
   assert.deepEqual(await page.locator('.mobile-chapter-navigation option').allTextContents(),expected);
   assert.equal(await page.locator('#chapterTitleInput').inputValue(),'第一章 Departure');
   assert.equal(await page.locator('#chapterTitlePrefix').isVisible(),false);
   await page.locator('[data-action=save-editor]').click();assert.equal(writes.length,0);
   assert.equal(JSON.stringify(workspace),original,'Display normalization must not mutate source title or manuscript');
   const preview={preview_id:'synthetic-heading',revision:1,kind:'import',status:'pending',expires_at:new Date(Date.now()+600000).toISOString(),source_text:bodies[0],source_length:bodies[0].length,chapters:[{start:0,title:rawTitles[0],confidence:'explicit'}]};
   await page.evaluate(preview=>window.XumaiChapterPreview.open(preview,{projectId:'p1',request:()=>{throw Error('Display must not request or write a preview');}}),preview);
   assert.equal(await page.locator('[data-preview-title]').inputValue(),'第一章 Departure');
   assert.equal(await page.locator('[data-preview-current]').innerText(),'第一章 Departure');
   await page.locator('[data-preview-close]').click();
   assert.equal(JSON.stringify(workspace),original);assert.equal(writes.length,0);
   await page.locator('#chapterEditor').fill(bodies[0].replace(/\r\n/g,'\n')+'作者新增一行。');await save();
   assert.equal(workspace.active_version.chapters[0].title,rawTitles[0]);
   await page.reload();await page.waitForFunction(()=>document.querySelector('#chapterTitleInput').value==='第一章 Departure');
   assert.equal(writes.length,1);
   await page.locator('#chapterTitleInput').fill('新的离岸');await save();
   assert.equal(workspace.active_version.chapters[0].title,'新的离岸');
   assert.equal(await page.locator('#chapterTitlePrefix').innerText(),'第一章');
   await page.goto(origin+'/independent/p1?chapter=c2');await page.waitForFunction(()=>document.querySelector('#chapterTitleInput').value==='第二章 归航');
   assert.equal(workspace.active_version.chapters[1].title,rawTitles[1]);assert.equal(writes.length,2);
   await page.locator('#chapterTitleInput').fill('第九章—作者新题');await save();
   assert.equal(workspace.active_version.chapters[1].title,'第九章—作者新题');
   assert.equal(await page.locator('#chapterTitleInput').inputValue(),'第二章 作者新题');
   assert.equal(workspace.active_version.chapters[1].content,bodies[1]);
   assert.equal(await page.locator('.chapter-list-copy strong').nth(4).innerText(),'Chapter 7 Explicit');
   assert.equal(await page.locator('.chapter-list-copy strong').nth(5).innerText(),'第九章—旧约');
   assert.deepEqual(errors,[]);results.push({width,writes:writes.length,consoleErrors:errors.length});
  }finally{await context.close();}
 }
 console.log(JSON.stringify({synthetic:true,results},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
