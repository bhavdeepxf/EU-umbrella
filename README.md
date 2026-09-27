# EU Umbrella

A personal, CV-matched job radar for MEMS, thin films, materials characterization, biomedical engineering, medtech and research roles in Germany and Europe.

## What was fixed

- Replaced the blocked Bundesagentur endpoint with permitted public feeds.
- Uses Arbeitnow plus selected employers' public Greenhouse Job Board APIs.
- Scores complete posting text against the CV, not only titles.
- Keeps prior valid data if a source temporarily produces no matches.
- Deploys generated `data/live-jobs.json` in the same GitHub Pages artifact.
- Removes duplicate script tags and all demonstration vacancies.
- Adds clear live/error/loading states, responsive filters, dark mode and safe link handling.
- Updates Actions to Node 24-compatible action versions.

## Install in GitHub

1. Download and unzip this project.
2. In the `EU-umbrella` repository, upload the files **with their folders preserved**.
3. Replace the old files when GitHub asks.
4. Delete any obsolete workflow such as `.github/workflows/update-live-jobs.yml`; keep only `.github/workflows/deploy.yml`.
5. Open **Settings → Pages → Build and deployment** and set **Source** to **GitHub Actions**.
6. Open **Actions → Refresh jobs and deploy EU Umbrella → Run workflow → main → Run workflow**.
7. A successful run shows `CV-matched jobs: N`, validates `data/live-jobs.json`, uploads the Pages artifact and deploys it.
8. Open `https://bhavdeepxf.github.io/EU-umbrella/` and use a hard refresh once.

No repository API secret is required for the included sources.

## Refresh behavior

The workflow runs:

- on every push to `main`;
- manually with **Run workflow**;
- every day at 05:17 UTC.

The browser's **Reload latest data** button reloads the latest deployed JSON. It cannot run the GitHub Action itself; use the Actions page for an immediate server-side collection.

## Matching model

The Python collector prioritizes CV evidence in AlN, MEMS, thin films, ALD, sputtering, FTIR, XRD, SEM, materials characterization, sensors, biomedical engineering, medical devices, QA, calibration, validation, MATLAB, Python and medical imaging. It penalizes senior-only, student-only and strong language-requirement signals.

The displayed percentage is a transparent heuristic ranking score—not a probability of interview or employment. Always check the original posting.

## Add another Greenhouse employer

Public Greenhouse GET job-board endpoints do not require authentication. Add a known board token to `GREENHOUSE_BOARDS` in `scripts/fetch_and_score_jobs.py`, then run the workflow. Invalid or unavailable boards are skipped without destroying previous data.
