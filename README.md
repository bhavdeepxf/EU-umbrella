# EU Umbrella — expanded edition

A multi-source career radar matching a CV-derived profile to semiconductor, MEMS, materials, biomedical, medtech, validation and research opportunities across Germany, Europe and India.

## Improvements

- Adds Germany, Europe and India as explicit geographic tracks.
- Adds selected public Ashby employer boards alongside Arbeitnow, Greenhouse and Remotive.
- Expands semiconductor, MEMS, materials, biomedical, medical-device, imaging, equipment and quality coverage.
- Separates **technical fit** from **attainability**; overall rank is 64% technical fit and 36% attainability.
- Penalizes leadership-heavy titles, excessive experience requirements, student-only eligibility and hard language constraints.
- Adds filtering by region, career route, overall rank, attainability and sort order.
- Uses a CV-derived, honest positioning model without inventing qualifications.
- Keeps previous deployed data if every upstream source fails or produces no matches.

## Install

1. Extract the archive.
2. Open your `EU-umbrella` GitHub repository.
3. Use **Add file → Upload files** and drag everything *inside* the extracted project folder into the repository root.
4. Replace the existing files and preserve `.github/workflows/deploy.yml`, `data/` and `scripts/`.
5. Commit to `main`.
6. In **Settings → Pages**, keep **Source: GitHub Actions**.
7. Open **Actions → Refresh jobs and deploy EU Umbrella → Run workflow**.

No API secret is required for the included public posting endpoints.

## Refresh behavior

The GitHub workflow runs on every push, manually, and daily at 05:17 UTC. The website’s reload button only reloads the most recently deployed JSON; it cannot start a GitHub workflow.

## Add employers

- Add Greenhouse board tokens to `GREENHOUSE_BOARDS`.
- Add Ashby job-board names to `ASHBY_BOARDS`.
- Validate location coverage and inspect the resulting matches before committing.

The collector skips an unavailable individual employer board and continues with the remaining sources.
