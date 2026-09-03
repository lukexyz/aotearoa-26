# Build plan — South Island 2026 trip site

Status as of 2026-09-03. Phases are in order; each one ships something usable
on its own. Ticks are updated as work lands.

Decisions already made:

- Itinerary lives in a shared Google Sheet; a GitHub Action rebuilds the site
  nightly and on demand. Bookings tab never leaves the sheet.
- Public repo, public site, `noindex`. No encryption, no auth.
- Full-bleed satellite map by default, Dolomites layout, with a basemap
  switcher (Satellite / OpenTopoMap; CARTO Light and Voyager dropped 2026-09-03). Luke picks the
  final default at the end.
- Data is inlined into the page at build time so it works with no signal.

---

## Phase 0 — Plumbing  ✅ done

- [x] `SHEET_SCHEMA.md`: `days`, `stops`, `places`, `bookings`
- [x] `data/*.csv` seeded from the v1 itinerary
- [x] `scripts/fetch_sheet.py` (sheet via service account, or `--local`)
- [x] `scripts/build.py` (inlines JSON into `dist/index.html`)
- [x] `.github/workflows/build.yml` (nightly 02:00 NZDT, manual, on push; CSV fallback)
- [x] Placeholder `site/index.html` list view
- [x] Verified locally: 11 days, 11 stops, 21 places, bookings absent

## Phase 1 — Live on GitHub Pages  ✅ done 2026-09-03

Goal: a URL that exists, rebuilds from the CSVs, and proves the Action works
before the sheet is involved.

Claude:
- [x] `git init`, first commit, `gh repo create lukexyz/aotearoa-26 --public`
- [x] Set Pages source to GitHub Actions via `gh api`
- [x] Push, watch the first run, confirm the placeholder is live at
      https://lukexyz.github.io/aotearoa-26/
- [x] Add `--check` to `fetch_sheet.py`: fail the build with a readable message
      if a `from`/`to`/`place` name isn't in `places`, if `day` isn't an
      integer, or if a tab is missing. Sheet typos should break the build
      loudly, not render a blank map.

Luke (about ten minutes, steps in README):
- [x] Create the sheet ("New Zealand Aotearoa Trip - 2026"), seeded by `seed_sheet.py`; share with the crew
- [x] Google Cloud project `aotearoa-26` → Sheets + Drive APIs → `trip-site-reader` service account → key
- [x] Share the sheet with the service account email. Kept as Editor so Claude can edit the tables from the terminal too.
- [x] Add `SHEET_ID` and `GOOGLE_SERVICE_ACCOUNT_JSON` repo secrets

Done when: editing a cell in the sheet and pressing *Run workflow* changes
the live page.

## Phase 2 — The map page  ✅ done 2026-09-03

Goal: replace the placeholder with the real app. Same skeleton as the
Dolomites map, every trip-specific value read from `window.TRIP_DATA`.

Layout:
- [x] Full-bleed Leaflet map (cdnjs 1.9.4), top bar with brand, day nav,
      basemap switcher. Cream/amber palette from the v1 image, dark chrome
      from the Dolomites site.
- [x] Basemaps: Esri World Imagery + CARTO label overlay (default) and
      OpenTopoMap. Switcher in the top-right. (CARTO Light and Voyager were
      dropped 2026-09-03: they fail in the browser without an API key.) Choice
      remembered in `localStorage`. One `DEFAULT_BASEMAP` constant to flip
      later.
- [x] Day nav: Overview + one chip per day (day number, date if set), prev/next
      arrows, left/right keys. Opens on today's day if we're mid-trip, or on
      `#day-N` from the URL.
- [x] Brief panel (left): leg label, title, from → to, drive-time chip, notes,
      stop list with links and icons, "Sleeping in X · booking details ↗"
      deep-linked to the sheet's bookings tab.
- [x] Photo cards (right, up to three per day) from `places.photo`, Wikimedia
      hotlinked with `onerror` fallback, numbered to match pins.
- [x] Tonight's bed halo at the `to` town, pulsing, behind the numbered pins.

Map content:
- [x] Per day: polyline `from` → stops with a `place` → `to`, straight lines
      for now. Numbered pins for stops, waypoint dots for pass-through places.
      Fit to that day's places with padding for the panels.
- [x] Overview: the whole loop, one pin per sleeping town with night counts,
      legs in distinct colours, fit to the island.
- [x] Legend: drive, stop, tonight's bed. (Activity spurs come with Phase 3.)

Mobile (everyone will use this from a phone in the car):
- [x] Below 760px: map is the top ~45vh, brief becomes a scrollable sheet
      below, photo cards collapse into a horizontal strip, nav chips scroll.
- [x] Tap targets ≥ 44px, no hover-only affordances.

Hygiene:
- [x] Prefix every CSS class per subsystem (`nav-`, `brief-`, `card-`,
      `pin-`) so nothing collides with Leaflet's divIcons again.
- [x] Sheet-first test: dates typed into the sheet appeared on the chips and
      brief without touching HTML.

Done when: the site reads as well as the Dolomites one and nothing about the
South Island is hardcoded in `index.html`.

## Phase 3 — Routes that follow the road  ✅ done 2026-09-03

Goal: driving legs trace SH6/SH8/SH1 instead of cutting across the Alps.

- [x] `scripts/routes.py`: one OSRM request per consecutive pair of places
      (`router.project-osrm.org`, no key), geometry simplified to ~70 m and
      written into `data.json` as encoded polylines with distance and
      duration. Straight-line fallback and a `::warning::` if a request
      fails. Runs in the workflow after the fetch step.
- [x] Cache in `data/routes.json` keyed by the two coordinates, committed, so
      a nightly rebuild with no changes makes no requests and a new stop
      only fetches the legs either side of it.
- [x] Auto-fill `drive_time` from OSRM when the sheet cell is blank (shown as
      `~5h40`); the sheet wins when it isn't. `drive_km` always comes from OSRM.
- [x] Non-driving legs (Doubtful Sound boat, Great Taste Trail, Lake Dunstan
      ride) drawn as dashed spurs from a `stops.type` (bike, boat, ferry,
      cruise, kayak, hike, tramp, ride), not routed. The rule lives in
      `fetch_sheet.py` (`SPUR_TYPES`), which tags each stop; routes.py and the
      page just read the flag.

Done when: the Day 7 line goes over Haast Pass and says roughly 6h30 without
anyone typing it. (It does: OSRM says 6h55 and 509 km.)

## Phase 3b — Photos without hunting  ✅ done 2026-09-03

- [x] `scripts/photos.py`: Wikipedia lead image per place, exact title then
      search, 40 km coordinate check, cached in `data/photos.json`. Sheet
      `photo` cell overrides (`wiki:Title`, Commons filename, URL, `-`).
- [x] Credit + licence link on cards and popups from Commons extmetadata.
- [x] `--preview` contact sheet; README "Photos" explainer.

## Phase 4 — Live bits  ✅ done 2026-09-03

- [x] Open-Meteo daily forecast for tonight's town, `Pacific/Auckland`,
      16-day window, 30 min cache in `localStorage`. Shown in the day brief
      only when the day is inside the window; hidden when offline or past.
- [x] Countdown in the top bar and the overview stats until day 1, then
      "Day N of 11" during, "Home again" after. By New Zealand's calendar.
- [x] Punakaiki tide: `stops.link` = `tides` links to NIWA's tide forecaster
      for the stop's coordinates on that day (LINZ has no per-day URL; NIWA
      reads latitude/longitude/startDate from the query string).
- [x] `stops.type = booked` chip linking to the bookings tab (a row-level
      link would need the row number exported; the tab is close enough).

## Phase 5 — Offline  ✅ done 2026-09-03

- [x] `manifest.webmanifest` + PNG icons (`scripts/make_icons.py`) so it
      installs to the home screen on iOS and Android.
- [x] `site/sw.js`: page network-first with a 4 s timeout then cache;
      Leaflet cache-first; tiles and photos cache-first as viewed, capped at
      2,500, oldest dropped. Fetched with CORS so nothing is stored opaque.
      Nothing pre-cached speculatively. `build.py` stamps a page hash into
      the worker so each deploy replaces the page cache.
- [x] Verified headless: page installed over two loads, then every host
      blackholed (`--host-resolver-rules="MAP * 127.0.0.1"`): the page, day
      brief, photos and the viewed tiles all rendered from cache.

## Phase 6 — Finish

- [ ] Luke picks the default basemap; flip `DEFAULT_BASEMAP`.
- [x] Dates filled in once flights are booked. (Flights booked 2026-09; trip 25 Oct – 7 Nov.)
- [x] Photos for every sleeping town and headline stop (automatic since Phase 3b).
- [ ] MUSINGS gets the retrospective. (README already has the live link.)
- [ ] Share the URL and the sheet with the other five.

---

## Risks and known limits

- **OSRM demo server** is rate-limited and offers no uptime promise. Hence
  the cache and the straight-line fallback.
- **Esri World Imagery** is used under its free tier for non-commercial
  display, same as the Dolomites site. Attribution stays on the map.
- **Wikimedia hotlinks** occasionally die when a file is renamed. `onerror`
  hides the card image; the page keeps working.
- **Coordinates** in `places.csv` were typed from memory, ±300 m. Fine for
  the map, not for navigation. Google Maps links on stops cover the rest.
- **Free GitHub plan** means the repo is public. Already accepted.
- **Sheet edits by six people** will produce typos. Phase 1's `--check`
  turns those into a red X on the Actions tab with a message naming the
  cell, instead of a silently broken page.

## What only Luke can do

Sheet creation, Google Cloud service account, repo secrets, picking the
default basemap, dates, and the final "ship it" to the group chat.
