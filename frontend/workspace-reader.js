/* Stage 37: one index OR one object, always scoped to a report document.
 * View state contains no manuscript/report content and never writes a draft. */
(() => {
  'use strict';
  const B = window.XumaiReportBrowser, esc = B.esc;
  const list = value => Array.isArray(value) ? value : [];
  const short = (text, size = 90) => window.XumaiVisualReading.short(text || '', size);
  const statusLabels = {fact:'正文可证', reported:'人物说法', inferred:'分析推断', unknown:'尚未确定'};
  const badge = value => `<span class="analysis-badge is-${statusLabels[value] ? value : 'unknown'}">${statusLabels[value] || statusLabels.unknown}</span>`;
  const groups = ['主要人物', '配角', '未分级'];
  const modelGroup = p => p.importance==='main' ? groups[0] : p.importance==='support' ? groups[1]
    : p.importance!=null ? groups[2]
    : /^(主角|主要人物|主人公)(\s*[：:]|$)/u.test(p.role || '') ? groups[0]
    : /^(配角|次要人物|实质配角)(\s*[：:]|$)/u.test(p.role || '') ? groups[1] : groups[2];
  const chapterLabel = e => e.chapter_end && e.chapter_end !== e.chapter_number ? `第 ${e.chapter_number}–${e.chapter_end} 章` : `第 ${e.chapter_number} 章`;
  const details = (title, body) => `<details class="analysis-details"><summary>${esc(title)}</summary><div class="analysis-details-body">${body}</div></details>`;
  let graphSerial=0;
  // Geometry is shared by SVG lines and HTML hit targets; no window listeners
  // or scale-dependent text. A page bounds work, never the source collection.
  const personSlots=count=>Array.from({length:count},(_,i)=>({x:i%2?88:12,y:count<=2?50:count<=4?30+40*Math.floor(i/2):16+34*Math.floor(i/2)}));
  const plotSlots=count=>Array.from({length:count},(_,i)=>({x:15+35*(Math.floor(i/3)%2?2-i%3:i%3),y:80+190*Math.floor(i/3)}));
  const arrow=id=>`<defs><marker id="${id}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 1 L 9 5 L 0 9" fill="none" stroke="currentColor" stroke-width="1.5"/></marker></defs>`;

  // Whole-report layout. Components and multi-hop paths use only supplied
  // endpoints; an isolated person stays isolated, never a made-up relation.
  function graphLayout(items, edges, sequential=false,compactWidth=0,desktopWidth=920) {
    const ids=items.map(item=>String(item.id)), known=new Set(ids), positions=new Map();
    const valid=edges.filter(r=>known.has(String(r.from)) && known.has(String(r.to)));
    if(compactWidth>0) {
      const width=Math.max(300,Math.floor(compactWidth));
      ids.forEach((id,i)=>positions.set(id,{x:width/2,y:90+i*240}));
      return {positions,edges:valid,width,height:Math.max(220,ids.length*240+20)};
    }
    if(sequential) {
      if(ids.length && ids.length<=7){
        const width=Math.max(660,Math.min(1000,Math.floor(desktopWidth)));
        ids.forEach((id,i)=>{const row=Math.floor(i/3),col=row%2?2-i%3:i%3;positions.set(id,{x:80+col*(width-160)/2,y:80+row*220});});
        return {positions,edges:valid,width,height:Math.max(180,Math.ceil(ids.length/3)*220-40),nodeWidth:150,nodeHeight:94,labelWidth:110,labelHeight:52};
      }
      ids.forEach((id,i)=>{const row=Math.floor(i/3),col=row%2?2-i%3:i%3;positions.set(id,{x:140+col*320,y:90+row*210});});
      return {positions,edges:valid,width:920,height:Math.max(220,Math.ceil(ids.length/3)*210)};
    }
    if(ids.length && ids.length<=7) {
      const width=Math.max(660,Math.min(1000,Math.floor(desktopWidth))),columns=Math.min(3,ids.length);
      const slots=ids.map((id,i)=>({x:columns===1?width/2:80+i%columns*(width-160)/(columns-1),y:80+Math.floor(i/columns)*220,col:i%columns,row:Math.floor(i/columns)}));
      let best=ids,bestScore=Infinity;
      const visit=(order,remaining)=>{
        if(remaining.length){remaining.forEach((id,i)=>visit([...order,id],remaining.filter((_,j)=>j!==i)));return;}
        const at=new Map(order.map((id,i)=>[id,slots[i]]));
        const score=valid.reduce((sum,r)=>{const a=at.get(String(r.from)),b=at.get(String(r.to)),dx=Math.abs(a.col-b.col),dy=Math.abs(a.row-b.row);return sum+(dx+dy)*100+(dx&&dy?180:0)+(dx>1 || dy>1?300:0);},0);
        if(score<bestScore){bestScore=score;best=order;}
      };
      visit([],ids);
      best.forEach((id,i)=>positions.set(id,{x:slots[i].x,y:slots[i].y}));
      return {positions,edges:valid,width,height:Math.max(180,Math.ceil(ids.length/columns)*220-40),nodeWidth:150,nodeHeight:94,labelWidth:110,labelHeight:52};
    }
    const adjacent=new Map(ids.map(id=>[id,new Set()]));
    valid.forEach(r=>{adjacent.get(String(r.from)).add(String(r.to));adjacent.get(String(r.to)).add(String(r.from));});
    const isolated=ids.filter(id=>!adjacent.get(id).size);
    const unseen=new Set(ids.filter(id=>adjacent.get(id).size));let bottom=0,maxX=0;
    while(unseen.size) {
      // Stable tie-breaking retains the report's person order.
      const seed=[...unseen].sort((a,b)=>adjacent.get(b).size-adjacent.get(a).size)[0];
      const levels=[[seed]];unseen.delete(seed);
      for(let depth=0;depth<levels.length;depth++) {
        const next=[];
        for(const id of levels[depth])for(const neighbor of adjacent.get(id))if(unseen.delete(neighbor))next.push(neighbor);
        if(next.length)levels.push(next);
      }
      let band=bottom;
      // Fold deep paths into bands to avoid a thousands-of-pixels-wide graph.
      for(let first=0;first<levels.length;first+=3) {
        const part=levels.slice(first,first+3), rows=Math.max(...part.map(level=>level.length));
        part.forEach((level,col)=>level.forEach((id,row)=>{
          const x=140+col*320,y=band+90+row*180;
          positions.set(id,{x,y});maxX=Math.max(maxX,x);
        }));
        band+=Math.max(1,rows)*180+50;
      }
      bottom=band;
    }
    isolated.forEach((id,i)=>{const x=140+(i%3)*320,y=bottom+90+Math.floor(i/3)*180;positions.set(id,{x,y});maxX=Math.max(maxX,x);});
    bottom+=Math.ceil(isolated.length/3)*180;
    return {positions,edges:valid,width:Math.max(600,maxX+160),height:Math.max(220,bottom)};
  }

  // Rectilinear visibility-grid search, used only after the short route
  // templates fail. Rectangle corridors are connected (labels have clearance
  // from every node/label); prior lines forbid retracing, not point crossings.
  function searchGraphPath(blocks, tracks, starts, goals, width, height, refined=false) {
    if(!starts.length || !goals.length)return null;
    const coordinates=(values,limit)=>{
      const sorted=[...new Set(values)].filter(v=>v>=1 && v<=limit-1).sort((a,b)=>a-b);
      return refined?[...new Set([...sorted,...sorted.slice(1).map((v,i)=>(v+sorted[i])/2)])].sort((a,b)=>a-b):sorted;
    };
    const xs=coordinates([1,width-1,...blocks.flatMap(b=>[b.left-2,b.right+2,...(refined?[b.left,b.right]:[])]),...tracks.flatMap(s=>[s.start.x-4,s.start.x+4,s.end.x-4,s.end.x+4,...(refined?[s.start.x,s.end.x]:[])]),...starts.map(s=>s.x),...goals.map(g=>g.x)],width);
    const ys=coordinates([1,height-1,...blocks.flatMap(b=>[b.top-2,b.bottom+2,...(refined?[b.top,b.bottom]:[])]),...tracks.flatMap(s=>[s.start.y-4,s.start.y+4,s.end.y-4,s.end.y+4,...(refined?[s.start.y,s.end.y]:[])]),...starts.map(s=>s.y),...goals.map(g=>g.y)],height);
    const nx=xs.length,xIndex=new Map(xs.map((x,i)=>[x,i])),yIndex=new Map(ys.map((y,i)=>[y,i]));
    const cell=p=>yIndex.get(p.y)*nx+xIndex.get(p.x),targets=new Map(goals.map((g,i)=>[cell(g),i]));
    const horizontal=new Map(),vertical=new Map();
    for(const s of tracks){const map=s.start.y===s.end.y?horizontal:vertical,key=map===horizontal?s.start.y:s.start.x;
      if(!map.has(key))map.set(key,[]);map.get(key).push(map===horizontal?[Math.min(s.start.x,s.end.x),Math.max(s.start.x,s.end.x)]:[Math.min(s.start.y,s.end.y),Math.max(s.start.y,s.end.y)]);}
    const rows=new Map(),columns=new Map();
    const allowed=(x1,y1,x2,y2)=>{
      const horizontalMove=y1===y2,coordinate=horizontalMove?y1:x1,cache=horizontalMove?rows:columns;
      if(!cache.has(coordinate))cache.set(coordinate,blocks.filter(b=>horizontalMove?coordinate>b.top && coordinate<b.bottom:coordinate>b.left && coordinate<b.right).map(b=>horizontalMove?[b.left,b.right]:[b.top,b.bottom]));
      const lo=Math.min(horizontalMove?x1:y1,horizontalMove?x2:y2),hi=Math.max(horizontalMove?x1:y1,horizontalMove?x2:y2);
      return !cache.get(coordinate).some(([a,b])=>lo<b && hi>a) && !(horizontalMove?horizontal:vertical).get(coordinate)?.some(([a,b])=>lo<b && hi>a);
    };
    const minX=Math.min(...goals.map(g=>g.x)),maxX=Math.max(...goals.map(g=>g.x)),minY=Math.min(...goals.map(g=>g.y)),maxY=Math.max(...goals.map(g=>g.y));
    const heuristic=(x,y)=>Math.max(minX-x,0,x-maxX)+Math.max(minY-y,0,y-maxY);
    // Keep incoming-axis state so equally short grid paths prefer a few clear
    // bends over a staircase of tiny alternating horizontal/vertical steps.
    const distance=new Float64Array(nx*ys.length*3).fill(Infinity),previous=new Int32Array(distance.length).fill(-1),owner=new Int32Array(distance.length),heap=[];
    const push=item=>{let i=heap.length;heap.push(item);while(i){const p=(i-1)>>1;if(heap[p].score<=item.score)break;heap[i]=heap[p];i=p;}heap[i]=item;};
    const pop=()=>{const first=heap[0],last=heap.pop();if(heap.length){let i=0;while(i*2+1<heap.length){let c=i*2+1;if(c+1<heap.length && heap[c+1].score<heap[c].score)c++;if(heap[c].score>=last.score)break;heap[i]=heap[c];i=c;}heap[i]=last;}return first;};
    starts.forEach((s,i)=>{const id=cell(s)*3;if(!Number.isInteger(id) || blocks.some(b=>s.x>b.left && s.x<b.right && s.y>b.top && s.y<b.bottom))return;distance[id]=0;owner[id]=i;push({id,cost:0,score:heuristic(s.x,s.y)});});
    while(heap.length){const at=pop();if(at.cost!==distance[at.id])continue;
      const pointId=Math.floor(at.id/3),axis=at.id%3;
      if(targets.has(pointId)){const points=[];for(let id=at.id;id!==-1;id=previous[id]){const p=Math.floor(id/3);points.push({x:xs[p%nx],y:ys[Math.floor(p/nx)]});}return {points:points.reverse(),start:owner[at.id],goal:targets.get(pointId),refined};}
      const ix=pointId%nx,iy=Math.floor(pointId/nx),x=xs[ix],y=ys[iy];
      for(const [jx,jy] of [[ix-1,iy],[ix+1,iy],[ix,iy-1],[ix,iy+1]]){
        if(jx<0 || jx>=nx || jy<0 || jy>=ys.length || !allowed(x,y,xs[jx],ys[jy]))continue;
        const direction=jy===iy?1:2,id=(jy*nx+jx)*3+direction,cost=at.cost+Math.abs(xs[jx]-x)+Math.abs(ys[jy]-y)+(axis && axis!==direction?12:0);
        if(cost>=distance[id])continue;distance[id]=cost;previous[id]=at.id;owner[id]=owner[at.id];push({id,cost,score:cost+heuristic(xs[jx],ys[jy])});
      }
    }
    // Complete subdivision: each free interval between obstacles/used lines
    // gets its own coordinate, even if a narrow corridor saturated coarse rails.
    return refined?null:searchGraphPath(blocks,tracks,starts,goals,width,height,true);
  }

  function graphRoute(layout,edge,occupied=[],labelSize=null) {
    const initialHeight=layout.height;
    const a=layout.positions.get(String(edge.from)),b=layout.positions.get(String(edge.to));
    const nw=layout.nodeWidth || 210,nh=layout.nodeHeight || 94,lw=labelSize?.width ?? layout.labelWidth ?? 138,lh=labelSize?.height ?? layout.labelHeight ?? 52;
    const nodes=[...layout.positions.values()].map(p=>({left:p.x-nw/2,right:p.x+nw/2,top:p.y-nh/2,bottom:p.y+nh/2}));
    const overlaps=(a,b,pad=0)=>a.left<b.right+pad && a.right>b.left-pad && a.top<b.bottom+pad && a.bottom>b.top-pad;
    const rect=p=>({left:p.x-lw/2,right:p.x+lw/2,top:p.y-lh/2,bottom:p.y+lh/2});
    const segmentHits=(a,b,r)=>a.x===b.x?a.x>r.left+1 && a.x<r.right-1 && Math.max(a.y,b.y)>r.top+1 && Math.min(a.y,b.y)<r.bottom-1:a.y>r.top+1 && a.y<r.bottom-1 && Math.max(a.x,b.x)>r.left+1 && Math.min(a.x,b.x)<r.right-1;
    const labelHits=(a,b,r)=>segmentHits(a,b,{left:r.left-1,right:r.right+1,top:r.top-1,bottom:r.bottom+1});
    const reserved=occupied.flatMap(r=>r.segments || []);
    const segments=points=>points.slice(1).map((end,i)=>({start:points[i],end}));
    const shared=(a,b)=>a.start.x===a.end.x && b.start.x===b.end.x && a.start.x===b.start.x
      ? Math.min(Math.max(a.start.y,a.end.y),Math.max(b.start.y,b.end.y))-Math.max(Math.min(a.start.y,a.end.y),Math.min(b.start.y,b.end.y))>0
      : a.start.y===a.end.y && b.start.y===b.end.y && a.start.y===b.start.y
        && Math.min(Math.max(a.start.x,a.end.x),Math.max(b.start.x,b.end.x))-Math.max(Math.min(a.start.x,a.end.x),Math.min(b.start.x,b.end.x))>0;
    const unique=values=>[...new Set(values)].sort((a,b)=>a-b);
    const xs=unique([...layout.positions.values()].map(p=>p.x)),ys=unique([...layout.positions.values()].map(p=>p.y));
    const xlanes=unique([18,layout.width-18,...xs.slice(1).map((x,i)=>(x+xs[i])/2)]);
    const ylanes=unique([18,layout.height-18,...ys.slice(1).map((y,i)=>(y+ys[i])/2)]);
    let best=null;
    function consider(raw) {
      const points=[];
      raw.forEach(p=>{
        if(points.length && p.x===points.at(-1).x && p.y===points.at(-1).y)return;
        if(points.length>=2){const first=points.at(-2),last=points.at(-1);if(first.x===last.x && last.x===p.x || first.y===last.y && last.y===p.y)points.pop();}
        points.push(p);
      });
      if(points.length<2)return;
      if(points.some((p,i)=>i && nodes.some(n=>segmentHits(points[i-1],p,n))))return;
      const tracks=segments(points);
      // Distinct endpoint pairs never share a trunk. A perpendicular crossing
      // remains a single point; it does not imply a semantic junction.
      if(tracks.some(s=>reserved.some(r=>shared(s,r))))return;
      if(tracks.some(s=>occupied.some(box=>labelHits(s.start,s.end,box))))return;
      const length=points.reduce((sum,p,i)=>sum+(i?Math.abs(p.x-points[i-1].x)+Math.abs(p.y-points[i-1].y):0),0);
      for(let i=1;i<points.length;i++) {
        const start=points[i-1],end=points[i],horizontal=start.y===end.y;
        const span=horizontal?Math.abs(end.x-start.x):Math.abs(end.y-start.y);
        if(span<(horizontal?lw:lh)+14)continue;
        for(const t of [.5,.35,.65]) {
          const label={x:start.x+(end.x-start.x)*t,y:start.y+(end.y-start.y)*t},box=rect(label);
          if(box.left<4 || box.top<4 || box.right>layout.width-4 || box.bottom>layout.height-4)continue;
          if(nodes.some(n=>overlaps(box,n,6)) || occupied.some(n=>overlaps(box,n,8)))continue;
          if(reserved.some(s=>labelHits(s.start,s.end,box)))continue;
          const score=length+(points.length-2)*20+Math.abs(.5-t)*60;
          if(!best || score<best.score)best={points,segments:tracks,label,box,score,direction:horizontal?(end.x>start.x?'→':'←'):(end.y>start.y?'↓':'↑')};
        }
      }
    }
    if(a.x===b.x && a.y!==b.y){const direction=Math.sign(b.y-a.y);consider([{x:a.x,y:a.y+direction*nh/2},{x:b.x,y:b.y-direction*nh/2}]);}
    if(a.y===b.y && a.x!==b.x){const direction=Math.sign(b.x-a.x);consider([{x:a.x+direction*nw/2,y:a.y},{x:b.x-direction*nw/2,y:b.y}]);}
    for(const x of xlanes)consider([{x:a.x+(x>a.x?nw/2:-nw/2),y:a.y},{x,y:a.y},{x,y:b.y},{x:b.x+(x>b.x?nw/2:-nw/2),y:b.y}]);
    for(const y of ylanes)consider([{x:a.x,y:a.y+(y>a.y?nh/2:-nh/2)},{x:a.x,y},{x:b.x,y},{x:b.x,y:b.y+(y>b.y?nh/2:-nh/2)}]);
    // Try separate ports and parallel corridors before growing the canvas.
    // Node positions and graph ordering stay exactly as supplied by layout.
    const offsets=[0,-16,16,-32,32];
    const nearby=(lanes,first,last,limit)=>unique(lanes.flatMap(v=>offsets.map(d=>v+d)).filter(v=>v>=10 && v<=limit-10))
      .sort((x,y)=>Math.min(Math.abs(x-first),Math.abs(x-last))-Math.min(Math.abs(y-first),Math.abs(y-last))).slice(0,14);
    const alternateX=unique([10,18,layout.width-18,layout.width-10,...nearby(xlanes,a.x,b.x,layout.width)]),alternateY=nearby(ylanes,a.y,b.y,layout.height);
    if(!best)for(const da of offsets)for(const db of offsets) {
      if(a.x===b.x && da===db){const d=Math.sign(b.y-a.y);consider([{x:a.x+da,y:a.y+d*nh/2},{x:b.x+db,y:b.y-d*nh/2}]);}
      if(a.y===b.y && da===db){const d=Math.sign(b.x-a.x);consider([{x:a.x+d*nw/2,y:a.y+da},{x:b.x-d*nw/2,y:b.y+db}]);}
      for(const x of alternateX)consider([{x:a.x+(x>a.x?nw/2:-nw/2),y:a.y+da},{x,y:a.y+da},{x,y:b.y+db},{x:b.x+(x>b.x?nw/2:-nw/2),y:b.y+db}]);
      for(const y of alternateY)consider([{x:a.x+da,y:a.y+(y>a.y?nh/2:-nh/2)},{x:a.x+da,y},{x:b.x+db,y},{x:b.x+db,y:b.y+(y>b.y?nh/2:-nh/2)}]);
    }
    if(!best) {
      // Use a free horizontal corridor; its label remains ON its own route.
      // Dense reports may grow, but neither nodes nor semantic edges disappear.
      for(let extension=0;extension<3 && !best;extension++) {
        if(extension)layout.height+=160;
        const candidates=extension?[layout.height-38]:ylanes;
        const near=p=>unique([
          ...alternateX.filter(x=>Math.abs(x-p.x)>=nw/2+8).sort((x,y)=>Math.abs(x-p.x)-Math.abs(y-p.x)).slice(0,4),
          ...[10,18,layout.width-18,layout.width-10].filter(x=>Math.abs(x-p.x)>=nw/2+8),
        ]);
        for(const da of offsets)for(const db of offsets)for(const x1 of near(a))for(const x2 of near(b))for(const y of candidates)consider([{x:a.x+(x1>a.x?nw/2:-nw/2),y:a.y+da},{x:x1,y:a.y+da},{x:x1,y},{x:x2,y},{x:x2,y:b.y+db},{x:b.x+(x2>b.x?nw/2:-nw/2),y:b.y+db}]);
        // Two separate return rails also support a long back-edge whose
        // endpoints are in one column. The bottom label corridor is bounded;
        // neither its outbound nor return segment retraces another route.
        if(extension && !best)for(const da of offsets)for(const db of offsets)for(const x1 of near(a))for(const x2 of near(b)) {
          if(x1===x2)continue;
          for(const x of [18,layout.width-18])consider([{x:a.x+(x1>a.x?nw/2:-nw/2),y:a.y+da},{x:x1,y:a.y+da},{x:x1,y:layout.height-118},{x,y:layout.height-118},{x,y:layout.height-38},{x:x2,y:layout.height-38},{x:x2,y:b.y+db},{x:b.x+(x2>b.x?nw/2:-nw/2),y:b.y+db}]);
        }
      }
    }
    if(!best) {
      // A free label bay below the existing graph guarantees label space.
      // Search both legs with all obstacle-corner coordinates, rather than
      // repeatedly trying the same saturated ports/corridors farther away.
      layout.height=initialHeight;
      const bayY=Math.ceil(layout.height+lh/2+24),left={x:18,y:bayY},right={x:18+lw+32,y:bayY},label={x:(left.x+right.x)/2,y:bayY},box=rect(label);
      layout.height=Math.ceil(bayY+lh/2+24);
      const inflate=r=>({left:r.left-1,right:r.right+1,top:r.top-1,bottom:r.bottom+1});
      const blocks=[...nodes,...occupied,box].map(inflate),bay={start:left,end:right};
      const ports=p=>{
        const candidates=[];
        for(const verticalSide of [true,false])for(const sign of [-1,1]){
          const center=verticalSide?p.y:p.x,half=(verticalSide?nh:nw)/2-6;
          const used=reserved.flatMap(s=>[s.start,s.end]).filter(v=>verticalSide?Math.abs(v.x-p.x)===nw/2:Math.abs(v.y-p.y)===nh/2).map(v=>verticalSide?v.y:v.x).filter(v=>Math.abs(v-center)<half);
          const bounds=unique([center-half,...used,center+half]);
          const values=unique([center,center-12,center+12,center-24,center+24,...bounds.slice(1).map((v,i)=>(v+bounds[i])/2)]).filter(v=>Math.abs(v-center)<=half);
          for(const value of values){const port=verticalSide?{x:p.x+sign*nw/2,y:value}:{x:value,y:p.y+sign*nh/2},escape=verticalSide?{x:port.x+sign*3,y:value}:{x:value,y:port.y+sign*3},stub={start:port,end:escape};
            if(escape.x<1 || escape.x>layout.width-1 || escape.y<1 || escape.y>layout.height-1)continue;
            if(nodes.some(n=>segmentHits(port,escape,n)) || occupied.some(n=>labelHits(port,escape,n)) || reserved.some(s=>shared(stub,s)))continue;
            candidates.push({port,escape,stub});
          }
        }
        return candidates;
      };
      const starts=ports(a),ends=ports(b),first=searchGraphPath(blocks,[...reserved,bay],starts.map(p=>p.escape),[left],layout.width,layout.height);
      if(first){const firstTracks=segments([starts[first.start].port,...first.points]),endPorts=ends.filter(p=>!firstTracks.some(s=>shared(p.stub,s)));
        const second=searchGraphPath(blocks,[...reserved,bay,...firstTracks],[right],endPorts.map(p=>p.escape),layout.width,layout.height);
        if(second){consider([starts[first.start].port,...first.points,...second.points,endPorts[second.goal].port]);
          // The bay is on the route and outside every earlier object/line.
          // Keep its own label rather than placing one in a crowded interior.
          if(best)best={...best,label,box,direction:'→',searched:true};
        }
      }
    }
    if(!best)throw new Error('关系图可用路径搜索失败');
    occupied.push({...best.box,segments:best.segments});
    return {...best,d:best.points.map((p,i)=>`${i?'L':'M'}${p.x},${p.y}`).join(' ')};
  }

  function mountModel(root, report, options) {
    const evidence = options.evidence, claim = options.claim;
    const people = list(report.characters).map(p => ({...p, title:p.name, group:modelGroup(p), subtitle:p.identity?.text || '', status:p.identity?.status,
      search:[p.name, ...list(p.aliases), p.identity?.text, p.portrait?.text, p.change?.text].join(' ')}));
    const peopleById = new Map(people.map(p => [p.id,p]));
    const events = list(report.events).map(e => ({...e, label:chapterLabel(e), chapters:Array.from({length:Math.max(1,(e.chapter_end || e.chapter_number)-e.chapter_number+1)},(_,i)=>e.chapter_number+i), summary:e.action?.text || '', status:e.action?.status,
      search:[e.title,e.action?.text,e.consequence?.text,...list(e.actor_ids).map(id=>peopleById.get(id)?.name),...list(e.sub_events).map(s=>s.title+' '+s.text)].join(' ')}));
    const eventById = new Map(events.map(e=>[e.id,e]));
    // Only the optional semantic contract supplies relationships. Co-actors
    // are intentionally not converted into edges here.
    const relations = list(report.character_relations).filter(r=>peopleById.has(r.from_id) && peopleById.has(r.to_id));
    const kinds = {causes:'促成',enables:'提供条件',reveals:'揭示',foreshadow_payoff:'线索回收',follows:'先后'};
    return mount(root, {
      people,events,storyOrder:list(report.story_order),timeNote:report.time_note || '',
      personEdges:relations.map(r=>({from:r.from_id,to:r.to_id,label:r.label || r.text || '',status:r.status,body:()=>claim(r)})),
      eventEdges:list(report.relations).map(r=>({from:r.from_id,to:r.to_id,label:kinds[r.kind] || '待核对',kind:r.kind,status:r.status,body:()=>claim(r)})),
      personRelations:p=>relations.filter(r=>r.from_id===p.id || r.to_id===p.id).map(r=>({from:r.from_id,to:r.to_id,label:r.label || r.text || '',status:r.status,body:()=>claim(r)})),
      personExperiences:p=>events.filter(e=>list(e.actor_ids).includes(p.id)),
      personAnalysis:p=>`<section><h3>身份与处境</h3>${claim(p.identity)}</section><section><h3>性格与为人</h3>${claim(p.portrait || p.identity)}</section><section><h3>动机</h3>${claim(p.motivation)}</section><section><h3>关键经历与变化</h3>${claim(p.change)}</section><div class="analysis-phrase-row">${list(p.insights).map((i,n)=>`<button class="analysis-phrase" type="button" data-report-phrase="${esc(p.id)}~${n}">${esc(i.title)}</button>`).join('')}</div>`,
      openInsight:(id,index)=>{const p=peopleById.get(id),insight=list(p?.insights)[Number(index)];if(insight)options.openModal({eyebrow:p.name,title:insight.title,body:claim(insight)});},
      eventBody:e=>`<section><h3>事件经过</h3>${claim(e.action)}</section><section><h3>结果与后续</h3>${claim(e.consequence)}</section>`,
      subEvents:e=>list(e.sub_events).map((s,i)=>({id:String(i),title:s.title,body:()=>claim(s)})),
      peopleForEvent:e=>list(e.actor_ids).map(id=>peopleById.get(id)).filter(Boolean),
      extras:()=>list(report.open_questions).length + list(report.contradictions).length ? details(`疑问与矛盾 · ${list(report.open_questions).length + list(report.contradictions).length}`, `<div data-reader-questions></div>`) : '',
      bindExtras:node=>B.mount(node.querySelector('[data-reader-questions]'),{label:'疑问与矛盾',items:[...list(report.open_questions).map(text=>({text})),...list(report.contradictions)],renderItem:q=>q.title?`<h3>${esc(q.title)}</h3>${claim(q)}`:`<p>${esc(q.text)}</p>`}),
    }, options);
  }

  function mountRule(root, report, raw, options) {
    const rawPeople = new Map(list(raw.characters?.characters).map(p=>[p.item_id,p]));
    const sourcePeople=list(report.characters.characters), sourceEvents=list(report.plot.events);
    const chapter = item => list(item.chapterIds).map(id=>report.chapters.find(c=>c.id===id)?.number).filter(n=>n!=null).map(n=>`第 ${n} 章`).join('、');
    const evidence = item => options.evidence(item, report);
    const people = sourcePeople.map(p=>({...p,title:p.name,group:({main:groups[0],supporting:groups[1]})[rawPeople.get(p.id)?.importance] || groups[2],
      subtitle:rawPeople.get(p.id)?.summary || p.conclusion || '',search:[p.name,...list(p.aliases),p.role,p.conclusion].join(' ')}));
    const byPerson=new Map(people.map(p=>[p.id,p]));
    const events=sourceEvents.map(e=>({...e,title:e.action,label:chapter(e),chapters:list(e.chapterIds).map(id=>report.chapters.find(c=>c.id===id)?.number).filter(n=>n!=null),summary:e.consequence || e.conclusion,search:[e.action,e.conclusion,e.consequence,...list(e.characterIds).map(id=>byPerson.get(id)?.name)].join(' ')}));
    const claim=item=>`<p>${esc(item.conclusion || item.explanation || '')}</p>${details('原文依据',evidence(item))}`;
    return mount(root,{
      people,events,storyOrder:[],personEdges:[],
      eventEdges:list(report.plot.relations).map(r=>({from:r.start.id,to:r.end.id,label:options.relationLabel(r.relationType),kind:'clue',body:()=>claim(r)})),
      personRelations:()=>[],
      personExperiences:p=>events.filter(e=>list(e.characterIds).includes(p.id)),
      personAnalysis:p=>`<section><h3>原文记录</h3>${claim(p)}</section>${list(report.characters.states).filter(s=>s.characterId===p.id).map(s=>details(chapter(s),claim(s))).join('')}${list(report.characters.relations).filter(r=>r.start.id===p.id || r.end.id===p.id).map(r=>details('规则关联记录',`<p>${esc(byPerson.get(r.start.id)?.name)} → ${esc(byPerson.get(r.end.id)?.name)} · ${esc(options.relationLabel(r.relationType))}</p>${badge('unknown')}${claim(r)}`)).join('')}`,
      eventBody:e=>`<section><h3>事件经过</h3><p>${esc(e.action)}</p>${claim(e)}</section>${e.consequence?`<section><h3>结果</h3><p>${esc(e.consequence)}</p></section>`:''}`,
      subEvents:()=>[],peopleForEvent:e=>list(e.characterIds).map(id=>byPerson.get(id)).filter(Boolean),
      extras:()=>'',
    },options);
  }

  function mount(root, data, options) {
    const people=new Map(data.people.map(p=>[String(p.id),p])), events=new Map(data.events.map(e=>[String(e.id),e]));
    const key=`xumai-reader:${options.projectId}:${options.documentId}`;
    let saved={};
    try { saved=JSON.parse(sessionStorage.getItem(key) || '{}'); } catch { /* Storage is optional; the URL remains authoritative. */ }
    const fresh=()=>({query:'',page:1,filters:{},selected:'',order:'narrative',map:'total'});
    const browsing={characters:{...fresh(),...saved.characters},plot:{...fresh(),...saved.plot}};
    const legacyTime=options.section==='time';
    let section=options.section==='characters'?'characters':'plot', object=null, pane='relations', edgeChoices=[],timeNoteOpen=legacyTime;
    const params=new URLSearchParams(location.search);
    const validScope=params.get('volume')===options.documentId;
    if(validScope) {
      object=params.get(section==='characters'?'character':'event');pane=params.get('pane')==='experiences'?'experiences':'relations';
      const state=browsing[section];
      if(params.has('q'))state.query=params.get('q');
      if(params.has('page'))state.page=Math.max(1,Number(params.get('page')) || 1);
      if(params.has('group'))state.filters={group:params.get('group')};
      if(params.has('inChapter'))state.filters={...state.filters,chapter:params.get('inChapter')};
      if(params.has('selected'))state.selected=params.get('selected');
      if(params.has('order'))state.order=params.get('order')==='story'?'story':'narrative';
      if(params.has('map'))state.map=params.get('map')==='index'?'index':'total';
    } else if(params.has('character') || params.has('event')) {
      root.innerHTML='<p role="alert">此链接缺少报告来源。请从人物或剧情索引重新打开。</p>';return {select:()=>{}};
    }
    if(legacyTime)object=null;
    if (!data.storyOrder.length) browsing.plot.order='narrative';
    const state=()=>browsing[section];
    const persist=()=>{try{sessionStorage.setItem(key,JSON.stringify(browsing));}catch{/* In-memory and URL state continue to work. */}};
    function urlFor(targetSection=section,id=object,targetPane=pane) {
      const url=new URL(location.href),s=browsing[targetSection];
      for(const name of ['character','event','pane','focus','q','page','group','inChapter','order','selected','map'])url.searchParams.delete(name);
      url.searchParams.set('view','deconstruction');url.searchParams.set('volume',options.documentId);url.searchParams.set('section',targetSection);
      if(id)url.searchParams.set(targetSection==='characters'?'character':'event',id);
      if(id && targetSection==='characters' && targetPane==='experiences')url.searchParams.set('pane','experiences');
      if(s.query)url.searchParams.set('q',s.query);
      if(s.page>1)url.searchParams.set('page',s.page);
      if(s.filters?.group)url.searchParams.set('group',s.filters.group);
      if(s.filters?.chapter)url.searchParams.set('inChapter',s.filters.chapter);
      if(s.selected)url.searchParams.set('selected',s.selected);
      if(targetSection==='plot')url.searchParams.set('order',s.order);
      if(s.map==='index')url.searchParams.set('map','index');
      return url;
    }
    function sync(push=false) {
      persist();const url=urlFor();
      if(url.href!==location.href)history[push?'pushState':'replaceState'](push?{}:history.state,'',url);
      options.onSection?.(section,object);
    }
    function rememberIndexReturn(restore) {
      // A remembered selection alone must not scroll a fresh primary entry.
      const entry={...history.state};
      if(restore)entry.xumaiReaderReturn={key,section};
      else delete entry.xumaiReaderReturn;
      history.replaceState(entry,'',location.href);
    }
    function link(targetSection,id,text,cls='quiet-link') {
      return `<a class="${cls}" href="${esc(urlFor(targetSection,id))}" data-reader-open="${esc(id)}" data-reader-section="${targetSection}">${esc(text)}</a>`;
    }
    function navigate(targetSection,id=null,targetPane='relations',restoreIndex=false) {
      if(id && !object && targetSection===section){
        state().selected=id;sync(false);rememberIndexReturn(true);
      }
      section=targetSection;object=id;pane=targetPane;sync(true);
      if(!object)rememberIndexReturn(restoreIndex);
      draw(restoreIndex?'restore':'top');
    }
    function orderEvents() {
      if(state().order!=='story')return data.events;
      const ordered=data.storyOrder.map(id=>events.get(String(id))).filter(Boolean),seen=new Set(ordered.map(e=>e.id));
      return [...ordered,...data.events.filter(e=>!seen.has(e.id))];
    }
    function mountCollection(node,config) {
      return B.mount(node,{...config,state:state(),onState:()=>sync(false)});
    }
    function personIndex() {
      if(state().map!=='index'){totalGraph('characters');return;}
      const items=[...data.people].sort((a,b)=>groups.indexOf(a.group)-groups.indexOf(b.group));
      root.innerHTML=`<div class="workspace-reader-index" data-reader-index="characters">${mapSwitch()}<div data-person-index></div></div>`;
      mountCollection(root.querySelector('[data-person-index]'),{label:'人物',items,pageSize:12,className:'workspace-person-index',text:p=>p.search,
        filters:[{name:'group',label:'人物分组',options:[{value:'',label:'全部人物'},...groups.map(g=>({value:g,label:`${g} · ${items.filter(p=>p.group===g).length}`}))],match:(p,g)=>p.group===g}],
        renderItem:p=>`<article class="workspace-person-row" data-person-id="${esc(p.id)}"><span class="person-initial" aria-hidden="true">${esc(Array.from(p.name || '人')[0])}</span><div><span class="workspace-person-group">${esc(p.group)}</span><h2>${link('characters',p.id,p.name,'analysis-person-link')}</h2><p>${p.status?badge(p.status):''}${esc(short(p.subtitle,65))}</p></div><span aria-hidden="true" class="object-open-arrow">↗</span></article>`});
    }
    function plotIndex() {
      if(state().map!=='index'){totalGraph('plot');return;}
      root.innerHTML=`<div class="workspace-reader-index" data-reader-index="plot">${mapSwitch()}${orderSwitch()}<div data-event-index></div></div>`;
      const chapters=[...new Set(data.events.flatMap(e=>e.chapters))].sort((a,b)=>a-b);
      mountCollection(root.querySelector('[data-event-index]'),{label:'剧情',items:orderEvents(),pageSize:8,className:'workspace-plot-diagram',text:e=>e.search,
        filters:[{name:'chapter',label:'章节',options:[{value:'',label:'全部章节'},...chapters.map(n=>({value:String(n),label:`第 ${n} 章`}))],match:(e,n)=>e.chapters.includes(Number(n))}],
        renderItem:()=>'',afterRender:(node,visible)=>drawPlot(node,visible)});
      root.querySelector('[data-reader-index]').insertAdjacentHTML('beforeend','<section data-edge-basis hidden></section>');
    }
    function mapSwitch() {
      return `<div class="workspace-map-switch" role="group" aria-label="阅读方式"><button type="button" data-reader-map="total" aria-pressed="${state().map!=='index'}">${section==='characters'?'人物关系总图':'事件关系总图'}</button><button type="button" data-reader-map="index" aria-pressed="${state().map==='index'}">${section==='characters'?'人物索引':'逐章浏览'}</button></div>`;
    }
    function orderSwitch() {
      return `<div class="workspace-order" role="group" aria-label="事件顺序"><button data-reader-order="narrative" aria-pressed="${state().order==='narrative'}">叙述顺序</button><button data-reader-order="story" aria-pressed="${state().order==='story'}" ${data.storyOrder.length?'':'disabled title="本报告未提供故事顺序"'}>故事顺序</button></div>${data.timeNote?`<details class="workspace-time-note" data-reader-time-note ${timeNoteOpen?'open':''}><summary>时间与不确定性</summary><p>${esc(data.timeNote)}</p></details>`:''}`;
    }
    function totalGraph(kind) {
      const character=kind==='characters',items=character?data.people:orderEvents();
      const compactWidth=root.clientWidth>0 && root.clientWidth<620?root.clientWidth-2:0;
      const layout=graphLayout(items,character?list(data.personEdges):data.eventEdges,!character,compactWidth,root.clientWidth?root.clientWidth-20:920);
      edgeChoices=layout.edges;
      if(!character && !items.some(e=>e.id===state().selected))state().selected=items[0]?.id || '';
      const marker=`totalArrow${++graphSerial}`,byId=character?people:events;
      const routes=new Map(),routeReservations=[];
      edgeChoices.forEach((r,i)=>{const pair=JSON.stringify([r.from,r.to]);if(!routes.has(pair))routes.set(pair,[]);routes.get(pair).push(i);});
      const groups=[...routes.values()];
      const labels=groups.map(indices=>{
        const r=edgeChoices[indices[0]];
        const from=byId.get(String(r.from)),to=byId.get(String(r.to)),label=indices.map(i=>edgeChoices[i].label).join(' / ');
        return `<button type="button" class="total-graph-edge" data-reader-edges="${indices.join(',')}" aria-label="${esc(`${from.name || from.title} → ${label} → ${to.name || to.title}`)}"><span class="total-graph-edge-text">${esc(short(label,22))} <span class="total-graph-edge-direction" aria-hidden="true">→</span></span>${indices.length===1?badge(r.status):`<small>${indices.length} 项联系</small>`}</button>`;
      });
      const nodes=items.map((item,i)=>{const p=layout.positions.get(String(item.id));
        return `<article class="total-graph-node ${character?'is-person':'is-event'}" style="left:${p.x}px;top:${p.y}px" ${character?`data-person-id="${esc(item.id)}"`:`data-event-id="${esc(item.id)}"`}><span class="eyebrow">${character?esc(item.group):`<span class="total-graph-position">${String(i+1).padStart(2,'0')}</span> ${esc(item.label)}`}</span><h2>${link(kind,item.id,character?item.name:item.title,'total-graph-link')}</h2></article>`;
      }).join('');
      root.innerHTML=`<div class="workspace-reader-index" data-reader-index="${kind}">${mapSwitch()}${character?'':orderSwitch()}<div ${character?'data-person-index':'data-event-index'}><div class="total-graph-meta"><span>${items.length} ${character?'个人物':'个事件'} · ${edgeChoices.length} 条联系</span>${character?'':`<span>${state().order==='story'?'故事顺序':'叙述顺序'}</span>`}</div>${items.length?`<div class="total-graph-scroll" role="region" tabindex="0" aria-label="${character?'人物关系总图':'事件关系总图'}，可滚动查看"><div class="total-graph-canvas" style="width:${layout.width}px;height:${layout.height}px;--graph-node-width:${layout.nodeWidth || 210}px;--graph-label-width:${layout.labelWidth || 138}px"><svg class="total-graph-lines" viewBox="0 0 ${layout.width} ${layout.height}" aria-hidden="true">${arrow(marker)}</svg>${labels.join('')}${nodes}</div></div>`:'<p class="workspace-empty">报告中尚未记录'+(character?'人物':'事件')+'。</p>'}${items.length && !edgeChoices.length?`<p class="total-graph-empty">${character?'暂无已记录的语义关系，可点人物查看经历。':'暂无已记录的事件联系，可点节点查看经过。'}</p>`:''}</div><section data-edge-basis hidden></section></div>`;
      // Measure the real, two-line-clamped buttons before any routing. The
      // fixed-width direction glyph can change without changing their size.
      // The same dimensions drive ordinary obstacles, reservations and bays.
      const buttons=Array.from(root.querySelectorAll('.total-graph-edge'));
      const sizes=buttons.map(button=>{const {width,height}=button.getBoundingClientRect();return {width,height};});
      const paths=buttons.map((button,i)=>{
        const r=edgeChoices[groups[i][0]],route=graphRoute(layout,r,routeReservations,sizes[i]);
        button.style.left=`${route.label.x}px`;button.style.top=`${route.label.y}px`;
        button.querySelector('.total-graph-edge-direction').textContent=route.direction;
        return `<path d="${route.d}" marker-end="url(#${marker})" data-total-from="${esc(r.from)}" data-total-to="${esc(r.to)}"/>`;
      });
      if(buttons.length){
        const canvas=root.querySelector('.total-graph-canvas');
        canvas.style.height=`${layout.height}px`;
        const svg=canvas.querySelector('.total-graph-lines');
        svg.setAttribute('viewBox',`0 0 ${layout.width} ${layout.height}`);svg.insertAdjacentHTML('beforeend',paths.join(''));
      }
      if(!character)updatePlotFocus();
      sync(false);
    }
    function drawPlot(node,visible) {
      edgeChoices=[];
      const basis=root.querySelector('[data-edge-basis]');if(basis)basis.hidden=true;
      if(!visible.length){node.innerHTML='<p class="workspace-empty">没有符合条件的事件</p>';return;}
      if(!visible.some(e=>e.id===state().selected))state().selected=visible[0].id;
      const slots=plotSlots(visible.length), height=190*Math.ceil(visible.length/3)+30;
      const positions=new Map(visible.map((e,i)=>[String(e.id),{...slots[i],i}]));
      const marker=`plotArrow${++graphSerial}`;
      edgeChoices=data.eventEdges.filter(r=>positions.has(String(r.from)) && positions.has(String(r.to)));
      const grouped=new Map();
      edgeChoices.forEach((r,i)=>{const key=JSON.stringify([r.from,r.to]);if(!grouped.has(key))grouped.set(key,[]);grouped.get(key).push(i);});
      const track=slots.map((p,i)=>`${i?'L':'M'} ${p.x*10} ${p.y}`).join(' ');
      const edges=[...grouped.values()].map(indices=>{
        const r=edgeChoices[indices[0]],a=positions.get(String(r.from)),b=positions.get(String(r.to));
        const same=a.y===b.y,dir=a.x<b.x?1:-1;
        const start=same?[a.x*10+dir*137,a.y]:[a.x*10,a.y+(a.y<b.y?62:-62)];
        const end=same?[b.x*10-dir*137,b.y]:[b.x*10,b.y+(a.y<b.y?-62:62)];
        const bend=same?a.y+85:(a.y+b.y)/2;
        const d=same?`M${start} C${start[0]},${bend} ${end[0]},${bend} ${end}`:`M${start} C${start[0]},${bend} ${end[0]},${bend} ${end}`;
        const label=indices.map(i=>edgeChoices[i].label).join(' / '),name=`${visible[a.i].title} → ${label} → ${visible[b.i].title}`;
        return `<g class="plot-semantic-edge" data-edge-from="${esc(r.from)}" data-edge-to="${esc(r.to)}"><path d="${d}" marker-end="url(#${marker})"/><g role="button" tabindex="0" data-reader-edges="${indices.join(',')}" aria-label="${esc(name)}"><title>${esc(name)}</title><path class="edge-hit" d="${d}"/></g></g>`;
      }).join('');
      node.innerHTML=`<div class="plot-legend"><span class="plot-order-key">${state().order==='story'?'故事位置':'叙述位置'}</span><span class="plot-edge-key">事件联系 · ${edgeChoices.length}</span></div><div class="plot-canvas" style="height:${height}px"><svg class="workspace-graph-lines" viewBox="0 0 1000 ${height}" preserveAspectRatio="none">${arrow(marker)}<path class="plot-order-track" d="${track}"/>${edges}</svg>${visible.map((e,i)=>`<article class="plot-node" style="--node-x:${slots[i].x}%;--node-y:${slots[i].y}px" data-event-id="${esc(e.id)}"><div class="plot-node-meta"><span class="event-position">${String((state().page-1)*8+i+1).padStart(2,'0')}</span><span class="eyebrow">${esc(e.label)}</span>${e.status?badge(e.status):''}</div><h2>${link('plot',e.id,e.title,'workspace-event-link')}</h2><p>${esc(short(e.summary,48))}</p></article>`).join('')}</div><div class="plot-focus-links" aria-label="当前事件联系"></div>`;
      updatePlotFocus();
    }
    function updatePlotFocus() {
      root.querySelectorAll('[data-event-id]').forEach(node=>{const active=node.dataset.eventId===state().selected;node.classList.toggle('is-selected',active);node.querySelector('[data-reader-open]')?.setAttribute('aria-current',active?'true':'false');});
      root.querySelectorAll('.plot-semantic-edge').forEach(node=>node.classList.toggle('is-focused',node.dataset.edgeFrom===state().selected || node.dataset.edgeTo===state().selected));
      const choices=root.querySelector('.plot-focus-links');
      const grouped=new Map();edgeChoices.forEach((r,i)=>{if(String(r.from)!==state().selected && String(r.to)!==state().selected)return;const key=JSON.stringify([r.from,r.to]);if(!grouped.has(key))grouped.set(key,[]);grouped.get(key).push(i);});
      if(choices)choices.innerHTML=[...grouped.values()].map(indices=>{const r=edgeChoices[indices[0]];return `<button type="button" data-reader-edges="${indices.join(',')}">${esc(short(events.get(String(r.from))?.title,18))}<span> → ${esc(indices.length>1?`${indices.length} 项联系`:r.label)} → </span>${esc(short(events.get(String(r.to))?.title,18))}${indices.length===1?badge(r.status):''}</button>`;}).join('');
    }
    function relationshipPage(person) {
      const relations=data.personRelations(person);
      const region=root.querySelector('[data-person-body]');
      region.innerHTML=relations.length?`<div data-relationship-index class="${relations.length<=6?'is-compact':''}"></div>`:'<p class="workspace-empty">暂无已记录的关系</p>';
      if(relations.length)B.mount(region.querySelector('[data-relationship-index]'),{label:'关系',items:relations,pageSize:6,className:'workspace-relationships',
        text:r=>`${people.get(String(r.from))?.name} ${r.label} ${people.get(String(r.to))?.name}`,
        renderItem:()=>'',afterRender:(node,visible)=>{
          edgeChoices=visible;
          const basis=root.querySelector('[data-edge-basis]');if(basis)basis.hidden=true;
          if(!visible.length){node.innerHTML='<p class="workspace-empty">没有符合条件的关系</p>';return;}
          const neighbors=[...new Set(visible.map(r=>String(r.from)===String(person.id)?String(r.to):String(r.from)))], slots=personSlots(neighbors.length),marker=`personArrow${++graphSerial}`;
          const multiplicity=Math.max(1,...neighbors.map(id=>visible.filter(r=>String(r.from)===id || String(r.to)===id).length));
          const height=Math.max(neighbors.length<=2?230:380,multiplicity*100+40);
          const edges=visible.map(r=>{const other=String(r.from)===String(person.id)?String(r.to):String(r.from),p=slots[neighbors.indexOf(other)],outgoing=String(r.from)===String(person.id),left=p.x<50;
            const from=[left?410:590,height/2],to=[left?210:790,p.y*height/100];
            return `<path d="M${from[0]},${from[1]} C${left?340:660},${height/2} ${left?340:660},${to[1]} ${to[0]},${to[1]}" ${outgoing?'marker-end':'marker-start'}="url(#${marker})" data-relation-from="${esc(r.from)}" data-relation-to="${esc(r.to)}"/>`;
          }).join('');
          node.innerHTML=`<div class="person-graph" style="height:${height}px"><svg class="workspace-graph-lines" viewBox="0 0 1000 ${height}" preserveAspectRatio="none" aria-hidden="true">${arrow(marker)}${edges}</svg><div class="person-graph-center"><span class="person-initial" aria-hidden="true">${esc(Array.from(person.name)[0])}</span><strong>${esc(person.name)}</strong></div>${neighbors.map((id,i)=>{const p=slots[i],rs=visible.map((r,j)=>({r,j})).filter(({r})=>String(r.from)===id || String(r.to)===id);return `<div class="person-graph-neighbor" style="--node-x:${p.x}%;--node-y:${p.y}%">${link('characters',id,people.get(id)?.name || '未命名人物','person-graph-link')}</div><div class="person-graph-labels" style="--node-x:${p.x<50?31:69}%;--node-y:${p.y}%">${rs.map(({r,j})=>`<button type="button" data-reader-edges="${j}" aria-label="${esc(people.get(String(r.from))?.name)} → ${esc(r.label)} → ${esc(people.get(String(r.to))?.name)}"><span class="relation-short-label"><span class="relation-graph-direction">${(String(r.from)===String(person.id))===(p.x>50)?'':'← '}</span>${esc(short(r.label,12))}<span class="relation-graph-direction">${(String(r.from)===String(person.id))===(p.x>50)?' →':''}</span></span>${badge(r.status)}<span class="relation-mobile-route">${esc(people.get(String(r.from))?.name)} → ${esc(people.get(String(r.to))?.name)}</span></button>`).join('')}</div>`;}).join('')}</div>`;
        }});
      region.insertAdjacentHTML('beforeend','<section data-edge-basis hidden></section>');
    }
    function personPage(person) {
      root.innerHTML=`<article class="workspace-object-page analysis-person-page" data-reader-detail="characters"><a href="${esc(urlFor(section,null))}" class="quiet-link workspace-back" data-reader-back>← 人物索引</a><header class="workspace-object-heading"><span class="eyebrow">${esc(person.group)}</span><h2 tabindex="-1">${esc(person.name)}</h2><p>${person.status?badge(person.status):''}${esc(short(person.subtitle,160))}</p></header><nav class="workspace-object-tabs" aria-label="人物详情"><button data-reader-pane="relations" aria-pressed="${pane==='relations'}">关系</button><button data-reader-pane="experiences" aria-pressed="${pane==='experiences'}">经历</button></nav><section data-person-body></section>${details('人物分析与原文',data.personAnalysis(person))}</article>`;
      if(pane==='relations')relationshipPage(person);
      else B.mount(root.querySelector('[data-person-body]'),{label:'经历',items:data.personExperiences(person),pageSize:8,className:'workspace-event-path',text:e=>e.search,
        renderItem:e=>`<article class="workspace-event-stop"><div><span class="eyebrow">${esc(e.label)}</span><h3>${link('plot',e.id,e.title)}</h3><p>${esc(short(e.summary,130))}</p><div class="workspace-participants">${data.peopleForEvent(e).map(p=>link('characters',p.id,p.name)).join('')}</div></div></article>`});
    }
    function eventPage(event) {
      root.innerHTML=`<article class="workspace-object-page" data-reader-detail="plot"><a href="${esc(urlFor(section,null))}" class="quiet-link workspace-back" data-reader-back>← 剧情路径</a><header class="workspace-object-heading"><span class="eyebrow">${esc(event.label)}</span><h2 tabindex="-1">${esc(event.title)}</h2><div class="workspace-participants">${data.peopleForEvent(event).map(p=>link('characters',p.id,p.name)).join('')}</div></header><div class="workspace-event-body">${data.eventBody(event)}</div>${details('事件联系', '<div data-event-relations></div>')}${details('展开细节','<div data-event-beats></div>')}</article>`;
      const relations=data.eventEdges.filter(r=>String(r.from)===String(event.id)||String(r.to)===String(event.id));
      B.mount(root.querySelector('[data-event-relations]'),{label:'事件联系',items:relations,pageSize:6,renderItem:r=>`<article><div class="relationship-route">${link('plot',r.from,events.get(String(r.from))?.title || '未命名事件')}<span class="relationship-edge">${esc(r.label)}</span>${link('plot',r.to,events.get(String(r.to))?.title || '未命名事件')}</div>${r.body()}</article>`});
      B.mount(root.querySelector('[data-event-beats]'),{label:'事件细节',items:data.subEvents(event),pageSize:8,renderItem:s=>`<article><h3>${esc(s.title)}</h3>${s.body()}</article>`});
    }
    function draw(entry='preserve') {
      edgeChoices=[];
      root.classList.add('workspace-reader');
      const item=(section==='characters'?people:events).get(String(object));
      if(object && !item)root.innerHTML=`<section class="workspace-empty" role="alert"><p>此报告中找不到该${section==='characters'?'人物':'事件'}。</p><a class="quiet-link" href="${esc(urlFor(section,null))}" data-reader-back>返回索引</a></section>`;
      else if(item) {if(section==='characters')personPage(item);else eventPage(item);}
      else if(section==='characters')personIndex();else plotIndex();
      if(!object && data.extras){const extra=document.createElement('div');extra.className='workspace-reader-extras';extra.innerHTML=data.extras();root.append(extra);data.bindExtras?.(extra);}
      if(entry==='restore' || (entry==='top' && object)) {
        const target=object?root.querySelector('h2[tabindex]'):Array.from(root.querySelectorAll('[data-reader-open]')).find(n=>n.dataset.readerOpen===state().selected);
        target?.focus({preventScroll:true});
        if(!object)target?.scrollIntoView({block:'center',behavior:'instant'});
      }
      if(entry==='top')window.scrollTo({top:0,behavior:'instant'});
    }
    root.addEventListener('toggle',event=>{
      if(event.target.matches('[data-reader-time-note]'))timeNoteOpen=event.target.open;
    },true);
    root.addEventListener('click',event=>{
      const edge=event.target.closest('[data-reader-edges]');
      if(edge){const chosen=edge.dataset.readerEdges.split(',').map(i=>edgeChoices[Number(i)]).filter(Boolean),basis=root.querySelector('[data-edge-basis]');
        if(basis){const objects=section==='characters'?people:events;basis.innerHTML=`<button class="quiet-link" type="button" data-close-basis>收起依据</button><div data-basis-items class="${chosen.length<=6?'is-compact':''}"></div>`;B.mount(basis.querySelector('[data-basis-items]'),{label:'联系依据',items:chosen,pageSize:6,renderItem:r=>`<article><h3>${esc(objects.get(String(r.from))?.name || objects.get(String(r.from))?.title)} → ${esc(r.label)} → ${esc(objects.get(String(r.to))?.name || objects.get(String(r.to))?.title)}</h3>${r.status?'':badge('unknown')}${r.body()}</article>`});basis.hidden=false;basis.tabIndex=-1;basis.focus();basis.scrollIntoView({block:'nearest'});basis._opener=edge;}return;}
      if(event.target.closest('[data-close-basis]')){const basis=root.querySelector('[data-edge-basis]');basis.hidden=true;basis._opener?.focus();return;}
      const insight=event.target.closest('[data-report-phrase]');if(insight){const [id,index]=insight.dataset.reportPhrase.split('~');data.openInsight?.(id,index);return;}
      const open=event.target.closest('[data-reader-open]');
      if(open && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey){event.preventDefault();navigate(open.dataset.readerSection,open.dataset.readerOpen);return;}
      if(event.target.closest('[data-reader-back]')){event.preventDefault();navigate(section,null,'relations',true);return;}
      const tab=event.target.closest('[data-reader-pane]');if(tab){pane=tab.dataset.readerPane;sync(true);draw();root.querySelector(`[data-reader-pane="${pane}"]`).focus();return;}
      const map=event.target.closest('[data-reader-map]');if(map){state().map=map.dataset.readerMap==='index'?'index':'total';sync(true);draw();root.querySelector(`[data-reader-map="${state().map}"]`).focus();return;}
      const order=event.target.closest('[data-reader-order]');if(order){state().order=order.dataset.readerOrder;
        const matches=orderEvents().filter(e=>(!state().query || e.search.toLocaleLowerCase().includes(state().query.trim().toLocaleLowerCase())) && (!state().filters.chapter || e.chapters.includes(Number(state().filters.chapter))));
        const index=matches.findIndex(e=>e.id===state().selected);if(index>=0)state().page=Math.floor(index/8)+1;
        sync(false);draw();root.querySelector(`[data-reader-order="${state().order}"]`).focus();}
    });
    root.addEventListener('keydown',event=>{
      if(event.target.matches('g[data-reader-edges]') && ['Enter',' '].includes(event.key)){event.preventDefault();event.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));return;}
      if(object || !event.target.matches('[data-reader-open]') || !['ArrowDown','ArrowUp','ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
      const links=Array.from(root.querySelectorAll('[data-reader-open]')),i=links.indexOf(event.target);
      const next=event.key==='Home'?0:event.key==='End'?links.length-1:(i+(['ArrowLeft','ArrowUp'].includes(event.key)?-1:1)+links.length)%links.length;
      event.preventDefault();state().selected=links[next].dataset.readerOpen;sync(false);links[next].focus();
    });
    root.addEventListener('focusin',event=>{if(!object && section==='plot' && event.target.matches('[data-reader-open]')){state().selected=event.target.dataset.readerOpen;sync(false);updatePlotFocus();}});
    const returning=history.state?.xumaiReaderReturn;
    sync(false);draw(!object && returning?.key===key && returning.section===section?'restore':'top');
    function revealTimeNote(){
      const note=root.querySelector('[data-reader-time-note]');
      if(note){note.open=true;note.querySelector('summary').focus({preventScroll:true});note.scrollIntoView({block:'nearest',behavior:'instant'});}
    }
    if(legacyTime)revealTimeNote();
    return {select(next){if(next==='time')timeNoteOpen=true;navigate(next==='characters'?'characters':'plot');if(next==='time')revealTimeNote();}};
  }
  window.XumaiWorkspaceReader=Object.freeze({mountModel,mountRule,personSlots,plotSlots,graphLayout,graphRoute});
})();
