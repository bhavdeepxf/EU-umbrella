# EU Umbrella — Europe Career Radar

A static GitHub Pages dashboard that discovers and ranks full-time and PhD opportunities across European semiconductor, MEMS, acoustic-MEMS, thin-film/metrology, biomedical-engineering, medical-device and implant employers.

## Coverage and selection

- Europe-wide location model, with explicit priority for Heidelberg, Munich, Hannover, Hamburg, Aachen, Dresden, Stuttgart, Reutlingen, Freiburg, Berlin, Jena, Eindhoven, Delft, Zurich, Grenoble, Graz, Vienna, Leuven and other relevant clusters.
- Employer mix from open startup/company boards, EURAXESS, SmartRecruiters, Lever, Greenhouse, Personio and Odoo career feeds.
- 85+ = exceptional; 75+ = strong (default); 65+ = shortlisted.
- Separate attainability scoring reduces senior, high-experience and strict-language roles.
- Hard exclusion of student, Werkstudent, internship, thesis, trainee, apprenticeship and postdoc listings.
- Six-result cap per employer prevents Bosch, Fraunhofer or any other organisation from dominating.
- Applied-jobs tracker with statuses and notes.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python fetch_jobs.py
python validate_data.py
python -m http.server 8000
```

Open `http://localhost:8000`.

## Deploy

Place these files in the repository root. In GitHub **Settings → Pages**, select **GitHub Actions**, then run **Refresh jobs and deploy EU Umbrella**. The workflow refreshes every day and publishes the last valid feed if an individual source fails.

## Extend sources

Add public ATS slugs to `SMARTRECRUITERS`, `LEVER`, `GREENHOUSE`, or `PERSONIO` in `fetch_jobs.py`. A source failure is isolated and recorded in the workflow log; it does not block other employers.

## Tracking limitation

Application tracking uses browser `localStorage`, so it stays on that browser/device and is removed if site data is cleared. Cross-device sync requires an authenticated database.
