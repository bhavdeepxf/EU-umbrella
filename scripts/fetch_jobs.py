#!/usr/bin/env python3
"""Collect and rank CV-matched semiconductor, MEMS and biomedical jobs across Europe."""
from __future__ import annotations
import hashlib, html, json, re, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "jobs.json"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "EU-Umbrella/3.0 personal career research dashboard", "Accept-Language": "en,de;q=0.8"})
TIMEOUT = 15

EU_CODES = {"de":"Germany","at":"Austria","ch":"Switzerland","nl":"Netherlands","fr":"France","be":"Belgium","dk":"Denmark","se":"Sweden","fi":"Finland","no":"Norway","ie":"Ireland","gb":"United Kingdom","it":"Italy","es":"Spain","pt":"Portugal","cz":"Czechia","pl":"Poland","hu":"Hungary","ro":"Romania","bg":"Bulgaria","ee":"Estonia","lv":"Latvia","lt":"Lithuania","si":"Slovenia","sk":"Slovakia","hr":"Croatia","gr":"Greece","lu":"Luxembourg","mt":"Malta","cy":"Cyprus"}
EUROPE = set(EU_CODES.values()) | {"European Union", "Remote Europe"}
PRIORITY_CITIES = ["heidelberg","munich","münchen","hannover","hanover","hamburg","aachen","dresden","stuttgart","reutlingen","freiburg","berlin","jena","erfurt","regensburg","itzehoe","lübeck","nuremberg","erlangen","karlsruhe","villingen-schwenningen","zurich","eindhoven","delft","enschede","grenoble","paris","graz","vienna","leuven","mechelen","innsbruck"]

TITLE_TERMS = ["mems","microsystem","microfabric","semiconductor","microelectronic","sensor","thin film","thin-film","deposition","metrology","characterization","characterisation","materials","biomedical","medical device","medtech","implant","biomaterial","biointerface","microfluid","lab-on-a-chip","lab on chip","acoustic","ultrasound","ultrasonic","piezo","photonics","wafer","process engineer","validation engineer","quality engineer","research associate","scientific employee","wissenschaftlicher mitarbeiter","doctoral","phd","doktorand"]
DOMAIN_TERMS = TITLE_TERMS + ["aln","aluminum nitride","aluminium nitride","ald","atomic layer deposition","sputter","ftir","ft-ir","xrd","sem microscopy","surface analysis","failure analysis","cleanroom","lithography","cmos","asic","saw","baw","micromachining","cochlear","orthopaedic","orthopedic","neural interface","biosensor","medical implant","iso 13485","eu mdr","verification","calibration","3d printing","additive manufacturing"]
SEARCH_TERMS = ["MEMS","semiconductor","thin film","acoustic","biomedical","medical device","implant","PhD"]
EXCLUDED = ["working student","werkstudent","student assistant","studentische hilfskraft","hiwi","internship"," intern ","praktikum","praktikant","trainee","apprentice","ausbildung","bachelor thesis","master thesis","masters thesis","masterarbeit","bachelorarbeit","abschlussarbeit","postdoc","postdoctoral"]
HARD_SENIOR = ["director","head of","vice president","vp ","chief ","principal","staff engineer","lead engineer","senior manager","professor"]
LANGUAGE_WARNINGS = ["german c1","german c2","native german","deutsch c1","deutsch c2","verhandlungssicheres deutsch","fluent german"]
ENTRY = ["junior","graduate","entry level","early career","master's degree","masters degree","msc","m.sc","doctoral","phd position","doktorand","research associate","scientific employee","wissenschaftlicher mitarbeiter"]
DIRECT = ["mems","microsystem","aln","aluminum nitride","aluminium nitride","thin film","thin-film","ftir","ft-ir","xrd","scanning electron","ald","atomic layer deposition","sputtering","wafer bow","acoustic","ultrasound","ultrasonic","piezoelectric","surface characterization","materials characterization","medical device","biomedical engineering","biomaterial","implant","biointerface","microfluidic"]
GROUPS = {
 "MEMS & semiconductors": ["mems","microsystem","microfabrication","semiconductor","microelectronics","wafer","cleanroom","lithography","cmos","asic"],
 "Acoustic MEMS": ["acoustic","microphone","microspeaker","ultrasound","ultrasonic","piezoelectric","saw","baw","hearing"],
 "Thin films & metrology": ["aln","thin film","ald","sputtering","ftir","xrd","sem microscopy","surface analysis","characterization","metrology","failure analysis"],
 "Biomedical & implants": ["biomedical","medical device","medtech","biomaterial","implant","biointerface","cochlear","orthopaedic","neural","microfluidic","lab-on-a-chip","biosensor"],
 "Research": ["phd","doctoral","doktorand","research associate","scientific employee","wissenschaftlicher mitarbeiter","research engineer","r&d","research and development"]
}
MAX_PER_COMPANY = 6
MIN_FIT = 65
MIN_ATTAINABILITY = 50

# Companies with public ATS endpoints. Add slugs here without changing collector logic.
SMARTRECRUITERS = {"BoschGroup":"Bosch Group","Brainlab":"Brainlab","Eurofins":"Eurofins","Tomra":"TOMRA","Sika":"Sika","ASML":"ASML"}
LEVER = {"alifsemi":"Alif Semiconductor","MunichElectrification":"Munich Electrification","quantummotion":"Quantum Motion","axeleraai":"Axelera AI","materialise":"Materialise"}
GREENHOUSE = {"prophesee":"Prophesee","qblox":"Qblox","nekohealth":"Neko Health","onwardmedical":"ONWARD Medical"}
PERSONIO = {"cortec":"CorTec","marvelfusion":"Marvel Fusion","blacksemiconductor":"Black Semiconductor","sensry":"Sensry","inbrain-neuroelectronics":"INBRAIN Neuroelectronics"}
ODOO = {"https://usound-16.odoo.com/jobs":"USound"}

@dataclass
class Job:
 id:str; title:str; company:str; location:str; country:str; category:str; type:str; datePosted:str; deadline:str; url:str; description:str; source:str
 matchScore:int=0; matchedKeywords:list[str]|None=None; warnings:list[str]|None=None; attainabilityScore:int=0; perfectFit:bool=False; matchReason:str=""; employerType:str="Company"

def get(url, **kwargs):
 r=SESSION.get(url, timeout=TIMEOUT, **kwargs); r.raise_for_status(); return r

def clean(value):
 if value is None: return ""
 return re.sub(r"\s+", " ", BeautifulSoup(html.unescape(str(value)), "html.parser").get_text(" ", strip=True)).strip()

def iso_date(value):
 if not value: return ""
 if isinstance(value,(int,float)):
  try: return datetime.fromtimestamp(value/1000 if value>1e11 else value,timezone.utc).date().isoformat()
  except (ValueError,OSError): return ""
 m=re.search(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})",str(value))
 return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""

def make_id(source,url): return hashlib.sha256(f"{source}|{url}".encode()).hexdigest()[:16]

def country_from(location="",code=""):
 code=str(code).lower().strip()
 if code in EU_CODES: return EU_CODES[code]
 text=f" {location.lower()} "
 aliases={"germany":"Germany","deutschland":"Germany","austria":"Austria","österreich":"Austria","switzerland":"Switzerland","schweiz":"Switzerland","netherlands":"Netherlands","nederland":"Netherlands","france":"France","belgium":"Belgium","denmark":"Denmark","sweden":"Sweden","finland":"Finland","norway":"Norway","ireland":"Ireland","united kingdom":"United Kingdom"," uk ":"United Kingdom","italy":"Italy","spain":"Spain","poland":"Poland","czech":"Czechia","hungary":"Hungary","romania":"Romania","portugal":"Portugal"}
 for k,v in aliases.items():
  if k in text:return v
 city_country={"munich":"Germany","münchen":"Germany","berlin":"Germany","hamburg":"Germany","hannover":"Germany","hanover":"Germany","aachen":"Germany","dresden":"Germany","stuttgart":"Germany","heidelberg":"Germany","reutlingen":"Germany","freiburg":"Germany","eindhoven":"Netherlands","delft":"Netherlands","enschede":"Netherlands","amsterdam":"Netherlands","zurich":"Switzerland","zürich":"Switzerland","lausanne":"Switzerland","grenoble":"France","paris":"France","graz":"Austria","vienna":"Austria","wien":"Austria","leuven":"Belgium","mechelen":"Belgium","oulu":"Finland","copenhagen":"Denmark","stockholm":"Sweden"}
 for k,v in city_country.items():
  if k in text:return v
 return ""

def meaningful(j):
 text=f" {j.title} {j.description} ".lower()
 title=j.title.lower()
 return not any(x in text for x in EXCLUDED) and any(x in title for x in TITLE_TERMS) and any(x in text for x in DOMAIN_TERMS)

def category(text):
 t=text.lower(); scores={name:sum(x in t for x in terms) for name,terms in GROUPS.items() if name!="Research"}
 route=max(scores,key=scores.get) if scores and max(scores.values()) else "Research & development"
 if any(x in t for x in ["phd","doctoral","doktorand"]): return f"PhD · {route}"
 return route

def enrich(j):
 text=f" {j.title} {j.company} {j.location} {j.description} ".lower(); title=j.title.lower()
 matches=[]; score=18
 for term in DIRECT:
  if term in text: score+=5; matches.append(term)
 group_hits={name:[x for x in terms if x in text] for name,terms in GROUPS.items()}
 for hits in group_hits.values(): score+=min(len(hits),3)*4; matches.extend(hits)
 if any(x in title for x in TITLE_TERMS): score+=12
 if j.country in EUROPE: score+=4
 if j.country=="Germany": score+=3
 if any(x in text for x in PRIORITY_CITIES): score+=4
 if j.employerType in {"Startup","Scale-up"}: score+=3
 warnings=[]
 for x in HARD_SENIOR+LANGUAGE_WARNINGS:
  if x in text: warnings.append(x)
 score-=sum(8 for x in warnings if x in HARD_SENIOR)
 score-=sum(4 for x in warnings if x in LANGUAGE_WARNINGS)
 att=58
 if any(x in text for x in ENTRY):att+=12
 if any(x in title for x in ["phd","doctoral","doktorand","research associate","wissenschaftlicher mitarbeiter"]):att+=8
 if j.country=="Germany":att+=4
 if len(set(matches))>=5:att+=5
 for years,penalty in [("10+ years",30),("10 years",30),("8+ years",24),("8 years",24),("7+ years",20),("7 years",20),("6 years",16),("5+ years",12),("5 years",12),("several years",7)]:
  if years in text: att-=penalty; warnings.append(years)
 if any(x in title for x in HARD_SENIOR): att-=22
 if any(x in text for x in LANGUAGE_WARNINGS):att-=10
 j.matchScore=max(0,min(100,score)); j.attainabilityScore=max(0,min(100,att)); j.matchedKeywords=list(dict.fromkeys(matches))[:9]; j.warnings=list(dict.fromkeys(warnings))[:5]
 j.category=category(text); j.perfectFit=j.matchScore>=85 and j.attainabilityScore>=68 and not any(x in title for x in HARD_SENIOR)
 strongest=", ".join(j.matchedKeywords[:5])
 j.matchReason=(f"Direct CV overlap: {strongest}." if strongest else "Relevant transferable research and engineering experience.")
 return j

def smartrecruiters(slug,name):
 base=f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"; found={}
 for term in SEARCH_TERMS:
  try: data=get(base,params={"q":term,"limit":100,"offset":0}).json()
  except requests.RequestException: continue
  for item in data.get("content",[]): found[str(item.get("id"))]=item
 out=[]
 for pid,item in found.items():
  try:d=get(f"{base}/{pid}").json()
  except requests.RequestException:d=item
  loc=d.get("location") or {}; location=clean(loc.get("fullLocation") or loc.get("city")); country=country_from(location,loc.get("country",""))
  if country not in EUROPE:continue
  url=d.get("postingUrl") or f"https://jobs.smartrecruiters.com/{slug}/{pid}"
  desc=clean(" ".join(map(str,(d.get("jobAd") or {}).get("sections",{}).values())))[:8000]
  j=Job(make_id(name,url),clean(d.get("name") or item.get("name")),name,location,country,"","Full-time",iso_date(d.get("releasedDate")),"Check official posting",url,desc,f"{name} careers")
  if meaningful(j):out.append(j)
 return out

def lever(slug,name):
 data=get(f"https://api.lever.co/v0/postings/{slug}",params={"mode":"json"}).json(); out=[]
 for d in data:
  cats=d.get("categories") or {}; location=clean(cats.get("location") or d.get("workplaceType")); country=country_from(location)
  if country not in EUROPE:continue
  url=d.get("hostedUrl") or d.get("applyUrl"); desc=clean(" ".join([d.get("descriptionPlain",""),d.get("additionalPlain","")]))[:8000]
  j=Job(make_id(name,url),clean(d.get("text")),name,location,country,"",clean(cats.get("commitment") or "Full-time"),iso_date(d.get("createdAt")),"Check official posting",url,desc,f"{name} careers","",None,None,0,False,"","Startup")
  if meaningful(j):out.append(j)
 return out

def greenhouse(slug,name):
 data=get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",params={"content":"true"}).json(); out=[]
 for d in data.get("jobs",[]):
  location=clean((d.get("location") or {}).get("name")); country=country_from(location)
  if country not in EUROPE:continue
  url=d.get("absolute_url"); desc=clean(d.get("content"))[:8000]
  j=Job(make_id(name,url),clean(d.get("title")),name,location,country,"","Full-time",iso_date(d.get("updated_at")),"Check official posting",url,desc,f"{name} careers","",None,None,0,False,"","Startup")
  if meaningful(j):out.append(j)
 return out

def personio(slug,name):
 root=BeautifulSoup(get(f"https://{slug}.jobs.personio.de/xml").text,"xml");out=[]
 for p in root.find_all("position"):
  title=clean(p.find("name")); location=clean(p.find("office")); country=country_from(location)
  if country not in EUROPE:continue
  pid=clean(p.find("id")); url=f"https://{slug}.jobs.personio.de/job/{pid}"; desc=clean(p.find("jobDescriptions"))[:8000]
  j=Job(make_id(name,url),title,name,location,country,"",clean(p.find("schedule") or "Full-time"),"","Check official posting",url,desc,f"{name} careers","",None,None,0,False,"","Startup")
  if meaningful(j):out.append(j)
 return out

def odoo(url,name):
 soup=BeautifulSoup(get(url).text,"html.parser");out=[]
 for link in soup.select('a[href*="/jobs/detail/"]'):
  job_url=urljoin(url,link.get("href")); title=clean(link.get_text(" "))
  if not title or not any(x in title.lower() for x in TITLE_TERMS):continue
  try:detail=BeautifulSoup(get(job_url).text,"html.parser"); text=clean(detail); title=clean(detail.select_one("h1,h2,h3") or title); loc=" ".join(x for x in PRIORITY_CITIES if x in text.lower())
  except requests.RequestException:continue
  country=country_from(text)
  j=Job(make_id(name,job_url),title,name,loc.title() or country,country,"","Full-time","","Check official posting",job_url,text[:8000],f"{name} careers","",None,None,0,False,"","Startup")
  if country in EUROPE and meaningful(j):out.append(j)
 return out

def arbeitnow():
 out=[]
 for page in range(1,4):
  data=get("https://www.arbeitnow.com/api/job-board-api",params={"page":page}).json().get("data",[])
  for d in data:
   location=clean(d.get("location")); country=country_from(location)
   if country not in EUROPE:continue
   url=d.get("url"); desc=clean(d.get("description"))[:8000]; company=clean(d.get("company_name"))
   j=Job(make_id("Arbeitnow",url),clean(d.get("title")),company,location,country,"",clean((d.get("job_types") or ["Full-time"])[0]),iso_date(d.get("created_at")),"Check official posting",url,desc,"Arbeitnow startup & company board","",None,None,0,False,"","Startup")
   if meaningful(j):out.append(j)
 return out

def euraxess():
 base="https://euraxess.ec.europa.eu";found={};out=[]
 for page in range(4):
  soup=BeautifulSoup(get(f"{base}/jobs/search",params={"page":page}).text,"html.parser")
  for a in soup.select('a[href*="/jobs/"]'):
   href=a.get("href","")
   if re.search(r"/jobs/\d+",href):found[urljoin(base,href)]=clean(a)
 for url,listing in list(found.items())[:50]:
  try:soup=BeautifulSoup(get(url).text,"html.parser"); text=clean(soup.select_one("main") or soup.body)
  except requests.RequestException:continue
  country=next((c for c in EUROPE if c.lower() in text.lower()),"")
  if not country:continue
  title=clean(soup.select_one("h1")) or listing; org=clean(soup.select_one(".field--name-field-euraxess-organisation-name,.ecl-content-block__secondary")) or "European research organisation"
  j=Job(make_id("EURAXESS",url),title,org,country,country,"","Research position","","Check official posting",url,text[:8000],"EURAXESS","",None,None,0,False,"","University / research")
  if meaningful(j):out.append(j)
 return out

def dedupe(jobs):
 best={}
 for j in jobs:
  if not meaningful(j):continue
  j=enrich(j)
  if j.matchScore<MIN_FIT or j.attainabilityScore<MIN_ATTAINABILITY:continue
  key=re.sub(r"\W+","",f"{j.title}{j.company}{j.location}".lower())
  if key not in best or (j.matchScore,j.attainabilityScore)>(best[key].matchScore,best[key].attainabilityScore):best[key]=j
 ranked=sorted(best.values(),key=lambda j:(j.perfectFit,j.matchScore,j.attainabilityScore,j.datePosted),reverse=True)
 selected=[];counts=Counter()
 for j in ranked:
  key=re.sub(r"\W+","",j.company.lower())
  if counts[key]>=MAX_PER_COMPANY:continue
  selected.append(j);counts[key]+=1
 return selected[:240]

def main():
 collectors=[("Arbeitnow Europe",arbeitnow),("EURAXESS",euraxess)]
 collectors += [(name,lambda s=s,n=name:smartrecruiters(s,n)) for s,name in SMARTRECRUITERS.items()]
 collectors += [(name,lambda s=s,n=name:lever(s,n)) for s,name in LEVER.items()]
 collectors += [(name,lambda s=s,n=name:greenhouse(s,n)) for s,name in GREENHOUSE.items()]
 collectors += [(name,lambda s=s,n=name:personio(s,n)) for s,name in PERSONIO.items()]
 collectors += [(name,lambda u=u,n=name:odoo(u,n)) for u,name in ODOO.items()]
 all_jobs=[];health=[]
 def run_source(name,collector):
  started=time.monotonic()
  try:
   result=collector();return result,{"name":name,"status":"ok","count":len(result),"seconds":round(time.monotonic()-started,2)}
  except Exception as exc:
   return [],{"name":name,"status":"error","count":0,"error":f"{type(exc).__name__}: {str(exc)[:180]}"}
 with ThreadPoolExecutor(max_workers=8) as pool:
  futures=[pool.submit(run_source,name,collector) for name,collector in collectors]
  for future in as_completed(futures):
   result,status=future.result();all_jobs.extend(result);health.append(status);print(status["name"],status["count"],status["status"])
 jobs=dedupe(all_jobs)
 previous=None
 try:previous=json.loads(OUTPUT.read_text(encoding="utf-8"))
 except (OSError,ValueError):pass
 failed_names={x["name"] for x in health if x["status"]=="error"}
 if previous and previous.get("jobs") and (len(jobs)<12 or failed_names):
  old=[]
  for x in previous["jobs"]:
   source_name=x.get("company","")
   if len(jobs)<12 or source_name in failed_names:
    old.append(Job(**{k:v for k,v in x.items() if k in Job.__dataclass_fields__}))
  jobs=dedupe(jobs+old)
  health.append({"name":"Last-known-good source merge","status":"stale","count":len(old),"error":"Preserved valid roles while one or more public sources were unavailable."})
 if not jobs:return 1
 payload={"generatedAt":datetime.now(timezone.utc).isoformat(),"jobCount":len(jobs),"sources":health,"jobs":[asdict(j) for j in jobs]}
 OUTPUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8");print(f"Wrote {len(jobs)} jobs to {OUTPUT}");return 0

if __name__=="__main__":raise SystemExit(main())
