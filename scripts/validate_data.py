#!/usr/bin/env python3
import json,re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
p=Path(__file__).resolve().parent/"jobs.json"
data=json.loads(p.read_text(encoding="utf-8"))
assert isinstance(data.get("jobs"),list) and data["jobs"],"jobs must be a non-empty array"
required={"id","title","company","url","country","matchScore","attainabilityScore","perfectFit","employerType"}
excluded=re.compile(r"(?i)working student|werkstudent|student assistant|internship|praktikum|trainee|master thesis|bachelor thesis|postdoc")
ids=set();counts=Counter()
for i,j in enumerate(data["jobs"]):
 assert not(required-j.keys()),f"job {i} missing {required-j.keys()}"
 assert j["id"] not in ids,f"duplicate id {j['id']}";ids.add(j["id"])
 u=urlparse(j["url"]);assert u.scheme in {"http","https"} and u.netloc,f"invalid URL {j['url']}"
 assert 65<=j["matchScore"]<=100,f"fit below 65: {j['id']}"
 assert 50<=j["attainabilityScore"]<=100,f"attainability below 50: {j['id']}"
 assert not excluded.search(f"{j['title']} {j.get('type','')}"),f"excluded role leaked: {j['title']}"
 key=re.sub(r"\W+","",j["company"].lower());counts[key]+=1;assert counts[key]<=6,f"company cap exceeded: {j['company']}"
assert isinstance(data.get("sources"),list) and len(data["sources"])>=5,"too few configured sources"
print(f"Validated {len(data['jobs'])} selective vacancies from {len(data['sources'])} source records")
