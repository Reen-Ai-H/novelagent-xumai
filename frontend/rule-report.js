/* Rule reports organize source observations, not inferred psychology. The
 * source-bound evidence renderer remains owned by app.js. */
(() => {
  "use strict";
  const B = window.XumaiReportBrowser;
  const esc = B.esc;
  const list = value => Array.isArray(value) ? value : [];
  const short = (value, limit = 140) => { const text = String(value || ""); return text.length > limit ? `${text.slice(0, limit)}…` : text; };
  const detail = (label, body, cls = "") => `<details class="analysis-details ${cls}"><summary>${esc(label)}</summary><div class="analysis-details-body">${body}</div></details>`;
  const lazyDetail = (label, key, intro = "") => `<details class="analysis-details" data-browser-lazy="${esc(key)}"><summary>${esc(label)}</summary><div class="analysis-details-body">${intro}<div data-browser-slot></div></div></details>`;
  const importanceLabels = {main:"主要人物", supporting:"配角", incidental:"偶现人物", unknown:"待确认"};
  function mount(root, report, raw, options) {
    if (!root) return;
    const progress = options.progress ?? 100;
    const visible = item => (item.normalizedStart ?? 0) <= progress + .0001 && (!options.chapterId || item.chapterIds.includes(options.chapterId));
    const rawCharacters = new Map(list(raw.characters?.characters).map(item => [item.item_id, item]));
    const rank = {main:0, supporting:1, incidental:2, unknown:3};
    const characters = report.characters.characters.filter(visible).sort((a,b) => (rank[rawCharacters.get(a.id)?.importance] ?? 3) - (rank[rawCharacters.get(b.id)?.importance] ?? 3));
    const events = report.plot.events.filter(visible);
    const index = new Map([...report.characters.characters, ...report.characters.states, ...report.plot.events, ...report.plot.plotlines].map(item => [item.id, item]));
    const chapters = item => item.chapterIds.map(id => report.chapters.find(c => c.id === id)?.number).filter(n => n != null).map(n => `第 ${n} 章`).join("、") || "章节待定位";
    const readable = value => report.chapters.reduce((text, c) => text.split(c.id).join(`第 ${c.number} 章`), String(value || ""));
    const evidence = item => options.evidence(item, report);
    const itemLabel = id => { const item = index.get(id); return item?.name || item?.action || item?.title || (item?.characterId ? `${index.get(item.characterId)?.name || '人物'}的状态` : "未命名记录"); };
    const configs = new Map();
    const G = window.XumaiVisualReading;
    const graph = G?.preference() === 'map';
    const toggle = () => G?.switcher(root,()=>mount(root,report,raw,options));
    const bind = node => B.lazy(node, configs);
    const mountList = (selector, config) => B.mount(root.querySelector(selector), {...config, afterRender:bind});
    const relationConfig = (items, label = "关系") => ({label, items, pageSize:8,
      text: r => `${itemLabel(r.start.id)} ${itemLabel(r.end.id)} ${r.explanation} ${r.conclusion}`,
      renderItem:r => `<article class="depth-relation-card"><div class="depth-relation-route"><strong>${esc(short(itemLabel(r.start.id), 70))}</strong><span>${esc(options.relationLabel(r.relationType))}</span><strong>${esc(short(itemLabel(r.end.id), 70))}</strong></div><p>${esc(r.explanation || r.conclusion)}</p>${detail("原文依据", evidence(r))}</article>`});
    const eventConfig = (items, label = "事件片段") => ({label, items, pageSize:12, className:"depth-event-list",
      text:e => `${e.action} ${e.conclusion} ${e.consequence} ${e.characterIds.map(itemLabel).join(' ')}`,
      renderItem:e => `<article class="depth-track-item" data-reading-event="${esc(e.id)}"><div><strong>${esc(short(e.action))}</strong><span>${esc(chapters(e))}</span></div>${detail("经过与原文依据", `<p>${esc(e.action)}</p><p>${esc(e.conclusion)}</p><p>${esc(e.consequence)}</p>${options.meta(e, report)}${e.uncertainty.length ? `<p>${esc(e.uncertainty.join('；'))}</p>` : ''}${evidence(e)}`)}</article>`});
    function personCard(person) {
      const original = rawCharacters.get(person.id) || {};
      const importance = importanceLabels[original.importance] || "待确认";
      const related = report.characters.relations.filter(r => visible(r) && (r.start.id === person.id || r.end.id === person.id));
      const partnerIds = [...new Set(related.map(r => r.start.id === person.id ? r.end.id : r.start.id))];
      const states = report.characters.states.filter(s => s.characterId === person.id && visible(s));
      configs.set(`relations-${person.id}`, relationConfig(related, `${person.name}的关系`));
      configs.set(`states-${person.id}`, {label:"人物记录", items:states, pageSize:8, renderItem:s => `<article class="depth-track-item"><strong>${esc(chapters(s))}</strong><p>${esc(readable(s.conclusion))}</p>${evidence(s)}${detail("旧报告字段（未验证心理判断）", `<dl class="depth-fact-list">${[['目标',s.goal],['信念',s.belief],['情绪',s.emotion],['行动',s.agency],['变化',s.change]].map(([label,text]) => `<div><dt>${label}</dt><dd>${esc(readable(text))}</dd></div>`).join('')}</dl>`)}</article>`});
      const summary = readable(original.summary || person.conclusion);
      const basis = original.importance_reason ? `<p>分组依据：${esc(readable(original.importance_reason))}${original.mention_count == null ? '' : ` · 提及 ${original.mention_count} 次`}</p>` : '';
      return `<article class="depth-entity-card" data-reading-person="${esc(person.id)}"><header><span class="depth-card-label">${importance} · ${esc(chapters(person))}</span><h3>${esc(person.name)}</h3>${person.aliases.length ? `<small>别名：${esc(person.aliases.join('、'))}</small>` : ''}</header><div class="analysis-card-summary"><span>原文线索</span><p>${esc(short(summary))}</p>${partnerIds.length ? `<span>相关人物 · ${partnerIds.length}</span><p>${esc(short(partnerIds.map(itemLabel).join('、'), 100))}</p>` : '<span>关系待核对</span>'}</div>${detail("展开分析与原文依据", `<p>${esc(summary)}</p><p>${esc(readable(person.role))}</p>${basis}${evidence(person)}${detail("旧报告字段（未验证心理判断）", `<p>以下为保存时的规则字段，不代表对人物心理的理解。</p><dl class="depth-fact-list"><div><dt>动机</dt><dd>${esc(readable(person.motivation))}</dd></div><div><dt>内在冲突</dt><dd>${esc(readable(person.innerConflict))}</dd></div><div><dt>人物弧</dt><dd>${esc(readable(person.arcSummary))}</dd></div></dl>`)}`)}${lazyDetail(`相关人物与关系 · ${related.length}`, `relations-${person.id}`)}${lazyDetail(`沿文记录 · ${states.length}`, `states-${person.id}`)}</article>`;
    }
    if (options.view === "characters") {
      const counts = Object.fromEntries(Object.keys(importanceLabels).map(key => [key, characters.filter(c => (rawCharacters.get(c.id)?.importance || 'unknown') === key).length]));
      const candidates = list(raw.characters?.identity_candidates);
      configs.set('identity-candidates',{label:'识别候选',items:candidates,renderItem:c=>`<article class="depth-track-item"><strong>${esc(c.name)}</strong><p>${esc(c.importance_reason)}</p><small>${c.mention_count} 次提及 · ${c.paragraph_count} 段；候选不等于正式人物</small></article>`});
      root.innerHTML = `<header class="report-reading-heading"><h2>人物与关系</h2></header><div data-rule-people></div>${lazyDetail(`全部人物关系 · ${report.characters.relations.filter(visible).length}`, 'all-people-relations')}`;
      configs.set('all-people-relations', relationConfig(report.characters.relations.filter(visible), '人物关系'));
      const config={label:"人物", items:characters, pageSize:8, className:"depth-view-grid depth-entity-grid", text:c => `${c.name} ${c.aliases.join(' ')} ${c.conclusion} ${c.role}`, filters:[{name:"importance",label:"人物分组", options:[{value:"",label:"全部记录"},...Object.entries(importanceLabels).map(([value,label]) => ({value,label:`${label} · ${counts[value]}`}))],match:(item,value) => (rawCharacters.get(item.id)?.importance || 'unknown') === value}], renderItem:personCard};
      if (graph) {
        let controller;
        controller=G.mount(root.querySelector('[data-rule-people]'),{...config,type:'people',title:p=>p.name,meta:p=>importanceLabels[rawCharacters.get(p.id)?.importance] || '待确认',bind,
          note:'原文关系线索，尚未作人物心理或关系定性。只显示选中人物的一跳。',
          neighbors:p=>report.characters.relations.filter(r=>visible(r) && (r.start.id===p.id || r.end.id===p.id)).map(r=>{
            const id=r.start.id===p.id?r.end.id:r.start.id;
            return {id:r.id,personId:id,title:itemLabel(id),label:options.relationLabel(r.relationType),edgeLabel:options.relationLabel(r.relationType),kind:'clue'};
          }),
          onNeighbor:n=>controller.reveal(n.personId),
          detail:p=>`<article><span class="eyebrow">原文线索 · ${esc(chapters(p))}</span><h3>${esc(p.name)}</h3><p>${esc(short(readable(rawCharacters.get(p.id)?.summary || p.conclusion),140))}</p>${detail('人物记录与依据',personCard(p))}</article>`});
      } else mountList('[data-rule-people]',config);
      bind(root);
      if (candidates.length) {
        const auxiliary = document.createElement('section');
        auxiliary.innerHTML = lazyDetail(`识别候选与分组依据 · ${candidates.length}`, 'identity-candidates');
        root.appendChild(auxiliary); bind(auxiliary);
      }
      toggle();
      return;
    }
    // Legacy fallback is explicitly mechanical grouping. Every event appears
    // once; no artificial plot title, motivation or causal claim is invented.
    const byEvent = new Map(report.plot.events.map(e => [e.id,e]));
    const segments = list(raw.plot?.reading_segments).map((s,i) => ({
      id:s.item_id || s.segment_id || `segment-${i}`, title:s.title || `阅读段落 ${i+1}`,
      summary:s.summary || s.conclusion || '', chapterIds:s.chapter_id ? [s.chapter_id] : list(s.chapter_ids),
      normalizedStart:s.normalized_start ?? 0, evidenceIds:list(s.evidence_ids),
      paragraphStart:s.paragraph_start, paragraphEnd:s.paragraph_end, characterIds:list(s.character_ids), uncertainty:list(s.uncertainty),
      events:list(s.event_ids).map(id => byEvent.get(id)).filter(Boolean),
    }));
    const covered = new Set(segments.flatMap(s => s.events.map(e => e.id)));
    const remaining = report.plot.events.filter(e => !covered.has(e.id));
    let current = null;
    for (const event of remaining) {
      const chapterKey = event.chapterIds.join('|');
      if (!current || current.chapterKey !== chapterKey || current.events.length === 12) {
        current = {id:`legacy-${segments.length}`, chapterKey, chapterIds:event.chapterIds, normalizedStart:event.normalizedStart,
          title:`${chapters(event)} · 原文片段组 ${segments.length+1}`, summary:'', events:[], evidenceIds:[], characterIds:[], uncertainty:[], legacy:true};
        segments.push(current);
      }
      current.events.push(event);
      if (!current.summary) current.summary = event.action;
    }
    const readingSegments = segments.filter(visible).sort((a,b) => (a.normalizedStart ?? 0) - (b.normalizedStart ?? 0));
    const overview = raw.plot?.overview;
    const relations = report.plot.relations.filter(visible);
    root.innerHTML = `<header class="report-reading-heading"><h2>沿着正文看故事</h2><p>${readingSegments.length} 个段落 · ${events.length} 条原文记录</p></header><p class="analysis-scope-note">${overview?.summary ? esc(short(overview.summary, 160)) : list(raw.plot?.reading_segments).length ? '按正文段落整理；分段与先后顺序不代表语义因果。' : '旧报告按章节与正文顺序，每 12 条记录归为一组；这不是模型提炼的大事件。'}</p><div data-rule-segments></div>${detail(`章节事件片段 · ${events.length}`, '<div data-rule-events></div>', 'depth-subsection depth-events-section')}${lazyDetail(`事件关系 · ${relations.length}`, 'all-event-relations')}${lazyDetail(`原报告剧情线 · ${report.plot.plotlines.length}`, 'plotlines')}`;
    configs.set('all-event-relations',relationConfig(relations,'事件关系'));
    configs.set('plotlines',{label:'剧情线',items:report.plot.plotlines.filter(visible),renderItem:line => `<article class="depth-entity-card"><h3>${esc(line.title)}</h3><p>${esc(line.conclusion)}</p>${detail('旧报告字段与原文依据', `<p>${esc(line.centralQuestion)}</p><p>${esc(line.stakes)}</p><p>${esc(line.resolution)}</p>${evidence(line)}`)}</article>`});
    const segmentConfig={label:'阅读段落',items:readingSegments,pageSize:6, className:'reading-segments',
      text:s => `${s.title} ${s.summary} ${s.events.map(e => `${e.action} ${e.conclusion}`).join(' ')}`,
      renderItem:(s,i) => {
        configs.set(`segment-${s.id}`, eventConfig(s.events.filter(visible), '段落内记录'));
        return `<article class="reading-segment" data-reading-segment="${esc(s.id)}"><div class="reading-segment-number" aria-hidden="true">${String(i+1).padStart(2,'0')}</div><div><span class="eyebrow">${esc(chapters(s))} · ${s.paragraphStart ? `第 ${esc(s.paragraphStart)}–${esc(s.paragraphEnd)} 段 · ` : ''}${s.events.length} 条记录</span><h3>${esc(s.title)}</h3><p>${esc(short(s.summary,180))}</p>${lazyDetail(`展开原文细节 · ${s.events.length}`, `segment-${s.id}`, `<p>${esc(s.summary)}</p>${s.characterIds.length ? `<p>出场人物：${esc(s.characterIds.map(itemLabel).join('、'))}</p>` : ''}${s.uncertainty.length ? `<p class="analysis-scope-note">${esc(s.uncertainty.join('；'))}</p>` : ''}`)}${s.evidenceIds.length ? detail('段落依据', evidence(s)) : ''}</div></article>`;
      }};
    if (graph) {
      const segmentByEvent=new Map(readingSegments.flatMap(s=>s.events.map(e=>[e.id,s.id])));
      const edges=relations.map(r=>({from:segmentByEvent.get(r.start.id),to:segmentByEvent.get(r.end.id),kind:'clue',label:options.relationLabel(r.relationType)})).filter(r=>r.from && r.to && r.from!==r.to);
      G.mount(root.querySelector('[data-rule-segments]'),{...segmentConfig,title:s=>s.title,meta:chapters,bind,edges,
        note:'按正文段落阅读；连线仅为已有规则线索，不推断语义因果。',
        detail:s=>segmentConfig.renderItem(s,readingSegments.indexOf(s))});
    } else mountList('[data-rule-segments]',segmentConfig);
    mountList('[data-rule-events]', eventConfig(events));
    bind(root);
    toggle();
  }
  window.XumaiRuleReport = Object.freeze({mount});
})();
