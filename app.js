const searchInput = document.getElementById("searchInput");
const countryFilter = document.getElementById("countryFilter");
const categoryFilter = document.getElementById("categoryFilter");
const scoreFilter = document.getElementById("scoreFilter");
const jobsContainer = document.getElementById("jobsContainer");
const resultsSummary = document.getElementById("resultsSummary");

function normalise(text) {
  return (text || "").toLowerCase();
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
      job.description
    ].join(" ")
  );
}

function unique(items) {
  return [...new Set(items)];
}

function matchedKeywords(job) {
  const text = getAllJobText(job);
  const matches = [];

  Object.values(candidateProfile.roleGroups).flat().forEach((keyword) => {
    if (text.includes(keyword.toLowerCase())) {
      matches.push(keyword);
    }
  });

  return unique(matches).slice(0, 8);
}

function calculateScore(job) {
  const text = getAllJobText(job);
  let score = 0;

  candidateProfile.directMatchKeywords.forEach((keyword) => {
    if (text.includes(keyword.toLowerCase())) {
      score += 6;
    }
  });

  Object.values(candidateProfile.roleGroups).forEach((keywords) => {
    const groupMatches = keywords.filter((keyword) =>
      text.includes(keyword.toLowerCase())
    ).length;

    if (groupMatches > 0) {
      score += Math.min(groupMatches * 3, 12);
    }
  });

  if (
    candidateProfile.preferredCountries.some((country) =>
      normalise(job.country).includes(country.toLowerCase())
    )
  ) {
    score += 8;
  }

  if (
    candidateProfile.priorityLocations.some((location) =>
      text.includes(location.toLowerCase())
    )
  ) {
    score += 5;
  }

  if (
    /\bphd\b|doctoral|doktorand|research associate|wissenschaftlicher mitarbeiter/.test(
      text
    )
  ) {
    score += 8;
  }

  if (/english|international|english-speaking/.test(text)) {
    score += 3;
  }

  candidateProfile.seniorityWarnings.forEach((warning) => {
    if (text.includes(warning.toLowerCase())) {
      score -= 10;
    }
  });

  candidateProfile.languageWarnings.forEach((warning) => {
    if (text.includes(warning.toLowerCase())) {
      score -= 7;
    }
  });

  return Math.max(0, Math.min(100, score));
}

function getMatchReason(job, score, tags) {
  const topTags = tags.slice(0, 5);

  if (score >= 80) {
    return `Excellent technical overlap: ${topTags.join(", ")}. This role aligns strongly with your MEMS, thin-film, characterization, and medical-technology background.`;
  }

  if (score >= 60) {
    return `Good match through ${topTags.join(", ")}. Review the experience and language requirements before applying.`;
  }

  return `Partial relevance through ${topTags.join(", ") || "general engineering"}. Apply only if the original vacancy has suitable entry-level requirements.`;
}

function scoreClass(score) {
  if (score >= 80) return "score-high";
  if (score >= 60) return "score-medium";
  return "score-low";
}

function scoreLabel(score) {
  if (score >= 80) return "High fit";
  if (score >= 60) return "Potential fit";
  return "Selective";
}

function renderJobs() {
  const searchTerm = normalise(searchInput.value);
  const country = countryFilter.value;
  const category = categoryFilter.value;
  const minimumScore = Number(scoreFilter.value);

  const scoredJobs = jobs
    .map((job) => {
      const score = calculateScore(job);
      const tags = matchedKeywords(job);

      return { ...job, score, tags };
    })
    .filter((job) => {
      const text = getAllJobText(job);

      const matchesSearch =
        !searchTerm ||
        text.includes(searchTerm) ||
        job.tags.some((tag) => tag.includes(searchTerm));

      const matchesCountry = !country || job.country === country;
      const matchesCategory = !category || job.category === category;
      const matchesScore = job.score >= minimumScore;

      return (
        matchesSearch &&
        matchesCountry &&
        matchesCategory &&
        matchesScore
      );
    })
    .sort((a, b) => b.score - a.score);

  resultsSummary.textContent =
    `${scoredJobs.length} matching opportunit${scoredJobs.length === 1 ? "y" : "ies"} shown`;

  if (!scoredJobs.length) {
    jobsContainer.innerHTML = `
      <div class="empty">
        No roles match these filters yet. Try a lower score threshold or add new roles to <code>jobs.js</code>.
      </div>
    `;
    return;
  }

  jobsContainer.innerHTML = scoredJobs
    .map((job) => {
      const reason = getMatchReason(job, job.score, job.tags);

      return `
        <article class="job-card">
          <div class="job-topline">
            <div>
              <h2>${job.title}</h2>
              <p class="company">${job.company}</p>
            </div>

            <div class="score ${scoreClass(job.score)}">
              ${job.score}%<br>
              <small>${scoreLabel(job.score)}</small>
            </div>
          </div>

          <div class="meta">
            <span>📍 ${job.location}</span>
            <span>💼 ${job.category}</span>
            <span>🕒 ${job.type}</span>
            <span>📅 ${job.deadline}</span>
          </div>

          <div class="job-tags">
            ${job.tags.map((tag) => `<span class="tag">${tag}</span>`).join("")}
          </div>

          <p class="match-reason">
            <strong>Why it matches:</strong> ${reason}
          </p>

          <div class="job-footer">
            <small>Source: ${job.source}</small>

            <a
              class="apply-button"
              href="${job.url}"
              target="_blank"
              rel="noopener noreferrer"
            >
              View / Apply ↗
            </a>
          </div>
        </article>
      `;
    })
    .join("");
}

function populateFilters() {
  const countries = unique(jobs.map((job) => job.country)).sort();
  const categories = unique(jobs.map((job) => job.category)).sort();

  countries.forEach((country) => {
    countryFilter.insertAdjacentHTML(
      "beforeend",
      `<option value="${country}">${country}</option>`
    );
  });

  categories.forEach((category) => {
    categoryFilter.insertAdjacentHTML(
      "beforeend",
      `<option value="${category}">${category}</option>`
    );
  });
}

[searchInput, countryFilter, categoryFilter, scoreFilter].forEach(
  (element) => {
    element.addEventListener("input", renderJobs);
    element.addEventListener("change", renderJobs);
  }
);

populateFilters();
renderJobs();
