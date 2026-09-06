/* A data-only viewer for imported, source-bound literary analysis. */
(() => {
  "use strict";
  const labels = { fact: "正文可证", reported: "人物说法", inferred: "分析推断", unknown: "尚未确定" };
  const kinds = { causes: "促成", enables: "提供条件", reveals: "揭示", foreshadow_payoff: "线索回收", follows: "仅为先后" };
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  function render(report) {
    return `<section class="analysis-report"><header class="analysis-intro"><span class="eyebrow">小说细读 · ${esc(report.producer)}</span><h2>${esc(report.title)}</h2><p>${esc(report.scope)}</p><div class="analysis-counts"><span>${report.characters.length} 张人物卡</span><span>${report.events.length} 个剧情节点</span><span>${report.evidence.length} 处原文依据</span></div></header><div class="analysis-findings">${report.findings.map((f, i) => `<details ${i === 0 ? "open" : ""}><summary><span class="analysis-number">0${i + 1}</span>${esc(f.title)}<span class="analysis-badge">${labels[f.status]}</span></summary><p>${esc(f.text)}</p><div data-finding-evidence="${esc(f.id)}"></div></details>`).join("")}</div><nav class="analysis-tabs" aria-label="拆解视角"><button type="button" data-report-tab="plot" aria-pressed="true">剧情地图</button><button type="button" data-report-tab="characters" aria-pressed="false">人物与动机</button><button type="button" data-report-tab="time" aria-pressed="false">双时间线</button></nav><div class="analysis-view"></div><details class="analysis-questions"><summary>读到这里，还不能确定的事 · ${report.open_questions.length}</summary><ul>${report.open_questions.map(q => `<li>${esc(q)}</li>`).join("")}</ul></details><p class="analysis-footnote">本轮为已读章节的局部分析。引用位置已匹配正文，文学解释仍可继续讨论和修正。</p></section>`;
  }
  function mount(container, report, evidenceRefs, evidenceRenderer) {
    const root = container.querySelector(".analysis-report");
    if (!root || !report) return;
    const byId = new Map(report.events.map(e => [e.id, e]));
    const people = new Map(report.characters.map(p => [p.id, p.name]));
    const evidence = ids => evidenceRenderer(evidenceRefs.filter(e => ids.includes(e.id)));
    const claim = c => `<span class="analysis-badge is-${esc(c.status)}">${labels[c.status]}</span><p>${esc(c.text)}</p><details class="analysis-proof"><summary>查看原文依据 · ${c.evidence_ids.length}</summary>${evidence(c.evidence_ids)}</details>`;
    for (const f of report.findings) root.querySelector(`[data-finding-evidence="${f.id}"]`).innerHTML = evidence(f.evidence_ids);
    let selected = report.events[0].id;
    let tab = "plot";
    let timeMode = "narrative";
    const view = root.querySelector(".analysis-view");
    const detail = event => `<header><span class="eyebrow">第 ${event.chapter_number} 章 · ${esc(event.story_time)}</span><h3>${esc(event.title)}</h3><p class="analysis-actors">${event.actor_ids.map(id => esc(people.get(id))).join(" / ")}</p></header><h4>行动与选择</h4>${claim(event.action)}<h4>后果与作用</h4>${claim(event.consequence)}${report.relations.filter(r => r.from_id === event.id || r.to_id === event.id).map(r => `<div class="analysis-relation"><strong>${esc(byId.get(r.from_id).title)} → ${esc(byId.get(r.to_id).title)}</strong><small>${kinds[r.kind]}</small>${claim(r)}</div>`).join("")}`;
    function draw() {
      root.querySelectorAll("[data-report-tab]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.reportTab === tab)));
      if (tab === "characters") {
        view.innerHTML = `<div class="analysis-characters">${report.characters.map(p => `<article class="analysis-person"><header><span class="eyebrow">${esc(p.role)}</span><h3>${esc(p.name)}</h3></header><h4>身份与认知</h4>${claim(p.identity)}<h4>想得到什么</h4>${claim(p.motivation)}<h4>选择与变化</h4>${claim(p.change)}</article>`).join("")}</div>`;
      } else if (tab === "time") {
        const events = timeMode === "story" ? report.story_order.map(id => byId.get(id)) : report.events;
        view.innerHTML = `<div class="analysis-time-heading"><h3>同一批事件，两种阅读顺序</h3><div class="analysis-time-toggle"><button type="button" data-report-time="narrative" aria-pressed="${timeMode === "narrative"}">正文揭示顺序</button><button type="button" data-report-time="story" aria-pressed="${timeMode === "story"}">故事发生顺序</button></div><p>${esc(report.time_note)}</p></div><ol class="analysis-time-list">${events.map(e => `<li><span class="analysis-time-dot"></span><div><small>正文第 ${e.chapter_number} 章 · ${esc(e.story_time)}</small><button type="button" data-report-node="${e.id}">${esc(e.title)} ↗</button><p>${esc(e.action.text)}</p></div></li>`).join("")}</ol>`;
      } else {
        const positions = new Map(report.events.map((e, i) => [e.id, { x: 24 + (i % 3) * 246, y: 30 + Math.floor(i / 3) * 146 }]));
        const height = Math.ceil(report.events.length / 3) * 146 + 20;
        const paths = report.relations.map(r => {
          const a = positions.get(r.from_id), b = positions.get(r.to_id);
          const active = r.from_id === selected || r.to_id === selected;
          const sameRow = a.y === b.y;
          const x1 = sameRow ? a.x + 210 : a.x + 105, y1 = sameRow ? a.y + 48 : a.y + 96;
          const x2 = sameRow ? b.x - 4 : b.x + 105, y2 = sameRow ? b.y + 48 : b.y - 4;
          const d = sameRow ? `M${x1},${y1} L${x2},${y2}` : `M${x1},${y1} C${x1},${(y1+y2)/2} ${x2},${(y1+y2)/2} ${x2},${y2}`;
          return `<path d="${d}" class="${active ? "is-active" : ""} ${r.kind === "follows" ? "is-sequence" : ""}" marker-end="url(#analysisArrow)"><title>${esc(kinds[r.kind] + "：" + r.text)}</title></path>`;
        }).join("");
        view.innerHTML = `<div class="analysis-map-heading"><h3>莫测的局面，由哪些选择改变</h3><p>点击节点查看行动、后果与连线依据。高亮线连接当前节点；虚线仅表示先后。</p></div><div class="analysis-map-layout"><div class="analysis-map-scroll" tabindex="0" aria-label="剧情地图，可横向滚动"><div class="analysis-map" style="height:${height}px"><svg viewBox="0 0 750 ${height}" aria-label="剧情关系连线"><defs><marker id="analysisArrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="none" stroke="context-stroke"/></marker></defs>${paths}</svg>${report.events.map((e, i) => { const p = positions.get(e.id); return `<button type="button" class="analysis-node ${e.id === selected ? "is-selected" : ""}" data-report-node="${e.id}" aria-pressed="${e.id === selected}" style="left:${p.x}px;top:${p.y}px"><small>${String(i+1).padStart(2,"0")} / 第 ${e.chapter_number} 章</small><strong>${esc(e.title)}</strong><span>${labels[e.action.status]}</span></button>`; }).join("")}</div></div><article class="analysis-node-detail" aria-live="polite">${detail(byId.get(selected))}</article></div>`;
      }
    }
    root.addEventListener("click", event => {
      const button = event.target.closest("button");
      if (!button) return;
      if (button.dataset.reportTab) { tab = button.dataset.reportTab; draw(); }
      if (button.dataset.reportTime) { timeMode = button.dataset.reportTime; draw(); view.querySelector(`[data-report-time="${timeMode}"]`).focus(); }
      if (button.dataset.reportNode) { selected = button.dataset.reportNode; tab = "plot"; draw(); view.querySelector(`[data-report-node="${selected}"]`).focus({ preventScroll: true }); }
    });
    draw();
  }
  window.XumaiAnalysis = Object.freeze({ render, mount });
})();
