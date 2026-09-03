"""Pull the itinerary out of the shared Google Sheet (or local CSVs) into site/data.json.

Usage:
    python scripts/fetch_sheet.py            # reads the sheet, needs env vars below
    python scripts/fetch_sheet.py --local    # reads data/*.csv, no credentials needed
    python scripts/fetch_sheet.py --check    # validate only, write nothing (add --local to check the CSVs)
    python scripts/fetch_sheet.py --dump     # refresh data/*.csv from the sheet (exported tabs only)

Validation always runs. A typo in the sheet (a town that isn't in `places`, a
day number that isn't a number) exits non-zero with a message naming the cell,
so the Actions run goes red instead of publishing a blank map.

Env vars for sheet mode:
    SHEET_ID                     the long id in the sheet's URL
    GOOGLE_SERVICE_ACCOUNT_JSON  full JSON of a service-account key (the sheet must
                                 be shared with that account's email, viewer is enough)

Only the tabs in EXPORT_TABS are read. The private tabs (`bookings`, `flights`)
are deliberately not in that list, so addresses, confirmation numbers and
passenger details never reach the website, and `--dump` never writes them to
disk either.

Dates: only `days.date` on the first day needs filling in. Blank dates on later
days are derived from the nearest earlier date plus the day-number difference,
so inserting a day in the sheet doesn't mean retyping every date after it.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_FILE = ROOT / "site" / "data.json"

EXPORT_TABS = ["days", "stops", "places"]
PRIVATE_TABS = ["bookings", "flights"]   # never read, never written

# stops of these types are legs we don't drive: a bike trail, a boat across a
# lake. They're drawn as a dashed spur from the last road place and skipped by
# the road router. Compared case-insensitively.
SPUR_TYPES = {"bike", "boat", "ferry", "cruise", "kayak", "hike", "tramp", "ride"}


def clean(rows: list[dict]) -> list[dict]:
    """Strip whitespace, drop fully-empty rows, normalise keys to snake_case."""
    out = []
    for r in rows:
        r = {str(k).strip().lower().replace(" ", "_"): (str(v).strip() if v is not None else "")
             for k, v in r.items() if k}
        if any(r.values()):
            out.append(r)
    return out


def read_local() -> dict[str, list[dict]]:
    tabs = {}
    for name in EXPORT_TABS:
        path = DATA_DIR / f"{name}.csv"
        with path.open(newline="", encoding="utf-8") as f:
            tabs[name] = clean(list(csv.DictReader(f)))
    return tabs


def read_sheet() -> dict[str, list[dict]]:
    import gspread  # imported lazily so --local works without it installed
    from google.oauth2.service_account import Credentials

    sheet_id = os.environ.get("SHEET_ID")
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sheet_id or not sa_json:
        sys.exit("SHEET_ID and GOOGLE_SERVICE_ACCOUNT_JSON must be set (or use --local)")

    creds = Credentials.from_service_account_info(
        json.loads(sa_json),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    book = gspread.authorize(creds).open_by_key(sheet_id)

    tabs = {}
    for name in EXPORT_TABS:
        ws = book.worksheet(name)
        tabs[name] = clean(ws.get_all_records())
        # remember the tab id so the site can deep-link to it
        tabs[f"_{name}_gid"] = ws.id
    # gid of the private tab, for the "open bookings" button. The id is not secret;
    # the sheet's own sharing settings are what protect the contents.
    try:
        tabs["_bookings_gid"] = book.worksheet("bookings").id
    except gspread.WorksheetNotFound:
        tabs["_bookings_gid"] = 0
    return tabs


def dump_local(tabs: dict) -> None:
    """Write the exported tabs to data/*.csv, header order as in the sheet. Private tabs are never touched."""
    for name in EXPORT_TABS:
        rows = tabs[name]
        if not rows:
            continue
        path = DATA_DIR / f"{name}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {path.relative_to(ROOT)}: {len(rows)} rows")


def cell(rows: list[dict], row: int, col: str) -> str:
    """Spreadsheet address (e.g. C4) for a data row and column name.

    `row` is 1-based over the data rows; row 1 of the sheet is the header, so
    data row 1 lives on sheet row 2. Column letter comes from the header order,
    which the dict preserves.
    """
    header = list(rows[0])
    n = header.index(col) + 1 if col in header else 1
    letters = ""
    while n:
        n, r = divmod(n - 1, 26)
        letters = chr(65 + r) + letters
    return f"{letters}{row + 1}"


def validate(tabs: dict) -> list[str]:
    """Return human-readable problems with the exported tabs. Empty means fine."""
    problems: list[str] = []

    for name in EXPORT_TABS:
        if name not in tabs:
            problems.append(f"{name}: tab is missing")
    if problems:
        return problems

    required = {"days": ["day", "to"], "stops": ["day", "name"], "places": ["name", "lat", "lng"]}
    for tab, cols in required.items():
        rows = tabs[tab]
        if not rows:
            problems.append(f"{tab}: tab is empty")
            continue
        have = set(rows[0])
        for c in cols:
            if c not in have:
                problems.append(f"{tab}: no '{c}' column in row 1 (found: {', '.join(sorted(have))})")
    if problems:
        return problems

    days, stops, places = tabs["days"], tabs["stops"], tabs["places"]

    # places: unique names, coordinates that parse and land in New Zealand
    known: dict[str, int] = {}
    for i, p in enumerate(places, start=1):
        name = p.get("name", "")
        if not name:
            problems.append(f"places!{cell(places, i, 'name')}: blank name")
            continue
        if name in known:
            problems.append(f"places!{cell(places, i, 'name')}: '{name}' is also on row {known[name] + 1}")
        known[name] = i
        for col, lo, hi in (("lat", -48.5, -33.5), ("lng", 165.0, 179.5)):
            raw = p.get(col, "")
            try:
                v = float(raw)
            except ValueError:
                problems.append(f"places!{cell(places, i, col)}: {col} for '{name}' is '{raw}', expected a number")
                continue
            if not lo <= v <= hi:
                problems.append(f"places!{cell(places, i, col)}: {col} {v} for '{name}' is outside "
                                f"New Zealand ({lo} to {hi}); lat and lng swapped?")

    def check_place_ref(tab: str, rows: list[dict], i: int, col: str, value: str) -> None:
        if value in known:
            return
        hint = difflib.get_close_matches(value, known, n=1, cutoff=0.6)
        did = f", did you mean '{hint[0]}'?" if hint else ""
        problems.append(f"{tab}!{cell(rows, i, col)}: {col} is '{value}', which has no row in places{did}")

    # days: integer day numbers, from/to that exist in places
    day_numbers: dict[int, int] = {}
    for i, d in enumerate(days, start=1):
        raw = d.get("day", "")
        try:
            n = int(raw)
        except ValueError:
            problems.append(f"days!{cell(days, i, 'day')}: day is '{raw}', expected a whole number")
            continue
        if n in day_numbers:
            problems.append(f"days!{cell(days, i, 'day')}: day {n} is also on row {day_numbers[n] + 1}")
        day_numbers[n] = i
        raw_date = d.get("date", "")
        if raw_date and parse_date(raw_date) is None:
            problems.append(f"days!{cell(days, i, 'date')}: date is '{raw_date}', expected 2026-10-25 style "
                            f"(format the column as plain text so Sheets doesn't localise it)")
        for col in ("from", "to"):
            v = d.get(col, "")
            if v:
                check_place_ref("days", days, i, col, v)
            elif col == "to":
                problems.append(f"days!{cell(days, i, 'to')}: blank; every day needs a town to sleep in")

    # stops: day must exist, optional place must exist
    for i, s in enumerate(stops, start=1):
        raw = s.get("day", "")
        try:
            n = int(raw)
        except ValueError:
            problems.append(f"stops!{cell(stops, i, 'day')}: day is '{raw}', expected a whole number")
            continue
        if n not in day_numbers:
            problems.append(f"stops!{cell(stops, i, 'day')}: day {n} ('{s.get('name', '')}') has no row in days")
        v = s.get("place", "")
        if v:
            check_place_ref("stops", stops, i, "place", v)

    return problems


def parse_date(raw: str) -> date | None:
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def fill_dates(days: list[dict]) -> None:
    """Derive blank dates from the nearest earlier dated day. Sorted input, mutates in place."""
    anchor: tuple[int, date] | None = None
    for d in days:
        n = int(d["day"])
        got = parse_date(d.get("date", ""))
        if got:
            anchor = (n, got)
        elif anchor:
            d["date"] = (anchor[1] + timedelta(days=n - anchor[0])).isoformat()


def shape(tabs: dict) -> dict:
    days = sorted(tabs["days"], key=lambda d: int(d.get("day") or 0))
    fill_dates(days)
    stops_by_day: dict[str, list[dict]] = {}
    for s in tabs["stops"]:
        if s.get("type", "").strip().lower() in SPUR_TYPES:
            s["spur"] = True
        stops_by_day.setdefault(s.get("day", ""), []).append(s)
    for d in days:
        d["stops"] = stops_by_day.get(d["day"], [])
    return {
        "sheet_id": os.environ.get("SHEET_ID", ""),
        "bookings_gid": tabs.get("_bookings_gid", 0),
        "days": days,
        "places": tabs.get("places", []),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="read data/*.csv instead of the sheet")
    ap.add_argument("--check", action="store_true", help="validate only, don't write data.json")
    ap.add_argument("--dump", action="store_true", help="write the exported tabs back to data/*.csv")
    args = ap.parse_args()
    if args.dump and args.local:
        ap.error("--dump reads the sheet; drop --local")

    tabs = read_local() if args.local else read_sheet()

    problems = validate(tabs)
    if problems:
        print(f"{len(problems)} problem(s) in the {'CSVs' if args.local else 'sheet'}:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        sys.exit(1)
    if args.check:
        print(f"ok: {len(tabs['days'])} days, {len(tabs['stops'])} stops, {len(tabs['places'])} places")
        return
    if args.dump:
        dump_local(tabs)
        return

    payload = shape(tabs)

    # belt and braces: refuse to write anything that looks like a private column
    forbidden = {"address", "confirmation", "check_in"}
    for d in payload["days"]:
        leaked = forbidden & set(d)
        if leaked:
            sys.exit(f"refusing to export private columns {leaked} found in days tab")

    OUT_FILE.parent.mkdir(exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT_FILE.relative_to(ROOT)}: {len(payload['days'])} days, "
          f"{sum(len(d['stops']) for d in payload['days'])} stops, "
          f"{len(payload['places'])} places")


if __name__ == "__main__":
    main()
