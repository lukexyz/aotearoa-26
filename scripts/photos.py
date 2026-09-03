"""Find a photo for every place: add Wikimedia imagery to site/data.json.

Usage:
    python scripts/photos.py                 # runs after fetch_sheet.py, rewrites site/data.json
    python scripts/photos.py --preview       # also write photos-preview.html, a contact sheet to eyeball
    python scripts/photos.py --refresh NAME  # forget the cached pick for one place (repeatable)
    python scripts/photos.py --refresh-all   # forget every automatic pick
    python scripts/photos.py --offline       # cache only, no network

Where a photo comes from, in order:

  1. The sheet's `places.photo` cell, if filled. Three forms are understood:
        https://...                        any image URL, used as-is (no credit shown)
        Some_File_Name.jpg                 a Wikimedia Commons filename
        wiki:Doubtful Sound                the lead image of that Wikipedia article
  2. Otherwise, automatically: the lead image of the English Wikipedia article
     for the place. Exact titles are tried first (`Name`, `Name, New Zealand`,
     `Name (New Zealand)`), then a search. A candidate only counts if the
     article has coordinates within 40 km of the place, so "Wakefield" can't
     become the one in Yorkshire.

Automatic picks and the credit lines for Commons files are cached in
data/photos.json, keyed by place name, so a rebuild makes no requests unless
the sheet gained a place. Delete a place's entry (or use --refresh) to pick
again. A place with nothing found just has no photo; the card shows its
gradient instead. The build never fails because of this script.

What goes into data.json for each place:
    photo         Commons filename or URL (the page turns filenames into hotlinks)
    photo_src     what the sheet cell said, so the script can be re-run on its own output
    photo_credit  "Artist · CC BY-SA 4.0", when known
    photo_page    the Commons file page, for the credit link
    photo_url     direct thumbnail URL on upload.wikimedia.org (the page falls back to Special:FilePath without it)
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "site" / "data.json"
CACHE_FILE = ROOT / "data" / "photos.json"
PREVIEW_FILE = ROOT / "photos-preview.html"

WIKI_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
UA = "aotearoa-26 trip site (github.com/lukexyz/aotearoa-26)"
TIMEOUT = 20
PAUSE = 1.0               # between requests; Wikipedia 429s a fast burst
MAX_KM = 40               # article must sit this close to the place's coordinates
BATCH = 40                # titles per query request (API max is 50)
THUMB_WIDTH = 760         # px asked for; Commons rounds to a standard size (960 today). A direct thumb.wikimedia.org
                          # URL, not the Special:FilePath redirect, so the browser can fetch it with CORS and cache it offline

sys.stdout.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------- http
def api(base: str, params: dict) -> dict | None:
    url = base + "?" + urllib.parse.urlencode(dict(params, format="json", formatversion=2))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                body = json.load(r)
            time.sleep(PAUSE)
            return body
        except urllib.error.HTTPError as e:
            wait = 10 * (attempt + 1) if e.code == 429 else 1.5
            print(f"  http {e.code} from {base.split('/')[2]}, retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            print(f"  request failed: {e}", file=sys.stderr)
            time.sleep(1.5)
    return None


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot((a[0] - b[0]) * 111, (a[1] - b[1]) * 111 * math.cos(math.radians(a[0])))


# ---------------------------------------------------------------- wikipedia
def query_titles(titles: list[str]) -> dict[str, dict] | None:
    """Resolve article titles (following redirects) → {requested title: page dict}. Batched. None if the API failed."""
    out: dict[str, dict] = {}
    for i in range(0, len(titles), BATCH):
        chunk = titles[i:i + BATCH]
        body = api(WIKI_API, {"action": "query", "titles": "|".join(chunk), "redirects": 1,
                              "prop": "pageimages|coordinates", "piprop": "name", "pilicense": "any",
                              "pilimit": "max", "colimit": "max"})     # without these only ONE page gets an image
        if not body:
            return None
        q = body.get("query", {})
        # map requested → final title through normalisation and redirects
        alias = {}
        for step in ("normalized", "redirects"):
            for m in q.get(step, []):
                alias[m["from"]] = m["to"]
        pages = {p["title"]: p for p in q.get("pages", [])}
        for t in chunk:
            final = t
            for _ in range(3):
                final = alias.get(final, final)
            if final in pages and not pages[final].get("missing"):
                out[t] = pages[final]
    return out


def search(name: str) -> list[dict] | None:
    body = api(WIKI_API, {"action": "query", "generator": "search", "gsrsearch": f"{name} New Zealand", "gsrlimit": 5,
                          "prop": "pageimages|coordinates", "piprop": "name", "pilicense": "any",
                          "pilimit": "max", "colimit": "max"})
    if body is None:
        return None
    pages = body.get("query", {}).get("pages", [])
    # a hit whose title contains the place name (Māpua for Mapua) beats a bigger neighbour that merely ranks higher
    return sorted(pages, key=lambda p: (fold(name) not in fold(p.get("title", "")), p.get("index", 99)))


def fold(s: str) -> str:
    """lowercase, macrons and other diacritics stripped: 'Kaikōura' → 'kaikoura'."""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


def acceptable(page: dict, at: tuple[float, float] | None) -> bool:
    if not page.get("pageimage"):
        return False
    co = page.get("coordinates") or []
    if at is None:
        return True
    return bool(co) and km(at, (co[0]["lat"], co[0]["lon"])) <= MAX_KM


def credits(files: list[str]) -> dict[str, dict]:
    """Commons extmetadata for filenames → {file: {"credit", "page"}}. Batched."""
    out: dict[str, dict] = {}
    for i in range(0, len(files), BATCH):
        chunk = files[i:i + BATCH]
        body = api(COMMONS_API, {"action": "query", "titles": "|".join("File:" + f for f in chunk), "redirects": 1,
                                 "prop": "imageinfo", "iiprop": "extmetadata|url", "iiurlwidth": THUMB_WIDTH,
                                 "iiextmetadatafilter": "Artist|LicenseShortName|Credit"})
        if not body:
            continue
        for p in body.get("query", {}).get("pages", []):
            info = (p.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()
            artist = re.sub(r"\s*\(talk.*?\)", "", artist)          # "Mattinbgn (talk · contribs)"
            artist = re.sub(r"\s+", " ", artist).strip()[:60]
            lic = meta.get("LicenseShortName", {}).get("value", "").strip()
            credit = " · ".join(x for x in (artist, lic) if x)
            fname = p["title"].split(":", 1)[-1].replace(" ", "_")
            out[fname] = {"credit": credit, "page": info.get("descriptionurl", ""),
                          "url": (info.get("thumburl") or info.get("url", "")).split("?")[0]}   # drop utm_ tracking
    return out


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="write photos-preview.html")
    ap.add_argument("--refresh", action="append", default=[], metavar="NAME", help="forget the cached pick for a place")
    ap.add_argument("--refresh-all", action="store_true")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    cache: dict = {}
    if CACHE_FILE.exists() and not args.refresh_all:
        cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    for n in args.refresh:
        cache.pop(n, None)
    before = json.dumps(cache, sort_keys=True)

    places = data.get("places", [])
    coords = {}
    for p in places:
        try:
            coords[p["name"]] = (float(p["lat"]), float(p["lng"]))
        except (KeyError, ValueError):
            coords[p["name"]] = None

    # 1. work out which places need an article lookup (blank cell, or a wiki: override), batched
    wanted: dict[str, list[str]] = {}          # place → candidate titles in preference order
    for p in places:
        # the sheet's cell; kept in photo_src so running this script twice is harmless
        p["photo_src"] = (p["photo_src"] if "photo_src" in p else p.get("photo") or "").strip()
        cell = p["photo_src"]
        n = p["name"]
        if cell.lower().startswith("wiki:"):
            title = cell[5:].strip()
            if cache.get(n, {}).get("from") != title:
                wanted[n] = [title]
        elif not cell and n not in cache:
            wanted[n] = [n, f"{n}, New Zealand", f"{n} (New Zealand)"]

    if wanted and not args.offline:
        all_titles = sorted({t for ts in wanted.values() for t in ts})
        found = query_titles(all_titles)
        if found is None:
            print("::warning::Wikipedia lookup failed; photos for new places will be tried again next build", file=sys.stderr)
        for n, titles in (wanted.items() if found is not None else []):
            # an explicit wiki: override is the editor's choice, so no distance check for it
            at = coords.get(n) if len(titles) > 1 else None
            pick = next((found[t] for t in titles if t in found and acceptable(found[t], at)), None)
            if pick is None and len(titles) > 1:              # automatic mode: fall back to search
                hits = search(n)
                if hits is None:
                    print(f"  {n}: search failed, will try again next build", file=sys.stderr)
                    continue
                pick = next((pg for pg in hits if acceptable(pg, at)), None)
            if pick:
                cache[n] = {"file": pick["pageimage"], "from": pick["title"]}
                print(f"  {n}: {pick['title']} → {pick['pageimage']}")
            else:
                cache[n] = {"file": "", "from": ""}            # remembered as "looked, found nothing"
                print(f"  {n}: no article with an image nearby; card keeps its gradient", file=sys.stderr)

    # 2. resolve every place's photo, then fetch credits for Commons files we haven't seen
    resolved: dict[str, str] = {}
    for p in places:
        cell = p["photo_src"]
        n = p["name"]
        if cell and not cell.lower().startswith("wiki:"):
            resolved[n] = cell
        else:
            resolved[n] = cache.get(n, {}).get("file", "")

    need_credit = sorted({f for f in resolved.values() if f and not f.startswith("http")
                          and not cache.get("_credits", {}).get(f, {}).get("url")})
    if need_credit and not args.offline:
        cache.setdefault("_credits", {}).update(credits(need_credit))

    # 3. write into data.json
    with_photo = 0
    for p in places:
        f = resolved[p["name"]]
        p["photo"] = f
        if f:
            with_photo += 1
        c = cache.get("_credits", {}).get(f, {}) if f and not f.startswith("http") else {}
        p["photo_credit"] = c.get("credit", "")
        p["photo_page"] = c.get("page", "")
        p["photo_url"] = c.get("url", "").split("?")[0]
    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    if json.dumps(cache, sort_keys=True) != before:
        CACHE_FILE.write_text(json.dumps(cache, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"photos: {with_photo} of {len(places)} places have one")

    if args.preview:
        rows = []
        for p in places:
            f = p["photo"]
            src = f if f.startswith("http") else (
                f"https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(f)}?width=480" if f else "")
            src_note = "from the sheet" if f and f != cache.get(p["name"], {}).get("file") else cache.get(p["name"], {}).get("from", "")
            rows.append(f"""<div class="c"><div class="ph">{f'<img src="{html.escape(src)}" loading="lazy">' if src else '<div class="none">no photo</div>'}</div>
<b>{html.escape(p['name'])}</b><small>{html.escape(f or '')}</small><small>{html.escape(src_note)} · {html.escape(p['photo_credit'])}</small></div>""")
        PREVIEW_FILE.write_text(f"""<!doctype html><meta charset="utf-8"><title>photos preview</title>
<style>body{{font:13px system-ui;background:#111;color:#eee;margin:16px}}.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}}
.c{{background:#1c1c1c;border-radius:8px;overflow:hidden}}.ph{{height:150px;background:#2b4a44}}.ph img{{width:100%;height:100%;object-fit:cover;display:block}}
.none{{height:100%;display:grid;place-items:center;color:#888}}b{{display:block;padding:8px 10px 0}}small{{display:block;padding:2px 10px 8px;color:#999;word-break:break-all}}</style>
<p>Override any of these in the sheet's <code>places.photo</code> cell: a Commons filename, <code>wiki:Article title</code>, or an image URL.</p>
<div class="g">{''.join(rows)}</div>""", encoding="utf-8")
        print(f"wrote {PREVIEW_FILE.name}")


if __name__ == "__main__":
    main()
