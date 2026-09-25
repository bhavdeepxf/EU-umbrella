import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

API_BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
API_KEY = os.getenv("BA_JOBS_API_KEY", "jobboerse-jobsuche")

OUTPUT_FILE = Path("data/live-jobs.json")

SEARCH_TERMS = [
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

SUPPORTING_KEYWORDS = [
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
    "image processing",
    "bildverarbeitung",
    "biomaterials",
    "biomaterialien",
    "sensor",
    "sensorik",
    "acoustic",
    "akustik",
    "ultrasonic",
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

PRIORITY_LOCATIONS = [
    "baden-württemberg",
    "stuttgart",
    "freiburg",
    "tübingen",
    "tuebingen",
    "karlsruhe",
    "ulm",
    "villingen-schwenningen",
    "bayern",
    "bavaria",
    "münchen",
    "munich",
    "nordrhein-westfalen",
    "north rhine-westphalia",
    "berlin",
    "brandenburg",
    "sachsen",
    "saxony",
    "hamburg",
]


def normalise(value):
    return str(value or "").lower()


def unique(items):
    return list(dict.fromkeys(item for item in items if item))


def job_text(job):
    fields = [
        job.get("titel"),
        job.get("beruf"),
        job.get("arbeitgeber"),
        job.get("arbeitsort"),
        job.get("arbeitsort_ort"),
        job.get("stellenangebotsbeschreibung"),
        job.get("beschreibung"),
    ]
    return " ".join(normalise(field) for field in fields)


def matches(text, keywords):
    return [keyword for keyword in keywords if keyword in text]


def calculate_score(job):
    text = job_text(job)

    direct_matches = matches(text, DIRECT_KEYWORDS)
    supporting_matches = matches(text, SUPPORTING_KEYWORDS)
    seniority_matches = matches(text, SENIORITY_WARNINGS)
    language_matches = matches(text, LANGUAGE_WARNINGS)

    score = min(len(direct_matches) * 7, 56)
    score += min(len(supporting_matches) * 3, 24)

    if any(
        term in text
        for term in [
            "phd",
            "doctoral",
            "doktorand",
            "wissenschaftlicher mitarbeiter",
            "research associate",
        ]
    ):
        score += 8

    if any(location in text for location in PRIORITY_LOCATIONS):
        score += 6

    if any(term in text for term in ["english", "international", "englisch"]):
        score += 3

    score -= len(seniority_matches) * 12
    score -= len(language_matches) * 8

    score = max(0, min(100, score))

    return {
        "score": score,
        "matchedKeywords": unique(direct_matches + supporting_matches)[:10],
        "warnings": unique(seniority_matches + language_matches)[:5],
    }


def search_jobs(search_term):
    headers = {
        "X-API-Key": API_KEY,
        "Accept": "application/json",
    }

    params = {
        "was": search_term,
        "angebotsart": 1,
        "page": 1,
        "size": 25,
    }

    response = requests.get(
        f"{API_BASE}/pc/v4/app/jobs",
        headers=headers,
        params=params,
        timeout=30,
    )

    response.raise_for_status()
    response_data = response.json()

    return response_data.get("stellenangebote", [])


def original_job_url(job):
    reference = job.get("refnr") or job.get("referenznummer") or ""

    if reference:
        return (
            "https://www.arbeitsagentur.de/jobsuche/"
            f"suche?angebotsart=1&was={reference}"
        )

    return "https://www.arbeitsagentur.de/jobsuche/"


def safe_location(job):
    city = job.get("arbeitsort_ort") or ""
    postal_code = job.get("arbeitsort_plz") or ""
    location = job.get("arbeitsort") or ""

    return ", ".join(
        item for item in [city, postal_code, location] if item
    ) or "Germany"


def convert_job(job, identifier):
    match = calculate_score(job)

    title = (
        job.get("titel")
        or job.get("beruf")
        or "Untitled vacancy"
    )

    description = (
        job.get("stellenangebotsbeschreibung")
        or job.get("beschreibung")
        or title
    )

    return {
        "id": identifier,
        "title": title,
        "company": job.get("arbeitgeber") or "Employer not listed",
        "location": safe_location(job),
        "country": "Germany",
        "category": "Live German vacancy",
        "type": job.get("arbeitszeit") or "See original vacancy",
        "datePosted": job.get("aktuelleVeroeffentlichungsdatum") or "",
        "deadline": "Check original vacancy",
        "url": original_job_url(job),
        "source": "Bundesagentur für Arbeit Jobsuche",
        "description": description,
        "matchScore": match["score"],
        "matchedKeywords": match["matchedKeywords"],
        "warnings": match["warnings"],
    }


def main():
    collected_jobs = {}

    for term in SEARCH_TERMS:
        try:
            print(f"Searching for: {term}")

            for job in search_jobs(term):
                identifier = (
                    job.get("refnr")
                    or job.get("hashId")
                    or f"{job.get('titel', '')}-{job.get('arbeitgeber', '')}"
                )

                collected_jobs[identifier] = job

        except requests.RequestException as error:
            print(f"Search failed for '{term}': {error}")

    ranked_jobs = []

    for identifier, job in collected_jobs.items():
        converted_job = convert_job(job, identifier)

        if converted_job["matchScore"] >= 25:
            ranked_jobs.append(converted_job)

    ranked_jobs.sort(
        key=lambda job: job["matchScore"],
        reverse=True,
    )

    output = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "count": len(ranked_jobs),
        "jobs": ranked_jobs,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Saved {len(ranked_jobs)} ranked jobs to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
