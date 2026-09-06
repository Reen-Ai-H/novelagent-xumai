/* A data-only viewer for imported, source-bound literary analysis. */
(() => {
  "use strict";
  const labels = { fact: "正文可证", reported: "人物说法", inferred: "分析推断", unknown: "尚未确定" };
  const kinds = { causes: "促成", enables: "提供条件", reveals: "揭示", foreshadow_payoff: "线索回收", follows: "仅为先后" };
  let viewerNumber = 0;
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  function render(report) {
    return `<section class="analysis-report"><div class="analysis-view"></div><section class="analysis-questions" id="analysisQuestions"><h3>矛盾与疑问</h3><div class="analysis-contradictions"></div><ul>${report.open_questions.map(q => `<li>${esc(q)}</li>`).join("")}</ul></section></section>`;
  }
  function mount(container, report, evidenceRefs, evidenceRenderer, options = {}) {
    const root = container.querySelector(".analysis-report");
    if (!root || !report) return;
    const arrowId = `analysisArrow${++viewerNumber}`;
    const byId = new Map(report.events.map(e => [e.id, e]));
    const people = new Map(report.characters.map(p => [p.id, p.name]));
    const evidence = ids => {
      const refs = evidenceRefs.filter(e => ids.includes(e.id));
      return Array.from({ length: Math.ceil(refs.length / 6) }, (_, i) => evidenceRenderer(refs.slice(i * 6, i * 6 + 6))).join("");
    };
    const claim = c => `<span class="analysis-badge is-${esc(c.status)}">${labels[c.status]}</span><p>${esc(c.text)}</p><details class="analysis-proof"><summary>查看原文依据 · ${c.evidence_ids.length}</summary>${evidence(c.evidence_ids)}</details>`;
    root.querySelector(".analysis-contradictions").innerHTML = (report.contradictions || []).map(c => `<h4>${esc(c.title)}</h4>${claim(c)}`).join("");
    let selected = report.events[0].id;
    let tab = options.section || "characters";
    let character = options.character || null;
    let timeMode = "narrative";
    const view = root.querySelector(".analysis-view");
    const chapterLabel = e => e.chapter_end && e.chapter_end !== e.chapter_number ? `第 ${e.chapter_number}–${e.chapter_end} 章` : `第 ${e.chapter_number} 章`;
    const detail = event => `<header><span class="eyebrow">${chapterLabel(event)} · ${esc(event.story_time)}</span><h3>${esc(event.title)}</h3><p class="analysis-actors">${event.actor_ids.map(id => esc(people.get(id))).join(" / ")}</p></header><h4>事件经过</h4>${claim(event.action)}<h4>结果与后续</h4>${claim(event.consequence)}${report.relations.filter(r => r.from_id === event.id || r.to_id === event.id).map(r => `<div class="analysis-relation"><strong>${esc(byId.get(r.from_id).title)} → ${esc(byId.get(r.to_id).title)}</strong><small>${kinds[r.kind]}</small>${claim(r)}</div>`).join("")}`;
    function draw() {
      options.onView?.(tab, character);
      root.querySelector(".analysis-questions").hidden = !!character;
      const person = report.characters.find(p => p.id === character);
      if (person) {
        const sections = person.insights || [];
        view.innerHTML = `<article class="analysis-person-page"><button type="button" class="quiet-link" data-report-back>← 返回人物卡</button><header><span class="eyebrow">${esc(person.role)}</span><h2>${esc(person.name)}</h2><p class="analysis-person-lead">${esc((person.portrait || person.identity).text)}</p></header><section><h3>身份与处境</h3>${claim(person.identity)}</section><section><h3>想要什么，为什么行动</h3>${claim(person.motivation)}</section>${sections.map(c => `<section><h3>${esc(c.title)}</h3>${claim(c)}</section>`).join("")}<section><h3>关键经历与变化</h3>${claim(person.change)}</section><section><h3>为人判断的依据</h3>${evidence((person.portrait || person.identity).evidence_ids)}</section></article>`;
        return;
      }
      character = null;
      if (tab === "characters") {
        view.innerHTML = `<div class="analysis-characters">${report.characters.map(p => {
          const portrait = p.portrait || p.identity;
          return `<article class="analysis-person"><header><span class="eyebrow">${esc(p.role)}</span><h3><a class="analysis-person-link" href="${esc(options.characterUrl?.(p.id) || '#')}" data-report-person="${esc(p.id)}">${esc(p.name)}</a></h3></header><p class="analysis-portrait">${esc(portrait.text)}</p><div class="analysis-experience"><h4>关键经历</h4><p>${esc(p.change.text)}</p></div><span class="analysis-read-more" aria-hidden="true">完整人物解析 ↗</span></article>`;
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
    root.addEventListener("click", event => {
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
