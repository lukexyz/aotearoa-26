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
| `scripts/routes.py`           | adds OSRM road geometry to `data.json`            |
| `data/routes.json`            | cache of OSRM answers, keyed by coordinates       |
| `scripts/photos.py`           | finds a Wikipedia photo per place → `data.json`   |
| `data/photos.json`            | cache of photo picks and credits, keyed by name   |
| `scripts/build.py`            | `site/` + data → `dist/`                          |
| `site/index.html`             | the page: Leaflet map, day nav, brief, cards      |
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
The robot stays Editor: Luke wants to build the journey with Claude editing
the tables from here, and the build itself only reads. First sheet-driven
deploy is live.

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

- [x] Dates: in the sheet, 25 Oct to 4 Nov. Only day 1 strictly needs one now.
- [ ] Decide days 1 and 2: straight to Wanaka (current, v1) or two
      Christchurch nights first. Open question 3 above.
- [x] `places.photo`: now automatic (2026-09-03). Fill the cell only to
      override; see README → Photos.
- [ ] Sanity-check the 21 sets of coordinates against Google Maps; they were
      typed from memory.
- [ ] `bookings` rows as things get booked. Never leaves the sheet.
- [ ] Doubtful Sound and the Lake Dunstan e-bikes need booking well ahead;
      they're already `type = booked` / `activity` in `stops`.

### Code todos (Claude)

- [x] **Phase 2, the map page.** Shipped 2026-09-03, see below.
- [x] `fetch_sheet.py --dump` to refresh `data/*.csv` from the sheet.
- [ ] Bump `actions/checkout` and `actions/setup-python` off Node 20 when
      next touching the workflow.
- [x] `seed_sheet.py --create` left in place with a comment saying why it's parked.
- [x] Phase 3, road routes. Shipped 2026-09-03, see below. Dashed spurs for
      the bike and boat legs still to do.
- [ ] Phases 4 to 6 per PLAN.md: weather and countdown, offline PWA, final
      basemap pick.

### Things to remember

- The privacy line is the `bookings` tab. Don't add address-like columns to
  the other tabs; the exporter will refuse and the build goes red anyway.
- Don't use "Publish to web" on the sheet. Sharing with named accounts is
  what keeps bookings private.
- The robot key is in the repo secret and on this disk. Rotate it from the
  Cloud console if it ever leaks; `gh secret set` takes the new file.

## 2026-09-03: Phase 2, the page itself

`site/index.html` is now the real thing: the Dolomites skeleton (full-bleed
Leaflet, top bar with day chips, brief panel left, photo cards right) rebuilt
so that every trip-specific value comes from `window.TRIP_DATA`. The only
words about New Zealand in the HTML are the brand and the page title.

What the page derives from the three tabs, so nobody has to type it twice:

- The **route per day** is `from` → each stop's `place` → `to`, de-duplicated,
  as straight lines. Phase 3 swaps these for road geometry.
- **Numbered pins** are the stops that have a `place`, in stop order, then
  tonight's town gets the bed pin and the halo. The brief's stop list shows
  the same numbers, and the photo cards match.
- The **overview** draws every day's line in its leg's colour and one pin per
  sleeping town with a night count. Christchurch gets ✈ because it's the
  first `from`. Click a line to jump to that day.
- **Dates** come from `days.date`; only day 1 is required. The exporter fills
  blanks from the nearest earlier date plus the day-number gap, so inserting
  a day means retyping one date, not eleven. A date that isn't `YYYY-MM-DD`
  fails the build with the cell named, because Sheets loves to localise.
- Stats on the overview (towns, total driving hours) are summed from
  `drive_time` strings like `4h30`. Anything else parses as zero.

Basemaps: Esri satellite with CARTO labels is the default, with CARTO Light,
Voyager and OpenTopoMap behind a switcher. The pick is saved in
`localStorage`. `DEFAULT_BASEMAP` at the top of the script is the one
constant to flip once Luke has chosen.

Mobile: below 760px the map is fixed to the top 45vh and the cards and brief
scroll beneath it. Legend and sheet button are hidden there. Nav chips are 44px
tall on purpose.

### Flights, and a fifth tab

Flights are booked, so the itinerary has hard edges now: wheels down at
Christchurch early afternoon on Sunday 25 October, wheels up early evening on
Saturday 7 November. The sheet's `days` currently runs to 4 November, so there
are **two unplanned nights (5 and 6 Nov) plus the departure day** to fill in.
Christchurch, Akaroa, or an extra night somewhere on the way back are the
obvious candidates. Open question, Luke's call.

The flight details went into a new `flights` tab, deliberately private like
`bookings`: the exporter can't see it, `--dump` can't write it, and
`seed_sheet.py` won't overwrite it once it has rows. One row per leg per
booking with a `who` column, since six people may not all be on the same
planes. Passenger dates of birth and the like were left out on purpose; the
sheet is shared with the whole group and that's not the place for them.

### Tested how

Local build from the CSVs and from the sheet, `node --check` on the inlined
script, a grep of the built HTML for anything from the private tabs, and
headless Chrome screenshots at 1440×900 and 390×844 of the overview and a busy
day. Not yet tested on a real phone. Wikimedia photos are untested because no
`places.photo` cells are filled in yet.

### Next

Phase 3 (OSRM road geometry, auto `drive_time`), then Phase 4 (weather,
countdown). Before either: photos, and the two missing nights.

## 2026-09-03: Phase 3, the drives follow the road

The straight lines are gone. `scripts/routes.py` runs after the fetch step and
asks the public OSRM server for a driving route between each consecutive pair
of places in a day (`from` → stop places → `to`, the same rule the page uses).
Seventeen requests for the whole trip, under a second each, no key.

Design choices, in case they need revisiting:

- **Cache by coordinates, not by day.** `data/routes.json` is keyed by
  `lat,lng>lat,lng`. Moving a stop, adding a day, reordering: only legs that
  have never been seen get fetched. A rebuild with no changes makes zero
  requests, which matters because OSRM's demo server is a courtesy.
- **Full geometry, simplified locally.** OSRM's own `simplified` overview is
  ~60 points for a 500 km leg, too coarse at zoom 11. `full` is 37 KB per
  leg. So the script fetches full and runs Douglas-Peucker at ~70 m. The
  whole trip's geometry is 10 KB inlined, and the road still hugs the valleys.
- **Never red.** A failed leg is logged as a warning and the page draws a
  straight segment for it. The build must not depend on a third-party server
  being up at 02:00.
- **The page stays dumb.** It looks up `days[].legs` in `routes`, decodes
  the polyline, and concatenates. Anything missing falls back to the two
  coordinates. No routing logic in JS, no runtime calls.
- **Drive times.** The sheet wins if it has a value. Blank cells get OSRM's
  estimate, shown with a `~`. `drive_km` always comes from OSRM. The script
  prints a sheet-vs-OSRM table, which is a decent sanity check: day 1 was
  typed as 4h30 and OSRM says 5h40, which is nearer the truth.

What it turned up straight away: day 10 "via Kaiteriteri" had no Kaiteriteri
stop, so the route went straight down SH6 and OSRM said 1h35 against the
sheet's 3h45. Added the stops row and the line now goes over the hill to the
beach. The rule, now in the README: a detour you want drawn needs a stops row
with a `place`, not just a mention in the notes.

Not done: the non-driving legs. Nelson → Mapua is a bike ride, Manapouri →
Doubtful Sound is a boat, and both are currently drawn as the road OSRM would
drive. Dashed spurs from `stops.type` are the last Phase 3 item.

Tested: local build, `node --check` on the inlined script, headless
screenshots of the overview, day 7 (over Haast Pass) and day 10.

## 2026-09-03: Photos, found rather than typed

`scripts/photos.py` runs after routes: for each place with a blank `photo`
cell it fetches the lead image of the English Wikipedia article. Exact titles
first (`Name`, `Name, New Zealand`, `Name (New Zealand)`), then a search, and
a candidate only counts if the article's coordinates are within 40 km of the
place. Picks and Commons credit lines are cached in `data/photos.json`.

Three lessons from the first run, all now in the code:

- **`pilimit` defaults to 1.** Ask the API for 40 titles with
  `prop=pageimages` and only the first page gets an image; the rest look
  imageless and fall through to search, which is how Haast Pass became the
  township of Haast and Gibbston became Queenstown. `pilimit=max` and
  `colimit=max` fixed it.
- **Wikipedia 429s a fast burst** even with a proper User-Agent. One second
  between requests, backoff to a minute, and batching (two title requests for
  the whole trip) keeps it civil. A failed lookup is never cached as "nothing
  found", it's just retried next build.
- **The script must be re-runnable on its own output.** First version wrote
  the pick into `photo`, then treated that as a sheet override on the second
  run. The sheet's cell now lives in `photo_src`.

Lead images of town articles are often a building (Renwick's post office,
Westport's municipal chambers). For a road trip page the sheet's `wiki:`
override is the fix: `wiki:Doubtful Sound` for Manapouri, `wiki:Pancake Rocks`
for Punakaiki, and so on. The README's Photos section is the explainer for
whoever changes the sheet.
