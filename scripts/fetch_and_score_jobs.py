import base64
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

API_BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
API_KEY = os.getenv("BA_JOBS_API_KEY", "jobboerse-jobsuche")
OUTPUT_FILE = Path("data/live-jobs.json")

SEARCH_QUERIES = [
    "MEMS",
    "Mikrosystemtechnik",
    "Dünnschicht",
    "Thin Film",
    "Materialcharakterisierung",
    "FTIR",
    "XRD",
    "SEM",
    "Medizintechnik",
    "Biomedical Engineer",
    "Sensorik",
    "Akustik",
    "Piezoelektrik",
]

DIRECT_KEYWORDS = [
    "aln",
    "aluminum nitride",
    "aluminium nitride",
    "acoustic mems",
    "mems",
    "microsystems",
    "mikrosystemtechnik",
    "piezoelectric",
    "piezoelektr",
    "thin film",
    "dünnschicht",
    "atomic layer deposition",
    "ald",
    "sputtering",
    "pvd",
    "ftir",
    "ft-ir",
    "xrd",
    "sem",
    "wafer bow",
    "materialcharakterisierung",
    "materials characterization",
    "surface characterization",
    "oberflächencharakterisierung",
]

SECONDARY_KEYWORDS = [
    "medical device",
    "medizintechnik",
    "biomedical",
    "verification",
    "verifikation",
    "validation",
    "validierung",
    "quality assurance",
    "qualitätssicherung",
    "calibration",
    "kalibrierung",
    "matlab",
    "python",
    "machine learning",
    "bildverarbeitung",
    "image processing",
    "biomaterials",
    "biomaterialien",
    "sensor",
    "akustik",
    "ultraschall",
]

SENIORITY_WARNINGS = [
    "phd required",
    "promotion erforderlich",
    "senior",
    "principal",
    "lead engineer",
    "manager",
    "director",
    "8 years",
    "10 years",
    "mehrjährige führungserfahrung",
]

LANGUAGE_WARNINGS = [
    "c1 deutsch",
    "deutsch c1",
    "c2 deutsch",
    "deutsch c2",
    "verhandlungssicher deutsch",
]

def normalize(value):
    return (value or "").lower()

def text_for_job(job):
    return " ".join(
        str(job.get(field, ""))
        for field in [
            "titel",
            "beruf",
            "arbeitgeber",
            "arbeitsort",
            "arbeitsort_plz",
            "arbeitsort_ort",
            "stellenangebotsbeschreibung",
            "beschreibung",
        ]
    ).lower()

def count_matches(text, keywords):
    return [keyword for keyword in keywords if keyword in text]

def calculate_score(job):
    text = text_for_job(job)

    direct_matches = count_matches(text, DIRECT_KEYWORDS)
    secondary_matches = count_matches(text, SECONDARY_KEYWORDS)
    seniority_matches = count_matches(text, SENIORITY_WARNINGS)
    language_matches = count_matches(text, LANGUAGE_WARNINGS)

    score = min(len(direct_matches) * 7, 56)
    score += min(len(secondary_matches) * 3, 24)

    if any(term in text for term in ["phd", "doktorand", "doctoral", "wissenschaftlicher mitarbeiter"]):
        score += 8

    if any(term in text for term in ["baden-württemberg", "stuttgart", "freiburg", "tübingen", "karlsruhe", "ulm"]):
        score += 5

    score -= len(seniority_matches) * 12
    score -= len(language_matches) * 8

    return max(0, min(100, score)), direct_matches, secondary_matches, seniority_matches, language_matches

def search_jobs(query):
    headers = {"X-API-Key": API_KEY}
    params = {
        "was": query,
        "angebotsart": 1,
        "size": 25,
        "page": 1,
    }

    response = requests.get(
        f"{API_BASE}/pc/v4/app/jobs",
        headers=headers,
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("stellenangebote", [])

def build_source_url(job):
    ref = job.get("refnr") or job.get("referenznummer") or ""
    if ref:
        return f"https://www.arbeitsagentur.de/jobsuche/suche?angebotsart=1&was={ref}"
    return "https://www.arbeitsagentur.de/jobsuche/"

def main():
    unique_jobs = {}

    for query in SEARCH_QUERIES:
        try:
            for job in search_jobs(query):
                key = job.get("refnr") or job.get("hashId") or f"{job.get('titel', '')}-{job.get('arbeitgeber', '')}"
                unique_jobs[key] = job
        except requests.RequestException as error:
            print(f"Search failed for {query}: {error}")

    output = []

    for key, job in unique_jobs.items():
        score, direct, secondary, seniority, language = calculate_score(job)

        if score < 25:
            continue

        title = job.get("titel") or job.get("beruf") or "Untitled role"
        company = job.get("arbeitgeber") or "Employer not listed"
        location = job.get("arbeitsort_ort") or job.get("arbeitsort") or "Germany"

        output.append(
            {
                "id": key,
                "title": title,
                "company": company,
                "location": location,
                "country": "Germany",
                "category": "Live German vacancy",
                "type": job.get("arbeitszeit") or "See original posting",
                "datePosted": job.get("aktuelleVeroeffentlichungsdatum") or "",
                "deadline": job.get("befristung") or "Check original posting",
                "url": build_source_url(job),
                "source": "Bundesagentur für Arbeit Jobsuche",
                "description": job.get("stellenangebotsbeschreibung")
                or job.get("beruf")
                or title,
                "matchScore": score,
                "matchedKeywords": direct + secondary,
                "warnings": seniority + language,
            }
        )

    output.sort(key=lambda item: item["matchScore"], reverse=True)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(
            {
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "count": len(output),
                "jobs": output,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Wrote {len(output)} ranked jobs to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
