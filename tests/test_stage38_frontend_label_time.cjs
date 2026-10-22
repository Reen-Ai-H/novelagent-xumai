/* Real DOM, synthetic intercepted GETs only. No service, author data or model.
 * Bounded label text must not turn measured buttons into guessed obstacles. */
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {chromium}=require('playwright');
const {fixture,root}=require('./test_stage38_frontend_browser.cjs');
const {denseFixture}=require('./test_stage38_frontend_route_fixture.cjs');
const {auditCases,auditFixture}=require('./test_stage38_frontend_route_search.cjs');
const {measure,check}=require('./test_stage38_frontend_routes.cjs');
const origin='http://bounded-label-time.invalid';
const longLabel='因共同调查旧港失踪船只而逐渐建立信任的同行者';
const timeNote='第三章为回忆，先后仍有不确定性。\n  不可据此确定绝对年代。\n<合成时间说明 & 原样保留>';
assert.equal([...longLabel].length,22);
(async()=>{
 const out=await fs.mkdtemp(path.join(os.tmpdir(),'xumai-stage38-label-time-')),browser=await chromium.launch({headless:true,channel:'chrome'}),summary=[];
 const fixtures=[['legacy6',fixture],['dense12',denseFixture],...auditCases().map(c=>[c.name,()=>auditFixture(c)])];
 try{for(const [kind,make]of fixtures)for(const [width,height]of [[1440,900],[1024,768],[390,844]]){
  const {workspace,response}=make(),report=response.result.report;
  report.character_relations[0].label=longLabel;report.time_note=timeNote;
  const before=JSON.stringify(response),context=await browser.newContext({viewport:{width,height},reducedMotion:'reduce'}),page=await context.newPage(),errors=[],requests=[],screenshots=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(['error','warning'].includes(m.type()))errors.push(m.text());});
  await context.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname;
   assert.equal(url.origin,origin);assert.equal(req.method(),'GET');requests.push(p);
   const json=d=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(d)});
   if(p.startsWith('/static/')){const n=p.slice(8);assert.ok(/^[a-z0-9.-]+$/.test(n));let body=await fs.readFile(path.join(root,'frontend',n),'utf8');
    if(n==='workspace-reader.js'){
     const hook='occupied.push({...best.box,segments:best.segments});';assert.equal(body.split(hook).length,2);
     body='window.__labelReservations=[];window.__readerMountTimes=[];\n'+body.replace(hook,'window.__labelReservations.push({...best.box});'+hook);
     body+='\n;(()=>{const R=window.XumaiWorkspaceReader;window.XumaiWorkspaceReader=Object.freeze({...R,mountModel(...args){const t=performance.now();try{return R.mountModel(...args);}finally{window.__readerMountTimes.push(performance.now()-t);}}});})();';
    }
    return route.fulfill({status:200,contentType:n.endsWith('.css')?'text/css':n.endsWith('.svg')?'image/svg+xml':'text/javascript',body});}
   if(!p.startsWith('/api/'))return route.fulfill({status:200,contentType:'text/html',body:await fs.readFile(path.join(root,'frontend/index.html'))});
   if(p==='/api/auth/session')return json({authenticated:true,account:{account_id:'synthetic',email:'bounded.synthetic@example.test'}});
   if(p==='/api/notifications')return json({notifications:[],unread_count:0});
   if(p.endsWith('/model-budget'))return json({model_available:false,budget:{budget_cny:0,estimated_spent_cny:0,reserved_cny:0,remaining_cny:0}});
   if(p.endsWith('/book'))return json({job:null});if(p.endsWith('/deconstruction'))return json(response);
   if(p==='/api/independent/projects/p1')return json(workspace);
   throw Error('Unexpected synthetic GET '+p);
  });
  const navigate=async q=>{await page.goto(origin+'/independent/p1?view=deconstruction&volume=doc&'+q);await page.locator('[data-reader-index]').waitFor();await page.evaluate(()=>document.fonts.ready);};
  const shot=async name=>{if(kind!=='dense12')return;const file=path.join(out,`${width}x${height}-${name}.png`);await page.screenshot({path:file});screenshots.push(file);};
  try{
   await navigate('section=characters&map=total');
   const people=await measure(page);check(people,report.characters.length,report.character_relations.length);
   assert.equal(await page.locator('.total-graph-position').count(),0,'People are not numbered');
   assert.deepEqual(await page.locator('path[data-total-from]').evaluateAll(ns=>ns.map(n=>[n.dataset.totalFrom,n.dataset.totalTo])),report.character_relations.map(r=>[r.from_id,r.to_id]));
   const dimensions=await page.locator('.total-graph-edge').evaluateAll(buttons=>{
    const canvas=buttons[0].closest('.total-graph-canvas').getBoundingClientRect(),boxes=window.__labelReservations.slice(-buttons.length);
    return buttons.map((b,i)=>{const r=b.getBoundingClientRect(),s=b.firstElementChild,sr=s.getBoundingClientRect(),css=getComputedStyle(s),badge=b.querySelector('.analysis-badge').getBoundingClientRect();
     return {width:r.width,height:r.height,textHeight:sr.height,lineHeight:parseFloat(css.lineHeight),fontSize:parseFloat(css.fontSize),clamp:css.webkitLineClamp,badgeInside:badge.top>=r.top&&badge.bottom<=r.bottom,reservation:boxes[i],actual:{left:r.left-canvas.left,right:r.right-canvas.left,top:r.top-canvas.top,bottom:r.bottom-canvas.top}};
    });
   });
   for(const d of dimensions){
    assert.equal(d.clamp,'2');assert.ok(d.textHeight<=d.lineHeight*2+.05,'At most two visible lines, not smaller type');assert.equal(d.fontSize,12.48);assert.equal(d.badgeInside,true);
    for(const name of ['left','right','top','bottom'])assert.ok(Math.abs(d.reservation[name]-d.actual[name])<.05,`Actual button and reserved ${name} disagree: ${JSON.stringify(d)}`);
   }
   const first=page.locator('.total-graph-edge').first(),accessibleName=await first.getAttribute('aria-label');
   assert.ok(accessibleName.includes(longLabel));assert.equal(await page.getByRole('button',{name:accessibleName,exact:true}).count(),1);
   await shot('people-two-line-label');
   for(const key of ['Enter','Space']){
    await first.focus();await page.keyboard.press(key);assert.equal(await page.locator('[data-edge-basis]').isVisible(),true);
    assert.ok((await page.locator('[data-edge-basis]').innerText()).includes(accessibleName));
    await page.locator('[data-close-basis]').focus();await page.keyboard.press('Enter');assert.equal(await first.evaluate(b=>b===document.activeElement),true);
   }
   const personId=report.characters[0].id;await page.locator(`[data-reader-open=${personId}]`).focus();await page.keyboard.press('Enter');
   await page.locator('[data-reader-detail=characters]').waitFor();await page.locator('[data-reader-back]').focus();await page.keyboard.press('Enter');await page.locator('.total-graph-scroll').waitFor();
   check(await measure(page),report.characters.length,report.character_relations.length);
   let timeChecked=false,styleMeasurementChecked=false;
   if(kind==='dense12'){
    assert.equal(await page.locator('[data-reader-time-note]').count(),0);
    await navigate('section=plot&map=total&order=narrative');
    const checkOrder=async ids=>{
     const cards=await page.locator('.total-graph-node').evaluateAll(ns=>ns.map(n=>({id:n.dataset.eventId,position:n.querySelector('.total-graph-position')?.textContent,source:n.querySelector('.eyebrow')?.textContent,title:n.querySelector('h2')?.textContent,href:n.querySelector('a')?.getAttribute('href')})));
     assert.deepEqual(cards.map(n=>n.id),ids);
     for(const [i,card]of cards.entries()){
      const event=report.events.find(e=>e.id===card.id),source=event.chapter_end&&event.chapter_end!==event.chapter_number?`第 ${event.chapter_number}–${event.chapter_end} 章`:`第 ${event.chapter_number} 章`;
      assert.equal(card.position,String(i+1).padStart(2,'0'));assert.ok(card.source.includes(source));assert.equal(card.title,event.title);
      const link=new URL(card.href,origin);assert.equal(link.searchParams.get('event'),event.id);assert.equal(link.searchParams.get('volume'),'doc');assert.equal(link.searchParams.get('section'),'plot');
     }
     assert.deepEqual(await page.locator('path[data-total-from]').evaluateAll(ns=>ns.map(n=>[n.dataset.totalFrom,n.dataset.totalTo])),report.relations.map(r=>[r.from_id,r.to_id]));
    };
    await checkOrder(report.events.map(e=>e.id));
    const note=page.locator('[data-reader-time-note]'),text=note.locator('p'),toggle=note.locator('summary');
    assert.equal(await note.count(),1);assert.equal(await note.evaluate(n=>n.open),false);assert.equal(await text.isVisible(),false);
    await page.locator('[data-reader-order=story]').click();assert.equal(await note.evaluate(n=>n.open),false);await checkOrder(report.story_order);
    await toggle.focus();await page.keyboard.press('Enter');assert.equal(await note.evaluate(n=>n.open),true);
    assert.equal(await text.textContent(),timeNote);assert.equal(await text.isVisible(),true);
    assert.equal(await text.evaluate(n=>getComputedStyle(n).whiteSpace),'pre-wrap');
    check(await measure(page),report.events.length,report.relations.length);await shot('events-story-time-note-expanded');
    await page.locator('[data-reader-order=narrative]').click();assert.equal(await note.evaluate(n=>n.open),true);await checkOrder(report.events.map(e=>e.id));
    check(await measure(page),report.events.length,report.relations.length);
    await page.locator('[data-reader-map=index]').click();assert.equal(await note.count(),1);assert.equal(await text.textContent(),timeNote);
    await page.locator('[data-reader-open=E0]').focus();await page.keyboard.press('Enter');await page.locator('[data-reader-detail=plot]').waitFor();
    await page.locator('[data-reader-back]').focus();await page.keyboard.press('Enter');assert.equal(await note.evaluate(n=>n.open),true);
    await toggle.focus();await page.keyboard.press('Space');assert.equal(await note.evaluate(n=>n.open),false);
    await navigate('section=time&map=total');await page.waitForFunction(()=>document.querySelector('[data-reader-time-note]')?.open);
    assert.equal(new URL(page.url()).searchParams.get('section'),'plot');assert.equal(await text.textContent(),timeNote);
    assert.equal(await toggle.evaluate(n=>n===document.activeElement),true);
    const box=await toggle.boundingBox();assert.ok(box.y>=0&&box.y+box.height<=height,'Old time link focuses a visible disclosure');
    for(const missing of ['',undefined]){report.time_note=missing;await navigate('section=plot&map=total');assert.equal(await note.count(),0);}
    report.time_note=timeNote;timeChecked=true;
    // A different real style must change the measured obstacles, not select
    // another guessed height. The override lives only in this intercepted page.
    await navigate('section=characters&map=total');
    const style=await page.addStyleTag({content:'.total-graph-edge { font-size:16px; padding:8px; }'});
    await page.locator('[data-reader-map=index]').click();await page.locator('[data-reader-map=total]').click();
    check(await measure(page),report.characters.length,report.character_relations.length);
    const styled=await page.locator('.total-graph-edge').evaluateAll(bs=>bs.map((b,i)=>{const r=b.getBoundingClientRect(),box=window.__labelReservations.slice(-bs.length)[i];return {height:r.height,reservedHeight:box.bottom-box.top,width:r.width,reservedWidth:box.right-box.left};}));
    assert.ok(styled[0].height>dimensions[0].height);
    for(const d of styled){assert.ok(Math.abs(d.height-d.reservedHeight)<.05);assert.ok(Math.abs(d.width-d.reservedWidth)<.05);}
    await style.evaluate(n=>n.remove());styleMeasurementChecked=true;
   }
   assert.equal(JSON.stringify(response),before);assert.deepEqual(errors,[]);
   const mountMs=await page.evaluate(()=>window.__readerMountTimes);assert.ok(mountMs.length);assert.ok(Math.max(...mountMs)<2000,`Synchronous mount too long: ${mountMs}`);
   summary.push({kind,width,height,nodes:people.nodes,edges:people.edges,longLabelButton:dimensions[0],allReservationsMatchDOM:true,collisions:0,shared:0,overflow:0,keyboard:true,detailReturn:true,timeChecked,styleMeasurementChecked,mountMs:mountMs.map(t=>+t.toFixed(2)),writes:0,errors,screenshots,requests:requests.length});
  }catch(e){await page.screenshot({path:path.join(out,`${kind}-${width}-failure.png`)});console.error({out,kind,width,errors});throw e;}finally{await context.close();}
 }
 await fs.writeFile(path.join(out,'results.json'),JSON.stringify({synthetic:true,summary},null,2));
 console.log(JSON.stringify({synthetic:true,out,cases:summary.map(s=>({kind:s.kind,width:s.width,height:s.height,nodes:s.nodes,edges:s.edges,labelHeight:s.longLabelButton.height,collisions:s.collisions,shared:s.shared,overflow:s.overflow,timeChecked:s.timeChecked,styleMeasurementChecked:s.styleMeasurementChecked,mountMs:s.mountMs,errors:s.errors.length}))},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
