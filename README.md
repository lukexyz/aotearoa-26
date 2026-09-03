# Aotearoa 2026 — South Island road trip

Live at https://lukexyz.github.io/aotearoa-26/

Eleven days, Christchurch loop, six of us. October–November 2026.

The itinerary lives in a shared Google Sheet. This repo turns it into a website
on GitHub Pages. Edit the sheet, and the site rebuilds itself overnight, or
straight away from the **Actions → Build from Google Sheet and deploy → Run
workflow** button.

Addresses, confirmation numbers, flight bookings and anything else you wouldn't
want on the open web stay in the sheet's `bookings` and `flights` tabs, which
are never exported. The site shows the town we're sleeping in and links back to
the sheet for the rest.

## How it fits together

```
Google Sheet ──(nightly / on demand)──▶ GitHub Action
   days                                   scripts/fetch_sheet.py  →  site/data.json
   stops                                  scripts/routes.py       →  + road geometry (OSRM, cached)
   places                                 scripts/photos.py       →  + a photo per place (Wikipedia, cached)
   bookings  ✗ never leaves the sheet     scripts/build.py        →  dist/index.html
   flights   ✗ never leaves the sheet     deploy-pages            →  https://<user>.github.io/aotearoa-26/
```

`SHEET_SCHEMA.md` describes the tabs and columns. `data/*.csv` is a copy of the
same shape used for local development and as the fallback when the sheet
secrets aren't configured.

## One-time setup

1. **Create the sheet** with the tabs in `SHEET_SCHEMA.md`. Quickest way:
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
python scripts/fetch_sheet.py --dump      # copy the sheet's exported tabs back into data/*.csv
python scripts/routes.py                  # make the drives follow the road (OSRM); commit data/routes.json after
python scripts/photos.py --preview        # find a photo per place; opens as photos-preview.html; commit data/photos.json
python scripts/build.py
python -m http.server -d dist 8000        # open http://localhost:8000
```

The sheet is the source of truth. `data/*.csv` is a snapshot of it, refreshed
with `--dump`, and is what CI builds from if the sheet secrets are missing.

## The page

One file, `site/index.html`. Leaflet map with a basemap switcher (satellite,
CARTO Light, Voyager, OpenTopoMap; the choice is remembered per browser).
Overview shows the whole loop with a pin per town; each day shows the drive
along the actual road, numbered pins for the stops that have a `place`,
tonight's town with a halo, and photo cards on the right. The drive is routed
through the stops that have a `place`, so a detour you want drawn (and timed)
needs a stops row, not just a mention in the notes. Below 760px the map sits on top and the rest
scrolls underneath. `#day-7` in the URL opens that day; during the trip the
page opens on today.

Nothing about the South Island is written into the HTML. Change the sheet and
the map follows.

## Photos

Every place gets a photo without anyone hunting for one. `scripts/photos.py`
looks up the place's English Wikipedia article (exact title first, then a
search, and only articles whose coordinates are within 40 km of the place)
and uses the article's lead image. Picks are cached in `data/photos.json`.

**When the itinerary changes:**

- **New place in the sheet** with the `photo` cell blank: nothing to do. The
  next build finds one. To see it before the nightly run, press *Run
  workflow*, or run `python scripts/photos.py --preview` locally.
- **Don't like the automatic pick**: fill in the `photo` cell in `places`.
  Three forms work:

  | you type                        | what happens                                              |
  |---------------------------------|-----------------------------------------------------------|
  | `wiki:Doubtful Sound`           | lead image of that Wikipedia article. Easiest.            |
  | `Doubtful_Sound_Clear.jpg`      | that exact Wikimedia Commons file (the name after `File:`) |
  | `https://…/something.jpg`       | any image URL, used as-is (no credit shown)               |

  The sheet always wins over the automatic pick.
- **Want a fresh automatic pick** (say the article changed its image):
  `python scripts/photos.py --refresh "Place Name"` and commit
  `data/photos.json`. Or delete that place's entry from the file by hand.
- **Renamed a place**: it's a new name, so it gets a new automatic pick.
- **No photo at all**: put `-` in the cell. (Any non-empty value that isn't
  a URL, a filename or `wiki:` is treated as a filename and will just fail to
  load, leaving the gradient. `-` is the tidy way to say "none".)

`photos-preview.html` (from `--preview`, gitignored) is a contact sheet of
every place with its current photo and where it came from. Credits and the
Commons licence appear on each card and popup, linking to the file page.

The nightly cron runs at 02:00 NZDT. Adjust the schedule in
`.github/workflows/build.yml` if that's the wrong time.
