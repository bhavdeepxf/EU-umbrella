from __future__ import annotations

import html
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"
OUTPUT_FILE = Path("data/live-jobs.json")
MAX_ARBEITNOW_PAGES = 12
MIN_SCORE = 32
MAX_PUBLISHED_JOBS = 100

GREENHOUSE_BOARDS = {
    "Isar Aerospace": "isaraerospace",
    "Element Biosciences": "elementbiosciences",
    "Formlabs": "formlabs",
    "Graphcore": "graphcore",
    "PsiQuantum": "psiquantum",
}

TARGET_COUNTRIES = {
    "germany": "Germany", "deutschland": "Germany", "berlin": "Germany",
    "munich": "Germany", "münchen": "Germany", "hamburg": "Germany",
    "stuttgart": "Germany", "karlsruhe": "Germany", "cologne": "Germany",
    "köln": "Germany", "mannheim": "Germany", "freiburg": "Germany",
    "aachen": "Germany", "dresden": "Germany", "jena": "Germany",
    "netherlands": "Netherlands", "amsterdam": "Netherlands",
    "eindhoven": "Netherlands", "belgium": "Belgium", "leuven": "Belgium",
    "austria": "Austria", "vienna": "Austria", "wien": "Austria",
    "switzerland": "Switzerland", "zurich": "Switzerland", "zürich": "Switzerland",
    "lausanne": "Switzerland", "saint-sulpice": "Switzerland",
    "denmark": "Denmark", "sweden": "Sweden", "finland": "Finland",
    "france": "France", "paris": "France", "ireland": "Ireland",
    "united kingdom": "United Kingdom", "london": "United Kingdom",
    "cambridge": "United Kingdom", "oxford": "United Kingdom", "bristol": "United Kingdom",
    "daresbury": "United Kingdom", "budapest": "Hungary", "hungary": "Hungary",
    "poland": "Poland", "warsaw": "Poland", "prague": "Czechia", "czech": "Czechia",
    "italy": "Italy", "milan": "Italy", "spain": "Spain", "barcelona": "Spain",
    "portugal": "Portugal", "lisbon": "Portugal",
}

OUTSIDE_EUROPE = re.compile(
    r"united states|\busa\b|california|massachusetts|texas|new york|colorado|florida|"
    r"palo alto|milpitas|somerville|boston|austin|san francisco|seattle|chicago|"
    r"canada|toronto|vancouver|australia|sydney|melbourne|india|bengaluru|bangalore|"
    r"singapore|japan|tokyo|china|beijing|shanghai|israel|tel aviv",
    re.I,
)

PRIORITY_LOCATIONS = re.compile(
    r"germany|deutschland|baden.?württemberg|stuttgart|freiburg|karlsruhe|"
    r"tübingen|ulm|villingen|munich|münchen|bavaria|bayern|berlin|dresden|jena",
    re.I,
)

SKILL_GROUPS = {
    "MEMS / microsystems": (r"\bmems\b|microsystem|mikrosystem|microfabrication|mikrofabrikation", 22),
    "AlN / piezoelectric": (r"\baln\b|alumini?um nitride|aluminiumnitrid|piezoelectric|piezoelektr", 20),
    "thin films / deposition": (r"thin[\s-]?film|dünnschicht|atomic layer deposition|\bald\b|sputter|\bpvd\b|\bcvd\b", 18),
    "materials characterization": (r"characteri[sz]ation|charakterisierung|metrology|material analysis|materialanalyse", 16),
    "FTIR / XRD / SEM": (r"\bft[\s-]?ir\b|\bxrd\b|\bsem\b|rasterelektronen|electron microscopy|spectroscop", 16),
    "semiconductor process": (r"semiconductor|halbleiter|wafer|lithograph|cleanroom|reinraum|process development", 14),
    "sensors / acoustics": (r"sensor|acoustic|akustik|ultrasonic|ultraschall|transducer", 13),
    "medical devices / biomedical": (r"medical device|medical technolog|medizintechnik|medizinprodukt|biomedical|biomedizin", 15),
    "verification / quality": (r"verification|validation|verifik|validier|quality assurance|qualitätssicherung|calibrat|kalibrier", 11),
    "medical imaging": (r"medical imaging|medical image|bildgebung|\boct\b|laparoscop|image processing", 12),
    "biomaterials / biointerfaces": (r"biomaterial|biointerface|implant|osseointegration|bioprint", 12),
    "MATLAB / Python / ML": (r"\bmatlab\b|\bpython\b|machine learning|data analysis|signal processing", 8),
    "laboratory engineering": (r"laboratory|laboratory engineer|lab engineer|laboringenieur|failure analysis|tensile", 10),
}

RELEVANT_TITLE = re.compile(
    r"mems|microsystem|microfabrication|thin[\s-]?film|dünnschicht|"
    r"characteri[sz]ation|charakterisierung|materials? engineer|materialwissenschaft|"
    r"semiconductor|wafer|process (?:development )?engineer|sensor|acoustic|"
    r"medical device|medizintechnik|biomedical|medical imaging|clinical engineer|"
    r"validation engineer|verification engineer|quality engineer|laboratory engineer|"
    r"research engineer|research scientist|doctoral|doktorand|\bphd\b|postdoc",
    re.I,
)

UNRELATED_TITLE = re.compile(
    r"sales|marketing|account executive|recruit|talent acquisition|human resources|"
    r"finance|accountant|controller|legal|customer service|frontend|backend|full[\s-]?stack|"
    r"product manager|project manager|business development|brand designer|copywriter",
    re.I,
)

SENIOR_TITLE = re.compile(r"\bsenior\b|\bprincipal\b|\bdirector\b|\bhead of\b|\blead\b|teamleiter", re.I)
STUDENT_TITLE = re.compile(r"working student|werkstudent|internship|praktikum|praktikant", re.I)
LANGUAGE_WARNING = re.compile(
    r"(?:german|deutsch).{0,18}\b[cn]1\b|\b[cn]1\b.{0,18}(?:german|deutsch)|"
    r"verhandlungssicher.{0,12}deutsch|native german",
    re.I,
)

session = requests.Session()
session.headers.update({
    "Accept": "application/json",
    "User-Agent": "EU-Umbrella-personal-job-finder/1.0 (+https://bhavdeepxf.github.io/EU-umbrella/)",
})


def clean_text(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def valid_https_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def infer_country(location: str) -> str:
    folded = location.casefold()
    for clue, country in TARGET_COUNTRIES.items():
        if clue in folded:
            return country
    if "remote" in folded:
        return "Remote / Europe"
    return "Europe"


def is_european_location(location: str, strict: bool = False) -> bool:
    if OUTSIDE_EUROPE.search(location):
        return False
    folded = location.casefold()
    if any(clue in folded for clue in TARGET_COUNTRIES):
        return True
    if "europe" in folded or "emea" in folded or "remote eu" in folded:
        return True
    return not strict


def category_for(title: str, text: str) -> str:
    combined = f"{title} {text}"
    if re.search(r"doctoral|doktorand|\bphd\b|postdoc|postdoctoral", combined, re.I):
        return "PhD / Research"
    if re.search(r"medical device|medizintechnik|biomedical|clinical engineer|medical imaging", combined, re.I):
        return "MedTech / Biomedical"
    if re.search(r"mems|semiconductor|wafer|thin[\s-]?film|characteri[sz]ation|materials", combined, re.I):
        return "MEMS / Materials"
    return "R&D / Engineering"


def score_job(title: str, description: str, location: str, tags: list[str]) -> tuple[int, list[str], list[str]] | None:
    full_text = " ".join([title, description, location, " ".join(tags)])
    title_relevant = bool(RELEVANT_TITLE.search(title))
    if UNRELATED_TITLE.search(title) and not title_relevant:
        return None

    evidence = []
    raw_score = 0
    for label, (pattern, weight) in SKILL_GROUPS.items():
        if re.search(pattern, full_text, re.I):
            evidence.append(label)
            raw_score += weight
            if re.search(pattern, title, re.I):
                raw_score += min(8, max(3, weight // 3))

    if not title_relevant and len(evidence) < 2:
        return None
    if title_relevant:
        raw_score += 18
    if not evidence:
        return None

    warnings = []
    if SENIOR_TITLE.search(title):
        raw_score -= 18
        warnings.append("Senior-level title")
    if STUDENT_TITLE.search(title):
        raw_score -= 18
        warnings.append("Check student-enrolment requirement")
    if LANGUAGE_WARNING.search(description):
        raw_score -= 7
        warnings.append("Check German-language requirement")
    if PRIORITY_LOCATIONS.search(location):
        raw_score += 5

    score = max(0, min(100, raw_score))
    if score < MIN_SCORE:
        return None
    return score, evidence[:10], warnings


def normalize_job(*, identifier: str, title: str, company: str, location: str,
                  description: str, url: str, source: str, job_type: str = "",
                  date_posted: str = "", tags: list[str] | None = None,
                  strict_europe: bool = False) -> dict[str, Any] | None:
    tags = tags or []
    title = clean_text(title)
    company = clean_text(company) or "Employer not listed"
    location = clean_text(location) or "Location in original posting"
    description = clean_text(description)
    if not title or not valid_https_url(url) or not is_european_location(location, strict_europe):
        return None
    result = score_job(title, description, location, tags)
    if result is None:
        return None
    score, evidence, warnings = result
    return {
        "id": identifier,
        "title": title,
        "company": company,
        "location": location,
        "country": infer_country(location),
        "category": category_for(title, description),
        "type": clean_text(job_type) or "See original posting",
        "datePosted": date_posted,
        "deadline": "Check original posting",
        "url": url,
        "source": source,
        "description": description[:3500],
        "matchScore": score,
        "matchedKeywords": evidence,
        "warnings": warnings,
    }


def fetch_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = session.get(url, params=params, timeout=40)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as error:
            last_error = error
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Could not retrieve {url}: {last_error}")


def collect_arbeitnow() -> tuple[list[dict[str, Any]], int]:
    raw_jobs: dict[str, dict[str, Any]] = {}
    next_url: str | None = ARBEITNOW_URL
    pages = 0
    while next_url and pages < MAX_ARBEITNOW_PAGES:
        payload = fetch_json(next_url, {"page": 1} if pages == 0 else None)
        listings = payload.get("data")
        if not isinstance(listings, list):
            raise RuntimeError("Arbeitnow response did not contain a data list")
        pages += 1
        print(f"Arbeitnow page {pages}: {len(listings)} listings")
        for raw in listings:
            key = str(raw.get("slug") or raw.get("url") or "")
            if key:
                raw_jobs[key] = raw
        candidate = (payload.get("links") or {}).get("next")
        next_url = candidate if valid_https_url(candidate) else None

    matches = []
    for key, raw in raw_jobs.items():
        created = raw.get("created_at")
        posted = ""
        if isinstance(created, (int, float)):
            posted = datetime.fromtimestamp(created, timezone.utc).date().isoformat()
        job = normalize_job(
            identifier=f"arbeitnow:{key}",
            title=raw.get("title", ""),
            company=raw.get("company_name", ""),
            location=raw.get("location", ""),
            description=raw.get("description", ""),
            url=raw.get("url", ""),
            source="Arbeitnow",
            job_type=", ".join(map(str, raw.get("job_types") or [])),
            date_posted=posted,
            tags=[str(item) for item in (raw.get("tags") or [])],
        )
        if job:
            matches.append(job)
    return matches, len(raw_jobs)


def collect_greenhouse() -> tuple[list[dict[str, Any]], int]:
    matches = []
    total = 0
    for board_name, token in GREENHOUSE_BOARDS.items():
        try:
            payload = fetch_json(
                f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
                {"content": "true"},
            )
        except RuntimeError as error:
            print(f"Warning: Greenhouse board {token} failed: {error}")
            continue
        listings = payload.get("jobs") or []
        total += len(listings)
        print(f"Greenhouse {board_name}: {len(listings)} listings")
        for raw in listings:
            location = clean_text((raw.get("location") or {}).get("name"))
            offices = raw.get("offices") or []
            if not location and offices:
                location = ", ".join(clean_text(item.get("name")) for item in offices if item.get("name"))
            departments = [clean_text(item.get("name")) for item in (raw.get("departments") or [])]
            job = normalize_job(
                identifier=f"greenhouse:{token}:{raw.get('id')}",
                title=raw.get("title", ""),
                company=board_name,
                location=location,
                description=raw.get("content", ""),
                url=raw.get("absolute_url", ""),
                source=f"{board_name} careers (Greenhouse)",
                date_posted=str(raw.get("updated_at") or "")[:10],
                tags=departments,
                strict_europe=True,
            )
            if job:
                matches.append(job)
    return matches, total


def deduplicate(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for job in jobs:
        key = re.sub(r"\W+", " ", f"{job['title']} {job['company']} {job['location']}".casefold()).strip()
        current = selected.get(key)
        if current is None or job["matchScore"] > current["matchScore"]:
            selected[key] = job
    return list(selected.values())


def main() -> int:
    collected = []
    source_stats: dict[str, int] = {}
    errors = []

    try:
        jobs, count = collect_arbeitnow()
        collected.extend(jobs)
        source_stats["Arbeitnow"] = count
    except RuntimeError as error:
        errors.append(str(error))
        print(f"Warning: {error}")

    jobs, count = collect_greenhouse()
    collected.extend(jobs)
    source_stats["Greenhouse"] = count

    ranked = deduplicate(collected)
    ranked.sort(key=lambda item: (-item["matchScore"], item["title"].casefold()))
    ranked = ranked[:MAX_PUBLISHED_JOBS]

    print(f"Source listings inspected: {source_stats}")
    print(f"CV-matched jobs: {len(ranked)}")

    if not ranked:
        if OUTPUT_FILE.exists():
            print("Warning: no matches found; preserving the previous live-jobs.json.")
            return 0
        print("Error: no matches found and no previous data file exists.", file=sys.stderr)
        return 1

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "count": len(ranked),
        "sourceStats": source_stats,
        "sourceErrors": errors,
        "scoringNote": "Heuristic CV-fit ranking, not a hiring probability.",
        "jobs": ranked,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(ranked)} ranked jobs to {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
