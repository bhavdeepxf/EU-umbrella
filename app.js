const ui = {
  search: document.getElementById("searchInput"), family: document.getElementById("familyFilter"),
  score: document.getElementById("scoreFilter"), readiness: document.getElementById("readinessFilter"),
  sort: document.getElementById("sortFilter"), jobs: document.getElementById("jobsContainer"),
  summary: document.getElementById("resultsSummary"), status: document.getElementById("statusPanel"),
  statusText: document.getElementById("statusText"), refresh: document.getElementById("refreshButton"),
  metrics: document.getElementById("metrics"), theme: document.querySelector("[data-theme-toggle]"),
  profileToggle: document.getElementById("profileToggle"), profilePanel: document.getElementById("profilePanel"),
  regionButtons: [...document.querySelectorAll("[data-region]")]
};
const state = { jobs: [], generatedAt: "", stats: {}, coverage: {}, region: "", visible: 50 };
const normalise = value => String(value ?? "").normalize("NFKD").toLowerCase();
const escapeHtml = value => String(value ?? "").replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"})[c]);
const unique = values => [...new Set(values.filter(Boolean))];
function safeUrl(value) { try { const url = new URL(value); return url.protocol === "https:" ? url.href : ""; } catch { return ""; } }
function allText(job) { return normalise([job.title, job.company, job.location, job.country, job.region, job.category, job.description, ...(job.matchedKeywords || []), ...(job.roleFamilies || [])].join(" ")); }
function formatDate(value, includeTime = false) {
  const date = new Date(value); if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(undefined, includeTime ? {dateStyle:"medium",timeStyle:"short"} : {dateStyle:"medium"}).format(date);
}
function setStatus(kind, text) { ui.status.className = `status-panel ${kind}`; ui.statusText.textContent = text; }
function scoreClass(value) { return value >= 80 ? "high" : value >= 65 ? "medium" : "low"; }
function regionLabel(region) { return region || "All regions"; }
function populateFamilies() {
  const previous = ui.family.value;
  const families = unique(state.jobs.flatMap(job => job.roleFamilies || [job.category])).sort();
  ui.family.replaceChildren(new Option("All career routes", ""));
  for (const family of families) ui.family.add(new Option(family, family));
  if (families.includes(previous)) ui.family.value = previous;
}
function renderMetrics() {
  const regions = state.coverage.regions || {};
  const sources = Object.keys(state.stats || {}).length;
  ui.metrics.innerHTML = [
    [state.jobs.length, "Current matches"], [regions.Germany || 0, "Germany"],
    [regions.Europe || 0, "Europe"], [regions.India || 0, "India"], [sources, "Source groups"]
  ].map(([value,label]) => `<div class="metric"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`).join("");
}
function filteredJobs() {
  const query = normalise(ui.search.value.trim());
  const minScore = Number(ui.score.value || 0); const minReadiness = Number(ui.readiness.value || 0);
  const jobs = state.jobs.filter(job => {
    const families = job.roleFamilies || [job.category];
    return (!query || allText(job).includes(query)) && (!state.region || job.region === state.region) &&
      (!ui.family.value || families.includes(ui.family.value)) && Number(job.matchScore) >= minScore &&
      Number(job.attainability) >= minReadiness;
  });
  const sorters = {
    overall: (a,b) => b.matchScore-a.matchScore || b.attainability-a.attainability,
    technical: (a,b) => b.technicalFit-a.technicalFit || b.attainability-a.attainability,
    attainability: (a,b) => b.attainability-a.attainability || b.technicalFit-a.technicalFit,
    newest: (a,b) => new Date(b.datePosted || 0)-new Date(a.datePosted || 0)
  };
  return jobs.sort(sorters[ui.sort.value] || sorters.overall);
}
function scoreMeter(label, value, kind) {
  return `<div class="score-meter ${scoreClass(value)}"><span>${escapeHtml(label)}</span><strong>${Math.round(value)}%</strong><div class="meter-track"><i style="width:${Math.max(0,Math.min(100,value))}%"></i></div><small>${escapeHtml(kind)}</small></div>`;
}
function evidenceText(job) {
  const top = (job.matchedKeywords || []).slice(0, 5).join(", ");
  const strengths = (job.strengths || []).slice(0, 3).join("; ");
  return `Evidence overlap: ${top || "related engineering experience"}.${strengths ? ` Attainability strengths: ${strengths}.` : ""}`;
}
function card(job) {
  const url = safeUrl(job.url);
  const tags = (job.matchedKeywords || []).slice(0, 8).map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join("");
  const warnings = (job.warnings || []).length ? `<p class="warning"><strong>Check before applying:</strong> ${(job.warnings || []).map(escapeHtml).join(" · ")}</p>` : "";
  return `<article class="job-card">
    <div class="card-main">
      <div class="job-heading"><div><span class="region-badge">${escapeHtml(job.region)}</span><h3>${escapeHtml(job.title)}</h3><p>${escapeHtml(job.company)}</p></div>
        <div class="overall ${scoreClass(job.matchScore)}"><strong>${Math.round(job.matchScore)}%</strong><span>overall</span></div>
      </div>
      <div class="meta"><span>${escapeHtml(job.location || "See posting")}</span><span>${escapeHtml(job.primaryFamily || job.category)}</span><span>${escapeHtml(job.type || "See posting")}</span>${job.datePosted ? `<span>Posted ${escapeHtml(formatDate(job.datePosted))}</span>` : ""}</div>
      <div class="tags">${tags || '<span class="tag">Related engineering</span>'}</div>
      <p class="reason">${escapeHtml(evidenceText(job))}</p>${warnings}
    </div>
    <aside class="score-panel" aria-label="Fit scores">
      ${scoreMeter("Technical fit", Number(job.technicalFit), "CV evidence")}
      ${scoreMeter("Attainability", Number(job.attainability), "seniority + eligibility")}
      ${job.compensation ? `<p class="compensation">${escapeHtml(job.compensation)}</p>` : ""}
      <a class="apply-button" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Open original posting ↗</a>
      <small class="source">${escapeHtml(job.source)}</small>
    </aside>
  </article>`;
}
function render() {
  const matches = filteredJobs(); const shown = matches.slice(0, state.visible);
  ui.jobs.setAttribute("aria-busy", "false");
  ui.summary.textContent = `${matches.length} matches in ${regionLabel(state.region)} · showing ${shown.length}`;
  if (!matches.length) {
    ui.jobs.innerHTML = `<div class="empty"><h3>No roles match this view</h3><p>Lower a score threshold, select another region, or clear the search. The full source data remains available.</p><button id="clearFilters" type="button">Reset filters</button></div>`;
    document.getElementById("clearFilters").addEventListener("click", resetFilters); return;
  }
  ui.jobs.innerHTML = shown.map(card).join("") + (shown.length < matches.length ? `<button id="loadMore" class="load-more" type="button">Show 50 more</button>` : "");
  document.getElementById("loadMore")?.addEventListener("click", () => { state.visible += 50; render(); });
}
function resetFilters() {
  ui.search.value = ""; ui.family.value = ""; ui.score.value = "65"; ui.readiness.value = "55"; ui.sort.value = "overall";
  setRegion("");
}
function setRegion(region) {
  state.region = region; state.visible = 50;
  for (const button of ui.regionButtons) button.classList.toggle("active", button.dataset.region === region);
  render();
}
async function loadJobs() {
  ui.refresh.disabled = true; setStatus("loading", "Loading the latest multi-source vacancy index…");
  try {
    const response = await fetch(`data/live-jobs.json?t=${Date.now()}`, {cache:"no-store"});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    if (!Array.isArray(payload.jobs) || !payload.jobs.length) throw new Error("No jobs in deployed data");
    state.jobs = payload.jobs.filter(job => safeUrl(job.url)); state.generatedAt = payload.generatedAt || "";
    state.stats = payload.sourceStats || {}; state.coverage = payload.coverage || {};
    setStatus("live", `${state.jobs.length} current vacancies loaded · refreshed ${formatDate(state.generatedAt, true)} · Germany, Europe and India included.`);
  } catch (error) {
    state.jobs = Array.isArray(globalThis.fallbackJobs) ? globalThis.fallbackJobs : [];
    setStatus("error", state.jobs.length ? "Live index unavailable; showing verified fallback jobs." : "No deployed job index found. Run the GitHub Actions workflow once.");
    console.error(error);
  } finally {
    ui.refresh.disabled = false; populateFamilies(); renderMetrics(); render();
  }
}
function setTheme(value) {
  document.documentElement.dataset.theme = value;
  ui.theme.setAttribute("aria-label", `Switch to ${value === "dark" ? "light" : "dark"} mode`);
  ui.theme.innerHTML = value === "dark" ? '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" stroke="currentColor" stroke-width="2"/></svg>' : '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" fill="none" stroke="currentColor" stroke-width="2"/></svg>';
}
let theme = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; setTheme(theme);
ui.theme.addEventListener("click", () => { theme = theme === "dark" ? "light" : "dark"; setTheme(theme); });
ui.profileToggle.addEventListener("click", () => { const opening = ui.profilePanel.hidden; ui.profilePanel.hidden = !opening; ui.profileToggle.textContent = opening ? "Hide positioning details" : "See positioning details"; if (opening) ui.profilePanel.scrollIntoView({behavior:"smooth",block:"nearest"}); });
ui.regionButtons.forEach(button => button.addEventListener("click", () => setRegion(button.dataset.region)));
[ui.family, ui.score, ui.readiness, ui.sort].forEach(control => control.addEventListener("change", () => {state.visible=50;render();}));
ui.search.addEventListener("input", () => {state.visible=50;render();}); ui.refresh.addEventListener("click", loadJobs);
loadJobs();
