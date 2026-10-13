/* Source-only diagrams. HTML buttons carry interaction; SVG carries real
 * typed edges. Pagination limits DOM, never the search/relationship data. */
(() => {
  'use strict';
  const B = window.XumaiReportBrowser, esc = B.esc;
  let serial = 0;
  const short = (value, length=26) => Array.from(String(value || '')).slice(0,length).join('') + (Array.from(String(value || '')).length>length?'…':'');
  function preference() { try { return sessionStorage.getItem('xumai-reading-view') === 'list' ? 'list' : 'map'; } catch { return 'map'; } }
  function switcher(root, redraw) {
    const bar=document.createElement('div');bar.className='visual-view-toggle';bar.setAttribute('aria-label','阅读方式');
    bar.innerHTML=`<button type="button" data-reading-mode="map" aria-pressed="${preference()==='map'}">脉络图</button><button type="button" data-reading-mode="list" aria-pressed="${preference()==='list'}">完整列表</button>`;
    root.prepend(bar);
    bar.addEventListener('click',event=>{const button=event.target.closest('[data-reading-mode]');if(!button)return;
      try { sessionStorage.setItem('xumai-reading-view',button.dataset.readingMode); } catch { return; }
      redraw();root.querySelector(`[data-reading-mode="${button.dataset.readingMode}"]`)?.focus({preventScroll:true});
    });
  }
  function mount(root, config) {
    root.classList.add('visual-reader');
    const uid=`visual${++serial}`, items=config.items, byId=new Map(items.map(item=>[String(item.id),item]));
    const edges=(config.edges || []).filter(e=>byId.has(String(e.from)) && byId.has(String(e.to)));
    const title=item=>config.title(item), meta=item=>config.meta?.(item) || '';
    let selected=String(config.selected || items[0]?.id || ''), visible=[], neighborPage=1;
    let results, detail, browser;
    const state=config.state || {query:'',page:1,filters:{}};
    function summary() {
      const item=byId.get(selected);
      detail.innerHTML=item ? config.detail(item) : '<p>没有符合条件的记录。可重置筛选继续查看。</p>';
      detail.dataset.selectedId=item?.id || '';config.bind?.(detail);config.onSelect?.(item);
      if(config.type!=='people' && item) {
        const related=edges.filter(e=>String(e.from)===selected || String(e.to)===selected);
        if(related.length) {
          const block=document.createElement('details');block.className='visual-connections analysis-details';
          block.innerHTML=`<summary>有据联系 · ${related.length}</summary><div data-connections></div>`;detail.append(block);
          block.addEventListener('toggle',()=>{if(!block.open || block.dataset.loaded)return;block.dataset.loaded='true';
            B.mount(block.querySelector('[data-connections]'),{label:'事件联系',items:related,pageSize:6,
              text:e=>`${title(byId.get(String(e.from)))} ${title(byId.get(String(e.to)))} ${e.label}`,
              renderItem:e=>{const id=String(e.from)===selected?String(e.to):String(e.from);return `<p class="visual-edge-reference"><span>${esc(title(byId.get(String(e.from))))} → ${esc(e.label)} → ${esc(title(byId.get(String(e.to))))}</span><button type="button" data-visual-jump="${esc(id)}">定位节点</button></p>`;}});
          });
        }
      }
    }
    function button(item,x,y,w,extra=false) {
      const id=String(item.id), label=extra?item.title:title(item), sub=extra?item.label:meta(item);
      return `<button type="button" class="visual-node ${id===selected&&!extra?'is-selected':''} ${extra?'is-neighbor':''}" style="left:${x}px;top:${y}px;width:${w}px" ${extra?`data-visual-neighbor="${esc(id)}"`:`data-visual-node="${esc(id)}"`} aria-label="${esc(label)}${sub?'，'+esc(sub):''}" ${extra?'':`aria-pressed="${id===selected}" tabindex="${id===selected?'0':'-1'}"`} title="${esc(label)}"><small>${esc(short(sub,24))}</small><strong>${esc(short(label))}</strong></button>`;
    }
    function svg(lines,w,h) {
      return `<svg class="visual-lines" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-hidden="true"><defs><marker id="${uid}Arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" /></marker></defs>${lines.join('')}</svg>`;
    }
    function line(from,to,kind,label,path,x,y) {
      return `<g class="visual-edge is-${esc(kind)}" data-edge-from="${esc(from)}" data-edge-to="${esc(to)}" data-edge-kind="${esc(kind)}"><path d="${path}" marker-end="url(#${uid}Arrow)"/><text x="${x}" y="${y}">${esc(label)}</text></g>`;
    }
    function board() {
      if(!results || !root.isConnected)return;
      const width=Math.max(250,Math.floor(results.clientWidth)), lines=[];
      if(config.type==='people') {
        const person=byId.get(selected);
        const neighbors=person?(config.neighbors?.(person)||[]):[];
        const size=3,pages=Math.max(1,Math.ceil(neighbors.length/size));neighborPage=Math.min(pages,neighborPage);
        const slice=neighbors.slice((neighborPage-1)*size,neighborPage*size), nw=Math.min(230,(width-76)/2);
        const rowHeight=slice.some(n=>n.actors?.length)?126:82;
        const height=Math.max(148,slice.length*rowHeight+22), cy=(height-62)/2, rx=width-nw-6;
        const nodes=person?[button(person,6,cy,nw)]:[];
        slice.forEach((n,i)=>{const y=12+i*rowHeight;nodes.push(button(n,rx,y,nw,true));
          if(n.actors?.length)nodes.push(`<div class="visual-coactors" style="left:${rx}px;top:${y+65}px;width:${nw}px" aria-label="${esc(n.title)}的其他参与者">${n.actors.slice(0,2).map(a=>`<button type="button" data-visual-actor="${esc(a.id)}" title="${esc(a.name)}">${esc(short(a.name,7))}</button>`).join('')}${n.actors.length>2?`<button type="button" data-visual-roster="${esc(n.id)}" aria-label="查看全部 ${n.actors.length} 位其他参与者">+${n.actors.length-2} 人</button>`:''}</div>`);
          lines.push(line(selected,n.id,n.kind || 'shared',n.edgeLabel || '共同经历',`M${nw+6} ${cy+31}C${width/2} ${cy+31} ${width/2} ${y+31} ${rx} ${y+31}`,width/2,y+24));
        });
        results.innerHTML=`<div class="visual-person-picks" role="group" aria-label="选择人物">${visible.map(item=>`<button type="button" data-visual-pick="${esc(item.id)}" aria-pressed="${String(item.id)===selected}">${esc(short(title(item),16))}</button>`).join('')}</div><p class="visual-caption">${esc(config.note || '')}</p><div class="visual-canvas" style="height:${height}px">${svg(lines,width,height)}${nodes.join('')}</div>${!neighbors.length&&person?'<p class="visual-empty">本报告没有该人物的结构化联系；未推测关系。</p>':''}<div class="visual-neighbor-pages" ${pages===1?'hidden':''}><button type="button" data-neighbor-page="${neighborPage-1}" ${neighborPage===1?'disabled':''}>上组联系</button><span role="status">${neighborPage} / ${pages} · 共 ${neighbors.length} 项</span><button type="button" data-neighbor-page="${neighborPage+1}" ${neighborPage===pages?'disabled':''}>下组联系</button></div>`;
      } else {
        const columns=width>650?3:2, gap=48, nw=(width-gap*(columns-1)-12)/columns;
        const positions=new Map(), height=Math.max(140,Math.ceil(visible.length/columns)*126+24),nodes=[];
        visible.forEach((item,i)=>{const row=Math.floor(i/columns),col=row%2?columns-1-i%columns:i%columns;
          const x=6+col*(nw+gap),y=18+row*126;positions.set(String(item.id),{x,y});nodes.push(button(item,x,y,nw));
        });
        for(let i=1;i<visible.length;i++) {
          const a=positions.get(String(visible[i-1].id)),b=positions.get(String(visible[i].id));
          const from={x:a.x+nw/2,y:a.y+62},to={x:b.x+nw/2,y:b.y};
          const path=a.y===b.y?`M${a.x+(a.x<b.x?nw:0)} ${a.y+31}L${b.x+(a.x<b.x?0:nw)} ${b.y+31}`:`M${from.x} ${from.y}C${from.x} ${from.y+30} ${to.x} ${to.y-30} ${to.x} ${to.y}`;
          lines.push(line(visible[i-1].id,visible[i].id,'order','',path,0,0));
        }
        edges.filter(e=>positions.has(String(e.from)) && positions.has(String(e.to))).forEach((e,i)=>{
          const a=positions.get(String(e.from)),b=positions.get(String(e.to));
          const sx=a.x+nw*.7,sy=a.y+62,tx=b.x+nw*.7,ty=b.y+62, lane=Math.min(height-6,Math.max(sy,ty)+24+(i%3)*10);
          lines.push(line(e.from,e.to,e.kind,e.label,`M${sx} ${sy}C${sx} ${lane} ${tx} ${lane} ${tx} ${ty}`,Math.max(34,Math.min(width-42,(sx+tx)/2)),lane));
        });
        results.innerHTML=`<p class="visual-caption">${esc(config.note || '虚线为阅读顺序；彩色连线来自报告，先后不表示因果。')}</p><div class="visual-canvas" style="height:${height}px">${svg(lines,width,height)}${nodes.join('')}</div>`;
      }
      const target=results.querySelector('.visual-node:not(.is-neighbor)');
      if(!results.querySelector('.visual-node[tabindex="0"]'))target?.setAttribute('tabindex','0');
    }
    browser=B.mount(root,{...config,pageSize:6,className:'visual-map-items',state,
      renderItem:()=>'',afterRender:(node,pageItems)=>{results=node;visible=pageItems;
        if(!visible.some(item=>String(item.id)===selected)){selected=String(visible[0]?.id || '');neighborPage=1;}
        board();if(detail)summary();
      }});
    detail=document.createElement('section');detail.className='visual-selected';detail.tabIndex=-1;detail.setAttribute('aria-label','选中节点摘要');root.append(detail);summary();
    const select=(id,focus=false)=>{selected=String(id);neighborPage=1;board();summary();
      if(focus)results.querySelector(`[data-visual-node="${CSS.escape(selected)}"]`)?.focus({preventScroll:true});};
    const reveal=id=>{
      const index=items.findIndex(item=>String(item.id)===String(id));if(index<0)return;
      selected=String(id);neighborPage=1;state.query='';state.filters={};state.page=Math.floor(index/6)+1;
      root.querySelector('input[type=search]').value='';root.querySelectorAll(':scope > .report-browser-tools [data-browser-filter]').forEach(n=>{n.value='';});browser.draw();
      results.focus({preventScroll:true});results.scrollIntoView({block:'start',behavior:'instant'});
    };
    root.addEventListener('click',event=>{
      const pick=event.target.closest('[data-visual-node],[data-visual-pick]');
      if(pick){event.stopPropagation();select(pick.dataset.visualNode || pick.dataset.visualPick,true);return;}
      const neighbor=event.target.closest('[data-visual-neighbor]');
      if(neighbor){event.stopPropagation();const n=(config.neighbors?.(byId.get(selected))||[]).find(n=>String(n.id)===neighbor.dataset.visualNeighbor);if(n)config.onNeighbor?.(n);return;}
      const actor=event.target.closest('[data-visual-actor]');
      if(actor){event.stopPropagation();reveal(actor.dataset.visualActor);return;}
      const roster=event.target.closest('[data-visual-roster]');
      if(roster){event.stopPropagation();const n=(config.neighbors?.(byId.get(selected))||[]).find(n=>String(n.id)===roster.dataset.visualRoster);if(n)config.onRoster?.(n);return;}
      const paging=event.target.closest('[data-neighbor-page]');
      if(paging){neighborPage=Number(paging.dataset.neighborPage);board();results.querySelector('[data-visual-node]')?.focus({preventScroll:true});return;}
      const jump=event.target.closest('[data-visual-jump]');
      if(jump){event.stopPropagation();reveal(jump.dataset.visualJump);}
    });
    root.addEventListener('keydown',event=>{
      const node=event.target.closest('[data-visual-node]');if(!node)return;
      const keys=['ArrowRight','ArrowDown','ArrowLeft','ArrowUp','Home','End'];if(!keys.includes(event.key))return;
      event.preventDefault();const i=visible.findIndex(n=>String(n.id)===node.dataset.visualNode);
      const next=event.key==='Home'?0:event.key==='End'?visible.length-1:(i+(['ArrowLeft','ArrowUp'].includes(event.key)?-1:1)+visible.length)%visible.length;
      if(visible[next])select(visible[next].id,true);
    });
    const observer=new ResizeObserver(()=>{if(!root.isConnected){observer.disconnect();return;}board();});observer.observe(results);
    return {select,reveal,redraw:()=>browser.draw()};
  }
  window.XumaiVisualReading=Object.freeze({mount,switcher,preference,short});
})();
