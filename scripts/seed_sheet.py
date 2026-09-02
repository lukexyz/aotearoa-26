"""Push data/*.csv into a Google Sheet, one tab per file.

Two ways to run it:

    # 1. Create a brand-new sheet in *your* Drive, seed it, share it with the
    #    service account as Viewer. Uses gcloud application-default credentials:
    #    gcloud auth application-default login --scopes=.../spreadsheets,.../drive,.../cloud-platform
    python scripts/seed_sheet.py --create "Aotearoa 2026" --share trip-site-reader@aotearoa-26.iam.gserviceaccount.com

    # 2. Re-seed an existing sheet using the service account key (the sheet
    #    must be shared with the service account as Editor for this to work).
    python scripts/seed_sheet.py <sheet id or url> [--key service-account.json]

Existing tabs with the same names are cleared and rewritten, other tabs are
left alone.
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

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
TABS = ["days", "stops", "places", "bookings"]
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]


def sheet_id_from(arg: str) -> str:
    m = re.search(r"/d/([A-Za-z0-9_-]+)", arg)
    return m.group(1) if m else arg


def client_as_user() -> gspread.Client:
    """Act as the person who ran `gcloud auth application-default login`."""
    import google.auth
    creds, _ = google.auth.default(scopes=SCOPES)
    return gspread.authorize(creds)


def client_as_robot(key: Path) -> gspread.Client:
    from google.oauth2.service_account import Credentials
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or key.read_text(encoding="utf-8")
    return gspread.authorize(Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES))


def seed(book: gspread.Spreadsheet) -> None:
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

    # a fresh sheet arrives with an empty "Sheet1"; drop it once our tabs exist
    if "Sheet1" in existing and len(book.worksheets()) > 1:
        book.del_worksheet(existing["Sheet1"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet", nargs="?", help="existing sheet id or URL (robot mode)")
    ap.add_argument("--create", metavar="TITLE", help="create a new sheet with this title (user mode)")
    ap.add_argument("--share", metavar="EMAIL", help="with --create: share read-only with this account")
    ap.add_argument("--key", default=ROOT / "service-account.json", help="service-account JSON key file")
    args = ap.parse_args()

    if args.create:
        gc = client_as_user()
        book = gc.create(args.create)
        print(f"created '{args.create}'")
        seed(book)
        if args.share:
            book.share(args.share, perm_type="user", role="reader", notify=False)
            print(f"shared read-only with {args.share}")
    elif args.sheet:
        book = client_as_robot(Path(args.key)).open_by_key(sheet_id_from(args.sheet))
        seed(book)
    else:
        ap.error("give a sheet id/URL, or --create TITLE")

    print(f"done: https://docs.google.com/spreadsheets/d/{book.id}/edit")
    print(f"SHEET_ID={book.id}")


if __name__ == "__main__":
    sys.exit(main())
