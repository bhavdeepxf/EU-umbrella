#!/usr/bin/env python3
import json, sys
from pathlib import Path
from urllib.parse import urlparse
p=Path(__file__).resolve().parents[1]/"data"/"jobs.json"
try: data=json.loads(p.read_text(encoding="utf-8"))
except Exception as exc: raise SystemExit(f"Invalid jobs.json: {exc}")
assert isinstance(data.get("jobs"),list), "jobs must be an array"
required={"id","title","company","url","country","matchScore"}
ids=set()
for i,job in enumerate(data["jobs"]):
    missing=required-job.keys(); assert not missing,f"job {i} missing {missing}"
    assert job["id"] not in ids,f"duplicate id {job['id']}"; ids.add(job["id"])
    parsed=urlparse(job["url"]); assert parsed.scheme in {"http","https"} and parsed.netloc,f"invalid URL {job['url']}"
    assert 0<=job["matchScore"]<=100,f"invalid score for {job['id']}"
assert isinstance(data.get("sources"),list),"sources must be an array"
print(f"Validated {len(data['jobs'])} vacancies from {len(data['sources'])} source records")
