const searchInput = document.getElementById("searchInput");
const countryFilter = document.getElementById("countryFilter");
const categoryFilter = document.getElementById("categoryFilter");
const scoreFilter = document.getElementById("scoreFilter");
const jobsContainer = document.getElementById("jobsContainer");
const resultsSummary = document.getElementById("resultsSummary");

let liveJobs = [];
let liveJobsGeneratedAt = "";
let liveDataAvailable = false;

function normalise(value) {
  return String(value || "").toLowerCase();
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function unique(items) {
  return [...new Set(items.filter(Boolean))];
}

function getAllJobText(job) {
  return normalise(
    [
      job.title,
      job.company,
      job.location,
      job.country,
      job.category,
      job.type,
      job.description,
      job.source,
      ...(job.matchedKeywords || [])
    ].join(" ")
  );
}

function getSourceJobs() {
  return liveJobs.length > 0 ? liveJobs : jobs;
}

function matchedKeywords(job) {
  const text = getAllJobText(job);
  const matches = [];

  Object.values(candidateProfile.roleGroups)
    .flat()
    .forEach((keyword) => {
      if (text.includes(normalise(keyword))) {
        matches.push(keyword);
      }
    });

  return unique(matches).slice(0, 8);
}

function calculateScore(job) {
  const text = getAllJobText(job);
  let score = 0;

  candidateProfile.directMatchKeywords.forEach((keyword) => {
    if (text.includes(normalise(keyword))) {
      score += 6;
    }
  });

  Object.values(candidateProfile.roleGroups).forEach((keywords) => {
    const groupMatches = keywords.filter((keyword) =>
      text.includes(normalise(keyword))
    ).length;

    if (groupMatches > 0) {
      score += Math.min(groupMatches * 3, 12);
    }
  });

  if (
    candidateProfile.preferredCountries.some((country) =>
      normalise(job.country).includes(normalise(country))
    )
  ) {
    score += 8;
  }

  if (
    candidateProfile.priorityLocations.some((location) =>
      text.includes(normalise(location))
    )
  ) {
    score += 5;
  }

  if (
    /\bphd\b|doctoral|doktorand|research associate|wissenschaftlicher mitarbeiter|scientific employee/.test(
      text
    )
  ) {
    score += 8;
  }

  if (/english|international|english-speaking|englisch/.test(text)) {
    score += 3;
  }

  candidateProfile.seniorityWarnings.forEach((warning) => {
    if (text.includes(normalise(warning))) {
      score -= 10;
    }
  });

  candidateProfile.languageWarnings.forEach((warning) => {
    if (text.includes(normalise(warning))) {
      score -= 7;
    }
  });

  return Math.max(0, Math.min(100, score));
}

function getScore(job) {
  const savedScore = Number(job.matchScore);

  if (Number.isFinite(savedScore) && savedScore >= 0) {
    return Math.max(0, Math.min(100, savedScore));
  }

  return calculateScore(job);
}

function getTags(job) {
  if (Array.isArray(job.matchedKeywords) && job.matchedKeywords.length > 0) {
    return unique(job.matchedKeywords).slice(0, 8);
  }

  return matchedKeywords(job);
}

function getWarnings(job) {
  if (Array.isArray(job.warnings)) {
    return unique(job.warnings).slice(0, 5);
  }

  const text = getAllJobText(job);

  return unique([
    ...candidateProfile.seniorityWarnings.filter((warning) =>
      text.includes(normalise(warning))
    ),
    ...candidateProfile.languageWarnings.filter((warning) =>
      text.includes(normalise(warning))
    )
  ]).slice(0, 5);
}

function scoreClass(score) {
  if (score >= 80) return "score-high";
  if (score >= 60) return "score-medium";
  return "score-low";
}

function scoreLabel(score) {
  if (score >= 85) return "Apply now";
  if (score >= 70) return "Strong fit";
  if (score >= 60) return "Potential fit";
  return "Selective";
}

function getMatchReason(job, score, tags, warnings) {
  const topTags = tags.slice(0, 5).join(", ");

  let message;

  if (score >= 85) {
    message =
      `High technical overlap with your profile through ${topTags || "relevant MEMS, materials, or medtech skills"}. ` +
      "Prioritize this role and tailor your application around the strongest matching methods and projects.";
  } else if (score >= 70) {
    message =
      `Strong alignment through ${topTags || "relevant engineering skills"}. ` +
      "Review the original posting carefully, then tailor your CV summary and cover letter to its key requirements.";
  } else if (score >= 60) {
    message =
      `Potential fit through ${topTags || "some relevant technical overlap"}. ` +
      "Check the required experience level, language expectations, and whether the role genuinely includes R&D, materials, MEMS, or medical-device work.";
  } else {
    message =
      `Limited or partial overlap through ${topTags || "general engineering terms"}. ` +
      "Apply only if the role is entry-level and its original requirements offer clear development potential.";
  }

  if (warnings.length > 0) {
    message += ` Watch for: ${warnings.join(", ")}.`;
  }

  return message;
}

function formatGeneratedDate(value) {
  if (!value) return "";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "";

  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  });
}

function populateFilters() {
  const sourceJobs = getSourceJobs();

  const currentCountry = countryFilter.value;
  const currentCategory = categoryFilter.value;

  const countries = unique(sourceJobs.map((job) => job.country)).sort();
  const categories = unique(sourceJobs.map((job) => job.category)).sort();

  countryFilter.innerHTML = `<option value="">All countries</option>`;
  categoryFilter.innerHTML = `<option value="">All role types</option>`;

  countries.forEach((country) => {
    countryFilter.insertAdjacentHTML(
      "beforeend",
      `<option value="${escapeHtml(country)}">${escapeHtml(country)}</option>`
    );
  });

  categories.forEach((category) => {
    categoryFilter.insertAdjacentHTML(
      "beforeend",
      `<option value="${escapeHtml(category)}">${escapeHtml(category)}</option>`
    );
  });

  if (countries.includes(currentCountry)) {
    countryFilter.value = currentCountry;
  }

  if (categories.includes(currentCategory)) {
    categoryFilter.value = currentCategory;
  }
}

function renderJobs() {
  const searchTerm = normalise(searchInput.value.trim());
  const selectedCountry = countryFilter.value;
  const selectedCategory = categoryFilter.value;
  const minimumScore = Number(scoreFilter.value);

  const scoredJobs = getSourceJobs()
    .map((job) => {
      const score = getScore(job);
      const tags = getTags(job);
      const warnings = getWarnings(job);

      return {
        ...job,
        score,
        tags,
        warnings
      };
    })
    .filter((job) => {
      const text = getAllJobText(job);

      const matchesSearch =
        !searchTerm ||
        text.includes(searchTerm) ||
        job.tags.some((tag) => normalise(tag).includes(searchTerm));

      const matchesCountry =
        !selectedCountry || job.country === selectedCountry;

      const matchesCategory =
        !selectedCategory || job.category === selectedCategory;

      const matchesMinimumScore = job.score >= minimumScore;

      return (
        matchesSearch &&
        matchesCountry &&
        matchesCategory &&
        matchesMinimumScore
      );
    })
    .sort((first, second) => second.score - first.score);

  const sourceText = liveDataAvailable
    ? "live German vacancy matches"
    : "saved demonstration jobs";

  const updatedText = liveDataAvailable && liveJobsGeneratedAt
    ? ` · Last updated: ${formatGeneratedDate(liveJobsGeneratedAt)}`
    : "";

  resultsSummary.textContent =
    `${scoredJobs.length} ${sourceText} shown${updatedText}`;

  if (scoredJobs.length === 0) {
    jobsContainer.innerHTML = `
      <div class="empty">
        <strong>No roles match these filters.</strong><br>
        Try lowering the match-score filter, changing the search words,
        or wait for the next live-job update.
      </div>
    `;
    return;
  }

  jobsContainer.innerHTML = scoredJobs
    .map((job) => {
      const title = escapeHtml(job.title || "Untitled role");
      const company = escapeHtml(job.company || "Employer not listed");
      const location = escapeHtml(job.location || "Location not listed");
      const category = escapeHtml(job.category || "Job opportunity");
      const type = escapeHtml(job.type || "See original posting");
      const deadline = escapeHtml(job.deadline || "Check original posting");
      const source = escapeHtml(job.source || "Original vacancy source");
      const url = escapeHtml(
        job.url || "https://www.arbeitsagentur.de/jobsuche/"
      );

      const reason = getMatchReason(
        job,
        job.score,
        job.tags,
        job.warnings
      );

      const tagsHtml = job.tags.length
        ? job.tags
            .map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`)
            .join("")
        : `<span class="tag">General engineering</span>`;

      const warningHtml = job.warnings.length
        ? `
          <p class="warning-note">
            <strong>Review before applying:</strong>
            ${job.warnings.map(escapeHtml).join(", ")}
          </p>
        `
        : "";

      return `
        <article class="job-card">
          <div class="job-topline">
            <div>
              <h2>${title}</h2>
              <p class="company">${company}</p>
            </div>

            <div class="score ${scoreClass(job.score)}">
              ${job.score}%<br>
              <small>${scoreLabel(job.score)}</small>
            </div>
          </div>

          <div class="meta">
            <span>📍 ${location}</span>
            <span>💼 ${category}</span>
            <span>🕒 ${type}</span>
            <span>📅 ${deadline}</span>
          </div>

          <div class="job-tags">
            ${tagsHtml}
          </div>

          <p class="match-reason">
            <strong>Why it matches:</strong> ${escapeHtml(reason)}
          </p>

          ${warningHtml}

          <div class="job-footer">
            <small>Source: ${source}</small>

            <a
              class="apply-button"
              href="${url}"
              target="_blank"
              rel="noopener noreferrer"
            >
              View original posting ↗
            </a>
          </div>
        </article>
      `;
    })
    .join("");
}

async function loadLiveJobs() {
  try {
    const response = await fetch("data/live-jobs.json", {
      cache: "no-store"
    });

    if (!response.ok) {
      throw new Error(`Could not load live job data: ${response.status}`);
    }

    const payload = await response.json();

    if (!Array.isArray(payload.jobs)) {
      throw new Error("Live job file does not contain a jobs array.");
    }

    liveJobs = payload.jobs;
    liveJobsGeneratedAt = payload.generatedAt || "";
    liveDataAvailable = liveJobs.length > 0;
  } catch (error) {
    console.warn(
      "Live job data is unavailable. Showing saved jobs from jobs.js instead.",
      error
    );

    liveJobs = [];
    liveJobsGeneratedAt = "";
    liveDataAvailable = false;
  }

  populateFilters();
  renderJobs();
}

[searchInput, countryFilter, categoryFilter, scoreFilter].forEach(
  (element) => {
    element.addEventListener("input", renderJobs);
    element.addEventListener("change", renderJobs);
  }
);

loadLiveJobs();
