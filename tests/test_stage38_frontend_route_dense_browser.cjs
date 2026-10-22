/* P1 integration regression: complete mount and every directed label clickable.
 * Synthetic GET-only Chromium; no real service/account/store/model. */
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {chromium}=require('playwright');
const {root}=require('./test_stage38_frontend_browser.cjs');
const {measure,check}=require('./test_stage38_frontend_routes.cjs');
const {auditCases,auditFixture}=require('./test_stage38_frontend_route_search.cjs');
const origin='http://dense-route.invalid';
(async()=>{
 const out=await fs.mkdtemp(path.join(os.tmpdir(),'xumai-stage38-dense-search-')),browser=await chromium.launch({headless:true,channel:'chrome'}),summary=[];
 try{for(const c of auditCases().filter(c=>c.n>=6))for(const [width,height] of [[1440,900],[1024,768],[390,844]]){
  const context=await browser.newContext({viewport:{width,height},reducedMotion:'reduce'}),page=await context.newPage(),errors=[],requests=[];
  const {response,workspace}=auditFixture(c),before=JSON.stringify(response);
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(['error','warning'].includes(m.type()))errors.push(m.text());});
  await context.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),p=url.pathname;assert.equal(url.origin,origin);assert.equal(req.method(),'GET');requests.push(p);
   const json=data=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
   if(p.startsWith('/static/')){const n=p.slice(8);assert.ok(/^[a-z0-9.-]+$/.test(n));let body=await fs.readFile(path.join(root,'frontend',n),'utf8');
    if(n==='workspace-reader.js')body+=`\n;(()=>{const original=window.XumaiWorkspaceReader;window.__routeMountTimes=[];window.XumaiWorkspaceReader=Object.freeze({...original,mountModel(...args){const t=performance.now();try{return original.mountModel(...args);}finally{window.__routeMountTimes.push(performance.now()-t);}}});})();`;
    return route.fulfill({status:200,contentType:n.endsWith('.css')?'text/css':n.endsWith('.svg')?'image/svg+xml':'text/javascript',body});}
   if(!p.startsWith('/api/'))return route.fulfill({status:200,contentType:'text/html',body:await fs.readFile(path.join(root,'frontend/index.html'))});
   if(p==='/api/auth/session')return json({authenticated:true,account:{account_id:'synthetic',email:'dense.synthetic@example.test'}});
   if(p==='/api/notifications')return json({notifications:[],unread_count:0});
   if(p.endsWith('/model-budget'))return json({model_available:false,budget:{budget_cny:0,estimated_spent_cny:0,reserved_cny:0,remaining_cny:0}});
   if(p.endsWith('/book'))return json({job:null});if(p.endsWith('/deconstruction'))return json(response);
   if(p==='/api/independent/projects/p1')return json(workspace);
   throw Error('Unexpected synthetic GET '+p);
  });
  try{
   await page.goto(origin+'/independent/p1?view=deconstruction&volume=doc&section=characters&map=total');await page.locator('.total-graph-scroll').waitFor();
   const geometry=await measure(page);check(geometry,c.n,c.edges.length);
   const file=path.join(out,`${c.name}-${width}x${height}.png`);await page.screenshot({path:file});
   assert.deepEqual(await page.locator('path[data-total-from]').evaluateAll(ns=>ns.map(n=>[n.dataset.totalFrom,n.dataset.totalTo])),c.edges.map(e=>[e.from,e.to]),'Every semantic endpoint pair stays present in report order');
   for(let i=0;i<c.edges.length;i++){const label=page.locator('.total-graph-edge').nth(i),name=await label.getAttribute('aria-label');await label.click();assert.equal(await page.locator('[data-edge-basis]').isVisible(),true);assert.ok((await page.locator('[data-edge-basis]').innerText()).includes(name));await page.locator('[data-close-basis]').click();}
   await page.locator('[data-reader-open=N0]').click();await page.locator('[data-reader-detail=characters]').waitFor();await page.locator('[data-reader-back]').click();await page.locator('.total-graph-scroll').waitFor();check(await measure(page),c.n,c.edges.length);
   const times=await page.evaluate(()=>window.__routeMountTimes);assert.ok(times.length>0);assert.ok(Math.max(...times)<2000,`Synchronous mount took ${times}ms`);
   assert.equal(JSON.stringify(response),before);assert.deepEqual(errors,[]);
   summary.push({case:c.name,width,height,geometry,mountMs:times.map(t=>+t.toFixed(2)),allEdgesClickable:true,detailReturn:true,writes:0,errors,screenshot:file});
  }catch(e){await page.screenshot({path:path.join(out,`${c.name}-${width}-failure.png`)});console.error({out,errors});throw e;}finally{await context.close();}
 }
 await fs.writeFile(path.join(out,'geometry.json'),JSON.stringify({synthetic:true,summary},null,2));
 console.log(JSON.stringify({synthetic:true,out,cases:summary.map(s=>({case:s.case,width:s.width,height:s.height,nodes:s.geometry.nodes,edges:s.geometry.edges,shared:s.geometry.shared.length,collisions:s.geometry.labelNode.length+s.geometry.lineNode.length+s.geometry.labelLabel.length,mountMs:s.mountMs,errors:s.errors.length,writes:s.writes,screenshot:s.screenshot}))},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
