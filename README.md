# EU Umbrella — Selective Career Radar

A static GitHub Pages dashboard that discovers and ranks only high-confidence jobs and PhD opportunities for Mano's biomedical microsystems, MEMS, thin-film characterization, medical-device QA and clinical-equipment background.

## What changed

- Hard-excludes working-student, Werkstudent, internship, Praktikum, thesis, trainee and postdoc roles.
- Requires both **technical fit ≥ 65** and **attainability ≥ 55**.
- Uses a green **Perfect fit** treatment only for exceptional, realistically attainable roles.
- Limits each company to eight listings so Bosch or another large employer cannot dominate.
- Adds an **Applied jobs** tracker with status and notes; browser storage preserves tracking on that device.
- Keeps the default view selective at 75+, with 65+ available when you want to broaden the search.
- Adds Brainlab and Eurofins public SmartRecruiters feeds, while retaining Bosch, Infineon, Hahn-Schickard, Fraunhofer and EURAXESS. The country model includes Germany, Switzerland, the Netherlands, broader Europe and India.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/fetch_jobs.py
python scripts/validate_data.py
python -m http.server 8000
```

Open `http://localhost:8000`.

## Deploy

Push the whole project to the root of your GitHub Pages repository. In **Settings → Pages**, select **GitHub Actions**, then run **Refresh jobs and deploy EU Umbrella**. The workflow refreshes daily at 04:17 UTC.

## Tracking limitation

Application tracking uses `localStorage`. It is private to the current browser/device and is not synced through GitHub. Clearing browser site data removes it. A future synced tracker would need a database or authenticated service.

## Collector policy

The collector searches public employer/research feeds, normalizes records, blocks excluded role types, checks title-level domain relevance, calculates separate technical-fit and attainability scores, deduplicates, and applies a per-company cap. Public career pages can change; check the workflow source-health output after failures.
