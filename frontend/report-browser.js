/* Shared, data-complete browsing for rule and imported reports. Pagination
 * bounds rendered DOM, never the source collection or the search space. */
(() => {
  "use strict";
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
  let serial = 0;
  function mount(root, config) {
    if (!root) return null;
    const items = config.items || [];
    const filters = config.filters || [];
    const state = config.state || {query: "", page: 1, filters: {}};
    state.filters ||= {};
    const size = config.pageSize || 8;
    const id = `reportBrowser${++serial}`;
    root.classList.add("report-browser");
    root.dataset.browserLabel = config.label;
    root.innerHTML = `<form class="report-browser-tools" role="search" aria-label="${esc(config.label)}"><label class="report-browser-search" for="${id}Search"><span>搜索${esc(config.label)}</span><input id="${id}Search" type="search" value="${esc(state.query)}" placeholder="${esc(config.placeholder || '名称、内容或关键词')}" autocomplete="off"></label>${filters.map((filter, i) => `<label for="${id}Filter${i}"><span>${esc(filter.label)}</span><select id="${id}Filter${i}" data-browser-filter="${esc(filter.name)}">${filter.options.map(option => `<option value="${esc(option.value)}" ${state.filters[filter.name] === option.value ? 'selected' : ''}>${esc(option.label)}</option>`).join("")}</select></label>`).join("")}<button type="button" data-browser-clear>重置筛选</button></form><p class="report-browser-count" role="status" aria-live="polite"></p><div class="report-browser-items ${esc(config.className || '')}"></div><nav class="report-browser-pages" aria-label="${esc(config.label)}分页"></nav>`;
    const own = selector => root.querySelector(selector);
    const results = own(".report-browser-items");
    results.tabIndex = -1;
    results.setAttribute("role", "region");
    const pages = own(".report-browser-pages");
    const search = own('input[type="search"]');
    let matches = [];
    function draw() {
      const query = String(state.query || "").trim().toLocaleLowerCase();
      matches = items.filter(item => (!query || String(config.text?.(item) ?? JSON.stringify(item)).toLocaleLowerCase().includes(query)) && filters.every(filter => !state.filters[filter.name] || filter.match(item, state.filters[filter.name])));
      const count = Math.max(1, Math.ceil(matches.length / size));
      state.page = Math.min(count, Math.max(1, Number(state.page) || 1));
      const start = (state.page - 1) * size;
      const visible = matches.slice(start, start + size);
      results.setAttribute("aria-label", `${config.label}结果，第 ${state.page} 页，${visible.length} 项`);
      own(".report-browser-count").textContent = `共 ${items.length} 项 · 符合 ${matches.length} 项${matches.length ? ` · 显示 ${start + 1}–${start + visible.length}` : ''}`;
      results.innerHTML = visible.map((item, i) => config.renderItem(item, start + i)).join("") || `<p class="report-browser-empty">${esc(items.length ? '没有符合条件的记录，试试其他词或重置筛选。' : config.empty || '当前报告没有这类记录。')}</p>`;
      pages.innerHTML = `<button type="button" data-browser-page="${state.page - 1}" ${state.page === 1 ? 'disabled' : ''}>上一页</button><label for="${id}Page">第 <select id="${id}Page" aria-label="${esc(config.label)}页码" data-browser-page-select>${Array.from({length:count}, (_, i) => `<option value="${i + 1}" ${state.page === i + 1 ? 'selected' : ''}>${i + 1}</option>`).join("")}</select> / ${count} 页</label><button type="button" data-browser-page="${state.page + 1}" ${state.page === count ? 'disabled' : ''}>下一页</button>`;
      pages.hidden = count === 1;
      config.afterRender?.(results, visible);
      config.onState?.(state);
    }
    const belongs = event => event.target.closest(".report-browser") === root;
    const focusResults = () => {
      results.focus({preventScroll:true});
      results.scrollIntoView({block:"start", behavior:"instant"});
    };
    root.addEventListener("input", event => {
      if (!belongs(event) || event.target !== search || event.isComposing) return;
      state.query = search.value; state.page = 1; draw();
    });
    search.addEventListener("compositionend", () => { state.query = search.value; state.page = 1; draw(); });
    own("form").addEventListener("submit", event => { event.preventDefault(); });
    root.addEventListener("change", event => {
      if (!belongs(event)) return;
      if (event.target.hasAttribute("data-browser-filter")) {
        state.filters[event.target.dataset.browserFilter] = event.target.value; state.page = 1; draw();
      } else if (event.target.hasAttribute("data-browser-page-select")) {
        state.page = Number(event.target.value); draw(); focusResults();
      }
    });
    root.addEventListener("click", event => {
      if (!belongs(event)) return;
      const button = event.target.closest("button");
      if (button?.hasAttribute("data-browser-clear")) {
        state.query = ""; state.page = 1; state.filters = {}; search.value = "";
        root.querySelectorAll(".report-browser-tools select").forEach(node => { node.value = ""; });
        draw(); search.focus({preventScroll:true});
      } else if (button?.hasAttribute("data-browser-page")) {
        state.page = Number(button.dataset.browserPage); draw();
        focusResults();
      }
    });
    draw();
    return {state, draw, matching: () => matches};
  }
  function lazy(root, configs) {
    root.querySelectorAll("details[data-browser-lazy]").forEach(details => {
      details.addEventListener("toggle", () => {
        if (!details.open || details.dataset.loaded) return;
        const config = configs.get(details.dataset.browserLazy);
        if (!config) return;
        details.dataset.loaded = "true";
        mount(details.querySelector("[data-browser-slot]"), config);
      });
    });
  }
  window.XumaiReportBrowser = Object.freeze({mount, lazy, esc});
})();
