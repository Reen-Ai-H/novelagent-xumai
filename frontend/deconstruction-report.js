/* A data-only viewer for imported, source-bound literary analysis.
   Big-arc nodes carry sub_events (small plot beats inside the arc); character
   images are short phrases that open a modal showing their textual basis. */
(() => {
  "use strict";
  const labels = { fact: "正文可证", reported: "人物说法", inferred: "分析推断", unknown: "尚未确定" };
  const kinds = { causes: "促成", enables: "提供条件", reveals: "揭示", foreshadow_payoff: "线索回收", follows: "仅为先后" };
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  let viewerNumber = 0;

  function openModal({ eyebrow, title, body }) {
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
      document.removeEventListener("keydown", onKey, true);
      backdrop.remove();
      document.body.style.overflow = previousOverflow;
      if (opener && typeof opener.focus === "function") opener.focus();
    };
    function onKey(event) {
      if (event.key === "Escape") { event.preventDefault(); close(); }
    }
    backdrop.querySelector(".analysis-modal-close").addEventListener("click", close);
    document.addEventListener("keydown", onKey, true);
    document.body.style.overflow = "hidden";
    document.body.appendChild(backdrop);
    backdrop.querySelector(".analysis-modal-close").focus();
  }

  function render(report) {
    const source = report && typeof report === "object" ? report : {};
    const questions = Array.isArray(source.open_questions) ? source.open_questions : [];
    return `<section class="analysis-report"><div class="analysis-view"></div><section class="analysis-questions" id="analysisQuestions"><h3>矛盾与疑问</h3><div class="analysis-contradictions"></div><ul>${questions.map(q => `<li>${esc(q)}</li>`).join("")}</ul></section></section>`;
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
      return rendered || unbound || `<span class="analysis-proof-empty">暂未绑定来源证据，不能回到正文核对。</span>`;
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

    root.querySelector(".analysis-contradictions").innerHTML = (report.contradictions || []).map(c => `<h4>${esc(c.title)}</h4>${claim(c)}`).join("");
    let selected = report.events[0]?.id || null;
    let tab = options.section || "characters";
    let character = options.character || null;
    let timeMode = "narrative";
    const view = root.querySelector(".analysis-view");
    const chapterLabel = e => e.chapter_end && e.chapter_end !== e.chapter_number ? `第 ${e.chapter_number}–${e.chapter_end} 章` : `第 ${e.chapter_number} 章`;
    const subEventsBlock = event => {
      const items = event.sub_events || [];
      if (!items.length) return "";
      return `<section class="analysis-subevents"><h4>本副本内小事件</h4><p class="analysis-subevents-hint">点击小事件，查看经过与原文依据。</p><div class="analysis-subevent-list">${items.map((item, index) =>
        `<button type="button" class="analysis-subevent" data-report-subevent="${esc(event.id)}~${index}"><span class="analysis-subevent-index">${String(index + 1).padStart(2, "0")}</span><span><strong>${esc(item.title)}</strong><small>${esc(item.text)}</small></span></button>`).join("")}</div></section>`;
    };
    const detail = event => `<header><span class="eyebrow">${chapterLabel(event)} · ${esc(event.story_time)}</span><h3>${esc(event.title)}</h3><p class="analysis-actors">${event.actor_ids.map(id => esc(people.get(id))).join(" / ")}</p></header><h4>事件经过</h4>${claim(event.action)}<h4>结果与后续</h4>${claim(event.consequence)}${report.relations.filter(r => r.from_id === event.id || r.to_id === event.id).map(r => `<div class="analysis-relation"><strong>${esc(byId.get(r.from_id).title)} → ${esc(byId.get(r.to_id).title)}</strong><small>${kinds[r.kind]}</small>${claim(r)}</div>`).join("")}${subEventsBlock(event)}`;
    function draw() {
      options.onView?.(tab, character);
      root.querySelector(".analysis-questions").hidden = !!character;
      const person = report.characters.find(p => p.id === character);
      if (person) {
        const chips = phraseChips(person, false);
        const identity = person.identity || {};
        const portrait = person.portrait || identity;
        view.innerHTML = `<article class="analysis-person-page"><button type="button" class="quiet-link" data-report-back>← 返回人物卡</button><header><span class="eyebrow">${esc(person.role || "故事人物")}</span><h2>${esc(person.name || "未命名人物")}</h2><p class="analysis-person-lead">${esc(portrait.text || identity.text || "暂无人物概览。")} </p></header><section><h3>身份与处境</h3>${claim(identity)}</section><section><h3>想要什么，为什么行动</h3>${claim(person.motivation)}</section>${chips ? `<section><h3>形象速览</h3><p class="analysis-person-hint">每个人物形象用一句话表示；点击短语，查看正文里哪些内容支撑这个判断。</p><div class="analysis-phrase-row">${chips}</div></section>` : ""}<section><h3>关键经历与变化</h3>${claim(person.change)}</section><section><h3>为人判断的依据</h3>${evidence(portrait.evidence_ids || identity.evidence_ids)}</section></article>`;
        return;
      }
      character = null;
      if (tab === "characters") {
        view.innerHTML = `<div class="analysis-characters">${report.characters.map(p => {
          const portrait = p.portrait || p.identity;
          const chips = phraseChips(p, true);
          return `<article class="analysis-person"><header><span class="eyebrow">${esc(p.role)}</span><h3><a class="analysis-person-link" href="${esc(options.characterUrl?.(p.id) || '#')}" data-report-person="${esc(p.id)}">${esc(p.name)}</a></h3></header><p class="analysis-portrait">${esc(portrait.text)}</p>${chips ? `<div class="analysis-phrase-row is-card">${chips}</div>` : ""}<div class="analysis-experience"><h4>关键经历</h4><p>${esc(p.change.text)}</p></div><span class="analysis-read-more" aria-hidden="true">完整人物解析 ↗</span></article>`;
        }).join("")}</div>`;
      } else if (tab === "time") {
        const events = timeMode === "story" ? report.story_order.map(id => byId.get(id)) : report.events;
        view.innerHTML = `<div class="analysis-time-heading"><h3>同一批事件，两种阅读顺序</h3><div class="analysis-time-toggle"><button type="button" data-report-time="narrative" aria-pressed="${timeMode === "narrative"}">正文揭示顺序</button><button type="button" data-report-time="story" aria-pressed="${timeMode === "story"}">故事发生顺序</button></div><p>${esc(report.time_note)}</p></div><ol class="analysis-time-list">${events.map(e => `<li><span class="analysis-time-dot"></span><div><small>正文${chapterLabel(e)} · ${esc(e.story_time)}</small><button type="button" data-report-node="${e.id}">${esc(e.title)} ↗</button><p>${esc(e.action.text)}</p></div></li>`).join("")}</ol>`;
      } else {
        const positions = new Map(report.events.map((e, i) => [e.id, { x: 24 + (i % 3) * 246, y: 30 + Math.floor(i / 3) * 146 }]));
        const width = Math.min(3, report.events.length) * 246 + 12;
        const height = Math.ceil(report.events.length / 3) * 146 + 20;
        const paths = report.relations.map(r => {
          const a = positions.get(r.from_id), b = positions.get(r.to_id);
          const active = r.from_id === selected || r.to_id === selected;
          const sameRow = a.y === b.y;
          const x1 = sameRow ? a.x + 210 : a.x + 105, y1 = sameRow ? a.y + 48 : a.y + 96;
          const x2 = sameRow ? b.x - 4 : b.x + 105, y2 = sameRow ? b.y + 48 : b.y - 4;
          const d = sameRow ? `M${x1},${y1} L${x2},${y2}` : `M${x1},${y1} C${x1},${(y1+y2)/2} ${x2},${(y1+y2)/2} ${x2},${y2}`;
          return `<path d="${d}" class="${active ? "is-active" : ""} ${r.kind === "follows" ? "is-sequence" : ""}" marker-end="url(#${arrowId})"><title>${esc(kinds[r.kind] + "：" + r.text)}</title></path>`;
        }).join("");
        view.innerHTML = `<div class="analysis-map-heading"><h3>按完整事件看故事推进</h3><p>每个节点是一段完整大剧情；点击查看经过与结果。虚线表示时间先后，不表示因果。</p></div><div class="analysis-map-layout"><div class="analysis-map-scroll" tabindex="0" aria-label="剧情地图，可横向滚动"><div class="analysis-map" style="height:${height}px;width:${width}px"><svg style="width:${width}px" viewBox="0 0 ${width} ${height}" aria-label="剧情关系连线"><defs><marker id="${arrowId}" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="none" stroke="context-stroke"/></marker></defs>${paths}</svg>${report.events.map((e, i) => { const p = positions.get(e.id); return `<button type="button" class="analysis-node ${e.id === selected ? "is-selected" : ""}" data-report-node="${e.id}" aria-pressed="${e.id === selected}" style="left:${p.x}px;top:${p.y}px"><small>${String(i+1).padStart(2,"0")} / ${chapterLabel(e)}</small><strong>${esc(e.title)}</strong><span>${labels[e.action.status]}</span></button>`; }).join("")}</div></div><article class="analysis-node-detail" aria-live="polite">${detail(byId.get(selected))}</article></div>`;
      }
    }
    const arrowId = `analysisArrow${++viewerNumber}`;
    root.addEventListener("click", event => {
      const phrase = event.target.closest("[data-report-phrase]");
      if (phrase) { event.preventDefault(); const [pid, index] = phrase.dataset.reportPhrase.split("~"); openPhrase(pid, index); return; }
      const sub = event.target.closest("[data-report-subevent]");
      if (sub) { event.preventDefault(); const [eid, index] = sub.dataset.reportSubevent.split("~"); openSubEvent(eid, index); return; }
      const personLink = event.target.closest("[data-report-person]");
      if (personLink && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
        event.preventDefault(); character = personLink.dataset.reportPerson; draw(); window.scrollTo(0, 0); return;
      }
      const button = event.target.closest("button");
      if (!button) return;
      if (button.hasAttribute("data-report-back")) { character = null; draw(); window.scrollTo(0, 0); }
      if (button.dataset.reportTab) { tab = button.dataset.reportTab; draw(); }
      if (button.dataset.reportTime) { timeMode = button.dataset.reportTime; draw(); view.querySelector(`[data-report-time="${timeMode}"]`).focus(); }
      if (button.dataset.reportNode) { selected = button.dataset.reportNode; tab = "plot"; draw(); view.querySelector(`[data-report-node="${selected}"]`).focus({ preventScroll: true }); }
    });
    draw();
    return { select(section) { tab = section; character = null; draw(); } };
  }
  window.XumaiAnalysis = Object.freeze({ render, mount });
})();
