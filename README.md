# Aotearoa 2026 — South Island road trip

Live at https://lukexyz.github.io/aotearoa-26/ (placeholder list view until Phase 2 lands).

Eleven days, Christchurch loop, six of us. October–November 2026.

The itinerary lives in a shared Google Sheet. This repo turns it into a website
on GitHub Pages. Edit the sheet, and the site rebuilds itself overnight, or
straight away from the **Actions → Build from Google Sheet and deploy → Run
workflow** button.

Addresses, confirmation numbers and anything else you wouldn't want on the
open web stay in the sheet's `bookings` tab, which is never exported. The site
shows the town we're sleeping in and links back to the sheet for the rest.

## How it fits together

```
Google Sheet ──(nightly / on demand)──▶ GitHub Action
   days                                   scripts/fetch_sheet.py  →  site/data.json
   stops                                  scripts/build.py        →  dist/index.html
   places                                 deploy-pages            →  https://<user>.github.io/aotearoa-26/
   bookings  ✗ never leaves the sheet
```

`SHEET_SCHEMA.md` describes the tabs and columns. `data/*.csv` is a copy of the
same shape used for local development and as the fallback when the sheet
secrets aren't configured.

## One-time setup

1. **Create the sheet** with the four tabs in `SHEET_SCHEMA.md`. Quickest way:
   import each `data/*.csv` into a tab of the same name, then share the sheet
   with the travellers.
2. **Create a service account** (a robot Google account the Action logs in as):
   - console.cloud.google.com → new project → *APIs & Services* → enable
     **Google Sheets API**
   - *IAM & Admin → Service Accounts → Create*. No roles needed.
   - Open it → *Keys → Add key → JSON*. A file downloads. Don't commit it.
   - Copy the service account's email (ends in `iam.gserviceaccount.com`) and
     **share the sheet with it**, like you would with a person. Viewer is enough for the build; ours is Editor so `seed_sheet.py` and friends can write to it.
3. **Add two repo secrets** (*Settings → Secrets and variables → Actions*):
   - `SHEET_ID`: the long id in the sheet URL, between `/d/` and `/edit`
   - `GOOGLE_SERVICE_ACCOUNT_JSON`: the entire contents of the downloaded JSON
4. **Turn on Pages**: *Settings → Pages → Source: GitHub Actions*.
5. Push, or press *Run workflow*.

## Local development

```
pip install -r requirements.txt
python scripts/fetch_sheet.py --local     # or without --local, with SHEET_ID and
                                          # GOOGLE_SERVICE_ACCOUNT_JSON in the env
python scripts/fetch_sheet.py --check     # validate the sheet without writing anything;
                                          # names the cell for any typo it finds
python scripts/build.py
python -m http.server -d dist 8000        # open http://localhost:8000
```

The nightly cron runs at 02:00 NZDT. Adjust the schedule in
`.github/workflows/build.yml` if that's the wrong time.
