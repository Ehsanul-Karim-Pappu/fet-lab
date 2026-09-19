#!/usr/bin/env python3
"""Assemble the shipped HTML from the template and the scene data.

  scripts/roadmap.tpl.html + explorer.* + data/* -> web/finfet-to-cfet.html
  standalone viewer + pwa/parts/*              -> pwa/index.html

Also bumps the service-worker cache name so an installed PWA picks the new
build up instead of serving the cached one. Run after every build_* script.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
tpl  = (ROOT / "scripts" / "roadmap.tpl.html").read_text()
data = json.loads((ROOT / "data" / "devices.json").read_text())
guide = json.loads((ROOT / "data" / "guide.json").read_text())

MARK = "/*__DATA__*/null"
for marker in (MARK, "/*__GUIDE__*/null", "/*__EXPLORER_CSS__*/", "/*__EXPLORER_JS__*/"):
    if tpl.count(marker) != 1:
        sys.exit(f"expected exactly one {marker} in roadmap.tpl.html, found {tpl.count(marker)}")

blob = json.dumps(data, separators=(",", ":"))
# </script> inside a JS string literal would close the tag early.
blob = blob.replace("</", "<\\/")
html = tpl.replace(MARK, blob)
html = html.replace("/*__GUIDE__*/null", json.dumps(guide, ensure_ascii=True).replace("</", "<\\/"))
html = html.replace("/*__EXPLORER_CSS__*/", (ROOT / "scripts" / "explorer.css").read_text())
html = html.replace("/*__EXPLORER_JS__*/", (ROOT / "scripts" / "explorer.js").read_text())
(ROOT / "web" / "finfet-to-cfet.html").write_text(html)
# Both native assets are generated from the same source as the browser bundle.
for name in ("devices.json", "guide.json"):
    (ROOT / "android/app/src/main/assets" / name).write_bytes((ROOT / "data" / name).read_bytes())

lines = html.split("\n")
title = lines[0]
if "<title>" not in title:
    sys.exit("roadmap.tpl.html must start with its <title> line")

p = ROOT / "pwa" / "parts"
pwa = "\n".join([
    (p / "head-open.html").read_text().rstrip("\n"),
    title,
    (p / "head-meta.html").read_text().rstrip("\n"),
    "\n".join(lines[1:]).rstrip("\n"),
    (p / "foot.html").read_text().rstrip("\n"),
]) + "\n"
(ROOT / "pwa" / "index.html").write_text(pwa)

# bump the cache so installed copies refresh
swp = ROOT / "pwa" / "sw.js"
sw  = swp.read_text()
m = re.search(r'CACHE\s*=\s*"fetlab-v(\d+)"', sw)
if not m:
    sys.exit("could not find the cache name in pwa/sw.js")
new = int(m.group(1)) + 1
swp.write_text(sw[:m.start(1)] + str(new) + sw[m.end(1):])

n = len(data["devices"]) if isinstance(data, dict) and "devices" in data else len(data)
print(f"web + PWA + Android assets rebuilt ({n} scenes, cache fetlab-v{new})")
