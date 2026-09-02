"""One-off: push data/*.csv into a blank Google Sheet, one tab per file.

Usage:
    python scripts/seed_sheet.py <sheet id or url> [--key service-account.json]

The sheet must be shared with the service account as Editor. Afterwards drop it
back to Viewer; the nightly build only reads. Existing tabs with the same names
are cleared and rewritten, other tabs are left alone.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
TABS = ["days", "stops", "places", "bookings"]


def sheet_id_from(arg: str) -> str:
    m = re.search(r"/d/([A-Za-z0-9_-]+)", arg)
    return m.group(1) if m else arg


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet", help="sheet id or full URL")
    ap.add_argument("--key", default=ROOT / "service-account.json",
                    help="service-account JSON key file (or set GOOGLE_SERVICE_ACCOUNT_JSON)")
    args = ap.parse_args()

    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or Path(args.key).read_text(encoding="utf-8")
    creds = Credentials.from_service_account_info(
        json.loads(raw), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    book = gspread.authorize(creds).open_by_key(sheet_id_from(args.sheet))
    existing = {ws.title: ws for ws in book.worksheets()}

    for name in TABS:
        with (DATA_DIR / f"{name}.csv").open(newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        if name in existing:
            ws = existing[name]
            ws.clear()
        else:
            ws = book.add_worksheet(name, rows=max(len(rows) + 20, 50), cols=len(rows[0]) + 2)
        ws.update(rows, "A1", value_input_option="RAW")  # RAW keeps "2026-10-24" and "4h30" as text
        ws.format("1:1", {"textFormat": {"bold": True}})
        ws.freeze(rows=1)
        print(f"{name}: {len(rows) - 1} rows")

    # a fresh sheet arrives with an empty "Sheet1"; drop it if we've added our own tabs
    if "Sheet1" in existing and len(book.worksheets()) > 1:
        book.del_worksheet(existing["Sheet1"])

    print(f"done: https://docs.google.com/spreadsheets/d/{book.id}/edit")
    print("now change the service account's access from Editor to Viewer")


if __name__ == "__main__":
    sys.exit(main())
