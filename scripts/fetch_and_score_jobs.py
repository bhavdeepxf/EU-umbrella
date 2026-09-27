import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

API_URL = "https://www.arbeitnow.com/api/job-board-api"
OUTPUT = Path("data/live-jobs.json")

MAX_PAGES = 12
MIN_SCORE = 28

CORE = {
    "MEMS": r"\bmems\b|mikrosystemtechnik|microsystem",
    "AlN": r"\baln\b|alumini?um nitride|aluminiumnitrid",
    "thin films": r"thin[\s-]?film|dünnschicht",
    "piezoelectric": r"piezoelektr|piezoelectric",
    "acoustic/ultrasonic": r"akustik|acoustic|ultraschall|ultrasonic",
    "ALD": r"\bald\b|atomic layer deposition",
    "sputtering/PVD": r"sputter|\bpvd\b",
    "FTIR": r"\bft[\s-]?ir\b",
    "XRD": r"\bxrd\b|röntgendiffrakt",
    "SEM": r"\bsem\b|\brem\b|rasterelektronenmikroskop",
    "wafer bow": r"wafer[\s-]?bow|waferkrümmung",
    "materials characterization": (
        r"materialcharakterisierung|materials characterization|"
        r"oberflächencharakterisierung"
    ),
}

SUPPORT = {
    "medical devices": r"medizintechnik|medical device|medizinprodukt|biomedical",
    "verification/validation": r"verifik|validier|validat|verification",
    "quality assurance": r"qualitätssicherung|quality assurance|\bqa\b",
    "calibration": r"kalibrier|calibrat",
    "MATLAB": r"\bmatlab\b",
    "Python": r"\bpython\b",
    "sensors": r"sensorik|\bsensor",
    "biomaterials": r"biomaterial",
    "imaging": r"bildverarbeitung|image processing|medical imaging|\boct\b",
    "laboratory": r"laboratory|lab engineer|laboringenieur",
}

ROLE_TITLE = re.compile(
    r"mems|mikrosystem|dünnschicht|thin[\s-]?film|material|"
    r"sensor|medizintechnik|medical device|biomedical|"
    r"phd|doctoral|doktorand|research|forschung|"
    r"labor|laboratory|characterization|charakterisierung|"
    r"validation|validierung|application engineer|"
    r"applikationsingenieur",
    re.IGNORECASE,
)

EXCLUDED_TITLE = re.compile(
    r"recruit|talent scout|sales|marketing|account manager|"
    r"finance|accounting|customer service|software tester|"
    r"frontend|backend|full[\s-]?stack",
    re.IGNORECASE,
)

STUDENT_TITLE = re.compile(
    r"working student|werkstudent|internship|praktikum|praktikant",
    re.IGNORECASE,
)

SENIOR_TITLE = re.compile(
    r"\bsenior\b|\bprincipal\b|\bdirector\b|"
    r"\bhead of\b|\bteam lead\b|\bteamleiter\b",
    re.IGNORECASE,
)

GERMAN_C1 = re.compile(
    r"(?:deutsch|german)\s*c[12]\b|"
    r"\bc[12]\s*(?:deutsch|german)\b|"
    r"verhandlungssicher(?:e|es|en|er)?\s+deutsch",
    re.IGNORECASE,
)

PRIORITY_LOCATION = re.compile(
    r"baden-württemberg|stuttgart|freiburg|karlsruhe|"
    r"tübingen|villingen-schwenningen|ulm|münchen|munich|"
    r"bayern|bavaria",
    re.IGNORECASE,
)

session = requests.Session()
session.headers.update({"Accept": "application/json"})


def clean_text(value):
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def match_labels(text, patterns):
    return [
        label
        for label, pattern in patterns.items()
        if re.search(pattern, text, re.IGNORECASE)
    ]


def fetch_page(page):
    response = session.get(
        API_URL,
        params={"page": page},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()

    if not isinstance(payload.get("data"), list):
        raise ValueError(
            f"Page {page} did not contain a data list; "
            f"response keys: {list(payload)[:10]}"
        )

    return payload


def score_job(raw):
    title = clean_text(raw.get("title"))
    description = clean_text(raw.get("description"))
    location = clean_text(raw.get("location"))

    # A matching word buried in a long description is not enough:
    # require a relevant role title or multiple core skill matches.
    core_matches = match_labels(f"{title} {description}", CORE)
    support_matches = match_labels(f"{title} {description}", SUPPORT)
    relevant_title = bool(ROLE_TITLE.search(title))

    if EXCLUDED_TITLE.search(title):
        return None

    if not relevant_title and len(core_matches) < 2:
        return None

    if not core_matches and len(support_matches) < 2:
        return None

    score = min(len(core_matches) * 11, 55)
    score += min(len(support_matches) * 4, 24)

    if relevant_title:
        score += 10

    if re.search(r"phd|doctoral|doktorand|research associate", title, re.I):
        score += 6

    if PRIORITY_LOCATION.search(location):
        score += 5

    warnings = []

    if STUDENT_TITLE.search(title):
        score -= 25
        warnings.append("Requires current student eligibility")

    if SENIOR_TITLE.search(title):
        score -= 25
        warnings.append("Senior-level title")

    if GERMAN_C1.search(description):
        score -= 8
        warnings.append("Check German-language requirement")

    score = max(0, min(100, score))

    if score < MIN_SCORE:
        return None

    url = raw.get("url")
    if not isinstance(url, str) or urlparse(url).scheme != "https":
        return None

    timestamp = raw.get("created_at")
    posted = ""
    if isinstance(timestamp, (int, float)):
        posted = datetime.fromtimestamp(
            timestamp, timezone.utc
        ).date().isoformat()

    job_types = raw.get("job_types") or []

    return {
        "id": str(raw.get("slug") or url),
        "title": title,
        "company": clean_text(raw.get("company_name")) or "Employer not listed",
        "location": location or "Check posting",
        "country": "Germany / Europe—verify location",
        "category": "Live European vacancy",
        "type": ", ".join(map(str, job_types)) or "See original posting",
        "datePosted": posted,
        "deadline": "Check original posting",
        "url": url,
        "source": "Arbeitnow job-board API",
        "description": description[:2500],
        "matchScore": score,
        "matchedKeywords": (core_matches + support_matches)[:10],
        "warnings": warnings,
    }


def main():
    unique_jobs = {}
    pages_fetched = 0

    for page in range(1, MAX_PAGES + 1):
        try:
            payload = fetch_page(page)
        except (requests.RequestException, ValueError) as error:
            print(f"Page {page} failed: {error}")
            if pages_fetched == 0:
                raise SystemExit(
                    "Job API is unavailable; preserving the deployed site."
                )
            break

        listings = payload["data"]
        pages_fetched += 1
        print(f"Page {page}: {len(listings)} listings")

        for raw in listings:
            identifier = raw.get("slug") or raw.get("url")
            if identifier:
                unique_jobs[identifier] = raw

        if not listings:
            break

ranked = []
sample_titles = []
technical_candidates = []

for raw in unique_jobs.values():
    title = clean_text(raw.get("title"))
    description = clean_text(raw.get("description"))
    tags = raw.get("tags") or []

    if len(sample_titles) < 12:
        sample_titles.append(title)

    core_matches = match_labels(
        f"{title} {description} {' '.join(map(str, tags))}",
        CORE,
    )
    support_matches = match_labels(
        f"{title} {description} {' '.join(map(str, tags))}",
        SUPPORT,
    )

    if core_matches or support_matches:
        technical_candidates.append({
            "title": title,
            "core": core_matches[:5],
            "support": support_matches[:5],
            "excluded_title": bool(EXCLUDED_TITLE.search(title)),
            "relevant_title": bool(ROLE_TITLE.search(title)),
        })

    result = score_job(raw)
    if result:
        ranked.append(result)

print("Sample titles:", json.dumps(sample_titles, ensure_ascii=False))
print(
    "Listings with at least one CV-related term:",
    len(technical_candidates),
)
print(
    "First 15 technical candidates:",
    json.dumps(technical_candidates[:15], ensure_ascii=False),
)

    ranked.sort(key=lambda item: item["matchScore"], reverse=True)

    print(
        f"Fetched {pages_fetched} pages; "
        f"{len(unique_jobs)} unique listings; "
        f"{len(ranked)} jobs passed the CV filter."
    )

    if not ranked:
        raise SystemExit(
            "No relevant jobs found. The site will not be overwritten "
            "with empty or fabricated results."
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(
            {
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "count": len(ranked),
                "jobs": ranked,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Saved {len(ranked)} ranked jobs to {OUTPUT}")


if __name__ == "__main__":
    main()
