/* Intercepted synthetic SPA only: no service, real account, manuscript store,
 * model or paid call. Exercise the actual library -> create -> editor flow. */
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {chromium}=require('playwright');
const {fixture,origin,root}=require('./test_stage38_frontend_browser.cjs');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'}),results=[];
 const out=await fs.mkdtemp(path.join(os.tmpdir(),'xumai-stage38-switch-'));
 try{for(const width of [1440,390]){
  const context=await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce'}),page=await context.newPage();
  const {workspace,response}=fixture(),original=JSON.stringify(workspace),errors=[],writes=[],failures=[];
  const projects=[{project_id:'p1',title:workspace.title,mode:'independent',status:'写作中',progress_percent:30,chapter_count:6,total_word_count:300}];
  const gates=new Map(),released=new Set(),account={account_id:'synthetic',email:'switch.reader@example.test'};
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(['error','warning'].includes(m.type()))errors.push(m.text());});
  page.on('response',r=>{if(r.status()===503)failures.push(new URL(r.url()).pathname);});
  await context.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname;assert.equal(url.origin,origin);
   const json=data=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
   if(p.startsWith('/static/')){const n=p.slice(8);assert.ok(/^[a-z0-9.-]+$/.test(n));return route.fulfill({status:200,contentType:n.endsWith('.css')?'text/css':n.endsWith('.svg')?'image/svg+xml':'text/javascript',body:await fs.readFile(path.join(root,'frontend',n))});}
   if(!p.startsWith('/api/'))return route.fulfill({status:200,contentType:'text/html',body:await fs.readFile(path.join(root,'frontend/index.html'))});
   if(req.method()!=='GET')writes.push({method:req.method(),path:p,body:req.postDataJSON()});
   if(p==='/api/auth/session')return json({authenticated:true,account});
   if(p==='/api/library')return json({account,projects});
   if(p==='/api/notifications')return json({notifications:[],unread_count:0});
   if(p==='/api/library/projects' && req.method()==='POST'){
    const body=req.postDataJSON();assert.equal(body.mode,'independent');
    const project={project_id:body.title,title:body.title,mode:body.mode,status:'尚未开始',progress_percent:0,chapter_count:0,total_word_count:0};projects.push(project);return json({project});
   }
   if(p==='/api/independent/projects/p1')return json(workspace);
   if(p.endsWith('/deconstruction'))return json({...response,effective_status:'empty',result:null,active_run:null});
   const created=p.match(/^\/api\/independent\/projects\/(blank|failed|late-failed)$/);
   if(created){
    const id=created[1];assert.ok(!gates.has(id),'Creating a book must issue exactly one workspace read');
    await new Promise(resolve=>gates.set(id,resolve));
    if(id==='blank')return json({project_id:id,title:id,mode:'independent',initialized:false,archive:{},tasks:[],pending_imports:[],active_version:null});
    await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:{message:'合成网络失败，请稍后重试。'}})});released.add(id);return;
   }
   throw Error(`Unexpected synthetic request: ${req.method()} ${p}`);
  });
  const clear=async()=>{
   assert.equal(await page.locator('#chapterList').innerHTML(),'');
   assert.equal(await page.locator('#chapterEditor').inputValue(),'');
   assert.equal(await page.locator('#chapterTitleInput').inputValue(),'');
   assert.equal(await page.locator('#chapterEditor').isDisabled(),true);
   assert.equal(await page.locator('#chapterTitleInput').isDisabled(),true);
   assert.equal(await page.locator('#chapterTitlePrefix').textContent(),'');
   assert.equal(await page.locator('#editorWorkspaceContent').isVisible(),false);
   assert.equal(await page.locator('#archiveSummary').innerHTML(),'');
   assert.equal(await page.locator('[data-action=save-editor]').isDisabled(),true);
   assert.equal(await page.locator('#completeChapterButton').isDisabled(),true);
   assert.equal(new URL(page.url()).searchParams.has('chapter'),false);
  };
  const library=async()=>{
   await page.locator('#independentScreen .editor-brand').click();
   await page.locator('#newProjectButton').waitFor();
   await page.locator('[data-project-id=p1]').waitFor();
  };
  const openExisting=async()=>{
   await page.locator('[data-project-id=p1]').click();await page.locator('#chapterEditor').waitFor();
   assert.equal(await page.locator('.chapter-list-copy strong').count(),6);
   assert.equal(await page.locator('#chapterEditor').isDisabled(),false);
   assert.equal(await page.locator('#chapterTitleInput').isDisabled(),false);
   assert.equal(await page.locator('#chapterEditor').inputValue(),workspace.active_version.chapters.at(-1).content.replace(/\r\n/g,'\n'));
  };
  const create=async id=>{
   await page.locator('#newProjectButton').click();
   assert.ok(!(await page.locator('#newProjectDialog').innerText()).includes('下一阶段'));
   await page.locator('[data-mode=independent]').click();await page.locator('#projectTitleInput').fill(id);
   assert.equal((await page.locator('#createProjectButton').textContent()).replace(/\s+/g,' ').trim(),'创建作品 →');
   await page.locator('#createProjectButton').click();await page.waitForURL(`**/independent/${id}`);
   await page.waitForFunction(()=>document.querySelector('#editorProjectTitle').textContent==='正在读取…');
   assert.ok(gates.has(id));await clear();
  };
  try{
   await page.goto(origin+'/independent/p1?chapter=c4');await page.locator('#chapterEditor').waitFor();
   assert.equal(await page.locator('#chapterTitleInput').inputValue(),'第四章 来信');
   await library();await create('blank');gates.get('blank')();
   await page.locator('[data-action=start-blank]').waitFor();await clear();
   assert.equal(await page.locator('#editorProjectTitle').innerText(),'blank');
   assert.equal(await page.locator('#editorAnalysisState').innerText(),'尚未开始');
   assert.equal(await page.locator('#editorWordCount').innerText(),'0 字');
   await page.screenshot({path:path.join(out,`${width}-blank-synthetic.png`),fullPage:true});
   await library();await openExisting();await library();await create('failed');gates.get('failed')();
   await page.waitForFunction(()=>document.querySelector('#editorProjectTitle').textContent==='读取失败');await clear();
   assert.ok((await page.locator('#editorNotice').innerText()).includes('合成网络失败'));
   assert.equal(await page.locator('#startWorkspaceContent').innerHTML(),'');
   await page.screenshot({path:path.join(out,`${width}-failed-synthetic.png`),fullPage:true});
   await library();await openExisting();await library();await create('late-failed');
   await library();await openExisting();
   const lateResponse=page.waitForResponse(r=>r.status()===503&&r.url().endsWith('/late-failed'));
   gates.get('late-failed')();await (await lateResponse).finished();
   const deadline=Date.now()+5000;while(!released.has('late-failed')&&Date.now()<deadline)await new Promise(r=>setTimeout(r,10));
   assert.equal(released.has('late-failed'),true);
   await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
   assert.equal(await page.locator('#editorProjectTitle').innerText(),workspace.title);
   assert.equal(await page.locator('.chapter-list-copy strong').count(),6);
   assert.equal(await page.locator('#editorNotice').isVisible(),false);
   assert.equal(JSON.stringify(workspace),original,'Switching/creating cannot change the previous manuscript');
   assert.equal(writes.length,3);assert.ok(writes.every(w=>w.method==='POST'&&w.path==='/api/library/projects'));
   assert.deepEqual(failures.sort(),['/api/independent/projects/failed','/api/independent/projects/late-failed']);
   assert.equal(errors.length,2,'Only the two intentional 503 console messages are expected');
   assert.ok(errors.every(e=>/503/.test(e)),JSON.stringify(errors));
   results.push({width,newBooks:writes.length,oldContentPreserved:true,expected503:failures.length,unexpectedErrors:0});
  }finally{for(const release of gates.values())release();await context.close();}
 }
 console.log(JSON.stringify({synthetic:true,screenshots:out,results},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
