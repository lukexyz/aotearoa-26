# MUSINGS.md

Working notes for the South Island trip site. Same idea as the Dolomites
MUSINGS: written for whoever picks this up next, including future me.

---

## 1. What this is, and how it differs from the Dolomites map

The Dolomites site (`D:\python\boys-expedition-2026`) was a single hand-built
HTML file. Every day, route, coordinate, photo and stat block lived in a JS
object literal. It looked great and it was a nightmare for anyone but the
author to change.

This project moves the *itinerary* out of the code and into a shared Google
Sheet, so six people can edit it. A GitHub Action reads the sheet nightly (or
on demand) and republishes the site. The code owns presentation and geography;
the sheet owns what we're doing each day.

Privacy decision (2026-09-02): the general itinerary is fine on the open web.
What stays private is the `bookings` tab: addresses, confirmation numbers,
check-in times. That tab is never read by the exporter. The site says
"Sleeping in Queenstown" and deep-links back to the sheet for the details.
No page encryption, no private repo, no auth. Just `noindex` and a robots.txt
so it doesn't turn up in search.

## 2. The split between sheet and code

| lives in the sheet                          | lives in the code                     |
|---------------------------------------------|---------------------------------------|
| day order, dates, titles, legs              | page layout, styling, map rendering   |
| from / to town, drive time, notes           | route drawing between known places    |
| stops per day, with links                   | icons, photo loading, weather widget  |
| the gazetteer: place name, lat/lng, photo   |                                       |
| bookings (private)                          |                                       |

The `places` tab is the hinge. `days.from`, `days.to` and `stops.place` are
names that must match a `places.name`. The map draws the route by joining the
towns for each day. That's coarse compared with the Dolomites map's hand-drawn
waypoints, and it's deliberate: a road trip is town-to-town, and anyone can
add a town to a sheet. If we ever want the drive to follow the actual highway,
the fix is a routing call at build time, not more hand-typed coordinates.

Coordinates in `data/places.csv` were typed from memory, accurate to a few
hundred metres. Fine for a map at this scale, not for navigation.

## 3. Pipeline

```
scripts/fetch_sheet.py   sheet (gspread, service account) or data/*.csv  →  site/data.json
scripts/build.py         inlines data.json into site/index.html          →  dist/
.github/workflows/build.yml   cron 02:00 NZDT + workflow_dispatch + push  →  GitHub Pages
```

The data is inlined into the HTML rather than fetched at runtime so the page
works with no signal. Haast Pass, the Doubtful Sound day and most of the West
Coast have none. A service worker for proper offline install is a later step.

The workflow falls back to the CSVs if the `SHEET_ID` secret isn't set, so the
site builds on day one before the sheet exists.

The exporter refuses to write if an `address`, `confirmation` or `check_in`
column ever appears in the `days` tab. Belt and braces against someone
"helpfully" merging tabs.

## 4. Things carried over from the Dolomites notes

- Prefix CSS classes per subsystem. `.card` colliding with a Leaflet divIcon
  cost real time last year.
- Wikimedia photos via `Special:FilePath/<name>?width=760` with an `onerror`
  that hides the img. Hotlink, don't embed.
- `weather.js` pattern: Open-Meteo, one regional coordinate, 30 min
  localStorage cache. Reusable as-is with NZ coordinates and `Pacific/Auckland`.
- A stat that says "3 BEDS" gets read as headcount. Say "6 · OF US".
- Free GitHub plan means public repo for Pages. Already decided that's fine.

## 5. Open questions

1. Look and feel: decided 2026-09-02. Full-bleed satellite like the Dolomites
   map, with a basemap switcher (CARTO Light, Voyager, OpenTopoMap). Default
   to be chosen at the end once Luke has seen them all. See PLAN.md.
2. Dates. The sheet has a `date` column but v1 had none. Fill in once flights
   are booked.
3. Whether days 1 and 2 are both Christchurch (per the latest message) or the
   v1 shape (straight to Wanaka). The CSVs currently follow v1.

## 6. File inventory

| file                          | what it is                                        |
|-------------------------------|---------------------------------------------------|
| `SHEET_SCHEMA.md`             | tabs and columns for the Google Sheet             |
| `data/*.csv`                  | local copy of the sheet, and the CI fallback      |
| `scripts/fetch_sheet.py`      | sheet or CSV → `site/data.json`                   |
| `scripts/build.py`            | `site/` + data → `dist/`                          |
| `site/index.html`             | the page. Placeholder list view for now.          |
| `.github/workflows/build.yml` | nightly + manual build and Pages deploy           |
| `PLAN.md`                     | phased build plan, ticked off as work lands       |
| `scripts/seed_sheet.py`       | one-off: CSVs → sheet tabs (robot key, Editor)    |

## 2026-09-03: the Google side, done from the terminal

gcloud via winget, `gcloud auth login` in the browser once, then everything
else scripted: project `aotearoa-26`, Sheets + Drive APIs, service account
`trip-site-reader`, key straight into a repo secret with `gh secret set`.

What didn't work: `gcloud auth application-default login --scopes=...` so
gspread could create the sheet *as Luke*. Two attempts hit a CSRF state
mismatch because Luke's own login and mine shared `localhost:8085`, and the
plain command without `--scopes` grants no Sheets access. gcloud also warns
that Sheets/Drive scopes on its default client ID are being blocked soon, so
that path has a shelf life anyway.

What did: Luke made a blank sheet and shared it with the robot as Editor.
The robot found it by listing its own Drive (`gc.list_spreadsheet_files()`),
so no URL had to change hands, then `seed_sheet.py` filled the four tabs.
The robot stays Editor: Luke wants to build the journey with Claude editing the tables from here, and the build itself only reads. First sheet-driven deploy is live.

## 2026-09-03: state of play, and what's next

### Where things stand

Phases 0 and 1 are done. The loop works end to end and was proven the only
way that counts: edit a cell in the sheet, press *Run workflow*, the live
page changes. Then reverted.

- Repo: `lukexyz/aotearoa-26`, public. Site: `https://lukexyz.github.io/aotearoa-26/`
- Sheet: "New Zealand Aotearoa Trip - 2026", owned by Luke, four tabs seeded
  from `data/*.csv`. The robot service account is Editor.
- Secrets `SHEET_ID` and `GOOGLE_SERVICE_ACCOUNT_JSON` are set on the repo.
  The key also lives locally as `service-account.json` (gitignored).
- Builds: nightly 02:00 NZDT, on push (except `*.md`), and on demand.
- The page itself is still the placeholder list view.

### How to work with it now

- **Edit the itinerary in the sheet.** That's the whole point. `from`/`to`/
  `place` must match a `places.name`; new town means a new `places` row first
  (right-click in Google Maps for lat, lng).
- **Publish now** rather than waiting for the cron: Actions tab → *Build from
  Google Sheet and deploy* → *Run workflow*. About a minute.
- **A red run** means a sheet typo. The message names the cell
  (`days!F8: to is 'Franz Joseph', did you mean 'Franz Josef'?`). The old
  site stays up until it's fixed.
- **Claude can write to the sheet** via gspread with the robot key, so
  "add two nights in Golden Bay" can be done from the terminal. The CSVs in
  `data/` are now a *fallback and seed*, not the source of truth. When the
  sheet drifts from them, refresh the CSVs from the sheet, not the reverse.
  (Todo: a `--dump` flag on `fetch_sheet.py` to do exactly that.)
- **Locally:** `python scripts/fetch_sheet.py --check` validates the sheet;
  `--local` uses the CSVs. `SHEET_ID` and `GOOGLE_SERVICE_ACCOUNT_JSON` must
  be in the env for sheet mode. gcloud is on the machine but a fresh shell
  needs the PATH refreshed.

### Sheet content todos (anyone)

- [ ] Dates, once flights are booked. Keep the column as plain text
      `2026-10-24` so it survives locale formatting.
- [ ] Decide days 1 and 2: straight to Wanaka (current, v1) or two
      Christchurch nights first. Open question 3 above.
- [ ] `places.photo`: a Wikimedia Commons filename per sleeping town at
      least. Blank cells just mean no photo card.
- [ ] Sanity-check the 21 sets of coordinates against Google Maps; they were
      typed from memory.
- [ ] `bookings` rows as things get booked. Never leaves the sheet.
- [ ] Doubtful Sound and the Lake Dunstan e-bikes need booking well ahead;
      they're already `type = booked` / `activity` in `stops`.

### Code todos (Claude)

- [ ] **Phase 2, the map page.** Full-bleed satellite, basemap switcher,
      day nav, brief panel, photo cards, bed halo, mobile layout. Everything
      read from `window.TRIP_DATA`, nothing South Island-specific in the
      HTML. See PLAN.md for the full list.
- [ ] `fetch_sheet.py --dump` to refresh `data/*.csv` from the sheet.
- [ ] Bump `actions/checkout` and `actions/setup-python` off Node 20 when
      next touching the workflow.
- [ ] `seed_sheet.py --create` (the ADC path) is dead weight now; either
      delete it or leave it with a comment saying why it's unused.
- [ ] Phases 3 to 6 per PLAN.md: OSRM road routes, weather and countdown,
      offline PWA, final basemap pick.

### Things to remember

- The privacy line is the `bookings` tab. Don't add address-like columns to
  the other tabs; the exporter will refuse and the build goes red anyway.
- Don't use "Publish to web" on the sheet. Sharing with named accounts is
  what keeps bookings private.
- The robot key is in the repo secret and on this disk. Rotate it from the
  Cloud console if it ever leaks; `gh secret set` takes the new file.
