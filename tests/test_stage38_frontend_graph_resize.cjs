/* Real Chromium, synthetic GET-only responses. Cross-breakpoint resizing must
 * preserve the reader DOM/state and never remount the application. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path'),os=require('node:os');
const {chromium}=require('playwright'),{fixture,root}=require('./test_stage38_frontend_browser.cjs');
const origin='http://graph-resize.invalid';
(async()=>{
  const out=await fs.mkdtemp(path.join(os.tmpdir(),'xumai-stage38-resize-'));
  const browser=await chromium.launch({headless:true,channel:'chrome'}),errors=[],requests=[],screenshots=[],cases=[];
  let page;
  try {
    const context=await browser.newContext({viewport:{width:1024,height:768},offline:true,serviceWorkers:'block',reducedMotion:'reduce'});
    page=await context.newPage();const {workspace,response}=fixture(),report=response.result.report;
    await page.addInitScript(()=>{
      const Native=ResizeObserver;window.__resizeObservers=new Set();
      window.ResizeObserver=class extends Native {
        observe(target,...args){this.target=target;window.__resizeObservers.add(this);return super.observe(target,...args);}
        disconnect(){window.__resizeObservers.delete(this);return super.disconnect();}
      };
    });
    const people=structuredClone(report.characters),events=structuredClone(report.events);
    report.characters=Array.from({length:11},(_,i)=>({...structuredClone(people[i%people.length]),id:`C${i}`,name:`合成人物${i}`,aliases:[]}));
    report.events=Array.from({length:13},(_,i)=>({...structuredClone(events[i%events.length]),id:`E${i}`,title:`合成事件${i}`,actor_ids:[`C${i%11}`]}));
    report.story_order=report.events.map(e=>e.id).reverse();
    report.character_relations=report.characters.slice(1).map(p=>({from_id:'C0',to_id:p.id,label:'合成相识',status:'fact',text:'合成关系',evidence_ids:['Q0']}));
    report.relations=[{from_id:'E0',to_id:'E12',kind:'follows',status:'fact',text:'合成先后',evidence_ids:['Q0']}];
    const frozen=JSON.stringify({workspace,response});
    page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(['warning','error'].includes(m.type()))errors.push(m.text());});
    await context.route('**/*',async route=>{
      const req=route.request(),url=new URL(req.url()),p=url.pathname;
      assert.equal(url.origin,origin);assert.equal(req.method(),'GET');requests.push(p);
      const json=data=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
      if(p.startsWith('/static/')){
        const n=p.slice(8);assert.match(n,/^[a-z0-9.-]+$/);let body=await fs.readFile(path.join(root,'frontend',n));
        if(n==='workspace-reader.js')body=body.toString()+`;(()=>{const r=window.XumaiWorkspaceReader;window.__mounts=0;window.XumaiWorkspaceReader={...r,mountModel(...args){window.__mounts++;return r.mountModel(...args);}};})();`;
        return route.fulfill({contentType:n.endsWith('.css')?'text/css':n.endsWith('.svg')?'image/svg+xml':'text/javascript',body});
      }
      if(!p.startsWith('/api/'))return route.fulfill({contentType:'text/html',body:await fs.readFile(path.join(root,'frontend/index.html'))});
      if(p==='/api/auth/session')return json({authenticated:true,account:{account_id:'synthetic',email:'resize@example.test'}});
      if(p==='/api/notifications')return json({notifications:[],unread_count:0});
      if(p.endsWith('/model-budget'))return json({model_available:false,budget:{budget_cny:0,remaining_cny:0}});
      if(p.endsWith('/book'))return json({job:null});if(p.endsWith('/deconstruction'))return json(response);
      if(p==='/api/independent/projects/p1')return json(workspace);
      throw Error('Unexpected synthetic GET '+p);
    });
    const nodes=()=>page.locator('.total-graph-node');
    const columns=()=>nodes().evaluateAll(ns=>new Set(ns.map(n=>n.style.left)).size);
    const ids=()=>nodes().evaluateAll(ns=>ns.map(n=>n.dataset.personId||n.dataset.eventId));
    async function capture(name){const file=path.join(out,name+'.png');await page.screenshot({path:file});screenshots.push(file);}
    async function remember(){await page.evaluate(()=>{
      window.__graphNodes=[...document.querySelectorAll('.total-graph-node')];
      window.__reader=document.querySelector('[data-reader-index]');window.__focused=document.activeElement;
      window.__url=location.href;window.__beforeMounts=window.__mounts;
    });}
    async function retained(){
      assert.equal(await page.evaluate(()=>window.__graphNodes.every((n,i)=>n===document.querySelectorAll('.total-graph-node')[i])),true);
      assert.equal(await page.evaluate(()=>window.__reader===document.querySelector('[data-reader-index]')),true);
      assert.equal(await page.evaluate(()=>window.__focused===document.activeElement),true);
      assert.equal(await page.evaluate(()=>window.__url===location.href),true);
      assert.equal(await page.evaluate(()=>window.__beforeMounts===window.__mounts),true);
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    }
    async function resize(width,single){
      await page.setViewportSize({width,height:width===390?844:768});
      await page.waitForFunction(single=>{const columns=new Set([...document.querySelectorAll('.total-graph-node')].map(n=>n.style.left)).size;return single?columns===1:columns>1;},single);
      await retained();
    }
    await page.goto(origin+'/independent/p1?view=deconstruction&volume=doc&section=characters');
    await nodes().first().waitFor();assert.equal(await nodes().count(),11);assert.ok(await columns()>1);
    await page.locator('[data-reader-open=C0]').focus();await page.keyboard.press('End');await remember();
    await capture('people-1024-before');await resize(390,true);await capture('people-390-after');cases.push('11 people compact on resize, same nodes/selection/focus');
    await page.evaluate(()=>{
      const svg=document.querySelector('.total-graph-lines');let last=svg.querySelector('marker').id;window.__reflows=0;
      window.__resizeAudit=new MutationObserver(()=>{const id=svg.querySelector('marker')?.id;if(id&&id!==last){last=id;window.__reflows++;}});
      window.__resizeAudit.observe(svg,{childList:true,subtree:true});
    });
    for(const width of [391,392,393,394])await page.setViewportSize({width,height:844});
    await page.waitForTimeout(250);assert.equal(await page.evaluate(()=>window.__reflows),1,'A compact resize burst is debounced');
    await page.evaluate(()=>window.__resizeAudit.disconnect());await retained();cases.push('compact resize burst reroutes once');
    await resize(1024,false);await capture('people-1024-return');
    const marker=()=>page.locator('.total-graph-lines marker').getAttribute('id');const initialMarker=await marker();
    for(const width of [1030,1040,1050,1060])await page.setViewportSize({width,height:768});
    await page.waitForTimeout(250);assert.equal(await marker(),initialMarker,'No redraw for every desktop width');cases.push('same desktop layout does not reroute');
    await page.locator('.total-graph-edge').first().click();
    const basis=page.locator('[data-edge-basis]');await page.locator('[data-close-basis]').focus();
    await page.evaluate(()=>{window.__basis=document.querySelector('[data-edge-basis]');});await remember();
    await resize(390,true);assert.equal(await basis.isVisible(),true);
    assert.equal(await page.evaluate(()=>window.__basis===document.querySelector('[data-edge-basis]')),true);
    await page.locator('[data-close-basis]').click();cases.push('open edge basis and its focus survive resize');
    await page.locator('#deconstructionSubnav [data-section=plot]').click();await nodes().first().waitFor();
    await page.locator('[data-reader-order=story]').click();
    const story=Array.from({length:13},(_,i)=>`E${12-i}`);assert.deepEqual(await ids(),story);
    await page.locator('[data-reader-open=E8]').focus();await remember();
    await resize(1024,false);assert.deepEqual(await ids(),story);await capture('plot-1024-story');
    await resize(390,true);assert.deepEqual(await ids(),story);await capture('plot-390-story');cases.push('13 plot nodes preserve story order and focused selection');
    await page.locator('[data-reader-order=narrative]').click();
    const narrative=Array.from({length:13},(_,i)=>`E${i}`);assert.deepEqual(await ids(),narrative);
    await remember();await resize(1440,false);assert.deepEqual(await ids(),narrative);cases.push('narrative order unchanged on expand');
    await page.locator('[data-reader-map=index]').click();
    await page.locator('[data-browser-page-select]').selectOption('1');await page.locator('[data-browser-page="2"]').click();
    const search=page.locator('[data-event-index] input[type=search]');await search.focus();
    await page.evaluate(()=>{window.__list=document.querySelector('[data-event-index]');window.__input=document.activeElement;window.__pageUrl=location.href;});
    for(const width of [390,1024]){await page.setViewportSize({width,height:768});await page.waitForTimeout(200);}
    assert.equal(await page.locator('[data-browser-page-select]').inputValue(),'2');
    assert.equal(await page.evaluate(()=>window.__list===document.querySelector('[data-event-index]')&&window.__input===document.activeElement&&window.__pageUrl===location.href),true);
    await page.locator('[data-reader-open=E8]').click();await page.locator('[data-reader-detail=plot]').waitFor();
    await page.evaluate(()=>{window.__detail=document.querySelector('[data-reader-detail]');window.__detailFocus=document.activeElement;window.__detailUrl=location.href;});
    await page.setViewportSize({width:390,height:844});await page.waitForTimeout(200);
    assert.equal(await page.evaluate(()=>window.__detail===document.querySelector('[data-reader-detail]')&&window.__detailFocus===document.activeElement&&window.__detailUrl===location.href),true);
    await page.locator('[data-reader-back]').click();assert.equal(await page.locator('[data-browser-page-select]').inputValue(),'2');
    cases.push('list page two, input focus and open detail survive resize and return');
    await page.locator('[data-reader-map=total]').click();
    const mounts=await page.evaluate(()=>window.__mounts);
    await page.locator('[data-action=open-workspace-tools]').click();await page.locator('#deconstructionRefreshButton').click();
    await page.waitForFunction(n=>window.__mounts>n,mounts);await nodes().first().waitFor();
    await page.waitForFunction(()=>[...window.__resizeObservers].every(observer=>observer.target.isConnected));
    await page.keyboard.press('Escape');
    await page.locator('[data-reader-open=E8]').focus();await remember();await resize(1024,false);
    cases.push('refresh disconnects obsolete observers; replacement graph still resizes');
    assert.deepEqual(errors,[]);assert.equal(JSON.stringify({workspace,response}),frozen);
    console.log(JSON.stringify({synthetic:true,out,cases,screenshots,errors,writes:0},null,2));
    await context.close();
  } catch(error) {
    if(page)await page.screenshot({path:path.join(out,'failure.png')});console.error({out,errors});throw error;
  } finally {await browser.close();}
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
