#!/usr/bin/env python3
"""Collect, rank and validate relevant European vacancies from public sources."""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "jobs.json"
HEADERS = {"User-Agent": "EU-Umbrella-Job-Collector/2.0 (+personal research dashboard)", "Accept-Language": "en,de;q=0.8"}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)
TIMEOUT = 35

SEARCH_TERMS = ["MEMS", "microsystem", "thin film", "AlN", "materials characterization", "biomedical", "medical device", "PhD", "Doktorand", "research engineer"]
EU_CODES = {"de":"Germany","at":"Austria","ch":"Switzerland","nl":"Netherlands","be":"Belgium","dk":"Denmark","se":"Sweden","fi":"Finland","fr":"France","ie":"Ireland","lu":"Luxembourg","no":"Norway","it":"Italy","es":"Spain","pt":"Portugal","cz":"Czechia","pl":"Poland","ee":"Estonia","lv":"Latvia","lt":"Lithuania","si":"Slovenia","sk":"Slovakia","hr":"Croatia","gr":"Greece","ro":"Romania","bg":"Bulgaria","hu":"Hungary","cy":"Cyprus","mt":"Malta"}
EU_NAMES = set(EU_CODES.values()) | {"Czech Republic", "European Union", "Remote", "India"}
PRIORITY_PLACES = ["baden-württemberg","bavaria","saxony","berlin","brandenburg","hamburg","north rhine-westphalia","villingen-schwenningen","freiburg","stuttgart","munich","dresden"]
DIRECT = ["mems","microsystem","aln","aluminum nitride","aluminium nitride","thin film","thin-film","ftir","ft-ir","xrd","sem","ald","atomic layer deposition","sputtering","wafer bow","acoustic sensor","ultrasonic","surface characterization","materials characterization","medical device","biomedical engineering","clinical engineering"]
GROUPS = {
 "MEMS & sensors":["mems","microsystem","microfabrication","microelectronics","sensor development","acoustic sensor","ultrasonic","piezoelectric","photonics"],
 "Thin films & characterization":["aln","aluminum nitride","aluminium nitride","thin film","ald","sputtering","ftir","ft-ir","xrd","sem","surface analysis","materials characterization","failure analysis","crystallography"],
 "Medical technology":["biomedical","medical device","medtech","clinical engineering","biomaterial","implant","biointerface","verification","validation","calibration","quality assurance","eu mdr"],
 "Data & imaging":["matlab","python","machine learning","image processing","medical imaging","computer vision","simulation","data analysis"],
 "Research":["phd","doctoral","doktorand","research associate","scientific employee","wissenschaftlicher mitarbeiter","researcher","r&d","research and development"]
}
SENIOR = ["senior manager","principal","director","head of","staff engineer","lead engineer","10+ years","8+ years","7+ years"]
LANGUAGE = ["german c1","german c2","native german","deutsch c1","deutsch c2","verhandlungssicheres deutsch"]
EXCLUDED_ROLES = ["working student", "werkstudent", "student assistant", "student research assistant", "studentische hilfskraft", "hiwi", "internship", "intern ", "praktikum", "praktikant", "trainee", "bachelor thesis", "master thesis", "master's thesis", "masterarbeit", "bachelorarbeit", "abschlussarbeit", "postdoc", "postdoctoral", "senior", "principal", "director", "head of", "staff engineer", "lead engineer", "group leader", "project leader"]
BROAD_DOMAIN = ["mems", "microsystem", "microfabrication", "semiconductor", "wafer", "microelectronics", "sensor", "photon", "microfluidic", "lab-on-a-chip", "lab on chip", "thin film", "thin-film", "spectroscopy", "materials", "polymer", "coating", "xrd", "ftir", "medical", "medtech", "biomedical", "clinical", "diagnostic", "imaging", "validation", "calibration", "quality"]
TITLE_SIGNALS = ["mems", "microsystem", "semiconductor", "wafer", "sensor", "photon", "microfluid", "lab-on-a-chip", "thin film", "spectroscopy", "materials", "polymer", "coating", "hydrogen", "fracture", "steel", "defect", "radar", "medical", "medtech", "biomedical", "bioelectronic", "clinical", "diagnostic", "imaging", "validation", "quality", "process", "test"]
MIN_RECOMMENDATION_SCORE = 52
MAX_PER_COMPANY = 7
MAX_PER_COUNTRY = 12
MAX_RECOMMENDATIONS = 30
RELEVANCE = set(DIRECT + [x for values in GROUPS.values() for x in values])

@dataclass
class Job:
    id: str
    title: str
    company: str
    location: str
    country: str
    category: str
    type: str
    datePosted: str
    deadline: str
    url: str
    description: str
    source: str
    matchScore: int = 0
    matchedKeywords: list[str] | None = None
    warnings: list[str] | None = None


def get(url: str, **kwargs) -> requests.Response:
    response = SESSION.get(url, timeout=TIMEOUT, **kwargs)
    response.raise_for_status()
    return response


def clean(value) -> str:
    if value is None: return ""
    soup = BeautifulSoup(html.unescape(str(value)), "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def iso_date(value) -> str:
    if not value: return ""
    if isinstance(value, (int, float)):
        try: return datetime.fromtimestamp(value, timezone.utc).date().isoformat()
        except (ValueError, OSError): return ""
    text = str(value).strip()
    match = re.search(r"(20\d{2})[-/]([01]?\d)[-/]([0-3]?\d)", text)
    if match: return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
    for fmt in ("%d %B %Y", "%d %b %Y", "%d.%m.%Y", "%m/%d/%Y"):
        try: return datetime.strptime(text, fmt).date().isoformat()
        except ValueError: pass
    return ""


def country_from(location: str, code: str = "") -> str:
    if code.lower() in EU_CODES: return EU_CODES[code.lower()]
    lowered = location.lower()
    aliases = {"deutschland":"Germany","germany":"Germany","österreich":"Austria","austria":"Austria","schweiz":"Switzerland","switzerland":"Switzerland","netherlands":"Netherlands","nederland":"Netherlands","belgium":"Belgium","denmark":"Denmark","sweden":"Sweden","finland":"Finland","france":"France","ireland":"Ireland"}
    for key, value in aliases.items():
        if key in lowered: return value
    return ""


def classify(text: str) -> str:
    t = text.lower()
    if re.search(r"\bphd\b|doctoral|doktorand|promotion", t): return "PhD / Research"
    if re.search(r"medical device|medtech|biomedical|clinical engineer", t): return "Medical Devices"
    if re.search(r"mems|microsystem|microfabrication|thin film|materials|semiconductor|photon", t): return "R&D / Industry"
    return "Engineering / Research"


def excluded_role(job: Job) -> bool:
    text = f"{job.title} {job.type}".lower()
    return any(term in text for term in EXCLUDED_ROLES)


def meaningful(job: Job) -> bool:
    title = job.title.lower()
    text = f"{job.title} {job.description}".lower()
    return not excluded_role(job) and any(term in title for term in TITLE_SIGNALS) and any(term in text for term in BROAD_DOMAIN)


def in_scope(job: Job) -> bool:
    return job.country in EU_NAMES or any(x in job.location.lower() for x in ["europe", "remote"])


def enrich(job: Job) -> Job:
    text = f"{job.title} {job.company} {job.location} {job.description}".lower()
    matches = []
    score = 15
    for term in DIRECT:
        if term in text:
            score += 7
            matches.append(term)
    for values in GROUPS.values():
        hits = [term for term in values if term in text]
        score += min(len(hits) * 3, 15)
        matches.extend(hits)
    if job.country in EU_NAMES: score += 8
    if job.country == "Germany": score += 8
    if any(place in text for place in PRIORITY_PLACES): score += 5
    if re.search(r"\bphd\b|doctoral|doktorand|wissenschaftlicher mitarbeiter|research associate", text): score += 10
    warnings = [term for term in SENIOR + LANGUAGE if term in text]
    score -= sum(10 if term in SENIOR else 7 for term in warnings)
    job.matchScore = max(0, min(100, score))
    job.matchedKeywords = list(dict.fromkeys(matches))[:8]
    job.warnings = list(dict.fromkeys(warnings))[:4]
    job.category = classify(text)
    return job


def make_id(source: str, url: str) -> str:
    return hashlib.sha256(f"{source}|{url}".encode()).hexdigest()[:16]


def collect_hahn() -> list[Job]:
    base = "https://jobs.hahn-schickard.de"
    soup = BeautifulSoup(get(f"{base}/public/jobs/?show=all&i18nLocale=de_DE").text, "html.parser")
    out = []
    for row in soup.select("table.coveto_jobs_table tbody tr"):
        cells = row.find_all("td")
        link = row.select_one('a[href*="/job-"]')
        if not link or len(cells) < 3: continue
        url = urljoin(base, link.get("href"))
        title = clean(link.get_text(" "))
        location = clean(cells[2].get_text(" "))
        description = ""
        try:
            detail = BeautifulSoup(get(url).text, "html.parser")
            description = clean(detail.select_one("#job_description, .job_description, main, #coveto_content") or detail.body)[:5000]
        except requests.RequestException: pass
        job = Job(make_id("Hahn-Schickard", url), title, "Hahn-Schickard", f"{location}, Germany", "Germany", "", "Full-time / Research", "", "Check official posting", url, description, "Hahn-Schickard careers")
        if meaningful(job): out.append(job)
    return out


def collect_bosch() -> list[Job]:
    base = "https://api.smartrecruiters.com/v1/companies/BoschGroup/postings"
    candidates = {}
    for term in SEARCH_TERMS:
        payload = get(base, params={"q": term, "limit": 100, "offset": 0}).json()
        for item in payload.get("content", []):
            location = item.get("location") or {}
            if location.get("country", "").lower() not in EU_CODES: continue
            candidates[item["id"]] = item
    out = []
    for item in candidates.values():
        try: detail = get(f"{base}/{item['id']}").json()
        except requests.RequestException: detail = item
        loc = detail.get("location") or item.get("location") or {}
        country = country_from(loc.get("fullLocation", ""), loc.get("country", ""))
        url = detail.get("postingUrl") or f"https://jobs.smartrecruiters.com/BoschGroup/{item['id']}"
        description = clean(" ".join(str(v) for v in (detail.get("jobAd") or {}).get("sections", {}).values()))
        job = Job(make_id("Bosch", url), clean(detail.get("name") or item.get("name")), "Bosch Group", clean(loc.get("fullLocation") or loc.get("city")), country, "", clean((detail.get("typeOfEmployment") or {}).get("label") or "Full-time"), iso_date(detail.get("releasedDate") or item.get("releasedDate")), "Check official posting", url, description[:5000], "Bosch careers / SmartRecruiters")
        if in_scope(job) and meaningful(job): out.append(job)
    return out


def collect_infineon() -> list[Job]:
    base = "https://jobs.infineon.com"
    candidates = {}
    for term in SEARCH_TERMS:
        data = get(f"{base}/api/pcsx/search", params={"domain":"infineon.com","query":term,"location":"","start":0}, headers={**HEADERS,"Accept":"application/json"}).json().get("data", {})
        for item in data.get("positions", []): candidates[str(item["id"])] = item
    out = []
    for item in candidates.values():
        location = clean(", ".join(item.get("standardizedLocations") or item.get("locations") or []))
        country = country_from(location, location.rsplit(",",1)[-1].strip().lower() if "," in location else "")
        if not country: continue
        try: detail = get(f"{base}/api/pcsx/position_details", params={"domain":"infineon.com","position_id":item["id"]}, headers={**HEADERS,"Accept":"application/json"}).json().get("data", {})
        except requests.RequestException: detail = item
        url = urljoin(base, detail.get("positionUrl") or item.get("positionUrl") or f"/careers/job/{item['id']}")
        job = Job(make_id("Infineon", url), clean(detail.get("name") or item.get("name")), "Infineon Technologies", location, country, "", clean(detail.get("employmentType") or "Full-time"), iso_date(detail.get("postedTs") or item.get("postedTs")), iso_date(detail.get("jobEndDate")) or "Check official posting", url, clean(detail.get("jobDescription"))[:5000], "Infineon careers")
        if in_scope(job) and meaningful(job): out.append(job)
    return out


def parse_successfactors_row(row, base: str, company: str, source: str) -> Job | None:
    link = row.select_one('a[href*="/job/"]')
    if not link: return None
    url = urljoin(base, link.get("href"))
    title = clean(link.get_text(" "))
    cells = row.find_all("td")
    location = clean(cells[1].get_text(" ")) if len(cells) > 1 else "Germany"
    institute = clean(cells[2].get_text(" ")) if len(cells) > 2 else company
    description = ""
    date = ""
    try:
        detail = BeautifulSoup(get(url).text, "html.parser")
        description = clean(detail.select_one(".jobdescription, .job, main, #content") or detail.body)[:5000]
        date_match = re.search(r"(?:Date|Posted|Veröffentlicht)[:\s]+([^|]{5,30})", description, re.I)
        date = iso_date(date_match.group(1).strip()) if date_match else ""
    except requests.RequestException: pass
    return Job(make_id(source, url), title, institute or company, location if "germany" in location.lower() else f"{location}, Germany", "Germany", "", "Research / Employment", date, "Check official posting", url, description, source)


def collect_fraunhofer() -> list[Job]:
    base = "https://jobs.fraunhofer.de"
    rows = {}
    for term in SEARCH_TERMS:
        soup = BeautifulSoup(get(f"{base}/search/", params={"q":term,"locationsearch":""}).text, "html.parser")
        for row in soup.select("table.searchResults tr.data-row"):
            link = row.select_one('a[href*="/job/"]')
            if link: rows[urljoin(base, link.get("href"))] = row
    out = []
    for row in rows.values():
        job = parse_successfactors_row(row, base, "Fraunhofer-Gesellschaft", "Fraunhofer careers")
        if job and meaningful(job): out.append(job)
    return out


def collect_euraxess() -> list[Job]:
    base = "https://euraxess.ec.europa.eu"
    found = {}
    # Recent pages are intentionally bounded; detailed CV filtering removes broad noise.
    for page in range(6):
        soup = BeautifulSoup(get(f"{base}/jobs/search", params={"page":page}).text, "html.parser")
        for article in soup.select("article.ecl-content-item"):
            link = article.select_one('a[href^="/jobs/"]')
            if not link or not re.match(r"/jobs/\d+", link.get("href", "")): continue
            text = clean(article.get_text(" "))
            if not any(term in text.lower() for term in RELEVANCE): continue
            found[urljoin(base, link.get("href"))] = (link, text)
    out = []
    for url, (link, listing_text) in found.items():
        title = clean(link.get_text(" "))
        soup = BeautifulSoup(get(url).text, "html.parser")
        full = clean(soup.select_one("main") or soup.body)[:6000]
        combined = f"{listing_text} {full}"
        country = next((name for name in EU_NAMES if name.lower() in combined.lower()), "")
        if not country: continue
        organisation = "EURAXESS research organisation"
        org = soup.select_one('[class*="organisation"] a, [class*="organization"] a, .ecl-content-block__secondary')
        if org: organisation = clean(org.get_text(" "))
        posted = re.search(r"Posted on:\s*(\d{1,2}\s+\w+\s+20\d{2})", combined, re.I)
        deadline = re.search(r"(?:Application Deadline|Deadline)[:\s]+(\d{1,2}\s+\w+\s+20\d{2})", combined, re.I)
        location = country
        job = Job(make_id("EURAXESS", url), title, organisation, location, country, "", "Research position", iso_date(posted.group(1)) if posted else "", iso_date(deadline.group(1)) if deadline else "Check official posting", url, full, "EURAXESS")
        if meaningful(job): out.append(job)
    return out


def deduplicate(jobs: list[Job]) -> list[Job]:
    best = {}
    for job in jobs:
        if not meaningful(job): continue
        enriched = enrich(job)
        if enriched.matchScore < MIN_RECOMMENDATION_SCORE: continue
        key = re.sub(r"\W+", "", f"{job.title}{job.company}{job.location}".lower())
        if key not in best or enriched.matchScore > best[key].matchScore: best[key] = enriched

    ranked = sorted(best.values(), key=lambda j: (j.matchScore, j.datePosted), reverse=True)
    selected, company_counts, country_counts = [], {}, {}

    # Preserve geographical breadth: reserve up to two good roles from each non-German country.
    for country in sorted({job.country for job in ranked if job.country and job.country != "Germany"}):
        for job in [item for item in ranked if item.country == country][:2]:
            company_key = re.sub(r"\W+", "", job.company.lower())
            if company_counts.get(company_key, 0) >= MAX_PER_COMPANY: continue
            selected.append(job)
            company_counts[company_key] = company_counts.get(company_key, 0) + 1
            country_counts[country] = country_counts.get(country, 0) + 1

    # Fill by score, with caps so one employer or country cannot dominate.
    for job in ranked:
        if job in selected: continue
        company_key = re.sub(r"\W+", "", job.company.lower())
        country_cap = MAX_PER_COUNTRY if job.country == "Germany" else 5
        if company_counts.get(company_key, 0) >= MAX_PER_COMPANY: continue
        if country_counts.get(job.country, 0) >= country_cap: continue
        selected.append(job)
        company_counts[company_key] = company_counts.get(company_key, 0) + 1
        country_counts[job.country] = country_counts.get(job.country, 0) + 1
        if len(selected) >= MAX_RECOMMENDATIONS: break

    return sorted(selected, key=lambda j: (j.matchScore, j.datePosted), reverse=True)


def main() -> int:
    collectors: list[tuple[str, Callable[[], list[Job]]]] = [
        ("Hahn-Schickard", collect_hahn), ("Bosch", collect_bosch), ("Infineon", collect_infineon),
        ("Fraunhofer", collect_fraunhofer), ("EURAXESS", collect_euraxess)
    ]
    all_jobs, health = [], []
    for name, collector in collectors:
        started = time.monotonic()
        try:
            result = collector()
            all_jobs.extend(result)
            health.append({"name":name,"status":"ok","count":len(result),"seconds":round(time.monotonic()-started,2)})
            print(f"{name}: {len(result)} relevant vacancies")
        except Exception as exc:
            health.append({"name":name,"status":"error","count":0,"error":f"{type(exc).__name__}: {exc}"[:240]})
            print(f"WARNING {name}: {exc}", file=sys.stderr)
    jobs = deduplicate(all_jobs)
    previous = None
    if OUTPUT.exists():
        try: previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
        except (ValueError, OSError): pass
    successful = sum(item["status"] == "ok" for item in health)
    if not jobs and previous and previous.get("jobs"):
        jobs = [Job(**{k:v for k,v in item.items() if k in Job.__dataclass_fields__}) for item in previous["jobs"]]
        health.append({"name":"Fallback","status":"stale","count":len(jobs),"error":"All fresh results were empty; preserved last known good data."})
    if successful < 2 and not jobs:
        print("ERROR: fewer than two sources succeeded and no fallback data exists", file=sys.stderr)
        return 1
    payload = {"generatedAt":datetime.now(timezone.utc).isoformat(),"jobCount":len(jobs),"sources":health,"jobs":[asdict(job) for job in jobs[:MAX_RECOMMENDATIONS]]}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temp = OUTPUT.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    json.loads(temp.read_text(encoding="utf-8"))
    temp.replace(OUTPUT)
    print(f"Wrote {len(jobs[:MAX_RECOMMENDATIONS])} curated jobs to {OUTPUT}")
    return 0

if __name__ == "__main__": raise SystemExit(main())
