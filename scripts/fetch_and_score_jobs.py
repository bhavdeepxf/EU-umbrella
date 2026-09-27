from __future__ import annotations

import html
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import requests

OUTPUT_FILE = Path("data/live-jobs.json")
MAX_JOBS = 300
MIN_TECHNICAL_FIT = 28

GREENHOUSE_BOARDS = {
    "Isar Aerospace": "isaraerospace",
    "Element Biosciences": "elementbiosciences",
    "Formlabs": "formlabs",
    "Graphcore": "graphcore",
    "PsiQuantum": "psiquantum",
    "Wayve": "wayve",
    "PathAI": "pathai",
}

ASHBY_BOARDS = {
    "Black Semiconductor": "blacksemiconductor",
    "Kandou AI": "kandou-ai",
    "Axelera AI": "axelera",
    "Neko Health": "neko-health",
    "Orbem": "orbem",
    "Rematiq": "rematiq-gmbh",
    "Tandem Health": "tandem-health",
    "Owkin": "owkin",
    "Triomics": "triomics",
    "Lumilens": "lumilens",
    "Scarlet": "scarlet",
    "Sonio": "Sonio",
}

COUNTRY_CLUES = {
    "Germany": ["germany", "deutschland", "berlin", "munich", "münchen", "hamburg", "stuttgart", "karlsruhe", "aachen", "dresden", "jena", "dortmund", "cologne", "köln", "freiburg", "tübingen", "ulm", "bavaria", "bayern"],
    "India": ["india", "bengaluru", "bangalore", "hyderabad", "pune", "chennai", "mumbai", "delhi", "gurugram", "gurgaon", "noida", "ahmedabad", "coimbatore"],
    "United Kingdom": ["united kingdom", "london", "cambridge", "bristol", "oxford", "daresbury", "england", "scotland", "reading"],
    "Switzerland": ["switzerland", "schweiz", "zurich", "zürich", "lausanne", "saint-sulpice", "basel"],
    "Netherlands": ["netherlands", "amsterdam", "eindhoven", "delft", "utrecht"],
    "Belgium": ["belgium", "leuven", "brussels", "ghent"],
    "Austria": ["austria", "vienna", "wien", "graz"],
    "France": ["france", "paris", "grenoble", "lyon", "toulouse"],
    "Sweden": ["sweden", "stockholm", "gothenburg", "lund"],
    "Denmark": ["denmark", "copenhagen", "aarhus"],
    "Finland": ["finland", "helsinki", "espoo"],
    "Ireland": ["ireland", "dublin", "cork", "galway"],
    "Italy": ["italy", "milan", "rome", "turin"],
    "Spain": ["spain", "madrid", "barcelona"],
    "Poland": ["poland", "warsaw", "krakow", "wroclaw"],
    "Czechia": ["czech", "prague", "brno"],
    "Hungary": ["hungary", "budapest"],
    "Portugal": ["portugal", "lisbon", "porto"],
    "Norway": ["norway", "oslo", "trondheim"],
}
EUROPE_COUNTRIES = set(COUNTRY_CLUES) - {"India"}
OUT_OF_SCOPE = re.compile(r"united states|\busa\b|california|texas|massachusetts|new york|canada|australia|singapore|japan|china|israel|south korea|taiwan", re.I)
REMOTE_GLOBAL = re.compile(r"worldwide|anywhere|global remote|remote.*(?:europe|eu|emea|india)|(?:europe|eu|emea|india).*remote", re.I)

FAMILIES = {
    "Semiconductor & MEMS": {
        "patterns": [r"\bmems\b", r"microsystem", r"microfabrication", r"semiconductor", r"wafer", r"cleanroom", r"lithograph", r"photonic", r"silicon", r"chiplet", r"process integration"],
        "labels": ["MEMS", "microsystems", "microfabrication", "semiconductors", "wafer processing", "cleanroom", "lithography", "photonics", "silicon", "process integration"],
    },
    "Thin Films & Materials": {
        "patterns": [r"thin[\s-]?film", r"dünnschicht", r"\baln\b", r"alumini?um nitride", r"atomic layer deposition|\bald\b", r"sputter", r"\bpvd\b|\bcvd\b", r"materials? characteri[sz]", r"surface characteri[sz]", r"metrology", r"\bxrd\b|\bft[\s-]?ir\b|electron microscopy|\bsem\b"],
        "labels": ["thin films", "AlN", "ALD", "sputtering", "PVD/CVD", "materials characterization", "surface analysis", "metrology", "XRD/FTIR/SEM"],
    },
    "Biomedical & MedTech": {
        "patterns": [r"biomedical", r"medical device", r"medical technolog", r"medizintechnik", r"medizinprodukt", r"medical imaging", r"clinical engineer", r"diagnostic", r"surgical", r"healthcare", r"biomaterial", r"implant", r"biointerface", r"laboratory instrument"],
        "labels": ["biomedical engineering", "medical devices", "medtech", "medical imaging", "clinical engineering", "diagnostics", "surgical systems", "healthcare", "biomaterials", "laboratory instrumentation"],
    },
    "Quality, Test & Validation": {
        "patterns": [r"verification", r"validation", r"quality engineer", r"quality assurance", r"quality control", r"calibrat", r"failure analysis", r"reliability", r"test engineer", r"hardware test", r"system test", r"compliance", r"iso 13485", r"eu mdr|medical device regulation"],
        "labels": ["verification", "validation", "quality engineering", "QA/QC", "calibration", "failure analysis", "reliability", "test engineering", "compliance", "ISO 13485/EU MDR"],
    },
    "Research & Data": {
        "patterns": [r"research engineer", r"research scientist", r"doctoral|doktorand|\bphd\b|postdoc", r"r&d engineer", r"matlab", r"python", r"data analysis", r"machine learning", r"image processing", r"signal processing", r"spectroscop", r"microscopy"],
        "labels": ["research engineering", "PhD/research", "R&D", "MATLAB", "Python", "data analysis", "machine learning", "image processing", "signal processing", "spectroscopy/microscopy"],
    },
    "Clinical Equipment & Service": {
        "patterns": [r"field service engineer", r"service engineer", r"clinical equipment", r"medical equipment", r"technical service", r"maintenance engineer", r"equipment engineer", r"applications engineer"],
        "labels": ["field service", "clinical equipment", "medical equipment", "technical service", "maintenance", "equipment engineering", "applications engineering"],
    },
}

RELEVANT_TITLE = re.compile(
    r"mems|microsystem|microfabrication|semiconductor|silicon|wafer|photon|thin[\s-]?film|materials?|characteri[sz]ation|metrology|process|test|validation|verification|quality|reliability|failure analysis|biomedical|medical|clinical|imaging|laboratory|equipment|field service|application|research|scientist|doctoral|doktorand|\bphd\b|r&d|sensor|acoustic|optical|hardware|manufacturing|npi|regulatory|compliance",
    re.I,
)
HARD_EXCLUDE_TITLE = re.compile(r"sales|account executive|recruit|talent|human resources|finance|accountant|controller|legal counsel|marketing|copywriter|graphic design|frontend|backend|full[\s-]?stack|product manager|business development|category manager|procurement", re.I)
SENIORITY = [
    (re.compile(r"chief|vice president|\bvp\b|director|head of", re.I), 35, "Leadership-level title"),
    (re.compile(r"principal|staff engineer|expert engineer|\blead\b|manager", re.I), 24, "Advanced seniority title"),
    (re.compile(r"\bsenior\b|\bsr\.?\b|smts", re.I), 14, "Senior-level title"),
]
STUDENT_ONLY = re.compile(r"working student|werkstudent|student assistant|internship|intern\b|praktikum|praktikant", re.I)
JUNIOR_SIGNAL = re.compile(r"junior|graduate|entry[\s-]?level|associate|early career|trainee", re.I)
PHD_SIGNAL = re.compile(r"doctoral|doktorand|\bphd (?:position|candidate|student)\b", re.I)
GERMAN_HARD = re.compile(r"(?:german|deutsch).{0,24}\b(?:c1|c2|native|mother tongue)\b|\b(?:c1|c2)\b.{0,24}(?:german|deutsch)|verhandlungssicher.{0,16}deutsch", re.I)
GERMAN_SOFT = re.compile(r"german (?:is )?(?:preferred|advantage|plus)|deutsch.{0,12}(?:wünschenswert|von vorteil)", re.I)
ENGLISH_SIGNAL = re.compile(r"fluent english|english required|working language.{0,12}english|business fluent english", re.I)
DEGREE_MATCH = re.compile(r"biomedical|materials? science|physics|medical engineering|engineering or related|natural science|applied science|microtechnology|nanotechnology", re.I)

session = requests.Session()
session.headers.update({"Accept": "application/json", "User-Agent": "EU-Umbrella-personal-career-radar/2.0"})


def clean(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def https_url(value: Any) -> bool:
    try:
        parsed = urlparse(str(value))
        return parsed.scheme == "https" and bool(parsed.netloc)
    except ValueError:
        return False


def fetch_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    error: Exception | None = None
    for attempt in range(3):
        try:
            response = session.get(url, params=params, timeout=45)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Could not retrieve {url}: {error}")


def location_scope(location: str) -> tuple[str, str] | None:
    folded = location.casefold()
    for country, clues in COUNTRY_CLUES.items():
        if any(clue in folded for clue in clues):
            return country, "India" if country == "India" else ("Germany" if country == "Germany" else "Europe")
    if REMOTE_GLOBAL.search(location):
        return "Remote / Global", "Remote"
    if OUT_OF_SCOPE.search(location):
        return None
    return None


def detect_matches(title: str, description: str, tags: list[str]) -> tuple[dict[str, int], list[str]]:
    full = " ".join([title, description, *tags])
    family_points: dict[str, int] = {}
    labels: list[str] = []
    for family, config in FAMILIES.items():
        points = 0
        for pattern, label in zip(config["patterns"], config["labels"]):
            if re.search(pattern, full, re.I):
                labels.append(label)
                points += 7
                if re.search(pattern, title, re.I):
                    points += 6
        if points:
            family_points[family] = min(45, points)
    return family_points, list(dict.fromkeys(labels))


def experience_requirement(text: str) -> int | None:
    opening = text[:7000]
    values = []
    for match in re.finditer(r"(?:minimum|min\.?|at least)?\s*(\d{1,2})(?:\s*[-–]\s*\d{1,2})?\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:relevant\s+)?experience", opening, re.I):
        value = int(match.group(1))
        if 0 < value < 30:
            values.append(value)
    return min(values) if values else None


def score_job(title: str, description: str, location: str, tags: list[str], job_type: str) -> dict[str, Any] | None:
    if HARD_EXCLUDE_TITLE.search(title):
        return None
    family_points, evidence = detect_matches(title, description, tags)
    if not family_points:
        return None
    anchor_families = {"Semiconductor & MEMS", "Thin Films & Materials", "Biomedical & MedTech", "Clinical Equipment & Service"}
    has_domain_anchor = bool(anchor_families.intersection(family_points))
    context_anchor = bool(re.search(
        r"semiconductor|wafer|mems|microfabrication|thin[\s-]?film|materials? characteri[sz]|"
        r"biomedical|medical device|medical imaging|medtech|clinical equipment|diagnostic|"
        r"laboratory instrument|photonics?|optical hardware|sensor hardware",
        f"{title} {description}", re.I,
    ))
    if not has_domain_anchor and not context_anchor:
        return None
    title_relevant = bool(RELEVANT_TITLE.search(title))
    if not title_relevant and sum(family_points.values()) < 26:
        return None

    ranked_families = sorted(family_points, key=family_points.get, reverse=True)
    technical = min(100, 22 + sum(sorted(family_points.values(), reverse=True)[:3]))
    if title_relevant:
        technical = min(100, technical + 8)
    if technical < MIN_TECHNICAL_FIT:
        return None

    full = f"{title} {description}"
    readiness = 62
    warnings: list[str] = []
    strengths: list[str] = []

    if JUNIOR_SIGNAL.search(title):
        readiness += 14
        strengths.append("Early-career level")
    if PHD_SIGNAL.search(title):
        readiness += 10
        strengths.append("MSc-to-PhD progression")
    if STUDENT_ONLY.search(title):
        readiness -= 18
        warnings.append("Check student-enrolment eligibility")
    for pattern, penalty, warning in SENIORITY:
        if pattern.search(title):
            readiness -= penalty
            warnings.append(warning)
            break

    years = experience_requirement(full)
    if years is not None:
        if years <= 3:
            readiness += 10
            strengths.append(f"Experience request around {years} years")
        elif years <= 5:
            readiness -= 2
        elif years <= 7:
            readiness -= 14
            warnings.append(f"Posting asks for about {years}+ years")
        else:
            readiness -= 24
            warnings.append(f"Posting asks for about {years}+ years")

    if DEGREE_MATCH.search(description):
        readiness += 8
        strengths.append("Related MSc background")
    if GERMAN_HARD.search(description):
        readiness -= 13
        warnings.append("Advanced German may be required")
    elif GERMAN_SOFT.search(description):
        readiness -= 2
        warnings.append("German is preferred")
    if ENGLISH_SIGNAL.search(description):
        readiness += 4
        strengths.append("English-language fit")

    scope = location_scope(location)
    if not scope:
        return None
    country, region = scope
    if region == "Germany":
        readiness += 8
        strengths.append("Germany priority")
    elif region == "India":
        readiness += 6
        strengths.append("India priority")
    elif region == "Europe":
        readiness += 3
    elif region == "Remote":
        readiness += 2

    readiness = max(0, min(100, readiness))
    overall = round(technical * 0.64 + readiness * 0.36)
    return {
        "technicalFit": technical,
        "attainability": readiness,
        "matchScore": overall,
        "matchedKeywords": evidence[:12],
        "roleFamilies": ranked_families[:3],
        "primaryFamily": ranked_families[0],
        "strengths": list(dict.fromkeys(strengths))[:5],
        "warnings": list(dict.fromkeys(warnings))[:5],
        "country": country,
        "region": region,
        "experienceRequired": years,
    }


def normalize(*, identifier: str, title: Any, company: Any, location: Any, description: Any,
              url: Any, source: str, job_type: Any = "", date_posted: Any = "",
              tags: list[str] | None = None) -> dict[str, Any] | None:
    title, company, location = clean(title), clean(company), clean(location)
    description, job_type = clean(description), clean(job_type)
    tags = [clean(tag) for tag in (tags or []) if clean(tag)]
    if not title or not https_url(url):
        return None
    scores = score_job(title, description, location, tags, job_type)
    if not scores:
        return None
    return {
        "id": identifier, "title": title, "company": company or "Employer not listed",
        "location": location, "category": scores["primaryFamily"], "type": job_type or "See posting",
        "datePosted": str(date_posted or "")[:10], "url": str(url), "source": source,
        "description": description[:5000], **scores,
    }


def collect_arbeitnow() -> tuple[list[dict[str, Any]], int]:
    raw_jobs: dict[str, dict[str, Any]] = {}
    next_url: str | None = "https://www.arbeitnow.com/api/job-board-api?page=1"
    pages = 0
    while next_url and pages < 15:
        payload = fetch_json(next_url)
        listings = payload.get("data")
        if not isinstance(listings, list):
            raise RuntimeError("Arbeitnow did not return a data list")
        pages += 1
        for raw in listings:
            key = str(raw.get("slug") or raw.get("url") or "")
            if key:
                raw_jobs[key] = raw
        candidate = (payload.get("links") or {}).get("next")
        next_url = candidate if https_url(candidate) else None
    matches = []
    for key, raw in raw_jobs.items():
        posted = ""
        if isinstance(raw.get("created_at"), (int, float)):
            posted = datetime.fromtimestamp(raw["created_at"], timezone.utc).date().isoformat()
        job = normalize(
            identifier=f"arbeitnow:{key}", title=raw.get("title"), company=raw.get("company_name"),
            location=raw.get("location"), description=raw.get("description"), url=raw.get("url"),
            source="Arbeitnow", job_type=", ".join(map(str, raw.get("job_types") or [])),
            date_posted=posted, tags=[str(x) for x in (raw.get("tags") or [])],
        )
        if job:
            matches.append(job)
    return matches, len(raw_jobs)


def collect_greenhouse() -> tuple[list[dict[str, Any]], int, list[str]]:
    matches, inspected, failures = [], 0, []
    for company, token in GREENHOUSE_BOARDS.items():
        try:
            listings = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{quote(token)}/jobs", {"content": "true"}).get("jobs") or []
            inspected += len(listings)
            for raw in listings:
                location = clean((raw.get("location") or {}).get("name"))
                tags = [clean(item.get("name")) for item in (raw.get("departments") or [])]
                job = normalize(
                    identifier=f"greenhouse:{token}:{raw.get('id')}", title=raw.get("title"), company=company,
                    location=location, description=raw.get("content"), url=raw.get("absolute_url"),
                    source=f"{company} careers · Greenhouse", date_posted=raw.get("updated_at"), tags=tags,
                )
                if job:
                    matches.append(job)
        except RuntimeError as exc:
            failures.append(f"{company}: {exc}")
    return matches, inspected, failures


def collect_ashby() -> tuple[list[dict[str, Any]], int, list[str]]:
    matches, inspected, failures = [], 0, []
    for company, token in ASHBY_BOARDS.items():
        try:
            listings = fetch_json(f"https://api.ashbyhq.com/posting-api/job-board/{quote(token)}", {"includeCompensation": "true"}).get("jobs") or []
            inspected += len(listings)
            for raw in listings:
                if raw.get("isListed") is False:
                    continue
                location_parts = [clean(raw.get("location"))]
                location_parts += [clean(x.get("location")) for x in (raw.get("secondaryLocations") or [])]
                location = "; ".join(dict.fromkeys(x for x in location_parts if x))
                tags = [clean(raw.get("department")), clean(raw.get("team"))]
                job = normalize(
                    identifier=f"ashby:{token}:{raw.get('jobUrl')}", title=raw.get("title"), company=company,
                    location=location, description=raw.get("descriptionPlain") or raw.get("descriptionHtml"),
                    url=raw.get("jobUrl") or raw.get("applyUrl"), source=f"{company} careers · Ashby",
                    job_type=" · ".join(x for x in [clean(raw.get("employmentType")), clean(raw.get("workplaceType"))] if x),
                    date_posted=raw.get("publishedAt"), tags=tags,
                )
                if job:
                    compensation = (raw.get("compensation") or {}).get("scrapeableCompensationSalarySummary")
                    if compensation:
                        job["compensation"] = clean(compensation)
                    matches.append(job)
        except RuntimeError as exc:
            failures.append(f"{company}: {exc}")
    return matches, inspected, failures


def collect_remotive() -> tuple[list[dict[str, Any]], int, list[str]]:
    try:
        listings = fetch_json("https://remotive.com/api/remote-jobs", {"limit": 200}).get("jobs") or []
    except RuntimeError as exc:
        return [], 0, [str(exc)]
    matches = []
    for raw in listings:
        location = clean(raw.get("candidate_required_location") or "Remote / Global")
        job = normalize(
            identifier=f"remotive:{raw.get('id')}", title=raw.get("title"), company=raw.get("company_name"),
            location=location, description=raw.get("description"), url=raw.get("url"), source="Remotive",
            job_type=raw.get("job_type"), date_posted=raw.get("publication_date"), tags=[clean(raw.get("category"))],
        )
        if job:
            matches.append(job)
    return matches, len(listings), []


def deduplicate(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for job in jobs:
        key = re.sub(r"\W+", " ", f"{job['title']} {job['company']} {job['location']}".casefold()).strip()
        current = result.get(key)
        if current is None or job["matchScore"] > current["matchScore"]:
            result[key] = job
    return list(result.values())


def main() -> int:
    all_jobs, stats, failures = [], {}, []
    collectors = [
        ("Arbeitnow", lambda: (*collect_arbeitnow(), [])),
        ("Greenhouse employers", collect_greenhouse),
        ("Ashby employers", collect_ashby),
        ("Remotive", collect_remotive),
    ]
    for name, collector in collectors:
        try:
            jobs, inspected, source_failures = collector()
            all_jobs.extend(jobs)
            stats[name] = {"inspected": inspected, "matched": len(jobs)}
            failures.extend(source_failures)
            print(f"{name}: inspected {inspected}, matched {len(jobs)}")
        except Exception as exc:
            failures.append(f"{name}: {exc}")
            print(f"Warning: {name} failed: {exc}")

    ranked = deduplicate(all_jobs)
    ranked.sort(key=lambda item: (-item["matchScore"], -item["technicalFit"], -item["attainability"], item["title"].casefold()))
    ranked = ranked[:MAX_JOBS]
    if not ranked:
        if OUTPUT_FILE.exists():
            print("No new matches; preserving previous live-jobs.json")
            return 0
        print("No publishable jobs and no previous data file", file=sys.stderr)
        return 1

    by_region: dict[str, int] = {}
    by_family: dict[str, int] = {}
    for job in ranked:
        by_region[job["region"]] = by_region.get(job["region"], 0) + 1
        by_family[job["primaryFamily"]] = by_family.get(job["primaryFamily"], 0) + 1

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(), "count": len(ranked),
        "sourceStats": stats, "sourceFailures": failures,
        "coverage": {"regions": by_region, "families": by_family},
        "scoringNote": "Overall rank is 64% technical fit and 36% attainability. It is not a hiring probability.",
        "jobs": ranked,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(ranked)} jobs; regions={by_region}; families={by_family}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
