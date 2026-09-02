"""Assemble dist/ from site/.

The itinerary JSON is inlined into index.html (as window.TRIP_DATA) rather than
fetched at runtime, for two reasons:
  1. the page works offline in the car with no signal
  2. when the page is passphrase-encrypted, the data is encrypted with it,
     instead of sitting next to it as a readable data.json
"""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DIST = ROOT / "dist"

data = (SITE / "data.json").read_text(encoding="utf-8")
html = (SITE / "index.html").read_text(encoding="utf-8")
assert "/*__TRIP_DATA__*/" in html, "index.html is missing the /*__TRIP_DATA__*/ placeholder"
html = html.replace("/*__TRIP_DATA__*/null", data)

if DIST.exists():
    shutil.rmtree(DIST)
DIST.mkdir()
(DIST / "index.html").write_text(html, encoding="utf-8")
for extra in ("robots.txt",):
    shutil.copy(SITE / extra, DIST / extra)
(DIST / ".nojekyll").touch()
print(f"built {DIST.relative_to(ROOT)}/ ({len(html)//1024} KB)")
