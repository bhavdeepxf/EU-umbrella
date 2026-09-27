import base64
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
OUTPUT = Path("data/live-jobs.json")
MIN_SCORE = 20
MAX_DETAIL_REQUESTS = 80

SEARCH_TERMS = [
    "MEMS",
    "Mikrosystemtechnik",
    "Dünnschicht",
    "Materialcharakterisierung",
    "FTIR",
    "Medizintechnik",
    "Sensorik",
    "Biomedizintechnik",
]

DIRECT_TERMS = {
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
    "materials characterization": r"materialcharakterisierung|materials characterization|oberflächencharakterisierung",
}

SUPPORT_TERMS = {
    "medical devices": r"medizintechnik|medical device|medizinprodukt|biomedical",
    "verification/validation": r"verifik|validier|validat|verification",
    "quality assurance": r"qualitätssicherung|quality assurance|\bqa\b",
    "calibration": r"kalibrier|calibrat",
    "MATLAB": r"\bmatlab\b",
    "Python": r"\bpython\b",
    "sensors": r"sensorik|\bsensor",
    "biomaterials": r"biomaterial",
    "imaging": r"bildverarbeitung|image processing|medical imaging|\boct\b",
}

PRIORITY_PLACE = re.compile(
    r"baden-württemberg|stuttgart|freiburg|karlsruhe|tübingen|"
    r"villingen-schwenningen|ulm|münchen|munich|bayern|bavaria",
    re.IGNORECASE,
)

SENIORITY_WARNING = re.compile(
    r"\bsenior\b|\bprincipal\b|\bdirector\b|"
    r"\bteamleiter\b|\babteilungsleiter\b|"
    r"\b(?:8|9|10)\+?\s*(?:years|jahre)",
    re.IGNORECASE,
)

LANGUAGE_WARNING = re.compile(
    r"(?:deutsch|german)\s*c[12]\b|"
    r"\bc[12]\s*(?:deutsch|german)\b|"
    r"verhandlungssicher(?:e|es|en|er)?\s+deutsch",
    re.IGNORECASE,
)

session = requests.Session()
session.headers.update({
    "X-API-Key": os.getenv("BA_JOBS_API_KEY") or "jobboerse-jobsuche",
    "Accept": "application/json",
})


def plain_text(value):
    return re.sub(r"<[^>]+>", " ", str(value or "")).strip()


def search(term):
    response = session.get(
        f"{BASE_URL}/pc/v4/app/jobs",
        params={
            "was": term,
            "angebotsart": 1,
            "page": 1,
            "size": 25,
            "pav": "false",
            "veroeffentlichtseit": 30,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    listings = payload.get("stellenangebote")

    if not isinstance(listings, list):
        raise ValueError(
            f"Unexpected search response for {term!r}; keys: {list(payload)[:12]}"
        )

    return listings


def job_details(reference):
    encoded = base64.urlsafe_b64encode(reference.encode("utf-8")).decode("ascii")
    encoded = encoded.rstrip("=")

    response = session.get(
        f"{BASE_URL}/pc/v4/jobdetails/{encoded}",
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def score_job(title, description, location):
    text = f"{title} {description}".casefold()
    matched_direct = [
        label for label, pattern in DIRECT_TERMS.items()
        if re.search(pattern, text, re.IGNORECASE)
    ]
    matched_support = [
        label for label, pattern in SUPPORT_TERMS.items()
        if re.search(pattern, text, re.IGNORECASE)
    ]

    score = min(len(matched_direct) * 10, 60)
    score += min(len(matched_support) * 4, 24)

    if re.search(
        r"phd|doctoral|doktorand|wissenschaftlich(?:e|er|en|es)? "
        r"mitarbeiter|research associate",
        title,
        re.IGNORECASE,
    ):
        score += 8

    if PRIORITY_PLACE.search(location):
        score += 6

    warnings = []
    if SENIORITY_WARNING.search(title):
        score -= 20
        warnings.append("Senior/management title")

    if LANGUAGE_WARNING.search(description):
        score -= 8
        warnings.append("Check German-language requirement")

    return (
        max(0, min(100, score)),
        matched_direct + matched_support,
        warnings,
    )


def location_from(search_result, details):
    search_place = search_result.get("arbeitsort") or {}
    if not isinstance(search_place, dict):
        search_place = {}

    detail_places = details.get("arbeitsorte") or []
    detail_place = detail_places[0] if detail_places else {}
    if not isinstance(detail_place, dict):
        detail_place = {}

    city = detail_place.get("ort") or search_place.get("ort") or ""
    region = detail_place.get("region") or search_place.get("region") or ""
    return ", ".join(part for part in (city, region, "Germany") if part)


def safe_url(search_result, details, reference):
    for candidate in (
        search_result.get("externeUrl"),
        details.get("externeUrl"),
    ):
        if isinstance(candidate, str) and candidate.startswith("https://"):
            return candidate

    return (
        "https://www.arbeitsagentur.de/jobsuche/suche?"
        f"was={requests.utils.quote(reference)}"
    )


def main():
    found = {}
    successes = 0
    failures = 0

    for term in SEARCH_TERMS:
        try:
            results = search(term)
            successes += 1
            print(f"Search {term!r}: {len(results)} listings")

            for result in results:
                reference = result.get("refnr") or result.get("referenznummer")
                if reference:
                    found[reference] = result

        except (requests.RequestException, ValueError) as error:
            failures += 1
            print(f"Search {term!r} failed: {error}")

    print(
        f"Successful searches: {successes}; "
        f"failed searches: {failures}; unique listings: {len(found)}"
    )

    if not found:
        raise SystemExit(
            "No listings returned. Check the API errors above; "
            "keeping the previously deployed site unchanged."
        )

    ranked = []
    detail_successes = 0
    detail_failures = 0

    for reference, result in list(found.items())[:MAX_DETAIL_REQUESTS]:
        try:
            details = job_details(reference)
            detail_successes += 1
        except (requests.RequestException, ValueError) as error:
            detail_failures += 1
            print(f"Details failed for {reference}: {error}")
            continue

        title = plain_text(
            details.get("titel")
            or details.get("stellenangebotsTitel")
            or result.get("beruf")
        )
        description = plain_text(
            details.get("stellenbeschreibung")
            or details.get("stellenangebotsBeschreibung")
        )
        location = location_from(result, details)
        score, keywords, warnings = score_job(title, description, location)

        if score < MIN_SCORE:
            continue

        ranked.append({
            "id": reference,
            "title": title or result.get("beruf") or "Untitled vacancy",
            "company": plain_text(
                details.get("arbeitgeber")
                or result.get("arbeitgeber")
                or "Employer not listed"
            ),
            "location": location,
            "country": "Germany",
            "category": "Live German vacancy",
            "type": "See original posting",
            "datePosted": (
                details.get("aktuelleVeroeffentlichungsdatum")
                or result.get("aktuelleVeroeffentlichungsdatum")
                or ""
            ),
            "deadline": "Check original posting",
            "url": safe_url(result, details, reference),
            "source": "Bundesagentur für Arbeit Jobsuche",
            "description": description[:2500],
            "matchScore": score,
            "matchedKeywords": keywords[:10],
            "warnings": warnings,
        })

    ranked.sort(key=lambda job: job["matchScore"], reverse=True)

    print(
        f"Detail requests succeeded: {detail_successes}; "
        f"failed: {detail_failures}; jobs scoring {MIN_SCORE}+: {len(ranked)}"
    )

    if not ranked:
        raise SystemExit(
            "Search returned listings but none passed matching. "
            "Check detail failures and search terms above; "
            "keeping the previously deployed site unchanged."
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps({
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "count": len(ranked),
            "jobs": ranked,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Saved {len(ranked)} real jobs to {OUTPUT}")


if __name__ == "__main__":
    main()
