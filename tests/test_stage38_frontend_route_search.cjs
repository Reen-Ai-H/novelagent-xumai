/* Regression equivalents of Kepler's unchanged five synthetic graphs.
 * Real routing AND mountModel: losing the entire DOM is a failing result. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {performance}=require('node:perf_hooks');
const {denseFixture}=require('./test_stage38_frontend_route_fixture.cjs');
function auditCases(){
 const edges=pairs=>pairs.map(([a,b],i)=>({from:`N${a}`,to:`N${b}`,label:`联系${i}`,status:'fact'}));
 const bidi=edges([[0,1],[1,0],[0,2],[2,0],[0,3],[3,0]]);
 return [
  {name:'fan-in-out',n:5,edges:edges([[0,1],[0,2],[0,3],[1,4],[2,4],[3,4]])},
  {name:'bidirectional',n:4,edges:bidi},
  {name:'dense-six-DAG',n:6,edges:edges(Array.from({length:6},(_,i)=>Array.from({length:5-i},(_,j)=>[i,i+j+1])).flat())},
  {name:'twelve-twenty-DAG',n:12,edges:edges([...Array.from({length:11},(_,i)=>[i,i+1]),...Array.from({length:9},(_,i)=>[i,i+3])])},
  {name:'narrow-bidirectional',n:4,edges:bidi,width:350},
 ];
}
function auditFixture(c){
 const value=denseFixture(),raw=value.response.result.report;
 const claim=()=>({text:'合成人物/联系，仅供路由检查。',status:'fact',evidence_ids:['Q0']});
 raw.characters=Array.from({length:c.n},(_,i)=>({id:`N${i}`,name:`节点${i}`,aliases:[],importance:'support',role:'配角',identity:claim(),motivation:claim(),change:claim(),insights:[]}));
 raw.events=[];raw.relations=[];raw.story_order=[];
 raw.character_relations=c.edges.map(e=>({from_id:e.from,to_id:e.to,label:e.label,...claim()}));
 raw.title=`独立密图 · ${c.name} · 合成`;
 value.response.title=value.workspace.title=raw.title;return value;
}
module.exports={auditCases,auditFixture};
if(require.main===module){
 const source=fs.readFileSync(path.resolve(__dirname,'../frontend/workspace-reader.js'),'utf8'),summary=[];
 const context={window:{XumaiReportBrowser:{esc:String,mount(){}},XumaiVisualReading:{short:s=>s},scrollTo(){}},history:{state:null,replaceState(){},pushState(){}},location:{search:'',href:'https://offline-fixture.invalid/'},sessionStorage:{getItem:()=>null,setItem(){}},document:{createElement:()=>({innerHTML:'',className:'',querySelector:()=>null})},URL,URLSearchParams};
 const hook='graphLayout,graphRoute});';assert.equal(source.split(hook).length,2);
 vm.runInNewContext(source.replace(hook,'graphLayout,graphRoute,searchGraphPath});'),context);const R=context.window.XumaiWorkspaceReader;
 const overlap=(a,b)=>Math.min(a.right,b.right)>Math.max(a.left,b.left)&&Math.min(a.bottom,b.bottom)>Math.max(a.top,b.top);
 const shared=(a,b)=>a.start.x===a.end.x&&b.start.x===b.end.x&&a.start.x===b.start.x
  ?Math.max(0,Math.min(Math.max(a.start.y,a.end.y),Math.max(b.start.y,b.end.y))-Math.max(Math.min(a.start.y,a.end.y),Math.min(b.start.y,b.end.y)))
  :a.start.y===a.end.y&&b.start.y===b.end.y&&a.start.y===b.start.y
  ?Math.max(0,Math.min(Math.max(a.start.x,a.end.x),Math.max(b.start.x,b.end.x))-Math.max(Math.min(a.start.x,a.end.x),Math.min(b.start.x,b.end.x))):0;
 const hit=(s,r)=>s.start.x===s.end.x?s.start.x>r.left&&s.start.x<r.right&&Math.max(s.start.y,s.end.y)>r.top&&Math.min(s.start.y,s.end.y)<r.bottom
  :s.start.y>r.top&&s.start.y<r.bottom&&Math.max(s.start.x,s.end.x)>r.left&&Math.min(s.start.x,s.end.x)<r.right;
 // A real available corridor is not rejected just because its original rails
 // are occupied. Exercise the complete subdivision, not another template count.
 const corridor={left:4,right:99,top:0,bottom:100},used=[1,2].map(x=>({start:{x,y:0},end:{x,y:100}}));
 const found=R.searchGraphPath([corridor],used,[{x:2,y:10}],[{x:2,y:90}],100,100);
 assert.ok(found&&found.refined);assert.ok(found.points.length>2);
 const foundSegments=found.points.slice(1).map((end,i)=>({start:found.points[i],end}));
 assert.ok(!foundSegments.some(s=>hit(s,corridor)));for(const a of foundSegments)for(const b of used)assert.equal(shared(a,b),0);
 const cases=auditCases(),matrix=[...cases.map(c=>({...c,desktop:920})),...cases.filter(c=>c.n>=6).flatMap(c=>[1108,728,356].map(w=>({...c,name:c.name+'-viewport'+w,width:w<620?w:0,desktop:w-20}))),...cases.filter(c=>c.n>=6).map(c=>({...c,name:c.name+'-reversed',edges:[...c.edges].reverse(),desktop:920}))];
 for(const c of matrix){
  const input=JSON.stringify(c.edges),items=Array.from({length:c.n},(_,i)=>({id:`N${i}`,name:`节点${i}`}));
  const l=R.graphLayout(items,c.edges,false,c.width||0,c.desktop),initialHeight=l.height,positions=JSON.stringify([...l.positions]),reservations=[],routes=[],start=performance.now();
  for(const e of l.edges)routes.push(R.graphRoute(l,e,reservations));const routingMs=performance.now()-start;
  assert.equal(routes.length,c.edges.length,c.name);assert.equal(reservations.length,c.edges.length);assert.equal(JSON.stringify(c.edges),input);assert.equal(JSON.stringify([...l.positions]),positions);
  assert.ok(l.height<=initialHeight+c.edges.length*320,'Canvas growth is bounded per retained edge');
  const boxes=[...l.positions.values()].map(p=>({left:p.x-(l.nodeWidth||210)/2,right:p.x+(l.nodeWidth||210)/2,top:p.y-47,bottom:p.y+47}));
  for(let i=0;i<routes.length;i++){
   const r=routes[i],p=r.label;
   assert.ok(r.segments.some(s=>s.start.x===s.end.x?p.x===s.start.x&&p.y>=Math.min(s.start.y,s.end.y)&&p.y<=Math.max(s.start.y,s.end.y):p.y===s.start.y&&p.x>=Math.min(s.start.x,s.end.x)&&p.x<=Math.max(s.start.x,s.end.x)));
   assert.ok(r.box.left>=0&&r.box.right<=l.width&&r.box.top>=0&&r.box.bottom<=l.height);
   for(const b of boxes){assert.equal(overlap(r.box,b),false,c.name+' label/node');assert.ok(!r.segments.some(s=>hit(s,b)),c.name+' line/node');}
   for(let j=0;j<i;j++){
    assert.equal(overlap(r.box,routes[j].box),false,c.name+' label/label');
    for(const a of r.segments)for(const b of routes[j].segments)assert.equal(shared(a,b),0,c.name+' shared trunk');
    assert.ok(!r.segments.some(s=>hit(s,routes[j].box)),c.name+' line/foreign label');assert.ok(!routes[j].segments.some(s=>hit(s,r.box)),c.name+' foreign line/label');
   }
  }
  let html='',writes=0;const root={clientWidth:c.width||c.desktop+20,classList:{add(){}},addEventListener(){},querySelector:()=>null,querySelectorAll:()=>[],append(){},get innerHTML(){return html;},set innerHTML(v){writes++;html=v;}};
  const t=performance.now();R.mountModel(root,auditFixture(c).response.result.report,{projectId:'synthetic',documentId:'synthetic-report',section:'characters',evidence:()=>'',claim:()=>'',openModal(){}});const mountMs=performance.now()-t;
  assert.equal((html.match(/<article class="total-graph-node/g)||[]).length,c.n,c.name+' complete mount nodes');assert.equal((html.match(/class="total-graph-edge"/g)||[]).length,c.edges.length,c.name+' complete mount edges');assert.ok(writes>0);
  assert.ok(routingMs<2000&&mountMs<2000,c.name+` synchronous routing/mount budget exceeded: ${routingMs}/${mountMs}ms`);
  summary.push({case:c.name,nodes:c.n,edges:c.edges.length,routed:routes.length,searched:routes.filter(r=>r.searched).length,routingMs:+routingMs.toFixed(2),mountMs:+mountMs.toFixed(2),height:l.height,shared:0,collisions:0});
 }
 console.log(JSON.stringify({synthetic:true,cases:summary},null,2));
}
