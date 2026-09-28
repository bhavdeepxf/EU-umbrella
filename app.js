"use strict";

const $ = (id) => document.getElementById(id);
const searchInput = $("searchInput");
const countryFilter = $("countryFilter");
const categoryFilter = $("categoryFilter");
const scoreFilter = $("scoreFilter");
const resetFilters = $("resetFilters");
const jobsContainer = $("jobsContainer");
const resultsSummary = $("resultsSummary");

let liveJobs = [];
let generatedAt = "";
let sourceHealth = [];
let loadError = "";

const normalise = (value) => String(value ?? "").toLocaleLowerCase();
const unique = (items) => [...new Set(items.filter(Boolean))];
const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
const escapeAttr = escapeHtml;
const safeUrl = (value) => {
  try {
    const url = new URL(String(value));
    return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
  } catch { return "#"; }
};

function allText(job) {
  return normalise([job.title, job.company, job.location, job.country, job.category, job.type, job.description, job.source, ...(job.matchedKeywords || [])].join(" "));
}

function localScore(job) {
  const text = allText(job);
  let score = 15;
  candidateProfile.directMatchKeywords.forEach((term) => { if (text.includes(normalise(term))) score += 7; });
  Object.values(candidateProfile.roleGroups).forEach((terms) => {
    const hits = terms.filter((term) => text.includes(normalise(term))).length;
    score += Math.min(hits * 3, 15);
  });
  if (candidateProfile.preferredCountries.some((country) => normalise(job.country).includes(normalise(country)))) score += 7;
  if (candidateProfile.priorityLocations.some((place) => text.includes(normalise(place)))) score += 5;
  if (/\bphd\b|doctoral|doktorand|wissenschaftlicher mitarbeiter|research associate/.test(text)) score += 10;
  candidateProfile.seniorityWarnings.forEach((term) => { if (text.includes(normalise(term))) score -= 10; });
  candidateProfile.languageWarnings.forEach((term) => { if (text.includes(normalise(term))) score -= 7; });
  return Math.max(0, Math.min(100, score));
}

function score(job) {
  const collected = Number(job.matchScore);
  return Number.isFinite(collected) ? Math.max(0, Math.min(100, collected)) : localScore(job);
}

function tags(job) {
  if (Array.isArray(job.matchedKeywords) && job.matchedKeywords.length) return unique(job.matchedKeywords).slice(0, 8);
  const text = allText(job);
  return unique(Object.values(candidateProfile.roleGroups).flat().filter((term) => text.includes(normalise(term)))).slice(0, 8);
}

function warnings(job) {
  if (Array.isArray(job.warnings)) return unique(job.warnings).slice(0, 4);
  const text = allText(job);
  return unique([...candidateProfile.seniorityWarnings, ...candidateProfile.languageWarnings].filter((term) => text.includes(normalise(term)))).slice(0, 4);
}

function scoreLabel(value) {
  if (value >= 85) return "High priority";
  if (value >= 70) return "Strong fit";
  if (value >= 60) return "Potential fit";
  return "Selective";
}

function scoreClass(value) {
  if (value >= 80) return "high";
  if (value >= 60) return "medium";
  return "low";
}

function dateLabel(value) {
  if (!value) return "Date not published";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? escapeHtml(value) : new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

function reason(job) {
  const matched = tags(job).slice(0, 5);
  if (!matched.length) return "Broader engineering overlap; inspect the official requirements before deciding.";
  return `CV overlap: ${matched.join(", ")}. ${score(job) >= 70 ? "Tailor the application around these methods and your closest project evidence." : "Confirm that the day-to-day work and required level justify an application."}`;
}

function options(select, placeholder, values) {
  const selected = select.value;
  select.replaceChildren(new Option(placeholder, ""), ...values.map((value) => new Option(value, value)));
  if (values.includes(selected)) select.value = selected;
}

function populateFilters() {
  options(countryFilter, "All countries", unique(liveJobs.map((job) => job.country)).sort());
  options(categoryFilter, "All role types", unique(liveJobs.map((job) => job.category)).sort());
}

function render() {
  const term = normalise(searchInput.value.trim());
  const minimum = Number(scoreFilter.value);
  const visible = liveJobs.map((job) => ({ ...job, computedScore: score(job), computedTags: tags(job), computedWarnings: warnings(job) }))
    .filter((job) => (!term || allText(job).includes(term)) && (!countryFilter.value || job.country === countryFilter.value) && (!categoryFilter.value || job.category === categoryFilter.value) && job.computedScore >= minimum)
    .sort((a, b) => b.computedScore - a.computedScore || String(b.datePosted).localeCompare(String(a.datePosted)));

  const failed = sourceHealth.filter((item) => item.status !== "ok").length;
  const timestamp = generatedAt ? ` Updated ${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(generatedAt))}.` : "";
  resultsSummary.textContent = `${visible.length} of ${liveJobs.length} verified vacancies shown.${timestamp}${failed ? ` ${failed} source${failed === 1 ? "" : "s"} unavailable during the last refresh.` : ""}`;

  if (!visible.length) {
    const message = loadError && !liveJobs.length ? "The live vacancy feed could not be loaded." : "No vacancies match the current filters.";
    jobsContainer.innerHTML = `<div class="empty-state"><svg aria-hidden="true" viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 7h16v12H4zM8 7V5h8v2M8 12h8"/></svg><h3>${escapeHtml(message)}</h3><p>${loadError ? "Try reloading. If this persists, run the refresh workflow and inspect its source-health output." : "Lower the fit threshold, clear filters, or try a broader keyword."}</p><button class="secondary-button" type="button" data-clear>Clear filters</button></div>`;
    jobsContainer.querySelector("[data-clear]")?.addEventListener("click", clearFilters);
    jobsContainer.setAttribute("aria-busy", "false");
    return;
  }

  jobsContainer.innerHTML = visible.map((job) => {
    const value = job.computedScore;
    const warningHtml = job.computedWarnings.length ? `<p class="warning"><strong>Review:</strong> ${job.computedWarnings.map(escapeHtml).join(", ")}</p>` : "";
    const deadline = job.deadline && job.deadline !== "Check original vacancy" ? `<span>Deadline ${dateLabel(job.deadline)}</span>` : "";
    const description = String(job.description || "").slice(0, 320);
    return `<article class="job-card">
      <div class="job-main">
        <div class="job-heading"><div><p class="source-line">${escapeHtml(job.source || "Official source")}</p><h3>${escapeHtml(job.title)}</h3><p class="company">${escapeHtml(job.company)} · ${escapeHtml(job.location || job.country)}</p></div><div class="score score-${scoreClass(value)}" aria-label="Match score ${value} out of 100"><strong>${value}</strong><span>${scoreLabel(value)}</span></div></div>
        <div class="meta"><span>${escapeHtml(job.category || "Technical role")}</span><span>Posted ${dateLabel(job.datePosted)}</span>${deadline}</div>
        ${description ? `<p class="description">${escapeHtml(description)}${String(job.description || "").length > 320 ? "…" : ""}</p>` : ""}
        <p class="match-reason">${escapeHtml(reason(job))}</p>${warningHtml}
        <div class="job-tags">${job.computedTags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</div>
      </div>
      <div class="job-action"><a class="apply-button" href="${escapeAttr(safeUrl(job.url))}" target="_blank" rel="noopener noreferrer">View official posting <span aria-hidden="true">↗</span></a><span class="verify-note">Verify status before applying</span></div>
    </article>`;
  }).join("");
  jobsContainer.setAttribute("aria-busy", "false");
}

function clearFilters() {
  searchInput.value = "";
  countryFilter.value = "";
  categoryFilter.value = "";
  scoreFilter.value = "52";
  render();
}

async function loadJobs() {
  try {
    const response = await fetch(`data/jobs.json?v=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Vacancy feed returned ${response.status}`);
    const payload = await response.json();
    if (!Array.isArray(payload.jobs)) throw new Error("Vacancy feed has an invalid format");
    liveJobs = payload.jobs.filter((job) => job && job.title && safeUrl(job.url) !== "#");
    generatedAt = payload.generatedAt || "";
    sourceHealth = Array.isArray(payload.sources) ? payload.sources : [];
  } catch (error) {
    loadError = error.message;
    liveJobs = Array.isArray(globalThis.jobs) ? globalThis.jobs : [];
  }
  populateFilters();
  render();
}

[searchInput, countryFilter, categoryFilter, scoreFilter].forEach((control) => control.addEventListener(control === searchInput ? "input" : "change", render));
resetFilters.addEventListener("click", clearFilters);

(function initTheme() {
  const root = document.documentElement;
  const toggle = document.querySelector("[data-theme-toggle]");
  let theme = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  const draw = () => {
    root.dataset.theme = theme;
    toggle.setAttribute("aria-label", `Switch to ${theme === "dark" ? "light" : "dark"} mode`);
    toggle.innerHTML = theme === "dark" ? '<svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/></svg>' : '<svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8Z"/></svg>';
  };
  toggle.addEventListener("click", () => { theme = theme === "dark" ? "light" : "dark"; draw(); });
  draw();
})();

loadJobs();
