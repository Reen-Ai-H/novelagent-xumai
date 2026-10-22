/* Entirely intercepted synthetic pages: no listening service, real login,
 * author store, network or model. Screenshots live in a temporary directory.
 * Run with NODE_PATH pointing at the bundled Playwright node_modules. */
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const os=require('node:os');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),origin='http://127.0.0.1:8069';
const template=require('./browser_stage37_fixture.cjs').report;
const primary='scribe.alpha@example.test',secondary='editor.beta@example.test';
const archive={characters:[],storylines:[],foreshadowing:[],questions:[],snapshots:[]};
const titles=['潮声','开蒙前','第三章 故人','第四章 来信','归航','赏与罚'];
function fixture(){
 const report=structuredClone(template);
 report.characters[0].importance='main';
 report.characters[0].role='在旧港记录来往船只并见证众人选择的普通人'.repeat(4).slice(0,80);
 report.characters[3].importance='support';report.characters[3].role='主要人物的导师';
 report.character_relations.push({from_id:'C0',to_id:'C1',label:'相识',text:'合成关系，仅供界面验收。',status:'reported',evidence_ids:['Q4']});
 report.relations.push({from_id:'E0',to_id:'E5',kind:'follows',text:'合成顺序，不作因果判断。',status:'fact',evidence_ids:['Q5']});
 const chapters=titles.map((title,i)=>({chapter_id:`c${i+1}`,chapter_number:i+1,title,status:'ready',server_revision:1,content:`  😀${template.evidence[i].quote}\r\n\r\n合成正文，测试不能改写它。\n`,word_count:50}));
 const workspace={project_id:'p1',title:'潮声 · 合成测试',mode:'independent',initialized:true,archive,tasks:[],active_version:{version_id:'v1',revision:1,chapters,archive}};
 const refs=template.evidence.map((e,i)=>({evidence_id:e.id,document_id:'doc',source_version_id:'v1',source_revision:1,source_hash:'a'.repeat(64),chapter_id:`c${i+1}`,chapter_number:i+1,granularity:'span',offset_unit:'utf16_code_unit',start_offset:4,end_offset:4+e.quote.length,excerpt:e.quote}));
 const result={status:'completed',document_id:'doc',analysis_contract_version:'model.1',source_version_id:'v1',source_revision:1,source_hash:'a'.repeat(64),scope_start:1,scope_end:6,scope_hash:'b'.repeat(64),report,evidence:refs};
 const response={project_id:'p1',title:workspace.title,effective_status:'completed',run_status:'completed',source_match:true,focus_document_id:'doc',progress:{percent:100,current_stage:'completed'},source:{version_id:'v1',revision:1,hash:'a'.repeat(64),chapter_count:6,total_word_count:300,match:true},actions:{retry:false,rebuild:false},active_run:{...result,run_status:'completed'},result,history:[],volumes:[]};
 return {workspace,response,refs};
}
module.exports={fixture,origin,root};
if(require.main===module)(async()=>{
 const out=await fs.mkdtemp(path.join(os.tmpdir(),'xumai-stage38-ui-'));
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 const summary=[];
 try{
  for(const width of [1440,1024,390]){
   const context=await browser.newContext({viewport:{width,height:width===1024?768:900},reducedMotion:'reduce'});
   const page=await context.newPage(),errors=[],requests=[],writes=[];
   let email=primary,empty=false;
   const {workspace,response,refs}=fixture(),initialBodies=workspace.active_version.chapters.map(c=>c.content);
   const account=()=>({account_id:email===primary?'a1':'a2',email,credit_balance:10});
   const projects=[{project_id:'p1',title:workspace.title,mode:'independent',status:'写作中',chapter_count:6,total_word_count:300,progress_percent:30},{project_id:'p2',title:'另一部作品',mode:'independent',status:'写作中',chapter_count:6,total_word_count:300,progress_percent:10},{project_id:'ai1',title:'合成 AI 创作室',mode:'ai_assisted',status:'写作中',chapter_count:0,total_word_count:0,progress_percent:0}];
   page.on('pageerror',e=>errors.push(e.message));
   page.on('console',m=>{if(['warning','error'].includes(m.type()))errors.push(m.text());});
   await context.route('**/*',async route=>{
    const req=route.request(),url=new URL(req.url()),p=url.pathname;
    assert.equal(url.origin,origin,'Synthetic page must never reach another host');
    requests.push(`${req.method()} ${p}`);
    const json=data=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
    if(p.startsWith('/static/')){
     const name=p.slice(8);assert.ok(/^[a-z0-9.-]+$/.test(name));
     return route.fulfill({status:200,contentType:name.endsWith('.css')?'text/css':name.endsWith('.svg')?'image/svg+xml':'text/javascript',body:await fs.readFile(path.join(root,'frontend',name))});
    }
    if(!p.startsWith('/api/'))return route.fulfill({status:200,contentType:'text/html',body:await fs.readFile(path.join(root,'frontend/index.html'))});
    if(req.method()!=='GET')writes.push(`${req.method()} ${p}`);
    if(p==='/api/auth/session')return json(email?{authenticated:true,account:account()}:{authenticated:false});
    if(p==='/api/auth/logout'){email=null;return json({authenticated:false});}
    if(p==='/api/auth/email'){email=req.postDataJSON().email;return json({authenticated:true,account:account(),next_path:'/library'});}
    if(p==='/api/library')return json({account:account(),projects});
    if(p==='/api/notifications')return json({notifications:[],unread_count:0});
    if(/\/deconstruction\/book$/.test(p))return json({job:null});
    if(/\/model-budget$/.test(p))return json({budget:{budget_cny:5,estimated_spent_cny:0,reserved_cny:0,remaining_cny:5},available:false});
    if(/\/deconstruction\/evidence\//.test(p)){
     const ref=refs.find(r=>r.evidence_id===p.split('/').at(-1));assert.ok(ref);
     return json({evidence:ref,source_matches_current:true,historical:false,chapter:{...workspace.active_version.chapters[ref.chapter_number-1],source_available:true}});
    }
    if(/\/deconstruction$/.test(p))return json(empty?{...response,effective_status:'empty',run_status:'none',source_match:false,source:{...response.source,match:false},result:null,active_run:null}:response);
    const draft=p.match(/\/chapters\/(c\d+)\/draft$/);
    if(draft){
     const body=req.postDataJSON(),chapter=workspace.active_version.chapters.find(c=>c.chapter_id===draft[1]);
     assert.equal(body.content,chapter.content,'Title editing must preserve the full manuscript');
     chapter.title=body.title;chapter.server_revision++;return json({workspace,chapter});
    }
    if(/\/chapters$/.test(p) && req.method()==='POST'){
     const chapter={chapter_id:'c7',chapter_number:7,title:'第7章',status:'draft',server_revision:0,content:'',word_count:0};
     workspace.active_version.chapters.push(chapter);return json({chapter,workspace});
    }
    if(/^\/api\/independent\/projects\/p[12]$/.test(p))return json({...workspace,project_id:p.split('/').at(-1)});
    if(/^\/api\/ai\/projects\/ai1$/.test(p))return json({project_id:'ai1',title:'合成 AI 创作室',mode:'ai_assisted',conversation:[],blueprint:{},model_available:false});
    throw Error(`Unexpected API in synthetic test: ${req.method()} ${p}`);
   });
   const visibleScreen=()=>page.locator('.screen:not(.is-hidden)').getAttribute('data-screen');
   const checkAccount=async expected=>{
    const badge=page.locator('.screen:not(.is-hidden) [data-account-identity]');
    assert.equal(await badge.locator('[data-account-name]').innerText(),expected.split('@')[0]);
    assert.equal(await badge.locator('[data-account-avatar]').innerText(),expected[0].toUpperCase());
    assert.equal(await badge.isVisible(),true);
   };
   const capture=async name=>{
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${name} document overflow`);
    await page.screenshot({path:path.join(out,`${width}-${name}.png`),fullPage:true});
   };
   try{
    // A valid session at the login deep link must match the visible page.
    await page.goto(origin+'/login');await page.waitForURL('**/library');await page.locator('.project-card').first().waitFor();
    assert.equal(await visibleScreen(),'library');await checkAccount(primary);
    assert.equal(await page.locator('.project-card a,.project-card button').count(),0);
    assert.equal(await page.locator('[data-project-id=ai1]').getAttribute('href'),'/ai/ai1');
    await capture('library');
    // Click the cover, not a tiny footer button, then the second card by keyboard.
    await page.locator('[data-project-id=p1] .project-cover').click();await page.locator('#chapterEditor').waitFor();
    assert.equal(new URL(page.url()).pathname,'/independent/p1');await checkAccount(primary);
    if(width<700)await page.locator('.mobile-chapter-navigation').selectOption('c1');
    else await page.locator('[data-action=select-chapter][data-chapter-id=c1]').click();
    assert.deepEqual(await page.locator('.chapter-list-copy strong').allTextContents(),['第一章 潮声','第二章 开蒙前','第三章 故人','第四章 来信','第五章 归航','第六章 赏与罚']);
    assert.equal(await page.locator('#chapterTitlePrefix').innerText(),'第一章');
    assert.equal(await page.locator('#chapterEditor').inputValue(),initialBodies[0].replace(/\r\n/g,'\n'));
    await capture('editor');
    await page.locator('#chapterTitleInput').fill('新潮声');
    await page.locator('[data-action=save-editor]').click();
    await page.waitForFunction(()=>document.querySelector('#editorSaveState').textContent==='已保存');
    assert.equal(workspace.active_version.chapters[0].title,'新潮声');
    assert.deepEqual(workspace.active_version.chapters.map(c=>c.content),initialBodies);
    await page.goto(origin+'/library');await page.locator('[data-project-id=p2]').focus();await page.keyboard.press('Enter');
    await page.waitForURL('**/independent/p2?chapter=c6');await page.locator('#chapterEditor').waitFor();
    assert.equal(new URL(page.url()).pathname,'/independent/p2');
    const peopleUrl=origin+'/independent/p1?view=deconstruction&volume=doc&section=characters';
    await page.goto(peopleUrl);await page.locator('.total-graph-scroll').waitFor();
    await checkAccount(primary);
    assert.equal(await page.locator('.total-graph-node').count(),6);
    assert.equal(await page.locator('[data-person-id=C0] .eyebrow').innerText(),'主要人物');
    assert.equal(await page.locator('[data-person-id=C3] .eyebrow').innerText(),'配角');
    assert.equal(await page.locator('[data-total-from]').count(),4);
    assert.ok(await page.locator('[data-total-from=C0][data-total-to=C1]').count());
    assert.ok(await page.locator('[data-total-from=C4][data-total-to=C1]').count());
    assert.equal(await page.locator('[data-reader-detail]').count(),0);
    assert.equal(await page.locator('#workspaceToolsDialog').isVisible(),false);
    const overlaps=await page.evaluate(()=>{
     const nodes=[...document.querySelectorAll('.total-graph-node')].map(n=>n.getBoundingClientRect());
     return [...document.querySelectorAll('.total-graph-edge')].filter(n=>{const r=n.getBoundingClientRect();return nodes.some(b=>r.left<b.right&&r.right>b.left&&r.top<b.bottom&&r.bottom>b.top);}).length;
    });
    assert.equal(overlaps,0,'Every semantic label must remain clear of person cards');
    const diagram=await page.evaluate(()=>{
     const region=document.querySelector('.total-graph-scroll'),r=region.getBoundingClientRect();
     const nodes=[...document.querySelectorAll('.total-graph-node')].map(n=>n.getBoundingClientRect());
     const canvas=document.querySelector('.total-graph-canvas'),paths=[...document.querySelectorAll('.total-graph-lines > path[data-total-from]')];
     const labels=[...document.querySelectorAll('.total-graph-edge')];
     const distances=labels.map((n,i)=>{
      const x=parseFloat(n.style.left),y=parseFloat(n.style.top),p=paths[i],length=p.getTotalLength();
      let distance=Infinity;
      for(let j=0;j<=600;j++){const at=p.getPointAtLength(length*j/600);distance=Math.min(distance,Math.hypot(at.x-x,at.y-y));}
      return distance;
     });
     return {top:r.top,allVisible:nodes.every(n=>n.left>=r.left && n.right<=r.right && n.top>=r.top && n.bottom<=r.bottom && n.bottom<=innerHeight),scrollX:region.scrollWidth-region.clientWidth,scrollY:region.scrollHeight-region.clientHeight,distances,guides:document.querySelectorAll('.total-label-guide').length};
    });
    assert.equal(diagram.guides,0);assert.ok(diagram.distances.every(n=>n<3),JSON.stringify(diagram));
    if(width>=1024){assert.ok(diagram.top<260);assert.equal(diagram.allVisible,true);assert.equal(diagram.scrollX,0);assert.equal(diagram.scrollY,0);}
    assert.equal(await page.locator('#reportWorkflow').isVisible(),false,'A current valid report has no redundant workflow bar');
    const assets=await page.evaluate(()=>[...document.querySelectorAll('script[src],link[rel=stylesheet]')].map(n=>n.src || n.href));
    assert.equal(assets.length,13);assert.ok(assets.every(url=>new URL(url).searchParams.get('v')==='stage38-platform10'));
    await capture('people-total');
    await page.locator('.total-graph-edge').first().focus();await page.keyboard.press('Enter');
    assert.equal(await page.locator('[data-edge-basis]').isVisible(),true);
    assert.match(await page.locator('[data-edge-basis]').innerText(),/母亲/);
    await page.locator('[data-close-basis]').click();
    await page.locator('[data-reader-open=C0]').focus();await page.keyboard.press('Enter');
    await page.locator('[data-reader-detail=characters]').waitFor();
    assert.equal(await page.locator('.total-graph-scroll').count(),0);
    await page.reload();await page.locator('[data-reader-detail=characters]').waitFor();
    await page.locator('[data-reader-back]').click();await page.locator('.total-graph-scroll').waitFor();
    assert.equal(await page.locator('[data-reader-open=C0]').evaluate(n=>n===document.activeElement),true);
    await page.locator('[data-reader-map=index]').click();await page.locator('.workspace-person-row').first().waitFor();
    await page.locator('[data-browser-filter=group]').selectOption('配角');
    assert.equal(await page.locator('[data-person-id=C3]').count(),1);assert.equal(await page.locator('[data-person-id=C0]').count(),0);
    await page.locator('[data-browser-filter=group]').selectOption('');
    await page.locator('[data-person-index] input[type=search]').fill('林舟');
    assert.equal(await page.locator('.workspace-person-row').count(),1);
    await page.locator('[data-reader-open=C0]').click();await page.locator('[data-reader-back]').click();
    assert.equal(await page.locator('[data-person-index] input[type=search]').inputValue(),'林舟');
    await page.goto(origin+'/independent/p1?view=deconstruction&volume=doc&section=plot');await page.locator('.total-graph-scroll').waitFor();
    assert.equal(await page.locator('.total-graph-node').count(),6);assert.equal(await page.locator('[data-total-from]').count(),2);
    if(width>=1024)assert.equal(await page.evaluate(()=>{
     const region=document.querySelector('.total-graph-scroll'),r=region.getBoundingClientRect();
     return region.scrollWidth===region.clientWidth && region.scrollHeight===region.clientHeight && [...document.querySelectorAll('.total-graph-node')].every(n=>{const b=n.getBoundingClientRect();return b.left>=r.left&&b.right<=r.right&&b.top>=r.top&&b.bottom<=r.bottom&&b.bottom<=innerHeight;});
    }),true,'The small event map also fits without hiding nodes');
    await capture('plot-total');
    await page.locator('[data-reader-open=E2]').click();await page.locator('[data-reader-detail=plot]').waitFor();
    await page.locator('.workspace-event-body .analysis-proof > summary').first().click();
    await page.locator('.workspace-event-body .deconstruction-evidence-link').first().click();
    await page.locator('#deconstructionEvidenceDialog[open]').waitFor();
    await page.waitForFunction(()=>!document.querySelector('#locateDeconstructionEvidenceButton').disabled);
    await page.locator('#locateDeconstructionEvidenceButton').click();
    await page.waitForFunction(quote=>{const t=document.querySelector('#chapterEditor');return t.value.slice(t.selectionStart,t.selectionEnd)===quote;},template.evidence[2].quote);
    assert.equal(await page.locator('#chapterTitlePrefix').isVisible(),false,'A numbered title has no second prefix');
    assert.deepEqual(workspace.active_version.chapters.map(c=>c.content),initialBodies);
    // Last chapter -> new chapter, preserving every existing body.
    await page.goto(origin+'/independent/p1?chapter=c6');await page.locator('#completeChapterButton').waitFor();
    await page.locator('#completeChapterButton').click();await page.waitForURL('**chapter=c7');
    await page.waitForFunction(()=>document.querySelector('#chapterTitleInput').value==='第7章');
    assert.equal(await page.locator('#chapterTitleInput').inputValue(),'第7章');
    assert.equal(await page.locator('#chapterTitlePrefix').isVisible(),false);
    assert.equal(await page.locator('.chapter-list-copy strong').last().innerText(),'第7章');
    assert.deepEqual(workspace.active_version.chapters.slice(0,6).map(c=>c.content),initialBodies);
    await page.locator('#editorLogoutButton').click();await page.waitForURL('**/login');assert.equal(await visibleScreen(),'login');
    await page.reload();assert.equal(await visibleScreen(),'login');
    await page.locator('#emailInput').fill(secondary);await page.locator('#emailSubmitButton').click();
    await page.waitForURL('**/library');await checkAccount(secondary);
    await page.goto(origin+'/login');await page.waitForURL('**/library');await checkAccount(secondary);
    await page.locator('[data-project-id=p1]').click();await page.locator('#chapterEditor').waitFor();await checkAccount(secondary);
    await page.goto(origin+'/independent/p1?chapter=c1');await page.waitForFunction(()=>document.querySelector('#chapterTitleInput').value==='新潮声');
    // Also exercise the report screen logout, not just library/editor.
    await page.goto(peopleUrl);await page.locator('[data-reader-index=characters]').waitFor();await checkAccount(secondary);
    await page.locator('#deconstructionLogoutButton').click();await page.waitForURL('**/login');
    await page.locator('#emailInput').fill(primary);await page.locator('#emailSubmitButton').click();await page.waitForURL('**/library');
    await checkAccount(primary);await page.locator('#logoutButton').click();await page.waitForURL('**/login');
    assert.equal(await visibleScreen(),'login');assert.equal(email,null);
    assert.deepEqual(errors,[]);
    assert.ok(writes.every(p=>/\/auth\/(email|logout)$|\/chapters(?:\/c1\/draft)?$/.test(p)),JSON.stringify(writes));
    assert.ok(!requests.some(p=>/analyze-preview|book\/start|\/retry$|\/rebuild$/.test(p)),'No paid or wrong-pipeline calls');
    summary.push({width,height:page.viewportSize().height,diagram,screenshots:4,consoleErrors:errors.length,requests:requests.length,writes});
   }catch(error){await page.screenshot({path:path.join(out,`${width}-failure.png`),fullPage:true});console.error({url:page.url(),errors,out});throw error;}
   finally{await context.close();}
  }
  console.log(JSON.stringify({synthetic:true,out,summary},null,2));
 }finally{await browser.close();}
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
