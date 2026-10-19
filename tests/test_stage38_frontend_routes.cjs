/* Real Chromium, entirely intercepted synthetic GETs. No service, author
 * store, account creation, model or paid call. Six key screenshots only. */
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {chromium}=require('playwright');
const {fixture,root}=require('./test_stage38_frontend_browser.cjs');
const {denseFixture}=require('./test_stage38_frontend_route_fixture.cjs');
const origin='http://route-regression.invalid';
async function measure(page){return page.evaluate(()=>{
 const region=document.querySelector('.total-graph-scroll'),canvas=document.querySelector('.total-graph-canvas'),cr=canvas.getBoundingClientRect();
 const rect=n=>{const r=n.getBoundingClientRect();return {left:r.left-cr.left,right:r.right-cr.left,top:r.top-cr.top,bottom:r.bottom-cr.top};};
 const nodes=[...document.querySelectorAll('.total-graph-node')].map(n=>({id:n.dataset.personId||n.dataset.eventId,...rect(n)}));
 const labels=[...document.querySelectorAll('.total-graph-edge')].map(n=>({name:n.getAttribute('aria-label'),...rect(n),x:parseFloat(n.style.left),y:parseFloat(n.style.top)}));
 const paths=[...document.querySelectorAll('.total-graph-lines > path[data-total-from]')];
 const segments=paths.map(p=>{const points=[...p.getAttribute('d').matchAll(/[ML]([\d.-]+),([\d.-]+)/g)].map(m=>({x:+m[1],y:+m[2]}));return points.slice(1).map((end,i)=>({start:points[i],end}));});
 const overlap=(a,b)=>a.left<b.right-1&&a.right>b.left+1&&a.top<b.bottom-1&&a.bottom>b.top+1;
 const hits=(s,r)=>s.start.x===s.end.x?s.start.x>r.left+1&&s.start.x<r.right-1&&Math.max(s.start.y,s.end.y)>r.top+1&&Math.min(s.start.y,s.end.y)<r.bottom-1
  :s.start.y>r.top+1&&s.start.y<r.bottom-1&&Math.max(s.start.x,s.end.x)>r.left+1&&Math.min(s.start.x,s.end.x)<r.right-1;
 const shared=[];for(let i=0;i<paths.length;i++)for(let j=i+1;j<paths.length;j++)for(const a of segments[i])for(const b of segments[j]){
  let length=0;
  if(a.start.y===a.end.y&&b.start.y===b.end.y&&a.start.y===b.start.y)length=Math.min(Math.max(a.start.x,a.end.x),Math.max(b.start.x,b.end.x))-Math.max(Math.min(a.start.x,a.end.x),Math.min(b.start.x,b.end.x));
  if(a.start.x===a.end.x&&b.start.x===b.end.x&&a.start.x===b.start.x)length=Math.min(Math.max(a.start.y,a.end.y),Math.max(b.start.y,b.end.y))-Math.max(Math.min(a.start.y,a.end.y),Math.min(b.start.y,b.end.y));
  if(length>0)shared.push({first:labels[i].name,second:labels[j].name,length});
 }
 const detached=labels.filter((l,i)=>!segments[i].some(s=>s.start.x===s.end.x?l.x===s.start.x&&l.y>=Math.min(s.start.y,s.end.y)&&l.y<=Math.max(s.start.y,s.end.y):l.y===s.start.y&&l.x>=Math.min(s.start.x,s.end.x)&&l.x<=Math.max(s.start.x,s.end.x))).map(l=>l.name);
 const labelNode=labels.flatMap(l=>nodes.filter(n=>overlap(l,n)).map(n=>({label:l.name,node:n.id})));
 const labelLabel=labels.flatMap((l,i)=>labels.slice(i+1).filter(b=>overlap(l,b)).map(b=>[l.name,b.name]));
 const lineNode=paths.flatMap((p,i)=>nodes.filter(n=>n.id!==p.dataset.totalFrom&&n.id!==p.dataset.totalTo&&segments[i].some(s=>hits(s,n))).map(n=>({from:p.dataset.totalFrom,to:p.dataset.totalTo,node:n.id})));
 const foreignLabel=segments.flatMap((ss,i)=>labels.filter((l,j)=>i!==j&&ss.some(s=>hits(s,l))).map(l=>({route:i,label:l.name})));
 return {nodes:nodes.length,edges:paths.length,shared,detached,labelNode,labelLabel,lineNode,foreignLabel,documentOverflow:document.documentElement.scrollWidth-innerWidth,canvas:{width:canvas.clientWidth,height:canvas.clientHeight},scroll:{x:region.scrollWidth-region.clientWidth,y:region.scrollHeight-region.clientHeight},positions:nodes.map(n=>({id:n.id,left:n.left,top:n.top}))};
 });}
function check(m,expectedNodes,expectedEdges){
 assert.equal(m.nodes,expectedNodes);assert.equal(m.edges,expectedEdges);
 for(const key of ['shared','detached','labelNode','labelLabel','lineNode','foreignLabel'])assert.deepEqual(m[key],[],key+': '+JSON.stringify(m[key]));
 assert.equal(m.documentOverflow,0);
}
(async()=>{
 const out=await fs.mkdtemp(path.join(os.tmpdir(),'xumai-stage38-routes-')),browser=await chromium.launch({headless:true,channel:'chrome'}),summary=[];
 try{for(const [width,height]of [[1440,900],[1024,768],[390,844]])for(const kind of ['dense','legacy6']){
  const context=await browser.newContext({viewport:{width,height},reducedMotion:'reduce'}),page=await context.newPage(),errors=[],requests=[],screenshots=[];
  const {workspace,response}=kind==='dense'?denseFixture():fixture(),raw=response.result.report,before=JSON.stringify(response);
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(['error','warning'].includes(m.type()))errors.push(m.text());});
  await context.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname;assert.equal(url.origin,origin);assert.equal(req.method(),'GET','No mutating endpoint is allowed');requests.push(p);
   const json=d=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(d)});
   if(p.startsWith('/static/')){const n=p.slice(8);assert.ok(/^[a-z0-9.-]+$/.test(n));return route.fulfill({status:200,contentType:n.endsWith('.css')?'text/css':n.endsWith('.svg')?'image/svg+xml':'text/javascript',body:await fs.readFile(path.join(root,'frontend',n))});}
   if(!p.startsWith('/api/'))return route.fulfill({status:200,contentType:'text/html',body:await fs.readFile(path.join(root,'frontend/index.html'))});
   if(p==='/api/auth/session')return json({authenticated:true,account:{account_id:'synthetic',email:'route.synthetic@example.test'}});
   if(p==='/api/notifications')return json({notifications:[],unread_count:0});
   if(p.endsWith('/model-budget'))return json({model_available:false,budget:{budget_cny:0,estimated_spent_cny:0,reserved_cny:0,remaining_cny:0}});
   if(p.endsWith('/book'))return json({job:null});
   if(p.endsWith('/deconstruction'))return json(response);
   if(p==='/api/independent/projects/p1')return json(workspace);
   throw Error('Unexpected read '+p);
  });
  const shot=async name=>{if(kind!=='dense')return;await page.evaluate(()=>{window.scrollTo(0,0);const r=document.querySelector('.total-graph-scroll');r.scrollTop=0;r.scrollLeft=0;});const file=path.join(out,`${width}x${height}-${name}.png`);await page.screenshot({path:file,fullPage:false});screenshots.push(file);};
  const clickEdges=async count=>{
   assert.equal(await page.locator('.total-graph-edge').count(),count);
   for(let i=0;i<count;i++){const edge=page.locator('.total-graph-edge').nth(i),name=await edge.getAttribute('aria-label');await edge.click();assert.equal(await page.locator('[data-edge-basis]').isVisible(),true);assert.ok((await page.locator('[data-edge-basis]').innerText()).includes(name));await page.locator('[data-close-basis]').click();}
  };
  try{
   await page.goto(origin+'/independent/p1?view=deconstruction&volume=doc&section=characters&map=total');await page.locator('.total-graph-scroll').waitFor();
   const people=await measure(page);check(people,raw.characters.length,raw.character_relations.length);await shot('people');await clickEdges(raw.character_relations.length);
   await page.locator('[data-reader-map=index]').click();const mainCount=kind==='dense'?4:3,supportCount=kind==='dense'?8:3;
   await page.locator('[data-browser-filter=group]').selectOption('主要人物');assert.equal(await page.locator('.workspace-person-row').count(),mainCount);
   await page.locator('[data-reader-open=C0]').click();await page.locator('[data-reader-detail=characters]').waitFor();await page.locator('[data-reader-back]').click();assert.equal(await page.locator('[data-browser-filter=group]').inputValue(),'主要人物');assert.equal(await page.locator('.workspace-person-row').count(),mainCount);
   await page.locator('[data-browser-filter=group]').selectOption('配角');assert.equal(await page.locator('.workspace-person-row').count(),supportCount);
   await page.locator(`[data-reader-open=${kind==='dense'?'C11':'C3'}]`).click();await page.locator('[data-reader-detail=characters]').waitFor();await page.locator('[data-reader-back]').click();assert.equal(await page.locator('[data-browser-filter=group]').inputValue(),'配角');assert.equal(await page.locator('.workspace-person-row').count(),supportCount);
   await page.goto(origin+'/independent/p1?view=deconstruction&volume=doc&section=plot&map=total&order=narrative');await page.locator('.total-graph-scroll').waitFor();
   const narrative=await measure(page);check(narrative,raw.events.length,raw.relations.length);assert.deepEqual(await page.locator('.total-graph-node').evaluateAll(ns=>ns.map(n=>n.dataset.eventId)),raw.events.map(e=>e.id));await clickEdges(raw.relations.length);
   await page.locator('[data-reader-order=story]').click();const story=await measure(page);check(story,raw.events.length,raw.relations.length);assert.deepEqual(await page.locator('.total-graph-node').evaluateAll(ns=>ns.map(n=>n.dataset.eventId)),raw.story_order);await shot('events-story');await clickEdges(raw.relations.length);
   await page.locator(`[data-reader-open=E${raw.events.length-1}]`).click();await page.locator('[data-reader-detail=plot]').waitFor();await page.locator('[data-reader-back]').click();assert.equal(await page.locator('[data-reader-order=story]').getAttribute('aria-pressed'),'true');
   const region=page.locator('.total-graph-scroll');await region.evaluate(r=>{r.scrollTop=0;const b=r.getBoundingClientRect();window.scrollBy(0,b.top-24);});
   const box=await region.boundingBox(),scrollBefore=await page.evaluate(()=>scrollY);await page.mouse.move(box.x+Math.min(150,box.width/2),Math.min(height-100,box.y+box.height/2));await page.mouse.wheel(0,240);await page.waitForTimeout(120);
   const afterWheel=await region.evaluate(r=>({inner:r.scrollTop,page:scrollY,max:r.scrollHeight-r.clientHeight}));assert.equal(afterWheel.page,scrollBefore);if(afterWheel.max>0)assert.ok(afterWheel.inner>0);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth),0);assert.equal(JSON.stringify(response),before);assert.deepEqual(errors,[]);
   summary.push({kind,width,height,people,narrative,story,mainCount,supportCount,interactions:'all edge labels, person/event details, return and story order passed',wheel:afterWheel,errors,writes:0,requests:requests.length,screenshots});
  }catch(e){const file=path.join(out,`${width}-${kind}-failure.png`);await page.screenshot({path:file});console.error({out,errors});throw e;}finally{await context.close();}
 }
 await fs.writeFile(path.join(out,'geometry.json'),JSON.stringify({synthetic:true,summary},null,2));console.log(JSON.stringify({synthetic:true,out,cases:summary.map(s=>({kind:s.kind,width:s.width,height:s.height,people:s.people.nodes,personEdges:s.people.edges,events:s.story.nodes,eventEdges:s.story.edges,shared:0,collisions:0,detached:0,overflow:0,writes:s.writes,errors:s.errors.length,screenshots:s.screenshots}))},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
