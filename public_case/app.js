const state = { data: null, view: "guide", volume: "all" };
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
const palette = ["#315ff5", "#b2588a", "#b86b3e", "#428b78", "#7964b7", "#a26b37"];

async function init() {
  state.data = await fetch("data.json", { cache: "no-store" }).then((response) => response.json());
  document.title = `叙脉｜${state.data.title}`;
  $("#page-title").textContent = state.data.title;
  $("#page-subtitle").textContent = state.data.subtitle;
  $("#notice").textContent = state.data.notice;
  renderStats(); renderVolumes(); render();
  $$(".tab").forEach((button) => button.addEventListener("click", () => { state.view = button.dataset.view; state.volume = "all"; render(); }));
  $("#volume-list").addEventListener("click", (event) => { const button = event.target.closest("button"); if (!button) return; state.volume = button.dataset.volume; state.view = button.dataset.view || state.view; render(); });
  $("#view-root").addEventListener("click", onContentClick);
  $("#modal").addEventListener("click", (event) => { if (event.target.dataset.close) closeModal(); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeModal(); });
}

function renderStats() {
  const s = state.data.stats;
  const items = [[s.chapter_count,"章节"],[s.window_count,"阅读窗口"],[s.event_count,"大剧情节点"],[s.character_count,"人物卡"],[s.question_count,"疑问点"],[s.evidence_count,"证据回链"]];
  $("#stats").innerHTML = items.map(([value, label]) => `<div class="stat"><strong>${esc(value)}</strong><span>${esc(label)}</span></div>`).join("");
}

function renderVolumes() {
  $("#volume-list").innerHTML = `<button class="volume-button active" data-volume="all"><b>全书</b><small>第1—126章</small></button>` + state.data.volumes.map((volume, index) => `<button class="volume-button" data-volume="${esc(volume.id)}"><b>窗口 ${String(index + 1).padStart(2, "0")}</b><small>第${volume.start}—${volume.end}章</small></button>`).join("");
}

function filteredVolumes() { return state.volume === "all" ? state.data.volumes : state.data.volumes.filter((volume) => volume.id === state.volume); }
function filteredEvents() { const ids = new Set(filteredVolumes().map((volume) => volume.id)); return state.data.events.filter((event) => ids.has(event.volume_id)); }

function render() {
  $$(".tab").forEach((button) => button.classList.toggle("active", button.dataset.view === state.view));
  $$(".volume-button").forEach((button) => button.classList.toggle("active", button.dataset.volume === state.volume));
  const views = { guide: renderGuide, plot: renderPlot, characters: renderCharacters, timeline: renderTimeline, questions: renderQuestions };
  $("#view-root").innerHTML = views[state.view]();
}

function header(kicker, title, description) { return `<div class="view-header"><div><div class="section-label">${esc(kicker)}</div><h2>${esc(title)}</h2><p>${esc(description)}</p></div></div>`; }
function volumeColor(index) { return palette[index % palette.length]; }
function volumeBlock(volume, index) {
  const nodes = volume.report.events || [];
  return `<article class="volume-card" style="--volume-color:${volumeColor(index)}">
    <div class="volume-card-head"><div><h3>${esc(volume.title)}</h3><p>第${volume.start}—${volume.end}章 · ${esc(volume.report.producer)}</p></div><div class="volume-counts"><span>${volume.events} 节点</span><span>${volume.characters} 人物</span><span>${volume.evidence} 证据</span></div></div>
    <div class="volume-scope">${esc(volume.scope)}</div>
    <div class="node-flow">${nodes.map((node, i) => `<div class="node-card"><div class="node-index">${String(i + 1).padStart(2, "0")}</div><h4>${esc(node.title)}</h4><p>${esc(node.consequence?.text || node.action?.text || "")}</p><div class="node-meta">第${node.chapter_number}${node.chapter_end && node.chapter_end !== node.chapter_number ? `—${node.chapter_end}` : ""}章 · ${node.actor_ids?.length || 0} 位人物</div></div>`).join("")}</div>
  </article>`;
}
function renderGuide() { return header("GUIDE / 全书导读", "从窗口到全书", "先看每个大剧情副本，再进入人物、时间与证据层。点击左侧窗口可以聚焦一段阅读范围。") + filteredVolumes().map((v) => volumeBlock(v, state.data.volumes.indexOf(v))).join(""); }

function renderPlot() {
  const events = filteredEvents();
  return header("PLOT / 剧情地图", state.volume === "all" ? "大剧情节点" : "窗口内的剧情节点", "每张卡片只保留一个副本或大剧情，行动、后果和来源证据在详情中展开。") + `<div class="node-flow plot-flow">${events.map((event, index) => `<button type="button" class="node-card" data-event="${esc(event.id)}" style="--volume-color:${volumeColor(state.data.volumes.findIndex((v) => v.id === event.volume_id))}"><div class="node-index">${String(index + 1).padStart(2, "0")}</div><h4>${esc(event.title)}</h4><p>${esc(event.action?.text || "")}</p><div class="node-meta">${esc(event.volume_label)} · ${esc(event.story_time)}</div></button>`).join("")}</div>`;
}

function renderCharacters() {
  const volumeIds = new Set(filteredVolumes().map((volume) => volume.id));
  const people = state.data.characters.filter((person) => volumeIds.has(person.volume_id));
  return header("CHARACTERS / 人物卡", state.volume === "all" ? "全书人物" : "窗口人物", "卡片先给出这个人是谁、经历了什么，以及当前能确认的变化；点击后查看完整分析。") + `<div class="card-grid">${people.map((person) => `<button type="button" class="person-card" data-person="${esc(person.id)}"><h3>${esc(person.name)}</h3><div class="person-role">${esc(person.role)}</div><p>${esc(person.identity?.text || "")}</p><span class="tag">${esc(person.volume_id === "run03" ? "开篇窗口" : person.volume_id)} · 查看详情</span></button>`).join("") || `<div class="empty">这个窗口暂无人物卡。</div>`}</div>`;
}

function renderTimeline() {
  const events = filteredEvents();
  return header("TIMELINE / 双时间线", "叙事顺序与故事时间", "叙事顺序按阅读窗口排列；故事时间保留模型给出的层次和不确定性，不强行压成一条线。") + `<div class="timeline-list">${events.map((event, index) => `<div class="timeline-item"><h3>${String(index + 1).padStart(2, "0")} · ${esc(event.title)}</h3><div class="time">故事时间：${esc(event.story_time)}</div><p>${esc(event.consequence?.text || event.action?.text || "")}</p></div>`).join("")}</div>`;
}

function renderQuestions() {
  const volumeIds = new Set(filteredVolumes().map((volume) => volume.id));
  const questions = state.data.questions.filter((item) => volumeIds.has(item.volume_id));
  const contradictions = state.data.contradictions.filter((item) => volumeIds.has(item.volume_id));
  return header("OPEN THREADS / 待核对", "矛盾与疑问", "这里保留拆解过程中还不能当作事实的线索，方便后续回看与修正。") + `<div class="question-list">${contradictions.map((item) => `<div class="question-item"><b>差异</b>${esc(item.title)}<br><span>${esc(item.text)}</span></div>`).join("")}${questions.map((item) => `<div class="question-item"><b>疑问</b>${esc(item.text)}<br><span class="evidence">来源窗口：${esc(item.volume_id)}</span></div>`).join("") || `<div class="empty">当前窗口没有记录待核对事项。</div>`}</div>`;
}

function onContentClick(event) {
  const person = event.target.closest("[data-person]");
  if (person) return openPerson(person.dataset.person);
  const node = event.target.closest("[data-event]");
  if (node) return openEvent(node.dataset.event);
}

function openPerson(id) {
  const person = state.data.characters.find((item) => item.id === id); if (!person) return;
  const claim = (title, value) => `<div class="detail-block"><h3>${title}</h3><p>${esc(value?.text || "本窗口未形成可确认结论。")}<span class="evidence">${value?.status || "unknown"} · ${value?.evidence_ids?.length || 0} 条证据</span></p></div>`;
  $("#modal-content").innerHTML = `<div class="section-label">人物解析 · ${esc(person.volume_id)}</div><h2 id="modal-title">${esc(person.name)}</h2><div class="role">${esc(person.role)}</div>${claim("身份与性格", person.identity)}${claim("行动动机", person.motivation)}${claim("经历与变化", person.change)}<div class="detail-block"><h3>可观察细节</h3>${(person.insights || []).map((item) => `<div class="insight"><strong>${esc(item.title)}</strong><span>${esc(item.text)}</span><div class="evidence">${item.status || "unknown"} · ${item.evidence_ids?.length || 0} 条证据</div></div>`).join("") || `<p>暂无更多观察。</p>`}</div>`;
  $("#modal").hidden = false; document.body.style.overflow = "hidden";
}

function openEvent(id) {
  const event = state.data.events.find((item) => item.id === id); if (!event) return;
  const claim = (title, value) => `<div class="detail-block"><h3>${title}</h3><p>${esc(value?.text || "")}</p><div class="evidence">${value?.status || "unknown"} · ${value?.evidence_ids?.length || 0} 条证据</div></div>`;
  $("#modal-content").innerHTML = `<div class="section-label">剧情节点 · ${esc(event.volume_label)}</div><h2 id="modal-title">${esc(event.title)}</h2><div class="role">故事时间：${esc(event.story_time)}</div>${claim("发生了什么", event.action)}${claim("造成了什么", event.consequence)}<div class="detail-block"><h3>节点内事件</h3>${(event.sub_events || []).map((item) => `<div class="insight"><strong>${esc(item.title)}</strong><span>${esc(item.text)}</span></div>`).join("") || `<p>没有进一步拆开的子事件。</p>`}</div>`;
  $("#modal").hidden = false; document.body.style.overflow = "hidden";
}
function closeModal() { $("#modal").hidden = true; document.body.style.overflow = ""; }
init().catch((error) => { $("#view-root").innerHTML = `<div class="empty">案例数据暂时无法加载：${esc(error.message)}</div>`; });
