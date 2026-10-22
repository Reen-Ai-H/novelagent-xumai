/* Sidebar-only acceptance in real Chromium. All data and requests are synthetic;
 * never starts a service or accesses manuscripts, models or paid operations. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {chromium}=require('playwright'),{fixture,root}=require('./test_stage38_frontend_browser.cjs');
const origin='http://sidebar-density.invalid';
(async()=>{
 const out=await fs.mkdtemp(path.join(os.tmpdir(),'xumai-stage38-sidebar-')),browser=await chromium.launch({headless:true,channel:'chrome'}),cases=[],fitFailures=[],screenshots=[];
 try{for(const [width,height]of [[1024,768],[1280,744],[1440,900],[390,844]]){
  const context=await browser.newContext({viewport:{width,height},offline:true,serviceWorkers:'block',reducedMotion:'reduce'}),page=await context.newPage(),errors=[];
  const {workspace,response}=fixture(),seed=structuredClone(workspace.active_version.chapters);
  let count=6;const requests=[];
  function current(){return {...workspace,title:'合成目录 · 留白检查',active_version:{...workspace.active_version,chapters:Array.from({length:count},(_,i)=>({...seed[i%6],chapter_id:`c${i+1}`,chapter_number:i+1,title:i<6?seed[i].title:`第${i+1}章 远处的灯`,content:`合成第${i+1}章。\n只用于布局与键盘测试。`}))}};}
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(['warning','error'].includes(m.type()))errors.push(m.text());});
  await context.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname;assert.equal(url.origin,origin);assert.equal(req.method(),'GET');requests.push(p);
   const json=body=>route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
   if(p.startsWith('/static/')){const n=p.slice(8);assert.match(n,/^[a-z0-9.-]+$/);return route.fulfill({contentType:n.endsWith('.css')?'text/css':n.endsWith('.svg')?'image/svg+xml':'text/javascript',body:await fs.readFile(path.join(root,'frontend',n))});}
   if(!p.startsWith('/api/'))return route.fulfill({contentType:'text/html',body:await fs.readFile(path.join(root,'frontend/index.html'))});
   if(p==='/api/auth/session')return json({authenticated:true,account:{account_id:'synthetic',email:'sidebar.reader@example.test'}});
   if(p==='/api/notifications')return json({notifications:[],unread_count:0});
   if(p==='/api/independent/projects/p1')return json(current());
   if(p.endsWith('/deconstruction'))return json({...response,title:current().title,effective_status:'empty',run_status:'none',source_match:false,focus_document_id:'',result:null,active_run:null,source:{...response.source,match:false,chapter_count:count}});
   if(p.endsWith('/book'))return json({job:null});
   if(p.endsWith('/model-budget'))return json({model_available:false});
   throw Error(`Unexpected synthetic operation ${p}`);
  });
  const side=page.locator('#independentScreen > .editor-spine'),rows=side.locator('.chapter-list-item'),mobile=side.locator('.mobile-chapter-navigation');
  async function open(n){count=n;await page.goto(origin+'/independent/p1?chapter=c1');await page.waitForFunction(()=>document.querySelector('#chapterEditor')?.value==='合成第1章。\n只用于布局与键盘测试。');await side.locator('[data-account-name]').waitFor();assert.equal(await rows.count(),n);}
  async function metrics(){return side.evaluate(n=>{
   const rect=e=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:r.width,height:r.height};};
   const list=n.querySelector('#chapterList'),column=n.querySelector('.chapter-column'),bottom=n.querySelector('.spine-bottom'),limit={top:Math.max(0,list.getBoundingClientRect().top,column.getBoundingClientRect().top),bottom:Math.min(innerHeight,list.getBoundingClientRect().bottom,column.getBoundingClientRect().bottom,bottom.getBoundingClientRect().top)};
   const rows=[...n.querySelectorAll('.chapter-list-item')].map(e=>({id:e.dataset.chapterId,...rect(e)}));
   const font=e=>{const c=getComputedStyle(e);return {fontSize:c.fontSize,fontFamily:c.fontFamily,lineHeight:c.lineHeight,color:c.color};};
   return {visibleChapters:rows.filter(r=>r.height>0&&r.top>=limit.top-.5&&r.bottom<=limit.bottom+.5).length,rows,limit,side:rect(n),account:rect(bottom),scroll:[list,column,n].map(e=>({className:e.className,clientHeight:e.clientHeight,scrollHeight:e.scrollHeight,scrollTop:e.scrollTop,overflow:getComputedStyle(e).overflowY})),appearance:{brand:font(n.querySelector('.spine-brand')),navigation:font(n.querySelector('.spine-link')),chapter:font(n.querySelector('.chapter-list-copy strong')),editor:font(document.querySelector('#chapterEditor')),sideBackground:getComputedStyle(n).backgroundColor,sideWidth:rect(n).width,writingWidth:rect(document.querySelector('.writing-column')).width,editorWidth:rect(document.querySelector('#chapterEditor')).width}};
  });}
  async function bounds(){
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No whole-page horizontal overflow');
   for(const selector of ['.spine-account','#editorLogoutButton','#addChapterButton','.chapter-management > summary']){
    const node=side.locator(selector);assert.equal(await node.isVisible(),true);assert.equal(await node.evaluate(n=>{const r=n.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&r.left>=0&&r.right<=innerWidth;}),true,`${selector} remains inside the viewport`);
   }
  }
  async function screenshot(name){const file=path.join(out,`${width}x${height}-${name}.png`);await page.screenshot({path:file});screenshots.push(file);}
  try{
   await open(6);await bounds();const six=await metrics();await screenshot('six-chapters');
   assert.equal(six.appearance.chapter.fontSize,'14.4px');assert.equal(six.appearance.editor.fontSize,width===390?'16.8px':'18.56px');
   if(width>700){
    if(six.visibleChapters!==6)fitFailures.push({width,height,visible:six.visibleChapters});
    assert.equal(await mobile.isVisible(),false);assert.equal(six.appearance.sideWidth,246);
    await rows.first().focus();await page.keyboard.press('Tab');assert.equal(await rows.nth(1).evaluate(n=>n===document.activeElement),true);
    await page.keyboard.press('Enter');await page.waitForURL('**chapter=c2');assert.match(await page.locator('#chapterEditor').inputValue(),/^合成第2章/);
   }else{
    assert.equal(await mobile.isVisible(),true);assert.equal(await mobile.locator('option').count(),6);assert.equal(await rows.first().isVisible(),false);
    await mobile.selectOption('c6');await page.waitForURL('**chapter=c6');assert.match(await page.locator('#chapterEditor').inputValue(),/^合成第6章/);
   }
   await side.locator('.chapter-management > summary').focus();await page.keyboard.press('Enter');
   assert.equal(await side.locator('.chapter-management').getAttribute('open'),'');assert.equal(await side.locator('[data-action=resegment-chapters]').isVisible(),true);assert.equal(await side.locator('[data-chapter-history]').isVisible(),true);
   await side.locator('.chapter-management > summary').focus();await page.keyboard.press('Enter');
   cases.push({width,height,case:'six chapters, keyboard and management controls',metrics:six});
   await open(40);await bounds();assert.equal(await rows.count(),40);
   if(width>700){
    const long=await metrics();assert.ok(long.scroll.some(s=>s.scrollHeight>s.clientHeight+100&&['auto','scroll'].includes(s.overflow)),'Long directories retain a real scroll region');
    await rows.first().focus();for(let i=1;i<40;i++)await page.keyboard.press('Tab');
    assert.equal(await rows.last().evaluate(n=>n===document.activeElement),true,'Every chapter is keyboard reachable without hidden rows');
    const atEnd=await metrics();assert.ok(atEnd.scroll.some(s=>s.scrollTop>0));
    assert.equal(atEnd.rows.at(-1).bottom<=atEnd.limit.bottom+.5,true,'Focused last chapter scrolls above the account');
    await page.keyboard.press('Enter');await page.waitForURL('**chapter=c40');assert.match(await page.locator('#chapterEditor').inputValue(),/^合成第40章/);
    await rows.first().focus();await side.locator('#chapterList').hover();await page.mouse.wheel(0,1200);
    await page.waitForFunction(()=>['#chapterList','.editor-spine .chapter-column'].some(s=>document.querySelector(s)?.scrollTop>100));
   }else{
    assert.equal(await mobile.locator('option').count(),40);await mobile.selectOption('c40');await page.waitForURL('**chapter=c40');assert.match(await page.locator('#chapterEditor').inputValue(),/^合成第40章/);
   }
   await bounds();await screenshot('long-directory');assert.deepEqual(errors,[]);assert.equal(await rows.count(),40);
   cases.push({width,height,case:'40 chapters remain scrollable and selectable',metrics:await metrics(),requests:requests.length});
  }catch(e){await screenshot('failure');console.error({out,width,errors});throw e;}
  finally{await context.close();}
 }
 const result={synthetic:true,out,cases,fitFailures,screenshots};await fs.writeFile(path.join(out,'results.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({out,cases:cases.length,fitFailures,screenshots},null,2));
 assert.deepEqual(fitFailures,[],'All six desktop chapter rows must be completely visible without scrolling');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
