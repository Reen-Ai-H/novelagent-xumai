/* A data-only viewer for imported, source-bound literary analysis.
   Big-arc nodes carry sub_events (small plot beats inside the arc); character
   images are short phrases that open a modal showing their textual basis. */
(() => {
  "use strict";
  const labels = { fact: "正文可证", reported: "人物说法", inferred: "分析推断", unknown: "尚未确定" };
  const kinds = { causes: "促成", enables: "提供条件", reveals: "揭示", foreshadow_payoff: "线索回收", follows: "仅为先后" };
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const compact = value => { const text = String(value || ''); return text.length > 160 ? `${text.slice(0,160)}…` : text; };
  let closeActiveModal = null;

  function openModal({ eyebrow, title, body }) {
    closeActiveModal?.();
    const opener = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    const backdrop = document.createElement("div");
    backdrop.className = "analysis-modal-backdrop";
    backdrop.innerHTML = `<div class="analysis-modal" role="dialog" aria-modal="true" aria-label="${esc(title)}">
      <header class="analysis-modal-head">
        <div><p class="eyebrow">${esc(eyebrow)}</p><h2>${esc(title)}</h2></div>
        <button type="button" class="analysis-modal-close" aria-label="关闭">×</button>
      </header>
      <div class="analysis-modal-body">${body}</div>
    </div>`;
    const close = () => {
      if (closeActiveModal === close) closeActiveModal = null;
      document.removeEventListener("keydown", onKey, true);
      backdrop.remove();
      document.body.style.overflow = previousOverflow;
      if (opener && typeof opener.focus === "function") opener.focus();
    };
    function onKey(event) {
      // A source-evidence dialog may be opened above this character/plot modal.
      if (document.querySelector("dialog[open]")) return;
      if (event.key === "Escape") { event.preventDefault(); close(); }
      if (event.key === "Tab") {
        const focusable = Array.from(backdrop.querySelectorAll('button:not([disabled]), a[href], summary, [tabindex="0"]'))
          .filter(node => node.getClientRects().length);
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && (document.activeElement === first || !backdrop.contains(document.activeElement))) {
          event.preventDefault(); last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault(); first?.focus();
        }
      }
    }
    backdrop.querySelector(".analysis-modal-close").addEventListener("click", close);
    closeActiveModal = close;
    document.addEventListener("keydown", onKey, true);
    document.body.style.overflow = "hidden";
    document.body.appendChild(backdrop);
    backdrop.querySelector(".analysis-modal-close").focus();
  }

  function render(report) {
    const source = report && typeof report === "object" ? report : {};
    const questions = Array.isArray(source.open_questions) ? source.open_questions : [];
    return `<section class="analysis-report"><div class="analysis-view"></div><details class="analysis-questions analysis-details" id="analysisQuestions"><summary>矛盾与疑问 · ${questions.length + (source.contradictions?.length || 0)}</summary><div class="analysis-details-body" data-model-questions></div></details></section>`;
  }
  function mount(container, report, evidenceRefs, evidenceRenderer, options = {}) {
    const root = container.querySelector(".analysis-report");
    if (!root || !report) return;
    // Older imported reports may omit optional arrays. Normalize only the
    // viewer input so a partial result remains readable without inventing
    // events, characters, or evidence links.
    report = {
      ...report,
      events: Array.isArray(report.events) ? report.events : [],
      characters: Array.isArray(report.characters) ? report.characters : [],
      relations: Array.isArray(report.relations) ? report.relations : [],
      story_order: Array.isArray(report.story_order) ? report.story_order : [],
      open_questions: Array.isArray(report.open_questions) ? report.open_questions : [],
      contradictions: Array.isArray(report.contradictions) ? report.contradictions : [],
      evidence: Array.isArray(report.evidence) ? report.evidence : [],
    };
    const byId = new Map(report.events.map(e => [e.id, e]));
    const people = new Map(report.characters.map(p => [p.id, p.name]));
    const refs = Array.isArray(evidenceRefs) ? evidenceRefs : [];
    const evidenceId = item => String(item?.id ?? item?.evidence_id ?? "");
    const reportEvidence = new Map(report.evidence.map(item => [evidenceId(item), item]).filter(([id]) => id));
    const staticEvidence = item => {
      const chapter = item?.chapter_number ?? item?.chapterNumber;
      const quote = String(item?.quote ?? item?.excerpt ?? "").replace(/\s+/g, " ").trim();
      const location = chapter === undefined || chapter === null || chapter === "" ? "章节待定位" : `第 ${esc(chapter)} 章`;
      return `<blockquote class="analysis-proof-evidence"><span>${location}</span>${quote ? ` · “${esc(quote)}”` : ""}<small>这条旧结果没有绑定当前正文回链</small></blockquote>`;
    };
    const evidence = ids => {
      const requested = Array.isArray(ids) ? ids.map(String).filter(Boolean) : [];
      const linked = refs.filter(item => requested.includes(evidenceId(item)));
      const linkedIds = new Set(linked.map(evidenceId));
      const rendered = typeof evidenceRenderer === "function"
        ? Array.from({ length: Math.ceil(linked.length / 6) }, (_, i) => evidenceRenderer(linked.slice(i * 6, i * 6 + 6))).join("")
        : linked.map(staticEvidence).join("");
      const unbound = requested.filter(id => !linkedIds.has(id)).map(id => staticEvidence(reportEvidence.get(id) || { id })).join("");
      return (rendered + unbound) || `<span class="analysis-proof-empty">暂未绑定来源证据，不能回到正文核对。</span>`;
    };
    const claim = c => {
      const item = c && typeof c === "object" ? c : {};
      const status = labels[item.status] ? item.status : "unknown";
      const ids = Array.isArray(item.evidence_ids) ? item.evidence_ids : [];
      const proof = ids.length
        ? `<details class="analysis-proof"><summary>查看原文依据 · ${ids.length}</summary>${evidence(ids)}</details>`
        : `<p class="analysis-proof-empty">暂未绑定原文依据</p>`;
      return `<span class="analysis-badge is-${esc(status)}">${labels[status]}</span><p>${esc(item.text || "暂无可确认分析。")} </p>${proof}`;
    };
    const hasAnalysis = value => report.schema_version !== "2" || value !== null;
    const analysisSection = (title, value) => hasAnalysis(value)
      ? `<section><h3>${title}</h3>${claim(value)}</section>` : "";

    const phraseChips = (person, mini) => (person.insights || []).map((insight, index) =>
      `<button type="button" class="analysis-phrase ${mini ? "is-mini" : ""}" data-report-phrase="${esc(person.id)}~${index}">${esc(insight.title)}</button>`).join("");

    function openPhrase(personId, index) {
      const person = report.characters.find(p => p.id === personId);
      const insight = person?.insights?.[Number(index)];
      if (!person || !insight) return;
      openModal({ eyebrow: `${person.name} · 形象速览`, title: insight.title, body: claim(insight) });
    }
    function openSubEvent(eventId, index) {
      const event = report.events.find(e => e.id === eventId);
      const item = event?.sub_events?.[Number(index)];
      if (!event || !item) return;
      const chapterLabel = event.chapter_end && event.chapter_end !== event.chapter_number
        ? `第 ${event.chapter_number}–${event.chapter_end} 章` : `第 ${event.chapter_number} 章`;
      openModal({ eyebrow: `${event.title} · 小事件（${chapterLabel}）`, title: item.title, body: claim(item) });
    }

    if (options.workspace && window.XumaiWorkspaceReader) {
      return window.XumaiWorkspaceReader.mountModel(root, report, {...options, evidence, claim, openModal});
    }
    // A directly embedded, source-bound person profile does not need the list
    // controller. Preserve that standalone use when only this viewer is loaded.
    window.XumaiReportBrowser?.mount(root.querySelector('[data-model-questions]'), {label:"矛盾与疑问",pageSize:6,
      items:[...report.contradictions.map(c=>({type:'contradiction',...c})),...report.open_questions.map(text=>({type:'question',text}))],
      renderItem:item=>item.type==='contradiction' ? `<article><h4>${esc(item.title)}</h4>${claim(item)}</article>` : `<p>${esc(item.text)}</p>`});
    let selected = report.events[0]?.id || null;
    let selectedPerson = null;
    let tab = options.section || "characters";
    let character = options.character || null;
    let returnPerson = character;
    let timeMode = "narrative";
    const view = root.querySelector(".analysis-view");
    const chapterLabel = e => e.chapter_end && e.chapter_end !== e.chapter_number ? `第 ${e.chapter_number}–${e.chapter_end} 章` : `第 ${e.chapter_number} 章`;
    const B = window.XumaiReportBrowser;
    const browsing = Object.fromEntries(["characters", "plot", "time"].map(key => [key, {query:"", page:1, filters:{}}]));
    const lazyConfigs = new Map();
    const lazyDetails = (label, key) => `<details class="analysis-details" data-browser-lazy="${esc(key)}"><summary>${esc(label)}</summary><div class="analysis-details-body" data-browser-slot></div></details>`;
    const importance = person => {
      // model.1 only has role, not importance. Accept an explicit leading
      // classification (or a standalone label), never an identity substring.
      const role = String(person.role || "").trim();
      if (/^(?:主角|主要人物|主人公)(?:\s*[：:]|$)/u.test(role)) return "主要人物";
      if (/^(?:配角|次要人物|实质配角)(?:\s*[：:]|$)/u.test(role)) return "配角";
      return "未分级";
    };
    const personText = p => `${p.name} ${(p.aliases || []).join(' ')} ${p.identity?.text || ''} ${p.portrait?.text || ''} ${p.change?.text || ''}`;
    const peopleForList = () => {
      const order = {"主要人物":0,"配角":1,"未分级":2};
      return [...report.characters].sort((a,b) => order[importance(a)] - order[importance(b)]);
    };
    const chapterNumbers = [...new Set(report.events.flatMap(e => Array.from({length:Math.max(1,(e.chapter_end || e.chapter_number)-e.chapter_number+1)},(_,i)=>e.chapter_number+i)).filter(Number.isFinite))].sort((a,b)=>a-b);
    const chapterFilter = {name:"chapter",label:"章节",options:[{value:"",label:"全部章节"},...chapterNumbers.map(n=>({value:String(n),label:`第 ${n} 章`}))],
      match:(event,value)=>Number(value)>=event.chapter_number && Number(value)<=(event.chapter_end || event.chapter_number)};
    const eventText = event => `${event.title} ${event.action?.text || ''} ${event.consequence?.text || ''} ${(event.actor_ids || []).map(id=>people.get(id)).join(' ')} ${(event.sub_events || []).map(e=>e.title+' '+e.text).join(' ')}`;
    const relationConfig = event => ({label:"事件关系",items:report.relations.filter(r=>r.from_id===event.id||r.to_id===event.id),pageSize:6,
      text:r=>`${byId.get(r.from_id)?.title || r.from_id} ${byId.get(r.to_id)?.title || r.to_id} ${r.text}`,
      renderItem:r=>`<div class="analysis-relation"><strong>${esc(byId.get(r.from_id)?.title || "未命名事件")} → ${esc(byId.get(r.to_id)?.title || "未命名事件")}</strong><small>${esc(kinds[r.kind] || "关系待核对")}</small>${claim(r)}</div>`});
    function detail(event) {
      if (!event) return '<p class="analysis-scope-note">没有符合条件的大事件，重置筛选后继续阅读。</p>';
      lazyConfigs.set("event-relations",relationConfig(event));
      const subEvents = (event.sub_events || []).map((item,index)=>({...item,index}));
      lazyConfigs.set("event-subevents",{label:"小事件",items:subEvents,pageSize:8,renderItem:item=>`<button type="button" class="analysis-subevent" data-report-subevent="${esc(event.id)}~${item.index}"><span class="analysis-subevent-index">${item.index+1}</span><span><strong>${esc(item.title)}</strong><small>${esc(item.text)}</small></span></button>`});
      return `<header><span class="eyebrow">${chapterLabel(event)} · ${esc(event.story_time)}</span><h3>${esc(event.title)}</h3><p class="analysis-actors">${(event.actor_ids || []).map(id=>esc(people.get(id) || "未命名人物")).join(" / ")}</p></header><h4>事件经过</h4>${claim(event.action)}<h4>结果与后续</h4>${claim(event.consequence)}${lazyDetails(`相关事件与关系 · ${relationConfig(event).items.length}`,"event-relations")}${lazyDetails(`展开小事件 · ${subEvents.length}`,"event-subevents")}`;
    }
    function renderSelected(event) {
      const target = view.querySelector(".analysis-node-detail");
      if (!target) return;
      selected = event?.id || null;
      target.tabIndex = -1;
      target.setAttribute('aria-label', '当前事件详情');
      target.innerHTML = '<button type="button" class="quiet-link report-back-to-index" data-report-index>← 返回事件列表</button>' + detail(event);
      B.lazy(target,lazyConfigs);
      view.querySelectorAll(".analysis-node").forEach(node=>{
        node.setAttribute("aria-pressed",String(node.dataset.reportNode===selected));
        node.classList.toggle("is-selected",node.dataset.reportNode===selected);
      });
    }
    function personCard(p) {
      const portrait = p.portrait || p.identity;
      const roleLabel = importance(p) === "未分级" ? `未分级 · ${p.role || "角色待补充"}` : p.role;
      const chips = phraseChips(p,true);
      const together = [...new Set(report.events.filter(e=>(e.actor_ids || []).includes(p.id)).flatMap(e=>e.actor_ids || []))].filter(id=>id!==p.id && people.has(id));
      lazyConfigs.set(`person-together-${p.id}`,{label:"同场人物",items:together,renderItem:id=>`<p><button type="button" class="quiet-link" data-report-person="${esc(id)}">${esc(people.get(id))}</button></p>`});
      return `<article class="analysis-person"><header><span class="eyebrow">${esc(roleLabel)}</span><h3><a class="analysis-person-link" href="${esc(options.characterUrl?.(p.id) || '#')}" data-report-person="${esc(p.id)}">${esc(p.name)}</a></h3></header><div class="analysis-card-summary"><span>性格 / 为人 · ${labels[portrait?.status] || labels.unknown}</span><p class="analysis-portrait">${esc(compact(portrait?.text || "当前报告没有性格判断。"))}</p>${hasAnalysis(p.change) ? `<span>关键经历 · ${labels[p.change?.status] || labels.unknown}</span><p>${esc(compact(p.change?.text || "当前报告没有经历记录。"))}</p>` : ""}</div>${chips ? `<div class="analysis-phrase-row is-card">${chips}</div>` : ""}${together.length ? lazyDetails(`同场人物 · ${together.length}（不代表关系定性）`,`person-together-${p.id}`) : ''}<details class="analysis-details"><summary>展开原文依据</summary><div class="analysis-details-body"><h4>性格 / 为人</h4>${evidence(portrait?.evidence_ids)}${hasAnalysis(p.change) ? `<h4>关键经历</h4>${evidence(p.change?.evidence_ids)}` : ""}</div></details><button type="button" class="quiet-link analysis-read-more" data-report-person="${esc(p.id)}">完整人物解析 ↗</button></article>`;
    }
    const G = window.XumaiVisualReading;
    function personSummary(kind, label, value, length, fallback) {
      if (!hasAnalysis(value)) return "";
      const status=labels[value?.status] ? value.status : 'unknown';
      return `<div class="visual-person-summary" data-summary-kind="${kind}"><span class="visual-summary-label">${label}</span><span class="analysis-badge visual-summary-status is-${status}">${labels[status]}</span><p>${esc(G.short(value?.text || fallback,length))}</p></div>`;
    }
    const peopleFilters = () => [{name:'importance',label:'人物分组',options:[{value:'',label:'全部人物'},...['主要人物','配角','未分级'].map(value=>({value,label:`${value} · ${report.characters.filter(p=>importance(p)===value).length}`}))],match:(p,value)=>importance(p)===value}];
    function drawMap() {
      view.innerHTML = '<div data-model-map></div>';
      const map = view.querySelector('[data-model-map]');
      if (tab === 'characters') {
        const controller=G.mount(map,{type:'people',label:'人物',items:peopleForList(),state:browsing.characters,selected:selectedPerson,onSelect:p=>{selectedPerson=p?.id || null;},text:personText,filters:peopleFilters(),
          title:p=>p.name,meta:importance,bind:node=>B.lazy(node,lazyConfigs),
          note:'人物 — 共同经历。连线只表示参与同一事件，不代表敌友或亲属。',
          neighbors:p=>report.events.filter(e=>(e.actor_ids || []).includes(p.id)).map(e=>({id:e.id,title:e.title,label:chapterLabel(e),edgeLabel:'共同经历',actors:(e.actor_ids || []).filter(id=>id!==p.id && people.has(id)).map(id=>({id,name:people.get(id)}))})),
          onRoster:n=>{
            openModal({eyebrow:'共同经历 · 不代表敌友亲属',title:n.title,body:`<div class="visual-roster">${n.actors.map(a=>`<button type="button" data-roster-person="${esc(a.id)}">${esc(a.name)}</button>`).join('')}</div>`});
            document.querySelector('.visual-roster').addEventListener('click',event=>{const button=event.target.closest('[data-roster-person]');if(button){closeActiveModal?.();controller.reveal(button.dataset.rosterPerson);}});
          },
          onNeighbor:n=>{selected=n.id;tab='plot';browsing.plot.query='';browsing.plot.filters={};browsing.plot.page=Math.floor(report.events.findIndex(e=>e.id===n.id)/6)+1;timeMode='narrative';draw();view.querySelector(`[data-visual-node="${CSS.escape(n.id)}"]`)?.focus();},
          detail:p=>`<article><span class="eyebrow">${esc(importance(p))}</span><h3>${esc(p.name)}</h3>${personSummary('portrait','性格 / 为人',p.portrait || p.identity,110,'当前报告没有性格判断。')}${personSummary('change','关键经历',p.change,80,'当前报告没有经历记录。')}<details class="analysis-details"><summary>完整解析与原文依据</summary>${personCard(p)}</details></article>`});
      } else {
        const ordered=report.story_order.map(id=>byId.get(id)).filter(Boolean),seen=new Set(ordered.map(e=>e.id));
        const events=timeMode==='story'?[...ordered,...report.events.filter(e=>!seen.has(e.id))]:report.events;
        const heading=document.createElement('div');heading.className='visual-order';
        heading.innerHTML=`<div class="analysis-time-toggle" aria-label="事件阅读顺序"><button type="button" data-report-time="narrative" aria-pressed="${timeMode==='narrative'}">正文揭示顺序</button><button type="button" data-report-time="story" aria-pressed="${timeMode==='story'}">故事发生顺序</button></div>${report.time_note?`<details class="visual-time-note"><summary>时间与不确定性</summary><p>${esc(report.time_note)}</p></details>`:''}${timeMode==='story' && events.length>seen.size?'<p class="analysis-scope-note">未提供故事顺序的事件列在末尾，未替它们推断时间。</p>':''}`;
        view.prepend(heading);
        G.mount(map,{label:'大事件',items:events,state:browsing[tab] || browsing.plot,selected,onSelect:e=>{selected=e?.id || null;},text:eventText,filters:[chapterFilter],
          title:e=>e.title,meta:chapterLabel,bind:node=>B.lazy(node,lazyConfigs),
          edges:report.relations.map(r=>({from:r.from_id,to:r.to_id,kind:r.kind,label:kinds[r.kind] || '待核对'})),
          note:'灰色虚线为阅读顺序；标注连线来自报告。先后 ≠ 因果，无虚构选择分支。',
          detail:e=>`<article><span class="eyebrow">${esc(chapterLabel(e))} · ${esc(labels[e.action?.status] || labels.unknown)}</span><h3>${esc(e.title)}</h3><p>${esc(G.short(e.action?.text,150))}</p><details class="analysis-details"><summary>经过、结果与原文依据</summary>${detail(e)}</details></article>`});
      }
      G.switcher(view,draw);
    }
    function draw() {
      options.onView?.(tab, character);
      root.querySelector(".analysis-questions").hidden = !!character;
      const person = report.characters.find(p => p.id === character);
      if (person) {
        const chips = phraseChips(person, false);
        const identity = person.identity || {};
        const portrait = person.portrait || identity;
        view.innerHTML = `<article class="analysis-person-page"><button type="button" class="quiet-link" data-report-back>← 返回人物卡</button><header><span class="eyebrow">${esc(person.role || "故事人物")}</span><h2>${esc(person.name || "未命名人物")}</h2><p class="analysis-person-lead">${esc(portrait.text || identity.text || "暂无人物概览。")}</p></header><section><h3>身份与处境</h3>${claim(identity)}</section>${analysisSection('想要什么，为什么行动',person.motivation)}${chips ? `<section><h3>形象速览</h3><div class="analysis-phrase-row">${chips}</div></section>` : ""}${analysisSection('关键经历与变化',person.change)}<section><h3>为人判断的依据</h3>${evidence(portrait.evidence_ids || identity.evidence_ids)}</section></article>`;
        return;
      }
      character = null;
      if (!B) {
        view.innerHTML = '<p role="alert">报告浏览组件尚未加载。</p><button type="button" class="quiet-link" data-report-reload>重新加载报告</button>';
        return;
      }
      if (G?.preference() === 'map') { drawMap(); return; }
      if (tab === "characters") {
        view.innerHTML = '<header class="report-reading-heading"><h2>人物与经历</h2></header><div data-model-people></div>';
        B.mount(view.querySelector('[data-model-people]'),{label:"人物",items:peopleForList(),state:browsing.characters,pageSize:8,className:"analysis-characters",
          text:personText,
          filters:[{name:"importance",label:"人物分组",options:[{value:"",label:"全部人物"},...["主要人物","配角","未分级"].map(value=>({value,label:`${value} · ${report.characters.filter(p=>importance(p)===value).length}`}))],match:(p,value)=>importance(p)===value}],
          renderItem:personCard,afterRender:node=>B.lazy(node,lazyConfigs)});
      } else if (tab === "time") {
        const ordered = report.story_order.map(id=>byId.get(id)).filter(Boolean);
        const seen = new Set(ordered.map(e=>e.id));
        const events = timeMode === "story" ? [...ordered,...report.events.filter(e=>!seen.has(e.id))] : report.events;
        view.innerHTML = `<div class="analysis-time-heading"><h3>同一批事件，两种阅读顺序</h3><div class="analysis-time-toggle"><button type="button" data-report-time="narrative" aria-pressed="${timeMode==="narrative"}">正文揭示顺序</button><button type="button" data-report-time="story" aria-pressed="${timeMode==="story"}">故事发生顺序</button></div><p>${esc(report.time_note)}</p>${timeMode==='story' && report.events.length>seen.size ? '<p>未提供故事顺序的事件列在末尾，未替它们推断时间。</p>' : ''}</div><div data-model-time></div>`;
        B.mount(view.querySelector('[data-model-time]'),{label:"时间线事件",items:events,state:browsing.time,pageSize:12,text:eventText,filters:[chapterFilter],className:"analysis-time-list",
          renderItem:e=>`<article><small>${chapterLabel(e)} · ${esc(e.story_time)}</small><h3><button class="quiet-link" type="button" data-report-node="${esc(e.id)}">${esc(e.title)} ↗</button></h3><p>${esc(e.action?.text)}</p></article>`});
      } else {
        view.innerHTML = '<header class="report-reading-heading"><h2>大事件与故事推进</h2><p>先选一段大剧情，再读经过、后果与原文细节。</p></header><div class="report-plot-layout"><div data-model-events></div><article class="analysis-node-detail" aria-live="polite"></article></div>';
        B.mount(view.querySelector('[data-model-events]'),{label:"大事件",items:report.events,state:browsing.plot,pageSize:8,text:eventText,filters:[chapterFilter],className:"report-event-index",
          renderItem:(e,i)=>`<button type="button" class="analysis-node" data-report-node="${esc(e.id)}" aria-pressed="${e.id===selected}"><small>${i+1} / ${chapterLabel(e)}</small><strong>${esc(e.title)}</strong><span class="analysis-node-summary">${esc(compact(e.action?.text))}</span><span>${labels[e.action?.status] || labels.unknown} · ${(e.sub_events || []).length} 个小事件</span></button>`,
          afterRender:(node,visible)=>renderSelected(visible.find(e=>e.id===selected)||visible[0])});
      }
      G?.switcher(view,draw);
    }
    root.addEventListener("click", event => {
      const phrase = event.target.closest("[data-report-phrase]");
      if (phrase) { event.preventDefault(); const [pid, index] = phrase.dataset.reportPhrase.split("~"); openPhrase(pid, index); return; }
      const sub = event.target.closest("[data-report-subevent]");
      if (sub) { event.preventDefault(); const [eid, index] = sub.dataset.reportSubevent.split("~"); openSubEvent(eid, index); return; }
      const personLink = event.target.closest("[data-report-person]");
      if (personLink && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
        returnPerson = personLink.closest('.analysis-person')?.querySelector('.analysis-person-link')?.dataset.reportPerson || returnPerson || personLink.dataset.reportPerson;
        event.preventDefault(); character = personLink.dataset.reportPerson; draw(); window.scrollTo(0, 0); view.querySelector('[data-report-back]')?.focus({preventScroll:true}); return;
      }
      const button = event.target.closest("button");
      if (!button) return;
      if (button.hasAttribute("data-report-reload")) window.location.reload();
      if (button.hasAttribute("data-report-back")) {
        const target = returnPerson || character;
        const query = browsing.characters.query.trim().toLocaleLowerCase();
        const group = browsing.characters.filters.importance;
        const candidates = peopleForList().filter(p => (!query || personText(p).toLocaleLowerCase().includes(query)) && (!group || importance(p) === group));
        const index = candidates.findIndex(p => p.id === target);
        if (index >= 0) browsing.characters.page = Math.floor(index / (G?.preference()==='map'?6:8)) + 1;
        character = null; tab = 'characters'; draw();
        const link = Array.from(view.querySelectorAll('.analysis-person-link,[data-visual-pick]')).find(node => (node.dataset.reportPerson || node.dataset.visualPick) === target);
        if (link) { link.focus({preventScroll:true}); link.scrollIntoView({block:'center',behavior:'instant'}); }
      }
      if (button.dataset.reportTab) { tab = button.dataset.reportTab; draw(); }
      if (button.dataset.reportTime) {
        timeMode = button.dataset.reportTime;
        if(G?.preference()==='map') {
          const ordered=report.story_order.map(id=>byId.get(id)).filter(Boolean),seen=new Set(ordered.map(e=>e.id));
          const events=timeMode==='story'?[...ordered,...report.events.filter(e=>!seen.has(e.id))]:report.events;
          const state=browsing[tab] || browsing.plot,query=state.query.trim().toLocaleLowerCase();
          const matches=events.filter(e=>(!query || eventText(e).toLocaleLowerCase().includes(query)) && (!state.filters.chapter || chapterFilter.match(e,state.filters.chapter)));
          const i=matches.findIndex(e=>e.id===selected);if(i>=0)state.page=Math.floor(i/6)+1;
        }
        draw(); view.querySelector(`[data-report-time="${timeMode}"]`).focus();
      }
      if (button.dataset.reportNode) {
        const id = button.dataset.reportNode;
        if (tab === "plot") renderSelected(byId.get(id));
        else {
          browsing.plot.query = ""; browsing.plot.filters = {};
          browsing.plot.page = Math.floor(report.events.findIndex(e => e.id === id) / 8) + 1;
          selected = id; tab = "plot"; draw();
        }
        if (window.matchMedia('(max-width: 1100px)').matches) {
          const target = view.querySelector('.analysis-node-detail');
          target?.focus({preventScroll:true}); target?.scrollIntoView({block:'start',behavior:'instant'});
        } else view.querySelector(`[data-report-node="${CSS.escape(id)}"]`)?.focus({ preventScroll: true });
      }
      if (button.hasAttribute('data-report-index')) {
        const node = view.querySelector(`[data-report-node="${CSS.escape(selected || '')}"]`);
        node?.focus({preventScroll:true}); node?.scrollIntoView({block:'center',behavior:'instant'});
      }
    });
    draw();
    return { select(section) { tab = section; character = null; draw(); } };
  }
  window.XumaiAnalysis = Object.freeze({ render, mount, closeModal() { closeActiveModal?.(); } });
})();
