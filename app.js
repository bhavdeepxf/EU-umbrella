"use strict";
const $ = (id) => document.getElementById(id);
const controls = { search: $("searchInput"), country: $("countryFilter"), category: $("categoryFilter"), score: $("scoreFilter") };
let liveJobs = [], generatedAt = "", sourceHealth = [], loadError = "", activeView = "matches";
const TRACKER_KEY = "euUmbrellaAppliedV3";
let applied = readTracker();
const normalise = (v) => String(v ?? "").toLocaleLowerCase();
const unique = (a) => [...new Set(a.filter(Boolean))];
const escapeHtml = (v) => String(v ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");
const safeUrl = (v) => { try { const u = new URL(String(v)); return ["http:","https:"].includes(u.protocol) ? u.href : "#"; } catch { return "#"; } };
function readTracker(){ try { return JSON.parse(localStorage.getItem(TRACKER_KEY) || "{}"); } catch { return {}; } }
function writeTracker(){ try { localStorage.setItem(TRACKER_KEY, JSON.stringify(applied)); } catch {} }
function allText(j){ return normalise([j.title,j.company,j.location,j.country,j.category,j.type,j.description,j.source,...(j.matchedKeywords||[])].join(" ")); }
function score(j){ return Math.max(0,Math.min(100,Number(j.matchScore)||0)); }
function attainability(j){ return Math.max(0,Math.min(100,Number(j.attainabilityScore ?? score(j))||0)); }
function tags(j){ return unique(j.matchedKeywords||[]).slice(0,7); }
function warnings(j){ return unique(j.warnings||[]).slice(0,4); }
function isPerfect(j){ return Boolean(j.perfectFit) || (score(j)>=88 && attainability(j)>=72 && !warnings(j).length); }
function dateLabel(v){ if(!v) return "Not published"; const d=new Date(v); return Number.isNaN(d.getTime())?escapeHtml(v):new Intl.DateTimeFormat(undefined,{dateStyle:"medium"}).format(d); }
function scoreLabel(j){ if(isPerfect(j)) return "Perfect fit"; if(score(j)>=85) return "Exceptional"; if(score(j)>=75) return "Strong fit"; return "Shortlisted"; }
function reason(j){ if(j.matchReason) return j.matchReason; const m=tags(j).slice(0,5); return m.length?`Strongest CV overlap: ${m.join(", ")}.`:"Relevant transferable technical experience; verify the detailed requirements."; }
function options(el,placeholder,values){ const old=el.value; el.replaceChildren(new Option(placeholder,""),...values.map(v=>new Option(v,v))); if(values.includes(old)) el.value=old; }
function populateFilters(){ options(controls.country,"All countries",unique(liveJobs.map(j=>j.country)).sort()); options(controls.category,"All routes",unique(liveJobs.map(j=>j.category)).sort()); }
function showToast(text){ const t=$("toast"); t.textContent=text; t.classList.add("is-visible"); clearTimeout(showToast.timer); showToast.timer=setTimeout(()=>t.classList.remove("is-visible"),2200); }
function setView(view){ activeView=view; location.hash=view; document.querySelectorAll("[data-view]").forEach(b=>{const on=b.dataset.view===view;b.classList.toggle("is-active",on);b.setAttribute("aria-current",on?"page":"false")}); $("results-title").textContent=view==="applied"?"Applied jobs":"Best matches"; $("viewEyebrow").textContent=view==="applied"?"Application tracker":"Opportunity shortlist"; $("filterToolbar").hidden=view==="applied"; $("resetFilters").hidden=view==="applied"; render(); }
function visibleJobs(){
  if(activeView==="applied") return Object.values(applied).map(a=>liveJobs.find(j=>j.id===a.id)||a.snapshot).filter(Boolean).sort((a,b)=>String(applied[b.id]?.appliedAt||"").localeCompare(String(applied[a.id]?.appliedAt||"")));
  const term=normalise(controls.search.value.trim()), min=Number(controls.score.value);
  return liveJobs.filter(j=>(!term||allText(j).includes(term))&&(!controls.country.value||j.country===controls.country.value)&&(!controls.category.value||j.category===controls.category.value)&&score(j)>=min).sort((a,b)=>(isPerfect(b)-isPerfect(a))||score(b)-score(a)||attainability(b)-attainability(a)||String(b.datePosted).localeCompare(String(a.datePosted)));
}
function render(){
  const list=visibleJobs(), failed=sourceHealth.filter(s=>s.status!=="ok").length;
  $("matchCount").textContent=liveJobs.length; $("appliedCount").textContent=Object.keys(applied).length;
  const stamp=generatedAt?` Updated ${new Intl.DateTimeFormat(undefined,{dateStyle:"medium"}).format(new Date(generatedAt))}.`:"";
  $("resultsSummary").textContent=activeView==="applied"?`${list.length} application${list.length===1?"":"s"} tracked in this browser.`:`${list.length} of ${liveJobs.length} curated opportunities shown.${stamp}${failed?` ${failed} source${failed===1?"":"s"} unavailable.`:""}`;
  if(!list.length){ const title=activeView==="applied"?"No applications tracked yet":loadError?"The vacancy feed could not be loaded":"No shortlisted jobs match these filters"; const body=activeView==="applied"?"When you apply, click “Mark applied” on the job card and it will appear here.":"Clear filters or lower the threshold to 65+ shortlisted."; $("jobsContainer").innerHTML=`<div class="empty-state"><svg aria-hidden="true" viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 7h16v12H4zM8 7V5h8v2M8 12h8"/></svg><h3>${escapeHtml(title)}</h3><p>${escapeHtml(body)}</p>${activeView==="matches"?'<button class="secondary-button" type="button" data-clear>Clear filters</button>':''}</div>`; $("jobsContainer").querySelector("[data-clear]")?.addEventListener("click",clearFilters); return; }
  $("jobsContainer").innerHTML=list.map(j=>card(j)).join("");
  $("jobsContainer").querySelectorAll("[data-applied]").forEach(b=>b.addEventListener("click",()=>toggleApplied(b.dataset.applied)));
  $("jobsContainer").querySelectorAll("[data-status]").forEach(s=>s.addEventListener("change",()=>updateStatus(s.dataset.status,s.value)));
  $("jobsContainer").querySelectorAll("[data-notes]").forEach(n=>n.addEventListener("change",()=>updateNotes(n.dataset.notes,n.value)));
  $("jobsContainer").setAttribute("aria-busy","false");
}
function card(j){
  const tracked=applied[j.id], perfect=isPerfect(j), ws=warnings(j), deadline=j.deadline&&!String(j.deadline).toLowerCase().startsWith("check")?`<span>Deadline ${dateLabel(j.deadline)}</span>`:"";
  const description=String(j.description||"").slice(0,330), appliedAt=tracked?dateLabel(tracked.appliedAt):"";
  return `<article class="job-card ${perfect?"perfect-fit":""} ${tracked?"is-applied":""}">${perfect?'<div class="perfect-banner"><span>Best of the best</span> Perfect fit for your profile</div>':''}<div class="job-main"><div class="job-heading"><div><p class="source-line">${escapeHtml(j.source||"Official source")}</p><h3>${escapeHtml(j.title)}</h3><p class="company">${escapeHtml(j.company)} · ${escapeHtml(j.location||j.country)}</p></div><div class="score ${perfect?"score-perfect":"score-high"}" aria-label="Technical fit ${score(j)} and attainability ${attainability(j)}"><strong>${score(j)}</strong><span>${scoreLabel(j)}</span></div></div><div class="metric-row"><span><b>${score(j)}</b> technical fit</span><span><b>${attainability(j)}</b> interview potential</span></div><div class="meta"><span>${escapeHtml(j.category||"Technical role")}</span><span>Posted ${dateLabel(j.datePosted)}</span>${deadline}</div>${description?`<p class="description">${escapeHtml(description)}${String(j.description||"").length>330?"…":""}</p>`:""}<p class="match-reason"><strong>Why it fits:</strong> ${escapeHtml(reason(j))}</p>${ws.length?`<p class="warning"><strong>Review:</strong> ${ws.map(escapeHtml).join(", ")}</p>`:""}<div class="job-tags">${tags(j).map(t=>`<span>${escapeHtml(t)}</span>`).join("")}</div>${tracked?`<div class="tracker-fields"><label>Status<select data-status="${escapeHtml(j.id)}"><option${tracked.status==="Applied"?" selected":""}>Applied</option><option${tracked.status==="Interview"?" selected":""}>Interview</option><option${tracked.status==="Offer"?" selected":""}>Offer</option><option${tracked.status==="Rejected"?" selected":""}>Rejected</option></select></label><label>Notes<input data-notes="${escapeHtml(j.id)}" value="${escapeHtml(tracked.notes||"")}" placeholder="Contact, follow-up, deadline…"></label><span>Added ${appliedAt}</span></div>`:""}</div><div class="job-action"><a class="apply-button" href="${escapeHtml(safeUrl(j.url))}" target="_blank" rel="noopener noreferrer">View official posting <span aria-hidden="true">↗</span></a><button class="secondary-button ${tracked?"applied-button":""}" type="button" data-applied="${escapeHtml(j.id)}">${tracked?"✓ Applied":"Mark applied"}</button><span class="verify-note">Official employer or research portal</span></div></article>`;
}
function toggleApplied(id){ const j=liveJobs.find(x=>x.id===id)||applied[id]?.snapshot; if(!j)return; if(applied[id]){delete applied[id];showToast("Removed from application tracker");}else{applied[id]={id,status:"Applied",notes:"",appliedAt:new Date().toISOString(),snapshot:j};showToast("Added to Applied jobs");} writeTracker();render(); }
function updateStatus(id,status){ if(applied[id]){applied[id].status=status;writeTracker();showToast(`Status changed to ${status}`);} }
function updateNotes(id,notes){ if(applied[id]){applied[id].notes=notes;writeTracker();showToast("Application note saved");} }
function clearFilters(){ controls.search.value="";controls.country.value="";controls.category.value="";controls.score.value="75";render(); }
async function loadJobs(){ try{const r=await fetch(`data/jobs.json?v=${Date.now()}`,{cache:"no-store"});if(!r.ok)throw Error(`Feed returned ${r.status}`);const p=await r.json();liveJobs=(p.jobs||[]).filter(j=>j&&j.title&&safeUrl(j.url)!=="#");generatedAt=p.generatedAt||"";sourceHealth=p.sources||[];}catch(e){loadError=e.message;liveJobs=Array.isArray(globalThis.jobs)?globalThis.jobs:[];}populateFilters();render(); }
Object.values(controls).forEach(c=>c.addEventListener(c===controls.search?"input":"change",render));
$("resetFilters").addEventListener("click",clearFilters);document.querySelectorAll("[data-view]").forEach(b=>b.addEventListener("click",()=>setView(b.dataset.view)));window.addEventListener("hashchange",()=>setView(location.hash==="#applied"?"applied":"matches"));
(function(){const root=document.documentElement,t=document.querySelector("[data-theme-toggle]");let theme=matchMedia("(prefers-color-scheme:dark)").matches?"dark":"light";const draw=()=>{root.dataset.theme=theme;t.setAttribute("aria-label",`Switch to ${theme==="dark"?"light":"dark"} mode`);t.innerHTML=theme==="dark"?'<svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4 4l2 2M18 18l2 2M1 12h2M21 12h2M4 20l2-2M18 6l2-2"/></svg>':'<svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8Z"/></svg>';};t.addEventListener("click",()=>{theme=theme==="dark"?"light":"dark";draw()});draw();})();
setView(location.hash==="#applied"?"applied":"matches");loadJobs();
