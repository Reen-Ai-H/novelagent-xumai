/* Deterministic frontend contracts. No server, data stores or model calls. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'frontend/app.js'),'utf8').replace(/\r\n/g,'\n');
const hook='  start();\n})();';assert.ok(source.includes(hook));
const ctx={window:{},document:{querySelector:()=>null,querySelectorAll:()=>[]},URL,URLSearchParams};
vm.runInNewContext(source.replace(hook,'  globalThis.api={chapterTitle,chapterPrefix,chapterEditTitle,chapterNumber,projectCard,reportStartBlock,reportJobMessage};\n})();'),ctx);
const {api}=ctx;
const headings=['死婴','开蒙前','第三章 潮声','第四章 来信','归来','赏与罚'];
const chapters=headings.map((title,i)=>({title,chapter_number:i+1,content:'  😀原文\r\n\r\n不可变。\n'}));
const frozen=JSON.stringify(chapters);
assert.deepEqual(chapters.map(c=>api.chapterTitle(c)),['第一章 死婴','第二章 开蒙前','第三章 潮声','第四章 来信','第五章 归来','第六章 赏与罚']);
for(const title of ['第 6 章 赏与罚','第六章 赏与罚','Chapter 6 Reward']) {
 assert.equal(api.chapterTitle({title,chapter_number:6}),title);
 assert.equal(api.chapterPrefix({title,chapter_number:6}),'');
}
assert.equal(api.chapterTitle({title:'',chapter_number:7}),'第七章');
assert.equal(api.chapterTitle({title:'改题',chapter_number:7}),'第七章 改题');
assert.equal(api.chapterTitle({title:'前言'}),'前言');
assert.equal(api.chapterNumber(101),'一百零一');assert.equal(api.chapterNumber(1001),'一千零一');
assert.equal(api.chapterNumber(10),'十');assert.equal(api.chapterNumber(20),'二十');
assert.equal(JSON.stringify(chapters),frozen,'Display must not rewrite title or body');
for(const [title,number,expected] of [
 ['Chapter 7 Departure',1,'第一章 Departure'],['第七章 启程',1,'第一章 启程'],['第 9 章：归航',2,'第二章 归航'],
 ['第一百零一章 归来',1,'第一章 归来'],['Chapter 7 Departure',7,'Chapter 7 Departure'],['第九章—归航',9,'第九章—归航']]){
 const chapter={title,chapter_number:number,content:'  😀逐字原稿\r\n'},before=JSON.stringify(chapter);
 assert.equal(api.chapterTitle(chapter),expected);assert.equal(api.chapterEditTitle(chapter),expected);
 assert.equal(JSON.stringify(chapter),before);
}
const scope={source:{versionId:'v1',revision:1,contentHash:'a',wordCount:100}};
const ready={loaded:true,budget:{remaining_cny:3},available:true};
assert.equal(api.reportStartBlock(scope,ready),'');
for(const available of [false,null,undefined])assert.ok(api.reportStartBlock(scope,{...ready,available}));
for(const budget of [null,{remaining_cny:null},{remaining_cny:0},{remaining_cny:'3'}])assert.ok(api.reportStartBlock(scope,{...ready,budget}));
for(const status of ['queued','running'])assert.ok(api.reportStartBlock(scope,{...ready,job:{kind:'report-v2',status}}));
assert.ok(api.reportStartBlock(scope,{...ready,sending:true}));
assert.ok(api.reportStartBlock(scope,{...ready,checking:true}));
assert.ok(api.reportStartBlock({source:{...scope.source,wordCount:30001}},ready));
assert.equal(api.reportStartBlock({source:{...scope.source,wordCount:30000}},ready),'');
assert.match(api.reportJobMessage({kind:'report-v2',status:'completed'}),/自动采用/);
for(const stage of ['queued','draft','review','revise','verify','adopt']){
 const message=api.reportJobMessage({kind:'report-v2',status:'running',stage});
 assert.match(message,/[\u3400-\u9fff]/);assert.ok(!message.includes(stage));
}
assert.ok(api.reportStartBlock(scope,{...ready,job:{kind:'report-v2',status:'failed',error_code:'report_request_unknown'}}));
for(const mode of ['independent','ai_assisted']) {
 const card=api.projectCard({project_id:'p-2',mode,title:'书名 <与> "引号"',status:'写作中',chapter_count:6,progress_percent:20},0);
 assert.match(card,/^\s*<a class="project-card"/);assert.match(card,/<\/a>\s*$/);
 assert.equal((card.match(/<a\b/g)||[]).length,1);
 assert.doesNotMatch(card,/<button|<input|tabindex/);
 assert.ok(card.includes(`href="/${mode==='independent'?'independent':'ai'}/p-2"`));
 assert.match(card,/data-route/);assert.doesNotMatch(card,/书名 <与>/);
}
const context={window:{XumaiReportBrowser:{esc:String},XumaiVisualReading:{short:String}}};
const reader=fs.readFileSync(path.join(root,'frontend/workspace-reader.js'),'utf8');
const marker='  function mount(root, data, options) {';
vm.runInNewContext(reader.replace(marker,marker+' return data;'),context);
const R=context.window.XumaiWorkspaceReader;
const report=structuredClone(require('./browser_stage37_fixture.cjs').report);
// A -> B -> C -> D is one connected component. E is isolated. A single
// person's one-hop view cannot satisfy this whole-report contract.
report.character_relations=[
 {from_id:'C0',to_id:'C1',label:'师徒',status:'fact',evidence_ids:['Q0']},
 {from_id:'C1',to_id:'C2',label:'同盟',status:'reported',evidence_ids:['Q1']},
 {from_id:'C2',to_id:'C3',label:'试探',status:'inferred',evidence_ids:['Q2']},
 {from_id:'missing',to_id:'C1',label:'无效端点',status:'fact'}];
const before=JSON.stringify(report),options={claim:JSON.stringify,evidence:()=>''};
const data=R.mountModel({},report,options);
assert.equal(data.timeNote,report.time_note);
const noteReport=structuredClone(report);noteReport.time_note='回忆中的顺序未定。\n  <原样 & 不改写>';
assert.equal(R.mountModel({},noteReport,options).timeNote,noteReport.time_note);
delete noteReport.time_note;
assert.equal(R.mountModel({},noteReport,options).timeNote,'');
assert.equal(data.people[0].group,'主要人物');assert.equal(data.people[3].group,'配角');
const explicit=structuredClone(report),longRole='在旧港记录来往船只并见证众人选择的普通人'.repeat(4).slice(0,80);
assert.equal(longRole.length,80);
explicit.characters[0].role=longRole;explicit.characters[0].importance='main';
explicit.characters[3].role='主要人物的导师';explicit.characters[3].importance='support';
const explicitBefore=JSON.stringify(explicit),adapted=R.mountModel({},explicit,options);
assert.equal(adapted.people[0].group,'主要人物');assert.equal(adapted.people[3].group,'配角');
assert.equal(adapted.people[0].role,longRole);assert.equal(adapted.people[3].role,'主要人物的导师');
assert.equal(JSON.stringify(explicit),explicitBefore,'Explicit importance must not rewrite any role or report field');
for(const importance of [undefined,null])for(const [role,expected] of [
 ['主要人物的导师','未分级'],['主要人物 · 旧版拼接身份','未分级'],['身份尚待整理','未分级'],
 ['主要人物：旧港见证人','主要人物'],['配角:旧港记录员','配角'],['主角','主要人物']]){
 const legacyRole=structuredClone(report);legacyRole.characters[0].role=role;legacyRole.characters[0].importance=importance;
 const item=R.mountModel({},legacyRole,options).people[0];assert.equal(item.group,expected);assert.equal(item.role,role);
}
const precedence=structuredClone(report);
precedence.characters[0].role='主要人物：导师';precedence.characters[0].importance='support';
assert.equal(R.mountModel({},precedence,options).people[0].group,'配角');
for(const invalid of ['MAIN','supporting','']){
 precedence.characters[0].importance=invalid;
 assert.equal(R.mountModel({},precedence,options).people[0].group,'未分级');
}
assert.equal(data.personEdges.length,3);assert.equal(data.personEdges[2].status,'inferred');
assert.match(data.personEdges[1].body(),/Q1/);
const layout=R.graphLayout(data.people,data.personEdges);
assert.equal(layout.positions.size,6);assert.equal(layout.edges.length,3);
assert.equal(new Set([...layout.positions.values()].map(p=>`${p.x},${p.y}`)).size,6);
for(const edge of layout.edges){assert.ok(layout.positions.has(edge.from));assert.ok(layout.positions.has(edge.to));}
assert.equal(JSON.stringify(report),before);
delete report.character_relations;
const legacy=R.mountModel({},report,options);
assert.equal(legacy.personEdges.length,0);assert.equal(legacy.personRelations(legacy.people[0]).length,0);
assert.ok(legacy.personExperiences(legacy.people[0]).length);
const nodes=Array.from({length:180},(_,i)=>({id:`N${i}`}));
const edges=Array.from({length:350},(_,i)=>({from:`N${i%180}`,to:`N${(i+1)%180}`,label:'有据联系'}));
for(const sequential of [true,false])for(const compactWidth of [0,358]){
 const all=R.graphLayout(nodes,edges,sequential,compactWidth);
 assert.equal(all.positions.size,180);assert.equal(all.edges.length,350);
 assert.equal(new Set([...all.positions.values()].map(p=>`${p.x},${p.y}`)).size,180);
 for(const p of all.positions.values()){assert.ok(Number.isFinite(p.x)&&Number.isFinite(p.y));assert.ok(p.x>0 && p.x<all.width && p.y>0 && p.y<all.height);}
}
// Labels belong to a real segment of their OWN route, never a remote guide.
for(const compactWidth of [0,358]){
 const all=R.graphLayout(nodes,edges,true,compactWidth),occupied=[];
 const unique=[...new Map(all.edges.map(e=>[`${e.from}:${e.to}`,e])).values()];
 for(const edge of unique){
  const route=R.graphRoute(all,edge,occupied),p=route.label;
  assert.ok(route.points.some((end,i)=>{if(!i)return false;const start=route.points[i-1];return start.x===end.x&&p.x===start.x&&p.y>=Math.min(start.y,end.y)&&p.y<=Math.max(start.y,end.y)||start.y===end.y&&p.y===start.y&&p.x>=Math.min(start.x,end.x)&&p.x<=Math.max(start.x,end.x);}));
 }
 assert.equal(occupied.length,180);
}
console.log('Stage 38 unit contracts passed: headings, native cards, multi-hop graphs, legacy fields, complete large graph.');

// Independent segment intersection arithmetic: no collinear trunks between
// distinct endpoint pairs, including the previously observed 420 px overlap.
const {denseFixture}=require('./test_stage38_frontend_route_fixture.cjs');
const smallReport=structuredClone(require('./browser_stage37_fixture.cjs').report);
smallReport.character_relations.push({from_id:'C0',to_id:'C1'});
smallReport.relations.push({from_id:'E0',to_id:'E5'});
const sharedLength=(a,b)=>a.start.x===a.end.x && b.start.x===b.end.x && a.start.x===b.start.x
 ? Math.max(0,Math.min(Math.max(a.start.y,a.end.y),Math.max(b.start.y,b.end.y))-Math.max(Math.min(a.start.y,a.end.y),Math.min(b.start.y,b.end.y)))
 : a.start.y===a.end.y && b.start.y===b.end.y && a.start.y===b.start.y
 ? Math.max(0,Math.min(Math.max(a.start.x,a.end.x),Math.max(b.start.x,b.end.x))-Math.max(Math.min(a.start.x,a.end.x),Math.min(b.start.x,b.end.x))) : 0;
const crossesBox=(s,r)=>s.start.x===s.end.x?s.start.x>r.left+1 && s.start.x<r.right-1 && Math.max(s.start.y,s.end.y)>r.top+1 && Math.min(s.start.y,s.end.y)<r.bottom-1
 : s.start.y>r.top+1 && s.start.y<r.bottom-1 && Math.max(s.start.x,s.end.x)>r.left+1 && Math.min(s.start.x,s.end.x)<r.right-1;
for(const raw of [denseFixture().response.result.report,smallReport])for(const width of [1108,728,356])for(const section of ['people','narrative','story']){
 const people=section==='people',items=people?raw.characters:section==='story'?raw.story_order.map(id=>raw.events.find(e=>e.id===id)):raw.events;
 const semantic=(people?raw.character_relations:raw.relations).map(r=>({from:r.from_id,to:r.to_id}));
 const l=R.graphLayout(items,semantic,!people,width<620?width:0,width-20),positions=JSON.stringify([...l.positions]),originalHeight=l.height,occupied=[],routes=[];
 for(const edge of semantic){const route=R.graphRoute(l,edge,occupied);routes.push(route);
  assert.ok(route.segments.some(s=>s.start.x===s.end.x?route.label.x===s.start.x && route.label.y>=Math.min(s.start.y,s.end.y)&&route.label.y<=Math.max(s.start.y,s.end.y):route.label.y===s.start.y && route.label.x>=Math.min(s.start.x,s.end.x)&&route.label.x<=Math.max(s.start.x,s.end.x)));
  for(const p of l.positions.values()){
   const box={left:p.x-(l.nodeWidth||210)/2,right:p.x+(l.nodeWidth||210)/2,top:p.y-47,bottom:p.y+47};
   assert.ok(!route.segments.some(s=>crossesBox(s,box)),'A route cannot pass through a node');
   assert.ok(!(route.box.left<box.right&&route.box.right>box.left&&route.box.top<box.bottom&&route.box.bottom>box.top),'A label cannot cover a node');
  }
 }
 for(let i=0;i<routes.length;i++)for(let j=i+1;j<routes.length;j++){
  for(const a of routes[i].segments)for(const b of routes[j].segments)assert.equal(sharedLength(a,b),0,`${width}/${section}: distinct relationships must not share a trunk`);
  assert.ok(!routes[i].segments.some(s=>crossesBox(s,routes[j].box)));
  assert.ok(!routes[j].segments.some(s=>crossesBox(s,routes[i].box)));
 }
 assert.equal(JSON.stringify([...l.positions]),positions,'Routing must not relocate any node');
 assert.equal(l.height,originalHeight,'These density fixtures need no canvas growth');
 assert.equal(occupied.length,semantic.length);assert.equal(l.edges.length,semantic.length);
}
console.log('Stage 38 routes passed: 12/8 and legacy 6, 7/5 narrative/story, three widths; zero shared segments or label/node collisions.');
