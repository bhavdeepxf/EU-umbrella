# EU Umbrella

EU Umbrella is a static, CV-matched vacancy dashboard for technical careers in Germany and Europe. It collects public vacancies, scores them against a biomedical/microsystems profile, publishes source-health metadata, and deploys to GitHub Pages.

## Coverage

The collector currently uses public listings or public job-search interfaces from:

- Hahn-Schickard
- Bosch
- Infineon
- Fraunhofer
- EURAXESS

The relevance model prioritizes acoustic MEMS, AlN and other thin films, ALD/sputtering, FTIR/XRD/SEM, materials characterization, biomedical engineering, medical devices, verification/validation, clinical engineering, MATLAB/Python, medical imaging, and related PhD/R&D roles.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python scripts/fetch_jobs.py
python scripts/validate_data.py
python -m http.server 8000
```

Open `http://localhost:8000`. A local HTTP server is required because the frontend fetches `data/jobs.json`.

## GitHub Pages

1. Push the complete project, including `.github/workflows`, `scripts`, and `data`.
2. In **Settings → Pages**, choose **GitHub Actions** as the source.
3. Run **Actions → Refresh jobs and deploy EU Umbrella → Run workflow**.
4. Remove or disable obsolete deployment workflows to avoid competing Pages deployments.

The workflow refreshes daily at 04:17 UTC and on pushes to `main`. It validates JSON, checks all JavaScript syntax, preserves last-known-good vacancies if every fresh result is empty, uploads one Pages artifact, and deploys it.

## Data model

`data/jobs.json` contains:

- `generatedAt` — refresh timestamp
- `jobCount` — number of published matches
- `sources` — per-source status, count, duration or error
- `jobs` — normalized vacancy records and CV-match metadata

## Maintenance notes

Public career pages can change HTML or API structure. A single connector failure does not erase successful results. Inspect the workflow log and `sources` array when the UI reports unavailable sources. Update only the affected collector function in `scripts/fetch_jobs.py`.

The match score is a prioritization aid, not an eligibility determination. Always verify vacancy status, qualifications, deadline, working language, visa requirements, and application instructions on the official posting.
