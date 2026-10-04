#!/usr/bin/env python3
import json,re
from pathlib import Path
from urllib.parse import urlparse
p=Path(__file__).resolve().parents[1]/"data"/"jobs.json"
try: data=json.loads(p.read_text(encoding="utf-8"))
except Exception as exc: raise SystemExit(f"Invalid jobs.json: {exc}")
assert isinstance(data.get("jobs"),list),"jobs must be an array"
required={"id","title","company","url","country","matchScore","attainabilityScore","perfectFit"}
excluded=re.compile(r"(?i)\\b(working student|werkstudent|student assistant|studentische hilfskraft|internship|praktikum|praktikant|trainee|master thesis|masterarbeit|bachelor thesis|bachelorarbeit|abschlussarbeit|postdoc|postdoctoral)\\b")
ids=set();companies={}
for i,job in enumerate(data["jobs"]):
    missing=required-job.keys();assert not missing,f"job {i} missing {missing}"
    assert job["id"] not in ids,f"duplicate id {job['id']}";ids.add(job["id"])
    parsed=urlparse(job["url"]);assert parsed.scheme in {"http","https"} and parsed.netloc,f"invalid URL {job['url']}"
    assert 65<=job["matchScore"]<=100,f"technical fit below shortlist threshold for {job['id']}"
    assert 55<=job["attainabilityScore"]<=100,f"attainability below threshold for {job['id']}"
    assert not excluded.search(f"{job['title']} {job.get('type','')}"),f"excluded role leaked into feed: {job['title']}"
    key=re.sub(r"\\W+","",job["company"].lower());companies[key]=companies.get(key,0)+1;assert companies[key]<=8,f"company cap exceeded: {job['company']}"
assert isinstance(data.get("sources"),list),"sources must be an array"
print(f"Validated {len(data['jobs'])} curated vacancies from {len(data['sources'])} source records")
