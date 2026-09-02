# Build plan — South Island 2026 trip site

Status as of 2026-09-02. Phases are in order; each one ships something usable
on its own. Ticks are updated as work lands.

Decisions already made:

- Itinerary lives in a shared Google Sheet; a GitHub Action rebuilds the site
  nightly and on demand. Bookings tab never leaves the sheet.
- Public repo, public site, `noindex`. No encryption, no auth.
- Full-bleed satellite map by default, Dolomites layout, with a basemap
  switcher (Satellite / CARTO Light / Voyager / OpenTopoMap). Luke picks the
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
- [x] Share the sheet with the service account email (drop from Editor to Viewer now the seed is done)
- [x] Add `SHEET_ID` and `GOOGLE_SERVICE_ACCOUNT_JSON` repo secrets

Done when: editing a cell in the sheet and pressing *Run workflow* changes
the live page.

## Phase 2 — The map page

Goal: replace the placeholder with the real app. Same skeleton as the
Dolomites map, every trip-specific value read from `window.TRIP_DATA`.

Layout:
- [ ] Full-bleed Leaflet map (cdnjs 1.9.4), top bar with brand, day nav,
      basemap switcher. Cream/amber palette from the v1 image, dark chrome
      from the Dolomites site.
- [ ] Basemaps: Esri World Imagery + CARTO label overlay (default), CARTO
      Light, CARTO Voyager, OpenTopoMap. Switcher in the top-right. Choice
      remembered in `localStorage`. One `DEFAULT_BASEMAP` constant to flip
      later.
- [ ] Day nav: Overview + one chip per day (day number, date if set), prev/next
      arrows, left/right keys. Opens on today's day if we're mid-trip.
- [ ] Brief panel (left): leg label, title, from → to, drive-time chip, notes,
      stop list with links and icons, "Sleeping in X · booking details ↗"
      deep-linked to the sheet's bookings tab.
- [ ] Photo cards (right, up to three per day) from `places.photo`, Wikimedia
      hotlinked with `onerror` fallback, numbered to match pins.
- [ ] Tonight's bed halo at the `to` town, pulsing, behind the numbered pins.

Map content:
- [ ] Per day: polyline `from` → stops with a `place` → `to`, straight lines
      for now. Numbered pins for stops, waypoint dots for pass-through places.
      Fit to that day's places with padding for the panels.
- [ ] Overview: the whole loop, one pin per sleeping town with night counts,
      legs in distinct colours, fit to the island.
- [ ] Legend: driving, activity (bike/boat), optional.

Mobile (everyone will use this from a phone in the car):
- [ ] Below 760px: map is the top ~45vh, brief becomes a scrollable sheet
      below, photo cards collapse into a horizontal strip, nav chips scroll.
- [ ] Tap targets ≥ 44px, no hover-only affordances.

Hygiene:
- [ ] Prefix every CSS class per subsystem (`nav-`, `brief-`, `card-`,
      `pin-`) so nothing collides with Leaflet's divIcons again.
- [ ] Sheet-first test: change a town in `days.csv`, rebuild, confirm the map
      moves without touching HTML.

Done when: the site reads as well as the Dolomites one and nothing about the
South Island is hardcoded in `index.html`.

## Phase 3 — Routes that follow the road

Goal: driving legs trace SH6/SH8/SH1 instead of cutting across the Alps.

- [ ] `scripts/routes.py`: for each day, call OSRM (`router.project-osrm.org`)
      with the day's place sequence, write the geometry, distance and
      duration into `data.json`. Straight-line fallback and a warning if the
      request fails. Runs in the workflow after the fetch step.
- [ ] Cache responses in `site/routes.cache.json` keyed by the place sequence,
      committed, so a nightly rebuild only calls OSRM for changed days.
- [ ] Auto-fill `drive_time` from OSRM when the sheet cell is blank; the sheet
      wins when it isn't.
- [ ] Non-driving legs (Doubtful Sound boat, Great Taste Trail, Lake Dunstan
      ride) drawn as dashed spurs from a `stops.type`, not routed.

Done when: the Day 7 line goes over Haast Pass and says roughly 6h30 without
anyone typing it.

## Phase 4 — Live bits

- [ ] Port `weather.js`: Open-Meteo forecast for the current day's town,
      `Pacific/Auckland`, 30 min cache. Shown only when the trip is within
      the 7-day forecast window; hidden otherwise.
- [ ] Countdown on the overview until day 1, then "Day N of 11" during.
- [ ] Punakaiki tide: link to the LINZ tide table for the day, so the
      blowhole call can be made the night before.
- [ ] Optional `stops.type = booked` badge with a link straight to the sheet
      row.

## Phase 5 — Offline

- [ ] `manifest.json` + icon so it installs to the home screen.
- [ ] Service worker: cache-first for `index.html`, Leaflet and the current
      basemap tiles as they're viewed, capped size. Pre-cache nothing
      speculative; tile corridors are too big.
- [ ] Verify in airplane mode: the page opens, today's brief and stops are
      readable, previously viewed map areas still render.

## Phase 6 — Finish

- [ ] Luke picks the default basemap; flip `DEFAULT_BASEMAP`.
- [ ] Dates filled in once flights are booked.
- [ ] Photos for every sleeping town and headline stop.
- [ ] README gets the live link; MUSINGS gets the retrospective.
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
