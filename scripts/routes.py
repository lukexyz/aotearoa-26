"""Make the drives follow the road: add OSRM route geometry to site/data.json.

Usage:
    python scripts/routes.py             # runs after fetch_sheet.py, rewrites site/data.json
    python scripts/routes.py --offline   # cache only, never call OSRM (cache misses stay straight lines)
    python scripts/routes.py --refresh   # ignore the cache and re-ask OSRM for every leg

For every day the driving sequence is `from` → each stop's `place` → `to`
(same rule the page uses). Each consecutive pair of places is one *leg*, and
each leg is one request to the public OSRM server (router.project-osrm.org,
no key needed). The answer is cached in data/routes.json keyed only by the two
coordinates, so when the itinerary changes, only legs that never existed
before are fetched. A nightly rebuild with no changes makes no requests.

What goes into data.json:
    routes: { "<lat,lng>lat,lng>": { "poly": "<encoded polyline>", "km": 426.4, "min": 339 }, ... }
    days[].legs        the route keys for that day, one per consecutive pair of places
    days[].drive_time  filled in as "~5h40" when the sheet cell is blank and every leg routed.
                       The sheet wins when it has a value; OSRM's number goes in `drive_est` either way.
    days[].drive_km    OSRM's distance for the day, rounded

The build must never go red because of routing. If OSRM is down or a leg fails,
that leg is left out and the page draws a straight line for it, with a warning
in the log so someone notices.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "site" / "data.json"
CACHE_FILE = ROOT / "data" / "routes.json"

OSRM = "https://router.project-osrm.org/route/v1/driving/"
UA = "aotearoa-26 trip site (github.com/lukexyz/aotearoa-26)"
TIMEOUT = 20          # seconds per request
PAUSE = 0.25          # be polite to the demo server
TOLERANCE = 0.0008    # degrees, ~70 m at 45°S: fine at zoom 11, invisible at zoom 8
PRECISION = 5         # polyline precision, same as OSRM's default


# ---------------------------------------------------------------- polyline
def decode(s: str, precision: int = PRECISION) -> list[tuple[float, float]]:
    """Google encoded polyline → [(lat, lng), ...]."""
    scale = 10 ** precision
    pts, i, lat, lng = [], 0, 0, 0
    while i < len(s):
        for axis in (0, 1):
            shift = result = 0
            while True:
                b = ord(s[i]) - 63
                i += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if axis == 0:
                lat += delta
            else:
                lng += delta
        pts.append((lat / scale, lng / scale))
    return pts


def encode(pts: list[tuple[float, float]], precision: int = PRECISION) -> str:
    scale = 10 ** precision
    out, prev = [], (0, 0)
    for lat, lng in pts:
        cur = (round(lat * scale), round(lng * scale))
        for d in (cur[0] - prev[0], cur[1] - prev[1]):
            v = ~(d << 1) if d < 0 else d << 1
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        prev = cur
    return "".join(out)


# ---------------------------------------------------------------- simplify
def simplify(pts: list[tuple[float, float]], tol: float = TOLERANCE) -> list[tuple[float, float]]:
    """Douglas-Peucker, iterative. Keeps the road's shape, drops the noise."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (ax, ay), (bx, by) = pts[a], pts[b]
        dx, dy = bx - ax, by - ay
        norm = (dx * dx + dy * dy) ** 0.5 or 1e-12
        best, idx = 0.0, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            dist = abs(dy * px - dx * py + bx * ay - by * ax) / norm
            if dist > best:
                best, idx = dist, i
        if best > tol:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


# ---------------------------------------------------------------- OSRM
def key(a: tuple[float, float], b: tuple[float, float]) -> str:
    return f"{a[0]:.4f},{a[1]:.4f}>{b[0]:.4f},{b[1]:.4f}"


def osrm(a: tuple[float, float], b: tuple[float, float]) -> dict | None:
    """One leg from OSRM: {"poly", "km", "min"} or None if anything went wrong."""
    coords = f"{a[1]},{a[0]};{b[1]},{b[0]}"     # OSRM wants lng,lat
    url = OSRM + coords + "?" + urllib.parse.urlencode({"overview": "full", "geometries": "polyline"})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                body = json.load(r)
            if body.get("code") != "Ok" or not body.get("routes"):
                print(f"  osrm said {body.get('code')} for {coords}", file=sys.stderr)
                return None
            rt = body["routes"][0]
            pts = simplify(decode(rt["geometry"]))
            return {"poly": encode(pts), "km": round(rt["distance"] / 1000, 1), "min": round(rt["duration"] / 60)}
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, OSError) as e:
            print(f"  attempt {attempt} failed for {coords}: {e}", file=sys.stderr)
            time.sleep(1.5)
    return None


# ---------------------------------------------------------------- itinerary
def day_places(d: dict, places: dict) -> list[str]:
    """from → stop places → to, de-duplicated, same as the page's dayPlaces()."""
    seq: list[str] = []
    for n in [d.get("from", "")] + [s.get("place", "") for s in d.get("stops", [])] + [d.get("to", "")]:
        if n and n in places and (not seq or seq[-1] != n):
            seq.append(n)
    return seq


def fmt_minutes(m: int) -> str:
    h, mm = divmod(int(round(m / 5.0) * 5), 60)       # nearest 5 min
    if not h:
        return f"~{mm}min"
    return f"~{h}h{mm:02d}" if mm else f"~{h}h"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="use the cache only, never call OSRM")
    ap.add_argument("--refresh", action="store_true", help="re-fetch every leg, ignoring the cache")
    args = ap.parse_args()

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    cache: dict = {}
    if CACHE_FILE.exists() and not args.refresh:
        cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))

    places = {p["name"]: (float(p["lat"]), float(p["lng"])) for p in data.get("places", [])}

    # every leg we need, in itinerary order, de-duplicated
    legs: list[tuple[str, tuple, tuple]] = []
    seen: set[str] = set()
    for d in data["days"]:
        seq = day_places(d, places)
        for a, b in zip(seq, seq[1:]):
            k = key(places[a], places[b])
            if k not in seen:
                seen.add(k)
                legs.append((k, places[a], places[b]))

    fetched = failed = 0
    for k, a, b in legs:
        if k in cache:
            continue
        if args.offline:
            failed += 1
            continue
        got = osrm(a, b)
        if got:
            cache[k] = got
            fetched += 1
        else:
            failed += 1
        time.sleep(PAUSE)

    if fetched:
        CACHE_FILE.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    # only ship the legs this itinerary uses; the cache may remember old ones
    data["routes"] = {k: cache[k] for k, _, _ in legs if k in cache}

    # per-day totals; fill drive_time when the sheet left it blank
    print(f"{'day':>3}  {'sheet':>7}  {'osrm':>7}  {'km':>6}  route")
    for d in data["days"]:
        seq = day_places(d, places)
        pairs = [key(places[a], places[b]) for a, b in zip(seq, seq[1:])]
        if not pairs:
            continue
        d["legs"] = pairs     # the page looks these up in `routes`, in dayPlaces() order
        d["legs"] = pairs     # the page looks these up in `routes`, in dayPlaces() order
        have = [cache[k] for k in pairs if k in cache]
        complete = len(have) == len(pairs)
        total_min = sum(r["min"] for r in have)
        total_km = sum(r["km"] for r in have)
        if complete:
            d["drive_est"] = fmt_minutes(total_min)
            d["drive_km"] = round(total_km)
            if not d.get("drive_time"):
                d["drive_time"] = d["drive_est"]
        flag = "" if complete else f"  ({len(pairs) - len(have)} of {len(pairs)} legs missing, straight line)"
        print(f"{d.get('day', '?'):>3}  {d.get('drive_time', '') or '-':>7}  {d.get('drive_est', '') or '-':>7}  "
              f"{d.get('drive_km', '') or '-':>6}  {' > '.join(seq)}{flag}")

    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    size = sum(len(r["poly"]) for r in data["routes"].values())
    print(f"routes: {len(legs)} legs, {fetched} fetched, {len(legs) - fetched - failed} cached, "
          f"{failed} missing, {size // 1024} KB of geometry")
    if failed:
        print(f"::warning::{failed} leg(s) could not be routed; they are drawn as straight lines", file=sys.stderr)


if __name__ == "__main__":
    main()
