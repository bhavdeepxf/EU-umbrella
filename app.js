const elements = {
  search: document.getElementById("searchInput"),
  country: document.getElementById("countryFilter"),
  category: document.getElementById("categoryFilter"),
  score: document.getElementById("scoreFilter"),
  jobs: document.getElementById("jobsContainer"),
  summary: document.getElementById("resultsSummary"),
  status: document.getElementById("statusPanel"),
  statusText: document.getElementById("statusText"),
  refresh: document.getElementById("refreshButton"),
  theme: document.querySelector("[data-theme-toggle]")
};

const state = { jobs: [], generatedAt: "", source: "", loading: true };

function normalise(value) { return String(value ?? "").normalize("NFKD").toLowerCase(); }
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
  })[character]);
}
function unique(values) { return [...new Set(values.filter(Boolean))]; }
function safeUrl(value) {
  try { const url = new URL(value); return url.protocol === "https:" ? url.href : ""; }
  catch { return ""; }
}
function allText(job) {
  return normalise([job.title, job.company, job.location, job.country, job.category,
    job.type, job.description, job.source, ...(job.matchedKeywords || [])].join(" "));
}
function fallbackScore(job) {
  const text = allText(job);
  let score = 0;
  for (const keyword of candidateProfile.directMatchKeywords) if (text.includes(normalise(keyword))) score += 7;
  for (const words of Object.values(candidateProfile.roleGroups)) {
    const hits = words.filter(word => text.includes(normalise(word))).length;
    score += Math.min(hits * 3, 12);
  }
  if (candidateProfile.preferredCountries.some(country => text.includes(normalise(country)))) score += 6;
  if (candidateProfile.priorityLocations.some(place => text.includes(normalise(place)))) score += 5;
  if (/doctoral|doktorand|\bphd\b|research engineer/.test(text)) score += 7;
  for (const warning of candidateProfile.seniorityWarnings) if (text.includes(normalise(warning))) score -= 9;
  return Math.max(0, Math.min(100, score));
}
function prepareJob(job) {
  const score = Number.isFinite(Number(job.matchScore)) ? Math.max(0, Math.min(100, Number(job.matchScore))) : fallbackScore(job);
  const matched = Array.isArray(job.matchedKeywords) && job.matchedKeywords.length
    ? job.matchedKeywords
    : candidateProfile.directMatchKeywords.filter(keyword => allText(job).includes(normalise(keyword)));
  return { ...job, score, matchedKeywords: unique(matched).slice(0, 10), warnings: unique(job.warnings || []).slice(0, 5) };
}
function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}
function setStatus(kind, message) {
  elements.status.className = `status-panel ${kind}`;
  elements.statusText.textContent = message;
}
function populateSelect(select, values, defaultLabel) {
  const previous = select.value;
  select.replaceChildren(new Option(defaultLabel, ""));
  for (const value of unique(values).sort((a, b) => a.localeCompare(b))) select.add(new Option(value, value));
  if ([...select.options].some(option => option.value === previous)) select.value = previous;
}
function populateFilters() {
  populateSelect(elements.country, state.jobs.map(job => job.country), "All countries");
  populateSelect(elements.category, state.jobs.map(job => job.category), "All career areas");
}
function scoreClass(score) { return score >= 80 ? "score-high" : score >= 60 ? "score-medium" : "score-low"; }
function scoreLabel(score) { return score >= 80 ? "Excellent fit" : score >= 65 ? "Strong fit" : score >= 50 ? "Relevant" : "Explore"; }
function icon(name) {
  const icons = {
    location: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="10" r="2.5" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
    briefcase: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 7V5h6v2m-12 4h18v9H3V11Zm0 0V8h18v3M9 13h6" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>',
    calendar: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 3v3m14-3v3M3 9h18M4 5h16v16H4V5Z" fill="none" stroke="currentColor" stroke-width="2"/></svg>'
  };
  return icons[name];
}
function matchReason(job) {
  const terms = job.matchedKeywords.slice(0, 5).join(", ");
  if (job.score >= 80) return `Excellent overlap with your CV in ${terms}. Review required experience and tailor your application around this evidence.`;
  if (job.score >= 65) return `Strong alignment through ${terms}. Check the full responsibilities and language requirement before applying.`;
  if (job.score >= 50) return `Relevant overlap through ${terms}. This may be worth exploring if the seniority and eligibility fit.`;
  return `Partial technical overlap through ${terms || "related engineering experience"}. Review selectively.`;
}
function jobCard(job) {
  const url = safeUrl(job.url);
  const tags = job.matchedKeywords.length
    ? job.matchedKeywords.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join("")
    : '<span class="tag">Related engineering</span>';
  const warnings = job.warnings.length
    ? `<p class="warning-note"><strong>Review:</strong> ${job.warnings.map(escapeHtml).join(", ")}</p>` : "";
  return `<article class="job-card">
    <div class="job-topline">
      <div><h3 class="job-title">${escapeHtml(job.title || "Untitled vacancy")}</h3><p class="company">${escapeHtml(job.company || "Employer not listed")}</p></div>
      <div class="score ${scoreClass(job.score)}"><span>${Math.round(job.score)}%</span><small>${scoreLabel(job.score)}</small></div>
    </div>
    <div class="meta">
      <span class="meta-item">${icon("location")}${escapeHtml(job.location || "See posting")}</span>
      <span class="meta-item">${icon("briefcase")}${escapeHtml(job.category || "Engineering")}</span>
      ${job.datePosted ? `<span class="meta-item">${icon("calendar")}Posted ${escapeHtml(job.datePosted)}</span>` : ""}
    </div>
    <div class="job-tags">${tags}</div>
    <p class="match-reason"><strong>Why it matches:</strong> ${escapeHtml(matchReason(job))}</p>
    ${warnings}
    <div class="job-footer"><span class="source">Source: ${escapeHtml(job.source || "Original employer")}</span>
      ${url ? `<a class="apply-button" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Open original posting ↗</a>` : ""}
    </div>
  </article>`;
}
function filteredJobs() {
  const query = normalise(elements.search.value.trim());
  const minScore = Number(elements.score.value || 0);
  return state.jobs.filter(job => {
    return (!query || allText(job).includes(query)) &&
      (!elements.country.value || job.country === elements.country.value) &&
      (!elements.category.value || job.category === elements.category.value) && job.score >= minScore;
  }).sort((a, b) => b.score - a.score || String(a.title).localeCompare(String(b.title)));
}
function render() {
  const jobs = filteredJobs();
  elements.jobs.setAttribute("aria-busy", "false");
  const updated = state.generatedAt ? ` · updated ${formatDate(state.generatedAt)}` : "";
  elements.summary.textContent = `${jobs.length} of ${state.jobs.length} ranked vacancies${updated}`;
  if (!jobs.length) {
    elements.jobs.innerHTML = `<div class="empty-state"><h3>No matches in this view</h3><p>Clear the search, lower the fit threshold, or wait for the next scheduled refresh. The collector keeps prior valid data if a source temporarily returns no matches.</p><button type="button" id="clearFilters">Clear filters</button></div>`;
    document.getElementById("clearFilters").addEventListener("click", () => {
      elements.search.value = ""; elements.country.value = ""; elements.category.value = ""; elements.score.value = "0"; render();
    });
    return;
  }
  elements.jobs.innerHTML = jobs.map(jobCard).join("");
}
async function loadJobs() {
  state.loading = true;
  elements.refresh.disabled = true;
  setStatus("loading", "Loading the latest ranked vacancies…");
  try {
    const response = await fetch(`data/live-jobs.json?t=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    if (!Array.isArray(payload.jobs) || payload.jobs.length === 0) throw new Error("No live jobs in data file");
    state.jobs = payload.jobs.map(prepareJob).filter(job => safeUrl(job.url));
    state.generatedAt = payload.generatedAt || "";
    state.source = "live";
    setStatus("live", `Live data loaded: ${state.jobs.length} CV-ranked vacancies. The scheduled collector refreshes this deployment daily.`);
  } catch (error) {
    const fallback = Array.isArray(globalThis.jobs) ? globalThis.jobs : (typeof jobs !== "undefined" ? jobs : []);
    state.jobs = fallback.map(prepareJob).filter(job => safeUrl(job.url));
    state.source = state.jobs.length ? "fallback" : "empty";
    setStatus(state.jobs.length ? "warning" : "error", state.jobs.length
      ? "Live data could not be loaded. Showing hand-curated fallback jobs."
      : "No job data is available yet. Run the GitHub Actions workflow to create and deploy live-jobs.json.");
    console.error("Could not load live job data", error);
  } finally {
    state.loading = false;
    elements.refresh.disabled = false;
    populateFilters(); render();
  }
}
function setTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  elements.theme.setAttribute("aria-label", `Switch to ${theme === "dark" ? "light" : "dark"} mode`);
  elements.theme.innerHTML = theme === "dark"
    ? '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" stroke="currentColor" stroke-width="2"/></svg>'
    : '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" fill="none" stroke="currentColor" stroke-width="2"/></svg>';
}
let theme = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
setTheme(theme);
elements.theme.addEventListener("click", () => { theme = theme === "dark" ? "light" : "dark"; setTheme(theme); });
[elements.search, elements.country, elements.category, elements.score].forEach(control => {
  control.addEventListener(control === elements.search ? "input" : "change", render);
});
elements.refresh.addEventListener("click", loadJobs);
loadJobs();
